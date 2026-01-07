"""Base interface for TOML providers."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

from anyenv.parse_errors import ParseErrorInfo


if TYPE_CHECKING:
    from io import TextIOWrapper
    from pathlib import Path


class TomlProviderBase(abc.ABC):
    """Base class for all TOML providers."""

    @staticmethod
    @abc.abstractmethod
    def load_toml(data: str | bytes | TextIOWrapper | Path) -> Any:
        """Load TOML data into Python objects."""

    @staticmethod
    @abc.abstractmethod
    def dump_toml(
        data: Any,
        *,
        pretty: bool = False,
    ) -> str:
        """Dump Python objects to TOML string."""


class TomlLoadError(Exception):
    """Unified exception for all TOML parsing errors."""

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        source_path: str | Path | None = None,
        source_content: str | None = None,
    ):
        super().__init__(message)
        self.info = ParseErrorInfo(
            message=message,
            format_name="TOML Parse",
            line=line,
            column=column,
            source_path=source_path,
            source_content=source_content,
        )

    @property
    def line(self) -> int | None:
        """Line number where the error occurred."""
        return self.info.line

    @property
    def column(self) -> int | None:
        """Column number where the error occurred."""
        return self.info.column

    @property
    def source_path(self) -> str | Path | None:
        """Path to the source file that caused the error."""
        return self.info.source_path

    @property
    def source_content(self) -> str | None:
        """Source content that caused the error."""
        return self.info.source_content

    def format(self, context_lines: int = 2, use_color: bool = True) -> str:
        """Format error with source context for display.

        Args:
            context_lines: Number of lines to show before/after the error line.
            use_color: Whether to include ANSI color codes.
        """
        return self.info.format(context_lines=context_lines, use_color=use_color)


class TomlDumpError(Exception):
    """Unified exception for all TOML serialization errors."""
