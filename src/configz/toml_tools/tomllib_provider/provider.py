"""TOMLLIB provider implementation."""

from __future__ import annotations

from io import BytesIO, TextIOWrapper
from pathlib import Path
import re
from typing import Any

from upath import UPath

from anyenv.toml_tools.base import TomlDumpError, TomlLoadError, TomlProviderBase


def _extract_tomllib_error_info(
    exc: Exception, source: str | None
) -> tuple[str, int | None, int | None]:
    """Extract line and column info from tomllib error message.

    tomllib errors typically have format like "... (at line X, column Y)"
    or "Invalid value (at line 3, column 5)" or "... (at end of document)"
    """
    msg = str(exc)
    line: int | None = None
    column: int | None = None

    # Try pattern "(at line X, column Y)"
    match = re.search(r"\(at line (\d+), column (\d+)\)", msg)
    if match:
        line = int(match.group(1))
        column = int(match.group(2))
    else:
        # Try pattern "at line X, column Y" without parentheses
        match = re.search(r"at line (\d+), column (\d+)", msg)
        if match:
            line = int(match.group(1))
            column = int(match.group(2))
        elif "at end of document" in msg and source:
            # For end-of-document errors, use last line
            lines = source.splitlines()
            line = len(lines)
            column = len(lines[-1]) + 1 if lines else 1

    return msg, line, column


class TomlLibProvider(TomlProviderBase):
    """TOMLLIB implementation of the TOML provider interface."""

    @staticmethod
    def load_toml(data: str | bytes | TextIOWrapper | Path | UPath) -> Any:
        """Load TOML using tomllib."""
        import tomllib

        try:
            source_content: str | None = None
            match data:
                case Path() | UPath():
                    content = data.read_bytes()
                    source_content = content.decode(errors="replace")
                    return tomllib.load(BytesIO(content))
                case TextIOWrapper():
                    text_content = data.read()
                    source_content = text_content
                    return tomllib.loads(text_content)
                case bytes():
                    source_content = data.decode(errors="replace")
                    return tomllib.loads(data.decode())
                case str():
                    source_content = data
                    return tomllib.loads(data)
        except tomllib.TOMLDecodeError as exc:
            msg, line, column = _extract_tomllib_error_info(exc, source_content)
            source_path: str | Path | None = (
                str(data) if isinstance(data, UPath) else (data if isinstance(data, Path) else None)
            )
            raise TomlLoadError(  # noqa: TRY003
                f"Invalid TOML: {msg}",
                line=line,
                column=column,
                source_path=source_path,
                source_content=source_content,
            ) from exc

    @staticmethod
    def dump_toml(data: Any, *, pretty: bool = False) -> str:
        """Dump data to TOML string using tomllib."""
        # tomllib is read-only, so we need to fallback to another library
        # or raise an error
        msg = "tomllib does not support writing TOML files (read-only library)"
        raise TomlDumpError(msg)
