"""OptionGenerator: produces 3-4 execution strategies with realistic cost estimates."""

from __future__ import annotations

import math
from pathlib import Path

import yaml

from maestro.models import Constraint, Option, Priority, Task

_TOOLS_PATH = Path(__file__).resolve().parent.parent / "tools.yaml"


def _load_tools() -> dict:
    """Load tool definitions and pricing from tools.yaml."""
    try:
        with open(_TOOLS_PATH) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise SystemExit(f"Error: tools.yaml not found at {_TOOLS_PATH}. Please ensure it exists.")
    except yaml.YAMLError as exc:
        raise SystemExit(f"Error: Failed to parse tools.yaml: {exc}")


def _llm_cost_per_page(tool: dict) -> float:
    """Calculate LLM extraction cost per page from token pricing."""
    input_cost = (tool["avg_input_tokens_per_page"] / 1_000_000) * tool["cost_per_million_input"]
    output_cost = (tool["avg_output_tokens_per_page"] / 1_000_000) * tool["cost_per_million_output"]
    return input_cost + output_cost


class OptionGenerator:
    """Generates execution options based on real tool pricing."""

    def __init__(self) -> None:
        self.tools = _load_tools()

    def generate(
        self,
        task: Task,
        constraint: Constraint | None = None,
        preferred_strategy: str | None = None,
    ) -> list[Option]:
        """Generate 3-4 options for executing the task.

        Options always represent different tradeoff profiles:
        Budget, Balanced (recommended), Quality, and Speed.

        If *preferred_strategy* names one of the options, that option becomes
        the recommendation instead of Balanced.
        """
        if task.type == "analysis":
            return self._generate_analysis_options(task, constraint, preferred_strategy)
        if task.type == "api":
            return self._generate_api_options(task, constraint, preferred_strategy)
        return self._generate_scraping_options(task, constraint, preferred_strategy)

    # ------------------------------------------------------------------
    # Scraping options
    # ------------------------------------------------------------------

    def _generate_scraping_options(
        self,
        task: Task,
        constraint: Constraint | None = None,
        preferred_strategy: str | None = None,
    ) -> list[Option]:
        """Generate options for a scraping task."""
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

        # Shift recommendation if user has a learned preference
        if preferred_strategy:
            match = next((o for o in options if o.name == preferred_strategy), None)
            if match and not match.recommended:
                for o in options:
                    o.recommended = False
                match.recommended = True

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

    # ------------------------------------------------------------------
    # Analysis options
    # ------------------------------------------------------------------

    def _llm_cost_per_1k_rows(self, tool: dict) -> float:
        """Calculate LLM analysis cost per 1000 rows.

        Assumes ~200 input tokens and ~100 output tokens per row batch of 50 rows,
        so per 1000 rows that's 20 batches.
        """
        input_tokens_per_1k = 200 * 20   # 4000 tokens input per 1k rows
        output_tokens_per_1k = 100 * 20  # 2000 tokens output per 1k rows
        input_cost = (input_tokens_per_1k / 1_000_000) * tool["cost_per_million_input"]
        output_cost = (output_tokens_per_1k / 1_000_000) * tool["cost_per_million_output"]
        return input_cost + output_cost

    def _generate_analysis_options(
        self,
        task: Task,
        constraint: Constraint | None = None,
        preferred_strategy: str | None = None,
    ) -> list[Option]:
        """Generate options for a data analysis task."""
        count = int(task.parameters.get("count", 1000))

        pandas_tool = self.tools["pandas"]
        polars_tool = self.tools["polars"]
        deepseek = self.tools["deepseek"]
        claude = self.tools["claude"]

        ds_cost_1k = self._llm_cost_per_1k_rows(deepseek)
        cl_cost_1k = self._llm_cost_per_1k_rows(claude)
        row_units = count / 1000  # scale factor

        # --- Budget Option: pandas + deepseek ---
        budget_cost = row_units * ds_cost_1k  # pandas is free
        budget_quality = pandas_tool["quality"] * deepseek["quality"]
        pandas_time = math.ceil(count / pandas_tool["speed_rows_per_second"])
        ds_analysis_time = math.ceil(count / (deepseek["pages_per_second"] * 50))  # 50 rows per batch
        budget_time = pandas_time + ds_analysis_time

        budget = Option(
            name="Budget Optimized",
            strategy="pandas processing + DeepSeek analysis",
            cost=round(budget_cost, 2),
            quality=round(budget_quality, 2),
            time_seconds=budget_time,
            explanation=(
                f"pandas processes data locally (free) and DeepSeek generates insights "
                f"(${ds_cost_1k:.4f}/1k rows). Reliable for standard tabular data."
            ),
            tools=["pandas", "deepseek"],
        )

        # --- Balanced Option: polars + deepseek (recommended) ---
        balanced_cost = row_units * ds_cost_1k  # polars is free
        balanced_quality = polars_tool["quality"] * deepseek["quality"]
        polars_time = math.ceil(count / polars_tool["speed_rows_per_second"])
        balanced_time = polars_time + ds_analysis_time

        balanced = Option(
            name="Balanced",
            strategy="polars processing + DeepSeek analysis",
            cost=round(balanced_cost, 2),
            quality=round(balanced_quality, 2),
            time_seconds=balanced_time,
            explanation=(
                f"polars processes data locally (free, 5x faster than pandas) "
                f"and DeepSeek generates insights (${ds_cost_1k:.4f}/1k rows). "
                f"Best value for most analysis tasks."
            ),
            tools=["polars", "deepseek"],
            recommended=True,
        )

        # --- Quality Option: polars + claude ---
        quality_cost = row_units * cl_cost_1k
        quality_quality = polars_tool["quality"] * claude["quality"]
        cl_analysis_time = math.ceil(count / (claude["pages_per_second"] * 50))
        quality_time = polars_time + cl_analysis_time

        quality = Option(
            name="Quality Focused",
            strategy="polars processing + Claude analysis",
            cost=round(quality_cost, 2),
            quality=round(quality_quality, 2),
            time_seconds=quality_time,
            explanation=(
                f"polars for fast local processing, Claude for premium analysis "
                f"(${cl_cost_1k:.4f}/1k rows vs ${ds_cost_1k:.4f}/1k rows). "
                f"Significantly better at nuanced insights and complex patterns."
            ),
            tools=["polars", "claude"],
        )

        # --- Speed Option: polars parallel (3x) + deepseek ---
        speed_cost = row_units * ds_cost_1k
        speed_quality = polars_tool["quality"] * deepseek["quality"]
        speed_time = math.ceil(count / (polars_tool["speed_rows_per_second"] * 3)) + ds_analysis_time

        speed = Option(
            name="Speed Optimized",
            strategy="parallel polars (3 workers) + DeepSeek analysis",
            cost=round(speed_cost, 2),
            quality=round(speed_quality, 2),
            time_seconds=speed_time,
            explanation=(
                f"Runs 3 parallel polars workers for maximum throughput. "
                f"Same analysis cost as Budget/Balanced (DeepSeek). "
                f"Ideal for large datasets where processing time matters."
            ),
            tools=["polars", "deepseek"],
        )

        options = [budget, balanced, quality, speed]

        # Scope reduction if budget is tight
        if constraint and constraint.budget_max is not None:
            scope_option = self._generate_analysis_scope_reduction(
                task, constraint, balanced_cost, count, balanced, ds_cost_1k,
            )
            if scope_option:
                options.append(scope_option)

        # Shift recommendation if user has a learned preference
        if preferred_strategy:
            match = next((o for o in options if o.name == preferred_strategy), None)
            if match and not match.recommended:
                for o in options:
                    o.recommended = False
                match.recommended = True

        return options

    # ------------------------------------------------------------------
    # API integration options
    # ------------------------------------------------------------------

    def _llm_cost_per_api_response(self, tool: dict) -> float:
        """Calculate LLM parsing cost per API response.

        API responses are typically larger than web pages: ~800 input tokens
        and ~200 output tokens per response.
        """
        input_cost = (800 / 1_000_000) * tool["cost_per_million_input"]
        output_cost = (200 / 1_000_000) * tool["cost_per_million_output"]
        return input_cost + output_cost

    def _generate_api_options(
        self,
        task: Task,
        constraint: Constraint | None = None,
        preferred_strategy: str | None = None,
    ) -> list[Option]:
        """Generate options for an API integration task."""
        count = int(task.parameters.get("count", 20))

        httpx_tool = self.tools["httpx"]
        requests_tool = self.tools["requests"]
        deepseek = self.tools["deepseek"]
        claude = self.tools["claude"]

        ds_cost = self._llm_cost_per_api_response(deepseek)
        cl_cost = self._llm_cost_per_api_response(claude)

        ds_parse_time = math.ceil(count / deepseek["pages_per_second"])
        cl_parse_time = math.ceil(count / claude["pages_per_second"])

        # --- Budget Option: requests (sequential) + deepseek ---
        budget_quality = requests_tool["success_rate"] * deepseek["quality"]
        budget_cost = count * (requests_tool["cost_per_request"] + ds_cost)
        budget_time = math.ceil(count / requests_tool["speed_requests_per_second"]) + ds_parse_time

        budget = Option(
            name="Budget Optimized",
            strategy="requests (sequential) + DeepSeek parsing",
            cost=round(budget_cost, 2),
            quality=round(budget_quality, 2),
            time_seconds=budget_time,
            explanation=(
                f"requests calls APIs sequentially (free, simple) and DeepSeek parses "
                f"responses (${ds_cost:.4f}/response). Slower due to sequential calls."
            ),
            tools=["requests", "deepseek"],
        )

        # --- Balanced Option: httpx (async) + deepseek (recommended) ---
        balanced_quality = httpx_tool["success_rate"] * deepseek["quality"]
        balanced_cost = count * (httpx_tool["cost_per_request"] + ds_cost)
        balanced_time = math.ceil(count / httpx_tool["speed_requests_per_second"]) + ds_parse_time

        balanced = Option(
            name="Balanced",
            strategy="httpx (async) + DeepSeek parsing",
            cost=round(balanced_cost, 2),
            quality=round(balanced_quality, 2),
            time_seconds=balanced_time,
            explanation=(
                f"httpx handles concurrent API calls (free, async) and DeepSeek "
                f"parses responses (${ds_cost:.4f}/response). Good speed and cost."
            ),
            tools=["httpx", "deepseek"],
            recommended=True,
        )

        # --- Quality Option: httpx + claude ---
        quality_quality = httpx_tool["success_rate"] * claude["quality"]
        quality_cost = count * (httpx_tool["cost_per_request"] + cl_cost)
        quality_time = math.ceil(count / httpx_tool["speed_requests_per_second"]) + cl_parse_time

        quality = Option(
            name="Quality Focused",
            strategy="httpx (async) + Claude parsing",
            cost=round(quality_cost, 2),
            quality=round(quality_quality, 2),
            time_seconds=quality_time,
            explanation=(
                f"httpx for fast API calls, Claude for premium response parsing "
                f"(${cl_cost:.4f}/response vs ${ds_cost:.4f}/response). "
                f"Better at understanding complex API responses."
            ),
            tools=["httpx", "claude"],
        )

        # --- Speed Option: httpx parallel (3x) + deepseek ---
        speed_quality = httpx_tool["success_rate"] * deepseek["quality"]
        speed_cost = count * (httpx_tool["cost_per_request"] + ds_cost)
        speed_time = math.ceil(count / (httpx_tool["speed_requests_per_second"] * 3)) + ds_parse_time

        speed = Option(
            name="Speed Optimized",
            strategy="httpx parallel (3 workers) + DeepSeek parsing",
            cost=round(speed_cost, 2),
            quality=round(speed_quality, 2),
            time_seconds=speed_time,
            explanation=(
                f"Runs 3 parallel httpx workers for maximum throughput. "
                f"Same parsing cost as Balanced (DeepSeek). "
                f"Ideal when response time matters."
            ),
            tools=["httpx", "deepseek"],
        )

        options = [budget, balanced, quality, speed]

        # Scope reduction if budget is tight
        if constraint and constraint.budget_max is not None:
            scope_option = self._generate_api_scope_reduction(
                task, constraint, balanced_cost, count, balanced, ds_cost,
            )
            if scope_option:
                options.append(scope_option)

        # Shift recommendation if user has a learned preference
        if preferred_strategy:
            match = next((o for o in options if o.name == preferred_strategy), None)
            if match and not match.recommended:
                for o in options:
                    o.recommended = False
                match.recommended = True

        return options

    def _generate_api_scope_reduction(
        self,
        task: Task,
        constraint: Constraint,
        full_cost: float,
        full_count: int,
        balanced: Option,
        ds_cost: float,
    ) -> Option | None:
        """Generate a scope-reduction option that fits the budget for API tasks."""
        if full_cost <= constraint.budget_max:
            return None

        httpx_tool = self.tools["httpx"]
        cost_per_endpoint = httpx_tool["cost_per_request"] + ds_cost
        if cost_per_endpoint <= 0:
            return None

        reduced_count = int(constraint.budget_max / cost_per_endpoint)
        if reduced_count >= full_count:
            return None
        if reduced_count < 2:
            return None

        deepseek = self.tools["deepseek"]
        reduced_cost = reduced_count * cost_per_endpoint
        call_time = math.ceil(reduced_count / httpx_tool["speed_requests_per_second"])
        parse_time = math.ceil(reduced_count / deepseek["pages_per_second"])

        return Option(
            name="Scope Reduction",
            strategy=f"Balanced approach but {reduced_count} endpoints instead of {full_count}",
            cost=round(reduced_cost, 2),
            quality=balanced.quality,
            time_seconds=call_time + parse_time,
            explanation=(
                f"Same strategy (httpx + DeepSeek) but calls "
                f"{reduced_count} endpoints instead of {full_count} to fit "
                f"within ${constraint.budget_max:.2f} budget. "
                f"Quality stays the same — you just get fewer results."
            ),
            tools=["httpx", "deepseek"],
        )

    def _generate_analysis_scope_reduction(
        self,
        task: Task,
        constraint: Constraint,
        full_cost: float,
        full_count: int,
        balanced: Option,
        ds_cost_1k: float,
    ) -> Option | None:
        """Generate a scope-reduction option that fits the budget for analysis."""
        if full_cost <= constraint.budget_max:
            return None

        cost_per_row = ds_cost_1k / 1000  # polars is free
        if cost_per_row <= 0:
            return None

        reduced_count = int(constraint.budget_max / cost_per_row)
        if reduced_count >= full_count:
            return None
        if reduced_count < 10:
            return None

        reduced_cost = (reduced_count / 1000) * ds_cost_1k
        polars_tool = self.tools["polars"]
        deepseek = self.tools["deepseek"]
        polars_time = math.ceil(reduced_count / polars_tool["speed_rows_per_second"])
        analysis_time = math.ceil(reduced_count / (deepseek["pages_per_second"] * 50))

        return Option(
            name="Scope Reduction",
            strategy=f"Balanced approach but {reduced_count} rows instead of {full_count}",
            cost=round(reduced_cost, 2),
            quality=balanced.quality,
            time_seconds=polars_time + analysis_time,
            explanation=(
                f"Same strategy (polars + DeepSeek) but processes "
                f"{reduced_count} rows instead of {full_count} to fit "
                f"within ${constraint.budget_max:.2f} budget. "
                f"Quality stays the same — you just analyze fewer rows."
            ),
            tools=["polars", "deepseek"],
        )
