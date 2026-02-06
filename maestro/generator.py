"""OptionGenerator: produces 3-4 execution strategies with realistic cost estimates."""

from __future__ import annotations

import math
from pathlib import Path

import yaml

from maestro.models import Constraint, Option, Priority, Task

_TOOLS_PATH = Path(__file__).resolve().parent.parent / "tools.yaml"


def _load_tools() -> dict:
    """Load tool definitions and pricing from tools.yaml."""
    with open(_TOOLS_PATH) as f:
        return yaml.safe_load(f)


def _llm_cost_per_page(tool: dict) -> float:
    """Calculate LLM extraction cost per page from token pricing."""
    input_cost = (tool["avg_input_tokens_per_page"] / 1_000_000) * tool["cost_per_million_input"]
    output_cost = (tool["avg_output_tokens_per_page"] / 1_000_000) * tool["cost_per_million_output"]
    return input_cost + output_cost


class OptionGenerator:
    """Generates execution options for scraping tasks based on real tool pricing."""

    def __init__(self) -> None:
        self.tools = _load_tools()

    def generate(self, task: Task, constraint: Constraint | None = None) -> list[Option]:
        """Generate 3-4 options for executing the task.

        Options always represent different tradeoff profiles:
        Budget, Balanced (recommended), Quality, and Speed.
        """
        count = int(task.parameters.get("count", 50))
        domain = str(task.parameters.get("domain", "websites"))

        scrapy = self.tools["scrapy"]
        playwright = self.tools["playwright"]
        deepseek = self.tools["deepseek"]
        claude = self.tools["claude"]

        ds_cost = _llm_cost_per_page(deepseek)
        cl_cost = _llm_cost_per_page(claude)

        ds_extract_time = math.ceil(count / deepseek["pages_per_second"])
        cl_extract_time = math.ceil(count / claude["pages_per_second"])

        # --- Budget Option ---
        # Scrapy only (no JS fallback) + DeepSeek
        budget_quality = scrapy["success_rate"] * deepseek["quality"]
        budget_cost = count * (scrapy["cost_per_page"] + ds_cost)
        budget_time = math.ceil(count / scrapy["speed_pages_per_second"]) + ds_extract_time

        budget = Option(
            name="Budget Optimized",
            strategy=f"Scrapy-only crawling + DeepSeek extraction",
            cost=round(budget_cost, 2),
            quality=round(budget_quality, 2),
            time_seconds=budget_time,
            explanation=(
                f"Scrapy handles crawling (free) and DeepSeek extracts data "
                f"(${ds_cost:.4f}/page). No JavaScript rendering — sites that "
                f"require JS will fail, reducing overall success rate."
            ),
            tools=["scrapy", "deepseek"],
        )

        # --- Balanced Option (Recommended) ---
        # Scrapy + Playwright fallback for JS sites + DeepSeek
        js_fraction = 1 - scrapy["success_rate"]  # ~15% need JS
        balanced_cost = count * (
            scrapy["cost_per_page"]
            + js_fraction * playwright["cost_per_page"]
            + ds_cost
        )
        balanced_quality = (
            scrapy["success_rate"] * deepseek["quality"]
            + js_fraction * playwright["success_rate"] * deepseek["quality"]
        )
        # Time: scrapy handles 85%, playwright handles 15% (slower), plus extraction
        scrapy_time = math.ceil((count * scrapy["success_rate"]) / scrapy["speed_pages_per_second"])
        pw_time = math.ceil((count * js_fraction) / playwright["speed_pages_per_second"])
        balanced_time = scrapy_time + pw_time + ds_extract_time

        balanced = Option(
            name="Balanced",
            strategy=f"Scrapy + Playwright fallback + DeepSeek extraction",
            cost=round(balanced_cost, 2),
            quality=round(balanced_quality, 2),
            time_seconds=balanced_time,
            explanation=(
                f"Scrapy crawls first (free, handles ~{scrapy['success_rate']:.0%} of sites). "
                f"Playwright renders JavaScript-heavy sites as fallback "
                f"(~${playwright['cost_per_page']}/page for ~{js_fraction:.0%} of sites). "
                f"DeepSeek extracts structured data from all pages."
            ),
            tools=["scrapy", "playwright", "deepseek"],
            recommended=True,
        )

        # --- Quality Option ---
        # Scrapy + Playwright fallback + Claude (premium extraction)
        quality_cost = count * (
            scrapy["cost_per_page"]
            + js_fraction * playwright["cost_per_page"]
            + cl_cost
        )
        quality_quality = (
            scrapy["success_rate"] * claude["quality"]
            + js_fraction * playwright["success_rate"] * claude["quality"]
        )
        quality_time = scrapy_time + pw_time + cl_extract_time

        quality = Option(
            name="Quality Focused",
            strategy=f"Scrapy + Playwright fallback + Claude extraction",
            cost=round(quality_cost, 2),
            quality=round(quality_quality, 2),
            time_seconds=quality_time,
            explanation=(
                f"Same crawling strategy as Balanced, but uses Claude for extraction "
                f"(${cl_cost:.4f}/page vs ${ds_cost:.4f}/page). "
                f"Significantly better at understanding complex page layouts and "
                f"extracting nuanced data."
            ),
            tools=["scrapy", "playwright", "claude"],
        )

        # --- Speed Option ---
        # Parallel Scrapy (no fallback) + DeepSeek, optimized for throughput
        speed_quality = scrapy["success_rate"] * deepseek["quality"]
        speed_cost = count * (scrapy["cost_per_page"] + ds_cost)
        # Parallel processing: 3x crawl throughput, extraction still sequential
        speed_time = math.ceil(count / (scrapy["speed_pages_per_second"] * 3)) + ds_extract_time

        speed = Option(
            name="Speed Optimized",
            strategy=f"Parallel Scrapy (3 workers) + DeepSeek extraction",
            cost=round(speed_cost, 2),
            quality=round(speed_quality, 2),
            time_seconds=speed_time,
            explanation=(
                f"Runs 3 parallel Scrapy workers for maximum throughput. "
                f"No Playwright fallback — trades JS-heavy site coverage for speed. "
                f"Same extraction cost as Budget (DeepSeek)."
            ),
            tools=["scrapy", "deepseek"],
        )

        options = [budget, balanced, quality, speed]

        # If there's a budget constraint, also generate a scope-reduction option
        if constraint and constraint.budget_max is not None:
            scope_option = self._generate_scope_reduction(
                task, constraint, balanced_cost, count, balanced, ds_cost, js_fraction, playwright
            )
            if scope_option:
                options.append(scope_option)

        return options

    def _generate_scope_reduction(
        self,
        task: Task,
        constraint: Constraint,
        full_cost: float,
        full_count: int,
        balanced: Option,
        ds_cost: float,
        js_fraction: float,
        playwright: dict,
    ) -> Option | None:
        """Generate a scope-reduction option that fits the budget."""
        if full_cost <= constraint.budget_max:
            return None  # Already fits, no need for scope reduction

        # Calculate how many pages fit in budget with balanced strategy
        cost_per_page = (
            self.tools["scrapy"]["cost_per_page"]
            + js_fraction * playwright["cost_per_page"]
            + ds_cost
        )
        if cost_per_page <= 0:
            return None

        reduced_count = int(constraint.budget_max / cost_per_page)
        if reduced_count >= full_count:
            return None  # No reduction needed
        if reduced_count < 5:
            return None  # Too few to be useful

        scrapy = self.tools["scrapy"]
        deepseek = self.tools["deepseek"]
        reduced_cost = reduced_count * cost_per_page
        scrapy_time = math.ceil((reduced_count * scrapy["success_rate"]) / scrapy["speed_pages_per_second"])
        pw_time = math.ceil((reduced_count * js_fraction) / playwright["speed_pages_per_second"])
        extract_time = math.ceil(reduced_count / deepseek["pages_per_second"])

        return Option(
            name="Scope Reduction",
            strategy=f"Balanced approach but {reduced_count} sites instead of {full_count}",
            cost=round(reduced_cost, 2),
            quality=balanced.quality,
            time_seconds=scrapy_time + pw_time + extract_time,
            explanation=(
                f"Same hybrid strategy (Scrapy + Playwright + DeepSeek) "
                f"but processes {reduced_count} sites instead of {full_count} to fit "
                f"within ${constraint.budget_max:.2f} budget. "
                f"Quality stays the same — you just get fewer results."
            ),
            tools=["scrapy", "playwright", "deepseek"],
        )
