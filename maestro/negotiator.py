"""Negotiator: formats options for display and parses user adjustments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from maestro.models import Constraint, ConstraintStatus, Option, Priority


class UserIntent(Enum):
    """What the user wants to do next."""
    ACCEPT = "accept"               # "yes", "go", "option B"
    ADJUST_BUDGET = "adjust_budget"  # "cheaper", "under $5"
    ADJUST_QUALITY = "adjust_quality"  # "better quality", "at least 90%"
    ADJUST_TIME = "adjust_time"      # "faster", "under 5 minutes"
    ADJUST_SCOPE = "adjust_scope"    # "only 50 sites"
    QUIT = "quit"                    # "quit", "cancel"
    UNKNOWN = "unknown"


@dataclass
class ParsedAdjustment:
    """A parsed user intent with optional extracted value."""
    intent: UserIntent
    value: float | None = None       # Dollar amount, percentage, seconds, count
    chosen_index: int | None = None  # Which option (0-based) if ACCEPT


class Negotiator:
    """Handles option presentation and user input parsing for constraint negotiation."""

    # --- Formatting ---

    def format_recommendation(self, options: list[Option]) -> str:
        """Format the initial recommendation (the recommended option + summary of others)."""
        recommended = next((o for o in options if o.recommended), options[0])
        lines = [
            "",
            "  Here's my recommendation:",
            "",
            f"  Strategy: {recommended.strategy}",
            "",
            *self._format_metrics(recommended, indent=4),
            "",
        ]

        other_options = [o for o in options if o is not recommended]
        if other_options:
            lines.append("  Other strategies available — say 'show options' to compare, or adjust")
            lines.append("  constraints like 'under $1' or 'faster'.")

        lines.append("")
        lines.append("  Proceed with this approach? (yes / show options / adjust)")
        return "\n".join(lines)

    def format_options(self, options: list[Option]) -> str:
        """Format all options as a lettered list with metrics."""
        lines = ["", "  Here are your options:", ""]
        labels = "ABCDEFGH"

        for i, option in enumerate(options):
            label = labels[i] if i < len(labels) else str(i + 1)
            rec_tag = " ⭐ Recommended" if option.recommended else ""
            lines.append(f"  Option {label}: {option.name}{rec_tag}")
            lines.append(f"    {option.strategy}")
            lines.extend(self._format_metrics(option, indent=4))
            if option.explanation:
                # Wrap explanation at ~70 chars
                lines.append(f"    ℹ️  {option.explanation}")
            lines.append("")

        lines.append("  Which option? (A/B/C/... or adjust constraints)")
        return "\n".join(lines)

    def _format_metrics(self, option: Option, indent: int = 4) -> list[str]:
        """Format cost/quality/time with pass/fail indicators."""
        pad = " " * indent
        lines = []

        # Cost
        cost_str = f"${option.cost:.2f}"
        budget_v = next((v for v in option.violations if v.constraint == "budget"), None)
        if budget_v:
            lines.append(f"{pad}💰 Cost: {cost_str}  ⚠️ ${budget_v.actual - budget_v.limit:.2f} over budget")
        else:
            lines.append(f"{pad}💰 Cost: {cost_str}  ✅")

        # Quality
        quality_pct = f"{option.quality:.0%}"
        quality_v = next((v for v in option.violations if v.constraint == "quality"), None)
        if quality_v:
            lines.append(f"{pad}✨ Quality: {quality_pct}  ⚠️ {quality_v.delta_pct:.0f}% below minimum")
        else:
            lines.append(f"{pad}✨ Quality: {quality_pct}  ✅")

        # Time
        time_str = self._format_time(option.time_seconds)
        time_v = next((v for v in option.violations if v.constraint == "time"), None)
        if time_v:
            lines.append(f"{pad}⏱️  Time: {time_str}  ⚠️ over time limit")
        else:
            lines.append(f"{pad}⏱️  Time: {time_str}  ✅")

        return lines

    def _format_time(self, seconds: int) -> str:
        """Format seconds into a human-readable string."""
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        remaining = seconds % 60
        if remaining == 0:
            return f"{minutes} min"
        return f"{minutes}m {remaining}s"

    # --- Parsing ---

    def parse_input(self, text: str, num_options: int = 0) -> ParsedAdjustment:
        """Parse user input to determine intent and extract values."""
        text = text.strip()
        if not text:
            return ParsedAdjustment(intent=UserIntent.UNKNOWN)

        lower = text.lower()

        # Quit
        if lower in ("quit", "exit", "cancel", "no", "q"):
            return ParsedAdjustment(intent=UserIntent.QUIT)

        # Accept — "yes", "go", "proceed", "option B", or just "B"
        if lower in ("yes", "y", "go", "proceed", "ok", "sure"):
            return ParsedAdjustment(intent=UserIntent.ACCEPT)

        # Show options
        if any(kw in lower for kw in ("show option", "compare", "all option", "list")):
            return ParsedAdjustment(intent=UserIntent.UNKNOWN, value=-1)  # Signal to show options

        # Option selection: "option B", "B", "b", "option 2", "2"
        option_match = re.match(r"^(?:option\s+)?([a-h]|\d)$", lower)
        if option_match:
            char = option_match.group(1)
            if char.isalpha():
                idx = ord(char) - ord("a")
            else:
                idx = int(char) - 1
            if 0 <= idx < num_options:
                return ParsedAdjustment(intent=UserIntent.ACCEPT, chosen_index=idx)

        # Budget adjustment: "under $5", "cheaper", "max $3", "can we do $2?"
        budget_match = re.search(r"(?:under|below|max|within|for|do)\s*\$(\d+(?:\.\d+)?)", lower)
        if budget_match:
            return ParsedAdjustment(
                intent=UserIntent.ADJUST_BUDGET,
                value=float(budget_match.group(1)),
            )
        # Just a dollar amount
        dollar_match = re.match(r"^\$(\d+(?:\.\d+)?)\s*$", lower)
        if dollar_match:
            return ParsedAdjustment(
                intent=UserIntent.ADJUST_BUDGET,
                value=float(dollar_match.group(1)),
            )
        if any(kw in lower for kw in ("cheaper", "less expensive", "lower cost", "budget")):
            return ParsedAdjustment(intent=UserIntent.ADJUST_BUDGET)

        # Quality adjustment: "at least 95%", "better quality", "higher quality"
        quality_match = re.search(r"(?:at least|above|minimum|min)\s*(\d+)\s*%", lower)
        if quality_match:
            return ParsedAdjustment(
                intent=UserIntent.ADJUST_QUALITY,
                value=float(quality_match.group(1)) / 100,
            )
        if any(kw in lower for kw in ("better", "higher quality", "more accurate", "quality")):
            return ParsedAdjustment(intent=UserIntent.ADJUST_QUALITY)

        # Time adjustment: "under 5 minutes", "faster", "within 2 min"
        time_match = re.search(r"(?:under|below|within|max)\s*(\d+)\s*min", lower)
        if time_match:
            return ParsedAdjustment(
                intent=UserIntent.ADJUST_TIME,
                value=float(time_match.group(1)) * 60,
            )
        time_sec_match = re.search(r"(?:under|below|within|max)\s*(\d+)\s*sec", lower)
        if time_sec_match:
            return ParsedAdjustment(
                intent=UserIntent.ADJUST_TIME,
                value=float(time_sec_match.group(1)),
            )
        if any(kw in lower for kw in ("faster", "quicker", "speed")):
            return ParsedAdjustment(intent=UserIntent.ADJUST_TIME)

        # Scope adjustment: "only 50 sites", "just 30", "reduce to 20"
        scope_match = re.search(r"(?:only|just|reduce to|limit to)\s*(\d+)", lower)
        if scope_match:
            return ParsedAdjustment(
                intent=UserIntent.ADJUST_SCOPE,
                value=float(scope_match.group(1)),
            )

        return ParsedAdjustment(intent=UserIntent.UNKNOWN)

    def build_constraint_from_adjustment(
        self, adjustment: ParsedAdjustment, current: Constraint | None = None,
    ) -> Constraint:
        """Create or update a Constraint based on the user's adjustment."""
        c = Constraint(
            budget_max=current.budget_max if current else None,
            quality_min=current.quality_min if current else None,
            time_max=current.time_max if current else None,
            priority=current.priority if current else Priority.BALANCED,
        )

        match adjustment.intent:
            case UserIntent.ADJUST_BUDGET:
                if adjustment.value is not None:
                    c.budget_max = adjustment.value
                c.priority = Priority.COST
            case UserIntent.ADJUST_QUALITY:
                if adjustment.value is not None:
                    c.quality_min = adjustment.value
                c.priority = Priority.QUALITY
            case UserIntent.ADJUST_TIME:
                if adjustment.value is not None:
                    c.time_max = int(adjustment.value)
                c.priority = Priority.TIME
            case UserIntent.ADJUST_SCOPE:
                pass  # Scope is handled by modifying the task, not constraint

        return c
