"""MockExecutor: simulates task execution with realistic progress display."""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from maestro.models import ExecutionResult, Option, Task


class MockExecutor:
    """Simulates task execution with multi-phase progress and variance."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def execute(self, task: Task, option: Option) -> ExecutionResult:
        """Run a simulated execution with progress display. Returns results."""
        count = int(task.parameters.get("count", 50))
        domain = str(task.parameters.get("domain", "websites"))
        target = str(task.parameters.get("target", "data"))

        # Determine phases based on tools
        phases = self._build_phases(task, option, count)

        self.console.print()
        self.console.print("  [bold]Starting execution...[/bold]")
        self.console.print()

        succeeded = 0
        total_processed = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        ) as progress:
            for phase_name, phase_count, fail_rate in phases:
                task_id = progress.add_task(f"  {phase_name}", total=phase_count)

                for i in range(phase_count):
                    # Non-uniform delays — some pages "take longer"
                    delay = random.uniform(0.02, 0.12)
                    if random.random() < 0.1:  # 10% chance of a "slow" page
                        delay *= 3
                    time.sleep(delay)

                    # Simulate success/failure
                    if random.random() > fail_rate:
                        succeeded += 1
                    total_processed += 1

                    progress.update(task_id, advance=1)

                    # Show running cost periodically
                    if total_processed % max(count // 5, 1) == 0:
                        running_cost = (total_processed / count) * option.cost
                        item_labels = {"analysis": "items processed", "api": "APIs called", "scraping": "pages extracted"}
                        item_label = item_labels.get(task.type, "items processed")
                        progress.console.print(
                            f"    Running cost: [green]${running_cost:.2f}[/green]  |  "
                            f"{succeeded}/{total_processed} {item_label}",
                            highlight=False,
                        )

        # Add gaussian variance to estimates (3-8%)
        variance = random.gauss(1.0, 0.05)
        actual_cost = round(option.cost * max(variance, 0.85), 2)
        actual_quality = succeeded / max(total_processed, 1)
        actual_time = int(option.time_seconds * random.uniform(0.85, 1.15))

        # Write output file
        output_file = self._write_results(
            task, option, count, succeeded, total_processed, actual_cost, domain, target,
        )

        result = ExecutionResult(
            option=option,
            actual_cost=actual_cost,
            actual_quality=round(actual_quality, 2),
            actual_time_seconds=actual_time,
            success=actual_quality >= 0.5,
            items_processed=total_processed,
            items_succeeded=succeeded,
            output_file=output_file,
        )

        self._print_summary(result)
        return result

    def _build_phases(self, task: Task, option: Option, count: int) -> list[tuple[str, int, float]]:
        """Build execution phases: (name, item_count, failure_rate)."""
        if task.type == "analysis":
            return self._build_analysis_phases(option, count)
        if task.type == "api":
            return self._build_api_phases(option, count)
        return self._build_scraping_phases(option, count)

    def _build_scraping_phases(self, option: Option, count: int) -> list[tuple[str, int, float]]:
        """Build scraping execution phases."""
        phases = []

        if "scrapy" in option.tools:
            if "playwright" in option.tools:
                scrapy_count = int(count * 0.85)
                pw_count = count - scrapy_count
                phases.append((f"Crawling with Scrapy ({scrapy_count} pages)", scrapy_count, 0.03))
                phases.append((f"Rendering JS pages with Playwright ({pw_count} pages)", pw_count, 0.05))
            else:
                phases.append((f"Crawling with Scrapy ({count} pages)", count, 0.15))

        extractor = "Claude" if "claude" in option.tools else "DeepSeek"
        phases.append((f"Extracting data with {extractor} ({count} pages)", count, 0.08))

        return phases

    def _build_analysis_phases(self, option: Option, count: int) -> list[tuple[str, int, float]]:
        """Build data analysis execution phases."""
        phases = []

        processor = "polars" if "polars" in option.tools else "pandas"
        phases.append((f"Loading data ({count} rows)", min(count, 100), 0.02))
        phases.append((f"Processing with {processor} ({count} rows)", count, 0.03))

        analyzer = "Claude" if "claude" in option.tools else "DeepSeek"
        phases.append((f"Analyzing with {analyzer} ({count} rows)", count, 0.05))

        return phases

    def _build_api_phases(self, option: Option, count: int) -> list[tuple[str, int, float]]:
        """Build API integration execution phases."""
        phases = []

        client = "httpx" if "httpx" in option.tools else "requests"
        phases.append((f"Calling APIs with {client} ({count} endpoints)", count, 0.08))

        parser = "Claude" if "claude" in option.tools else "DeepSeek"
        phases.append((f"Parsing responses with {parser} ({count} responses)", count, 0.05))

        return phases

    def _write_results(
        self,
        task: Task,
        option: Option,
        count: int,
        succeeded: int,
        processed: int,
        actual_cost: float,
        domain: str,
        target: str,
    ) -> str:
        """Write fake but structured results to a JSON file."""
        output_dir = Path.cwd() / "output"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"maestro_results_{timestamp}.json"

        if task.type == "analysis":
            results = self._build_analysis_results(task, succeeded)
        elif task.type == "api":
            results = self._build_api_results(task, succeeded)
        else:
            results = self._build_scraping_results(domain, target, succeeded)

        output_data = {
            "meta": {
                "task": task.description,
                "strategy": option.strategy,
                "tools": option.tools,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "summary": {
                "total_requested": count,
                "total_processed": processed,
                "total_succeeded": succeeded,
                "success_rate": round(succeeded / max(processed, 1), 2),
                "actual_cost_usd": actual_cost,
            },
            "results": results,
        }

        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)

        return str(output_file)

    def _build_scraping_results(self, domain: str, target: str, succeeded: int) -> list[dict]:
        """Generate fake scraping results."""
        results = []
        for i in range(succeeded):
            results.append({
                "url": f"https://example-{domain.replace(' ', '-')}-{i+1}.com",
                "status": "success",
                "extracted": {
                    "name": f"Sample {domain.title()} #{i+1}",
                    target: f"Sample {target} data for site {i+1}",
                },
            })
        return results

    def _build_analysis_results(self, task: Task, succeeded: int) -> list[dict]:
        """Generate fake analysis results."""
        source = str(task.parameters.get("source", "data"))
        analysis_type = str(task.parameters.get("analysis_type", "analysis"))
        results = []
        for i in range(min(succeeded, 10)):  # Cap at 10 insight rows
            results.append({
                "row_range": f"{i * (succeeded // 10) + 1}-{(i + 1) * (succeeded // 10)}",
                "status": "success",
                "insight": f"Sample {analysis_type} insight #{i+1} from {source}",
                "confidence": round(random.uniform(0.75, 0.99), 2),
            })
        return results

    def _build_api_results(self, task: Task, succeeded: int) -> list[dict]:
        """Generate fake API integration results."""
        source = str(task.parameters.get("source", "service"))
        target = str(task.parameters.get("target", "data"))
        results = []
        for i in range(succeeded):
            results.append({
                "endpoint": f"https://api.{source.replace(' ', '-')}-{i+1}.com/v1/{target.replace(' ', '-')}",
                "status_code": 200,
                "status": "success",
                "data": {
                    "source": f"{source.title()} API #{i+1}",
                    target: f"Sample {target} from endpoint {i+1}",
                },
            })
        return results

    def _print_summary(self, result: ExecutionResult) -> None:
        """Print execution summary."""
        self.console.print()
        status = "[bold green]Complete![/bold green]" if result.success else "[bold red]Completed with issues[/bold red]"
        self.console.print(f"  ✅ {status}")
        self.console.print(f"    💰 Final cost: [green]${result.actual_cost:.2f}[/green]")
        self.console.print(
            f"    ✨ Quality: [green]{result.actual_quality:.0%}[/green] "
            f"({result.items_succeeded}/{result.items_processed} successful)"
        )

        time_str = f"{result.actual_time_seconds // 60}m {result.actual_time_seconds % 60}s"
        self.console.print(f"    ⏱️  Time: [green]{time_str}[/green]")
        self.console.print()
        self.console.print(f"  Results saved to: [link]{result.output_file}[/link]")
