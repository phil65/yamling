"""PyTOMLPP provider implementation."""

from __future__ import annotations

from io import TextIOWrapper
from pathlib import Path
import re
from typing import Any

from upath import UPath

from anyenv.toml_tools.base import TomlDumpError, TomlLoadError, TomlProviderBase


def _extract_pytomlpp_error_info(exc: Exception) -> tuple[str, int | None, int | None]:
    """Extract line and column info from pytomlpp error message.

    pytomlpp errors may include position info in various formats.
    """
    msg = str(exc)
    line: int | None = None
    column: int | None = None

    # Try pattern "at line X column Y" or "(at line X, column Y)"
    match = re.search(r"at line (\d+)[,]? column (\d+)", msg)
    if match:
        line = int(match.group(1))
        column = int(match.group(2))
    else:
        # Try pattern "line X"
        match = re.search(r"line (\d+)", msg)
        if match:
            line = int(match.group(1))

    return msg, line, column


class PytomlppProvider(TomlProviderBase):
    """PyTOMLPP implementation of the TOML provider interface."""

    @staticmethod
    def load_toml(data: str | bytes | TextIOWrapper | Path | UPath) -> Any:
        """Load TOML using pytomlpp."""
        import pytomlpp

        try:
            source_content: str | None = None
            source_path: Path | UPath | None = None
            match data:
                case Path() | UPath():
                    source_path = data
                    content = data.read_text("utf-8")
                    source_content = content
                    return pytomlpp.loads(content)
                case TextIOWrapper():
                    content = data.read()
                    source_content = content
                    return pytomlpp.loads(content)
                case bytes():
                    content = data.decode()
                    source_content = content
                    return pytomlpp.loads(content)
                case str():
                    source_content = data
                    return pytomlpp.loads(data)
        except Exception as exc:
            msg, line, column = _extract_pytomlpp_error_info(exc)
            raise TomlLoadError(  # noqa: TRY003
                f"Invalid TOML: {msg}",
                line=line,
                column=column,
                source_path=str(source_path) if isinstance(source_path, UPath) else source_path,
                source_content=source_content,
            ) from exc

    @staticmethod
    def dump_toml(data: Any, *, pretty: bool = False) -> str:
        """Dump data to TOML string using pytomlpp."""
        import pytomlpp

        try:
            # pytomlpp doesn't have a pretty option, it always formats nicely
            return pytomlpp.dumps(data)
        except Exception as exc:
            error_msg = f"Cannot serialize to TOML: {exc}"
            raise TomlDumpError(error_msg) from exc
