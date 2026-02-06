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
    """Simulates scraping execution with multi-phase progress and variance."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def execute(self, task: Task, option: Option) -> ExecutionResult:
        """Run a simulated execution with progress display. Returns results."""
        count = int(task.parameters.get("count", 50))
        domain = str(task.parameters.get("domain", "websites"))
        target = str(task.parameters.get("target", "data"))

        # Determine phases based on tools
        phases = self._build_phases(option, count)

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
                        progress.console.print(
                            f"    Running cost: [green]${running_cost:.2f}[/green]  |  "
                            f"{succeeded}/{total_processed} pages extracted",
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
            pages_processed=total_processed,
            pages_succeeded=succeeded,
            output_file=output_file,
        )

        self._print_summary(result)
        return result

    def _build_phases(self, option: Option, count: int) -> list[tuple[str, int, float]]:
        """Build execution phases: (name, page_count, failure_rate)."""
        phases = []

        if "scrapy" in option.tools:
            if "playwright" in option.tools:
                # Hybrid: scrapy handles ~85%, playwright gets the rest
                scrapy_count = int(count * 0.85)
                pw_count = count - scrapy_count
                phases.append((f"Crawling with Scrapy ({scrapy_count} pages)", scrapy_count, 0.03))
                phases.append((f"Rendering JS pages with Playwright ({pw_count} pages)", pw_count, 0.05))
            else:
                phases.append((f"Crawling with Scrapy ({count} pages)", count, 0.15))

        # Extraction phase
        extractor = "Claude" if "claude" in option.tools else "DeepSeek"
        phases.append((f"Extracting data with {extractor} ({count} pages)", count, 0.08))

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

        # Generate fake results for each "scraped" site
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

    def _print_summary(self, result: ExecutionResult) -> None:
        """Print execution summary."""
        self.console.print()
        status = "[bold green]Complete![/bold green]" if result.success else "[bold red]Completed with issues[/bold red]"
        self.console.print(f"  ✅ {status}")
        self.console.print(f"    💰 Final cost: [green]${result.actual_cost:.2f}[/green]")
        self.console.print(
            f"    ✨ Quality: [green]{result.actual_quality:.0%}[/green] "
            f"({result.pages_succeeded}/{result.pages_processed} successful)"
        )

        time_str = f"{result.actual_time_seconds // 60}m {result.actual_time_seconds % 60}s"
        self.console.print(f"    ⏱️  Time: [green]{time_str}[/green]")
        self.console.print()
        self.console.print(f"  Results saved to: [link]{result.output_file}[/link]")
