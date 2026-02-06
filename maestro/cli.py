"""CLI state machine: the interactive conversation interface for Maestro."""

from __future__ import annotations

import copy
import io
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def _make_console() -> Console:
    """Create a Rich Console that handles Windows encoding gracefully."""
    # On Windows, piped output may use cp1252 which can't handle emojis.
    # Force UTF-8 output when not in a real terminal.
    if sys.platform == "win32" and not sys.stdout.isatty():
        return Console(file=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))
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

    def __init__(self) -> None:
        self.console = _make_console()
        self.analyzer = TaskAnalyzer()
        self.generator = OptionGenerator()
        self.validator = ConstraintValidator()
        self.negotiator = Negotiator()
        self.executor = MockExecutor(self.console)
        self.learner = PreferenceLearner()

    def run(self) -> None:
        """Main loop: welcome → input → analyze → negotiate → execute → done."""
        self._print_welcome()

        while True:
            # Get task from user
            task = self._get_task()
            if task is None:
                continue

            # Generate initial options
            self.console.print("\n  [dim]Analyzing task...[/dim]\n")
            options = self.generator.generate(task)
            constraint: Constraint | None = None

            # Show recommendation
            output = self.negotiator.format_recommendation(options)
            self.console.print(output)

            # Enter negotiation loop
            chosen = self._negotiation_loop(task, options, constraint)
            if chosen is None:
                self.console.print("\n  [dim]Task cancelled.[/dim]\n")
                if not self._ask_continue():
                    break
                continue

            # Execute
            result = self.executor.execute(task, chosen)

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
        self.console.print("  Describe a scraping task, and I'll show you the best approach.\n")

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

        task = self.analyzer.analyze(user_input)
        if task is None:
            self.console.print(
                "\n  [yellow]I can help with web scraping tasks.[/yellow]"
                "\n  Try something like: 'Scrape 100 dive shop websites and extract pricing'\n"
            )
            return None

        # Show what we parsed
        params = task.parameters
        self.console.print(f"\n  [dim]Understood: scrape {params.get('count', '?')} "
                          f"{params.get('domain', 'websites')}"
                          f"{' for ' + str(params.get('target', '')) if params.get('target') else ''}[/dim]")
        return task

    def _negotiation_loop(
        self,
        task: Task,
        options: list[Option],
        constraint: Constraint | None,
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
                    options = self._regenerate(task, constraint)
                    self.console.print(self.negotiator.format_options(options))
                    show_all = True

                case UserIntent.ADJUST_SCOPE:
                    if parsed.value is not None:
                        task = copy.deepcopy(task)
                        task.parameters["count"] = int(parsed.value)
                        options = self._regenerate(task, constraint)
                        self.console.print(self.negotiator.format_options(options))
                        show_all = True
                    else:
                        self.console.print("\n  [yellow]How many sites? (e.g., 'only 50')[/yellow]")

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

    def _regenerate(self, task: Task, constraint: Constraint | None) -> list[Option]:
        """Generate new options and validate against constraints."""
        options = self.generator.generate(task, constraint)
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


def main() -> None:
    """Entry point for `python -m maestro`."""
    cli = MaestroCLI()
    try:
        cli.run()
    except KeyboardInterrupt:
        Console().print("\n\n  [bold]Goodbye![/bold]\n")
