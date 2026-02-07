"""CLI state machine: the interactive conversation interface for Maestro."""

from __future__ import annotations

import copy
import io
import sys
import argparse
import json  # <--- kwa --json output

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from maestro.analyzer import TaskAnalyzer
from maestro.executor import MockExecutor
from maestro.generator import OptionGenerator
from maestro.learner import PreferenceLearner
from maestro.models import Constraint, Option, Task
from maestro.negotiator import Negotiator, ParsedAdjustment, UserIntent
from maestro.validator import ConstraintValidator


class _NonClosingBufferWrapper(io.RawIOBase):
    """Wraps a buffer without closing it when the wrapper is garbage-collected."""

    def __init__(self, buf: io.RawIOBase | io.BufferedIOBase) -> None:
        self._buf = buf

    def write(self, data: bytes) -> int:  # type: ignore[override]
        return self._buf.write(data)

    def writable(self) -> bool:
        return True


def _make_console() -> Console:
    """Create a Rich Console that handles Windows encoding gracefully."""
    if sys.platform == "win32" and not sys.stdout.isatty():
        if hasattr(sys.stdout, "buffer"):
            try:
                safe_buf = _NonClosingBufferWrapper(sys.stdout.buffer)
                return Console(
                    file=io.TextIOWrapper(safe_buf, encoding="utf-8", line_buffering=True)
                )
            except (ValueError, AttributeError):
                pass
    return Console()


