"""CLI state machine: the interactive conversation interface for Maestro."""

from __future__ import annotations

import copy
import io
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


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
    # On Windows, piped output may use cp1252 which can't handle emojis.
    # Force UTF-8 output when not in a real terminal, but only when
    # stdout.buffer is available (not in test runners that replace stdout).
    if sys.platform == "win32" and not sys.stdout.isatty():
        if hasattr(sys.stdout, "buffer"):
            try:
                safe_buf = _NonClosingBufferWrapper(sys.stdout.buffer)
                return Console(file=io.TextIOWrapper(safe_buf, encoding="utf-8", line_buffering=True))
            except (ValueError, AttributeError):
                pass
    return Console()

from maestro.analyzer import TaskAnalyzer
from maestro.executor import MockExecutor
from maestro.generator import OptionGenerator
from maestro.learner import PreferenceLearner
from maestro.models import Constraint, Option, Task
from maestro.negotiator import Negotiator, ParsedAdjustment, UserIntent
from maestro.validator import ConstraintValidator


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
            # Get task from user
            task = self._get_task()
            if task is None:
                continue

            # Check learned preferences
            preferred = self.learner.get_preferred_strategy(task.type)

            # Generate initial options
            self.console.print("\n  [dim]Analyzing task...[/dim]\n")
            options = self.generator.generate(task, preferred_strategy=preferred)
            constraint: Constraint | None = None

            # Show recommendation
            output = self.negotiator.format_recommendation(options)
            self.console.print(output)
            if preferred:
                self.console.print(
                    f"  [dim]📚 Based on your history, recommending: {preferred}[/dim]\n"
                )

            # Enter negotiation loop
            chosen = self._negotiation_loop(task, options, constraint, preferred)
            if chosen is None:
                self.console.print("\n  [dim]Task cancelled.[/dim]\n")
                if not self._ask_continue():
                    break
                continue

            # Execute
            try:
                result = self.executor.execute(task, chosen)
            except KeyboardInterrupt:
                self.console.print("\n\n  [yellow]Execution cancelled.[/yellow]\n")
                if not self._ask_continue():
                    break
                continue

            # Learn from choice
            self.learner.record_choice(task, options, chosen, constraint, result)
            self.console.print(
                "\n  [dim]📚 Choice recorded for future recommendations.[/dim]\n"
            )

            if not self._ask_continue():
                break

        self.console.print("\n  [bold]Goodbye![/bold]\n")

    def _print_welcome(self) -> None:
        """Print the welcome banner."""
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
        """Prompt user for task description and parse it."""
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

        # Validate count
        count = task.parameters.get("count", 0)
        if not isinstance(count, (int, float)) or count <= 0:
            self.console.print("\n  [yellow]Count must be a positive number. Please try again.[/yellow]\n")
            return None

        # Show what we parsed
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

    def _negotiation_loop(
        self,
        task: Task,
        options: list[Option],
        constraint: Constraint | None,
        preferred_strategy: str | None = None,
    ) -> Option | None:
        """Handle the negotiation conversation. Returns chosen Option or None if cancelled."""
        show_all = False  # Start by showing just the recommendation

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
                    # Accept the recommendation
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
                    # Check for "show options" signal
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

    def _regenerate(
        self,
        task: Task,
        constraint: Constraint | None,
        preferred_strategy: str | None = None,
    ) -> list[Option]:
        """Generate new options and validate against constraints."""
        options = self.generator.generate(task, constraint, preferred_strategy=preferred_strategy)
        if constraint:
            self.validator.validate(options, constraint)
        return options

    def _ask_continue(self) -> bool:
        """Ask if user wants to do another task."""
        try:
            answer = self.console.input("\n  [dim]Another task? (yes/no)[/dim] ")
            return answer.strip().lower() in ("yes", "y", "sure", "ok", "")
        except (EOFError, KeyboardInterrupt):
            return False

    # ------------------------------------------------------------------
    # Demo mode
    # ------------------------------------------------------------------

    @staticmethod
    def _build_demo_scenarios() -> list[dict[str, str]]:
        """Build the 3 demo scenarios."""
        return [
            {
                "title": "Web Scraping",
                "task_suggestion": "Scrape 100 dive shop websites and extract pricing",
                "adjustment_suggestion": "under $0.10",
                "pick_suggestion": "B",
            },
            {
                "title": "Data Analysis",
                "task_suggestion": "Analyze 500 rows of customer data for trends",
                "adjustment_suggestion": "better quality",
                "pick_suggestion": "yes",
            },
            {
                "title": "API Integration",
                "task_suggestion": "Fetch pricing from 20 hotel booking APIs",
                "adjustment_suggestion": "faster",
                "pick_suggestion": "A",
            },
        ]

    def _run_demo(self) -> None:
        """Run the guided demo walkthrough."""
        self.console.print(
            "  [bold cyan]Demo Mode[/bold cyan] — Press Enter to accept suggestions, "
            "or type your own input.\n"
        )

        for i, scenario in enumerate(self.demo_scenarios, 1):
            self.console.print(
                f"\n  [bold cyan]--- Demo {i}/{len(self.demo_scenarios)}: "
                f"{scenario['title']} ---[/bold cyan]\n"
            )

            # Step 1: Get task (with suggestion)
            task = self._get_task_with_suggestion(scenario["task_suggestion"])
            if task is None:
                continue

            # Step 2: Generate and show recommendation
            self.console.print("\n  [dim]Analyzing task...[/dim]\n")
            options = self.generator.generate(task)
            self.console.print(self.negotiator.format_recommendation(options))

            # Step 3: Adjustment (with suggestion)
            self.console.print(
                f"\n  [dim]Suggested adjustment: [bold]{scenario['adjustment_suggestion']}[/bold] "
                f"(press Enter to use)[/dim]"
            )
            try:
                user_input = self.console.input("\n[bold magenta]Maestro>[/bold magenta] ")
            except (EOFError, KeyboardInterrupt):
                break
            adjustment_text = user_input.strip() or scenario["adjustment_suggestion"]

            parsed = self.negotiator.parse_input(adjustment_text, len(options))
            constraint: Constraint | None = None

            if parsed.intent in (UserIntent.ADJUST_BUDGET, UserIntent.ADJUST_QUALITY, UserIntent.ADJUST_TIME):
                constraint = self.negotiator.build_constraint_from_adjustment(parsed)
                options = self._regenerate(task, constraint)
                self.console.print(self.negotiator.format_options(options))
            elif parsed.intent == UserIntent.ACCEPT:
                # User accepted the recommendation directly
                recommended = next((o for o in options if o.recommended), options[0])
                try:
                    self.executor.execute(task, recommended)
                except KeyboardInterrupt:
                    self.console.print("\n\n  [yellow]Execution cancelled.[/yellow]\n")
                self._demo_pause(i)
                continue

            # Step 4: Pick option (with suggestion)
            self.console.print(
                f"\n  [dim]Suggested pick: [bold]{scenario['pick_suggestion']}[/bold] "
                f"(press Enter to use)[/dim]"
            )
            try:
                user_input = self.console.input("\n[bold magenta]Maestro>[/bold magenta] ")
            except (EOFError, KeyboardInterrupt):
                break
            pick_text = user_input.strip() or scenario["pick_suggestion"]

            pick_parsed = self.negotiator.parse_input(pick_text, len(options))
            if pick_parsed.intent == UserIntent.ACCEPT:
                if pick_parsed.chosen_index is not None:
                    chosen = options[pick_parsed.chosen_index]
                else:
                    chosen = next((o for o in options if o.recommended), options[0])
                try:
                    self.executor.execute(task, chosen)
                except KeyboardInterrupt:
                    self.console.print("\n\n  [yellow]Execution cancelled.[/yellow]\n")

            self._demo_pause(i)

        self.console.print("\n  [bold cyan]Demo complete![/bold cyan] Run without --demo to try your own tasks.\n")

    def _get_task_with_suggestion(self, suggestion: str) -> Task | None:
        """Get task input, showing a suggestion the user can accept with Enter."""
        self.console.print(
            f"  [dim]Suggested task: [bold]{suggestion}[/bold] (press Enter to use)[/dim]"
        )
        try:
            user_input = self.console.input("[bold magenta]Maestro>[/bold magenta] ")
        except (EOFError, KeyboardInterrupt):
            return None

        text = user_input.strip() or suggestion
        task = self.analyzer.analyze(text)
        if task is None:
            self.console.print("\n  [yellow]Could not parse that task. Using suggestion instead.[/yellow]")
            task = self.analyzer.analyze(suggestion)
        if task is not None:
            # Show understood message
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

    def _demo_pause(self, current: int) -> None:
        """Pause between demo scenarios."""
        if current < len(self.demo_scenarios):
            try:
                self.console.input("\n  [dim]Press Enter for next demo...[/dim] ")
            except (EOFError, KeyboardInterrupt):
                pass


def main(demo: bool = False) -> None:
    """Entry point for `python -m maestro`."""
    cli = MaestroCLI(demo=demo)
    try:
        cli.run()
    except KeyboardInterrupt:
        Console().print("\n\n  [bold]Goodbye![/bold]\n")
