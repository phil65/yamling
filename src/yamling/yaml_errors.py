"""Enhanced YAML error with rich formatting capabilities."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import yaml


if TYPE_CHECKING:
    from collections.abc import Iterable


class YAMLError(yaml.YAMLError):
    """YAML error with rich formatting capabilities.

    Inherits from yaml.YAMLError so existing code that catches YAMLError
    will continue to work, but adds rich formatting methods.
    """

    def __init__(
        self,
        original_error: yaml.YAMLError,
        doc_path: str | Path | None = None,
        context_lines: int = 3,
        extra_help: Iterable[str] | str | None = None,
    ) -> None:
        super().__init__(str(original_error))
        self.original_error = original_error
        self.doc_path = doc_path
        self.context_lines = context_lines
        self.extra_help = extra_help

    def render(self) -> None:
        """Display the error with rich formatting to stderr."""
        try:
            from rich.console import Console
        except ImportError:
            self._render_fallback()
            return

        console = Console(stderr=True)
        self._render_with_rich(console)

    def format(self) -> str:
        """Return the error as a formatted string."""
        try:
            from rich.console import Console
        except ImportError:
            return self._format_fallback()

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        self._render_with_rich(console)
        return string_io.getvalue()

    def _render_with_rich(self, console) -> None:
        """Render error using rich formatting."""
        if not (
            hasattr(self.original_error, "problem_mark")
            or hasattr(self.original_error, "context_mark")
        ):
            self._render_simple(console)
            return

        if hasattr(self.original_error, "context_mark") and self.original_error.context_mark:
            self._render_marked_error(
                console,
                getattr(self.original_error, "context", str(self.original_error)),
                self.original_error.context_mark.line + 1,
                self.original_error.context_mark.column + 1,
                self.original_error.context_mark.get_snippet(),
            )

        if hasattr(self.original_error, "problem_mark") and self.original_error.problem_mark:
            self._render_marked_error(
                console,
                getattr(self.original_error, "problem", str(self.original_error)),
                self.original_error.problem_mark.line + 1,
                self.original_error.problem_mark.column + 1,
                self.original_error.problem_mark.get_snippet(),
            )

    def _render_simple(self, console) -> None:
        """Render simple error without line markers."""
        from rich import box
        from rich.panel import Panel
        from rich.text import Text

        path_str = f" in {self.doc_path}" if self.doc_path else ""
        title = Text(f"YAML Error{path_str}", style="bold bright_red")
        content = Text(str(self.original_error), style="red")

        panel = Panel(content, title=title, border_style="bright_red", box=box.ROUNDED)
        console.print(panel)

        if self.extra_help:
            self._render_extra(console)

    def _render_marked_error(
        self, console, cause: str, line_number: int, column_number: int, snippet: str | None
    ) -> None:
        """Render error with line and column markers."""
        from rich.text import Text

        arrow_color = "bright_blue"
        error_color = "bright_red"
        separator_color = "bright_blue"

        console.print()
        console.print(
            Text("  ")
            + Text("-->", style=arrow_color)
            + Text(
                f" {Path(self.doc_path or '<string>').resolve()}:{line_number}:{column_number}",
                style="white",
            )
        )

        if snippet:
            lines = snippet.split("\n")
            start_line = max(1, line_number - self.context_lines)
            end_line = min(len(lines), line_number + self.context_lines)
            rjust = len(str(end_line))

            for idx, line in enumerate(lines, start=start_line):
                if idx > end_line:
                    break

                if idx == line_number:
                    prefix = Text()
                    prefix.append("╭╴", style=error_color)
                    prefix.append(str(idx).rjust(rjust), style=error_color)
                    prefix.append(" │ ", style=separator_color)
                    console.print(prefix, Text(line), sep="")

                    pointer_prefix = Text()
                    pointer_prefix.append("│ ", style=error_color)
                    pointer_prefix.append(" " * rjust, style=error_color)
                    pointer_prefix.append(" │ ", style=separator_color)
                    pointer_prefix.append(" " * (column_number - 1), style="")
                    pointer_prefix.append("↑", style=error_color)
                    console.print(pointer_prefix)
                else:
                    startswith = "│ " if idx > line_number else "  "
                    prefix = Text()
                    prefix.append(startswith, style=error_color if idx > line_number else "")
                    prefix.append(str(idx).rjust(rjust), style="bright_blue")
                    prefix.append(" │ ", style=separator_color)
                    console.print(prefix, Text(line), sep="")

        console.print(
            Text("╰─" + "─" * len(str(line_number)) + "─❯ ", style=error_color)  # noqa: RUF001
            + Text(cause, style="bright_red")
        )

        if self.extra_help:
            self._render_extra(console)

        console.print()

    def _render_extra(self, console) -> None:
        """Render extra help information."""
        from collections.abc import Iterable as IterableABC

        from rich import box
        from rich.padding import Padding
        from rich.table import Table

        table = Table(
            box=box.ROUNDED,
            border_style="bright_blue",
            show_header=False,
            expand=False,
            show_lines=True,
        )
        table.add_column()

        extra_items = (
            self.extra_help
            if isinstance(self.extra_help, IterableABC) and not isinstance(self.extra_help, str)
            else [self.extra_help]
        )
        for item in extra_items:
            table.add_row(str(item))

        console.print(Padding(table, (0, 4, 0, 4)))

    def _render_fallback(self) -> None:
        """Fallback rendering when rich is not available."""
        print(self._format_fallback(), file=sys.stderr)

    def _format_fallback(self) -> str:
        """Format error as plain text when rich is not available."""
        lines = []
        path_str = f" in {self.doc_path}" if self.doc_path else ""
        lines.append(f"\n❌ YAML Error{path_str}:")

        if hasattr(self.original_error, "problem_mark") and self.original_error.problem_mark:
            mark = self.original_error.problem_mark
            lines.append(f"  Line {mark.line + 1}, Column {mark.column + 1}")
            if hasattr(self.original_error, "problem"):
                lines.append(f"  {self.original_error.problem}")
        elif hasattr(self.original_error, "context_mark") and self.original_error.context_mark:
            mark = self.original_error.context_mark
            lines.append(f"  Line {mark.line + 1}, Column {mark.column + 1}")
            if hasattr(self.original_error, "context"):
                lines.append(f"  {self.original_error.context}")
        else:
            lines.append(f"  {self.original_error}")

        lines.append("")
        return "\n".join(lines)
