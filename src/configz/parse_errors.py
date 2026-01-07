"""Shared parse error handling for JSON and TOML."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ParseErrorInfo:
    """Structured information about a parse error."""

    message: str
    format_name: str = "Parse"
    line: int | None = None
    column: int | None = None
    source_path: str | Path | None = None
    source_content: str | None = None

    def format(
        self,
        context_lines: int = 2,
        use_color: bool = True,
    ) -> str:
        """Format error with source context for display.

        Args:
            context_lines: Number of lines to show before/after the error line.
            use_color: Whether to include ANSI color codes.
        """
        parts: list[str] = []

        # Header with location
        location = str(self.source_path) if self.source_path else "<string>"
        if self.line is not None:
            location += f":{self.line}"
            if self.column is not None:
                location += f":{self.column}"

        if use_color:
            parts.append(f"\x1b[1;31m{self.format_name} Error\x1b[0m at \x1b[1m{location}\x1b[0m")
        else:
            parts.append(f"{self.format_name} Error at {location}")

        parts.append(f"  {self.message}")

        # Source context
        if self.source_content and self.line is not None:
            parts.append("")
            lines = self.source_content.splitlines()
            start = max(0, self.line - 1 - context_lines)
            end = min(len(lines), self.line + context_lines)

            line_num_width = len(str(end))

            for i in range(start, end):
                line_num = i + 1
                line_content = lines[i] if i < len(lines) else ""
                prefix = ">" if line_num == self.line else " "

                if use_color and line_num == self.line:
                    parts.append(
                        f"\x1b[1;31m{prefix} {line_num:>{line_num_width}} │\x1b[0m {line_content}"
                    )
                else:
                    parts.append(f"{prefix} {line_num:>{line_num_width}} │ {line_content}")

                # Column indicator
                if line_num == self.line and self.column is not None:
                    indicator_padding = " " * (line_num_width + 4 + self.column - 1)
                    if use_color:
                        parts.append(f"\x1b[1;31m{indicator_padding}^\x1b[0m")
                    else:
                        parts.append(f"{indicator_padding}^")

        return "\n".join(parts)