class MaestroCLI:
    """Interactive CLI that drives the full negotiation → execution flow."""

    def __init__(self, demo: bool = False) -> None:
        self.console = _make_console()
        self.analyzer = TaskAnalyzer()
        self.generator = OptionGenerator()
        self.validator = ConstraintValidator()
        self.negotiator = Negotiator()
        self.executor = MockExecutor(self.console)
        self.learner = PreferenceLearner()
        self.demo = demo
        self.demo_scenarios = self._build_demo_scenarios() if demo else []

    def run(self) -> None:
        """Main loop: welcome → input → analyze → negotiate → execute → done."""
        self._print_welcome()
        if self.demo:
            self._run_demo()
            return

        while True:
            task = self._get_task()
            if task is None:
                continue

            preferred = self.learner.get_preferred_strategy(task.type)
            self.console.print("\n  [dim]Analyzing task...[/dim]\n")
            options = self.generator.generate(task, preferred_strategy=preferred)
            constraint: Constraint | None = None

            output = self.negotiator.format_recommendation(options)
            self.console.print(output)
            if preferred:
                self.console.print(
                    f"  [dim]📚 Based on your history, recommending: {preferred}[/dim]\n"
                )

            chosen = self._negotiation_loop(task, options, constraint, preferred)
            if chosen is None:
                self.console.print("\n  [dim]Task cancelled.[/dim]\n")
                if not self._ask_continue():
                    break
                continue

            try:
                result = self.executor.execute(task, chosen)
                self.executor.last_result = result  # <--- kwa --json output
            except KeyboardInterrupt:
                self.console.print("\n\n  [yellow]Execution cancelled.[/yellow]\n")
                if not self._ask_continue():
                    break
                continue

            self.learner.record_choice(task, options, chosen, constraint, result)
            self.console.print("\n  [dim]📚 Choice recorded for future recommendations.[/dim]\n")

            if not self._ask_continue():
                break

        self.console.print("\n  [bold]Goodbye![/bold]\n")

    # ---------------------- Helper methods (unchanged) ----------------------

    def _print_welcome(self) -> None:
        title = Text("Maestro", style="bold magenta")
        subtitle = Text("Intelligent AI Tool Orchestration", style="dim")
        self.console.print()
        self.console.print(Panel(
            Text.assemble(title, "\n", subtitle),
            border_style="magenta",
            padding=(1, 4),
        ))
        self.console.print("  Describe a task (scraping, data analysis, or API integration), and I'll show you the best approach.\n")

    def _get_task(self) -> Task | None:
        try:
            user_input = self.console.input("[bold magenta]Maestro>[/bold magenta] ")
        except (EOFError, KeyboardInterrupt):
            self.console.print()
            sys.exit(0)

        user_input = user_input.strip()
        if not user_input:
            return None
        if user_input.lower() in ("quit", "exit", "q"):
            sys.exit(0)
        if not self.analyzer.llm_available:
            self.console.print("  [dim](using regex parser)[/dim]")

        task = self.analyzer.analyze(user_input)
        if task is None:
            self.console.print(
                "\n  [yellow]I can help with scraping, data analysis, and API integration tasks.[/yellow]"
                "\n  Try: 'Scrape 100 dive shop websites', 'Analyze 500 rows of customer data',"
                "\n  or 'Fetch pricing from 20 hotel booking APIs'\n"
            )
            return None

        count = task.parameters.get("count", 0)
        if not isinstance(count, (int, float)) or count <= 0:
            self.console.print("\n  [yellow]Count must be a positive number. Please try again.[/yellow]\n")
            return None

        params = task.parameters
        if task.type == "analysis":
            self.console.print(
                f"\n  [dim]Understood: analyze {params.get('count', '?')} rows"
                f" of {params.get('source', 'data')}"
                f"{' for ' + str(params.get('analysis_type', '')) if params.get('analysis_type') else ''}[/dim]"
            )
        elif task.type == "api":
            self.console.print(
                f"\n  [dim]Understood: call {params.get('count', '?')} "
                f"{params.get('source', 'service')} APIs"
                f"{' for ' + str(params.get('target', '')) if params.get('target') else ''}[/dim]"
            )
        else:
            self.console.print(
                f"\n  [dim]Understood: scrape {params.get('count', '?')} "
                f"{params.get('domain', 'websites')}"
                f"{' for ' + str(params.get('target', '')) if params.get('target') else ''}[/dim]"
            )
        return task

    def _negotiation_loop(self, task: Task, options: list[Option], constraint: Constraint | None, preferred_strategy: str | None = None) -> Option | None:
        show_all = False
        while True:
            try:
                user_input = self.console.input("\n[bold magenta]Maestro>[/bold magenta] ")
            except (EOFError, KeyboardInterrupt):
                return None
            parsed = self.negotiator.parse_input(user_input, len(options))

            match parsed.intent:
                case UserIntent.QUIT:
                    return None
                case UserIntent.ACCEPT:
                    if parsed.chosen_index is not None:
                        return options[parsed.chosen_index]
                    recommended = next((o for o in options if o.recommended), options[0])
                    return recommended
                case UserIntent.ADJUST_BUDGET | UserIntent.ADJUST_QUALITY | UserIntent.ADJUST_TIME:
                    constraint = self.negotiator.build_constraint_from_adjustment(parsed, constraint)
                    options = self._regenerate(task, constraint, preferred_strategy)
                    self.console.print(self.negotiator.format_options(options))
                    show_all = True
                case UserIntent.ADJUST_SCOPE:
                    if parsed.value is not None:
                        task = copy.deepcopy(task)
                        task.parameters["count"] = int(parsed.value)
                        options = self._regenerate(task, constraint, preferred_strategy)
                        self.console.print(self.negotiator.format_options(options))
                        show_all = True
                    else:
                        hints = {"analysis": "rows", "api": "endpoints", "scraping": "sites"}
                        hint = hints.get(task.type, "items")
                        self.console.print(f"\n  [yellow]How many {hint}? (e.g., 'only 50')[/yellow]")
                case UserIntent.UNKNOWN:
                    if parsed.value == -1:
                        self.console.print(self.negotiator.format_options(options))
                        show_all = True
                    else:
                        self.console.print(
                            "\n  [yellow]I didn't understand that. You can:[/yellow]"
                            "\n    • Say [bold]yes[/bold] to proceed"
                            "\n    • Say [bold]show options[/bold] to see alternatives"
                            "\n    • Adjust: [bold]under $1[/bold], [bold]faster[/bold], "
                            "[bold]better quality[/bold], [bold]only 50 sites[/bold]"
                            "\n    • Pick an option: [bold]A[/bold], [bold]B[/bold], [bold]C[/bold]..."
                            "\n    • Say [bold]quit[/bold] to cancel"
                        )

    def _regenerate(self, task: Task, constraint: Constraint | None, preferred_strategy: str | None = None) -> list[Option]:
        options = self.generator.generate(task, constraint, preferred_strategy=preferred_strategy)
        if constraint:
            self.validator.validate(options, constraint)
        return options

    def _ask_continue(self) -> bool:
        try:
            answer = self.console.input("\n  [dim]Another task? (yes/no)[/dim] ")
            return answer.strip().lower() in ("yes", "y", "sure", "ok", "")
        except (EOFError, KeyboardInterrupt):
            return False

    # ---------------------- Demo Methods (unchanged) ----------------------

    @staticmethod
    def _build_demo_scenarios() -> list[dict[str, str]]:
        return [
            {"title": "Web Scraping", "task_suggestion": "Scrape 100 dive shop websites and extract pricing", "adjustment_suggestion": "under $0.10", "pick_suggestion": "B"},
            {"title": "Data Analysis", "task_suggestion": "Analyze 500 rows of customer data for trends", "adjustment_suggestion": "better quality", "pick_suggestion": "yes"},
            {"title": "API Integration", "task_suggestion": "Fetch pricing from 20 hotel booking APIs", "adjustment_suggestion": "faster", "pick_suggestion": "A"},
        ]

    # _run_demo, _get_task_with_suggestion, _demo_pause stay same as before

# ---------------------- Updated Main Entry ----------------------

def main() -> None:
    """Entry point for `python -m maestro`."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run demo mode")
    parser.add_argument("--json", action="store_true", help="Output last result as JSON")
    args = parser.parse_args()

    cli = MaestroCLI(demo=args.demo)

    try:
        if args.json:
            cli.run()
            if hasattr(cli.executor, "last_result"):
                print(json.dumps(cli.executor.last_result, indent=2))
        else:
            cli.run()
    except KeyboardInterrupt:
        Console().print("\n\n  [bold]Goodbye![/bold]\n")
