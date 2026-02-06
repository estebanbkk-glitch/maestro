"""PreferenceLearner: logs user choices for future preference learning."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from maestro.models import Constraint, ExecutionResult, Option, Task

_PREFS_DIR = Path.home() / ".maestro"
_PREFS_FILE = _PREFS_DIR / "preferences.json"


class PreferenceLearner:
    """Records user choices to build a preference profile over time."""

    def __init__(self) -> None:
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        _PREFS_DIR.mkdir(exist_ok=True)

    def record_choice(
        self,
        task: Task,
        options_shown: list[Option],
        chosen: Option,
        constraint: Constraint | None,
        result: ExecutionResult | None = None,
    ) -> None:
        """Log a user's option choice."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_type": task.type,
            "task_description": task.description,
            "task_parameters": task.parameters,
            "constraint": {
                "budget_max": constraint.budget_max if constraint else None,
                "quality_min": constraint.quality_min if constraint else None,
                "time_max": constraint.time_max if constraint else None,
                "priority": constraint.priority.value if constraint else None,
            },
            "options_shown": [
                {"name": o.name, "cost": o.cost, "quality": o.quality, "time_seconds": o.time_seconds}
                for o in options_shown
            ],
            "chosen": {
                "name": chosen.name,
                "cost": chosen.cost,
                "quality": chosen.quality,
                "time_seconds": chosen.time_seconds,
                "had_violations": len(chosen.violations) > 0,
            },
            "result": {
                "actual_cost": result.actual_cost,
                "actual_quality": result.actual_quality,
                "success": result.success,
            } if result else None,
        }

        # Append to preferences file
        history = self._load_history()
        history.append(entry)
        self._save_history(history)

    def get_history(self) -> list[dict]:
        """Get all recorded choices."""
        return self._load_history()

    def get_preferred_strategy(self, task_type: str, min_choices: int = 2) -> str | None:
        """Return the option name the user picks most often for a task type.

        Returns None if fewer than *min_choices* recorded or no single option
        has a majority (>50%).
        """
        history = self._load_history()
        relevant = [h for h in history if h.get("task_type") == task_type]
        if len(relevant) < min_choices:
            return None

        counts: dict[str, int] = {}
        for entry in relevant:
            name = entry["chosen"]["name"]
            counts[name] = counts.get(name, 0) + 1

        top_name = max(counts, key=counts.get)  # type: ignore[arg-type]
        if counts[top_name] / len(relevant) > 0.5:
            return top_name
        return None

    def get_summary(self) -> dict:
        """Get a summary of learned preferences."""
        history = self._load_history()
        if not history:
            return {"total_choices": 0, "patterns": []}

        total = len(history)
        budget_chosen = sum(1 for h in history if h["chosen"]["name"] == "Budget Optimized")
        quality_chosen = sum(1 for h in history if h["chosen"]["name"] == "Quality Focused")
        scope_chosen = sum(1 for h in history if h["chosen"]["name"] == "Scope Reduction")
        avg_cost = sum(h["chosen"]["cost"] for h in history) / total

        patterns = []
        if budget_chosen > total * 0.5:
            patterns.append("Tends to prefer budget options")
        if quality_chosen > total * 0.5:
            patterns.append("Tends to prefer quality options")
        if scope_chosen > total * 0.3:
            patterns.append("Often accepts scope reduction to meet budget")

        return {
            "total_choices": total,
            "avg_cost": round(avg_cost, 2),
            "budget_preference": round(budget_chosen / total, 2) if total else 0,
            "quality_preference": round(quality_chosen / total, 2) if total else 0,
            "patterns": patterns,
        }

    def _load_history(self) -> list[dict]:
        if not _PREFS_FILE.exists():
            return []
        with open(_PREFS_FILE) as f:
            return json.load(f)

    def _save_history(self, history: list[dict]) -> None:
        self._ensure_dir()
        with open(_PREFS_FILE, "w") as f:
            json.dump(history, f, indent=2, default=str)
