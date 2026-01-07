"""TOML-RS provider implementation."""

from __future__ import annotations

from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any

from upath import UPath

from anyenv.toml_tools.base import TomlLoadError, TomlProviderBase


class TomlRsProvider(TomlProviderBase):
    """TOML-RS implementation of the TOML provider interface."""

    @staticmethod
    def load_toml(data: str | bytes | TextIOWrapper | Path | UPath) -> Any:
        """Load TOML using toml_rs."""
        import toml_rs

        try:
            source_content: str | None = None
            source_path: Path | UPath | None = None
            match data:
                case Path() | UPath():
                    source_path = data
                    bytes_data = data.read_bytes()
                    source_content = bytes_data.decode(errors="replace")
                    return toml_rs.load(BytesIO(bytes_data))
                case TextIOWrapper():
                    content = data.read()
                    source_content = content
                    return toml_rs.loads(content)
                case bytes():
                    content = data.decode()
                    source_content = content
                    return toml_rs.loads(content)
                case str():
                    source_content = data
                    return toml_rs.loads(data)
        except toml_rs.TOMLDecodeError as exc:
            raise TomlLoadError(  # noqa: TRY003
                f"Invalid TOML: {exc.msg}",
                line=exc.lineno,
                column=exc.colno,
                source_path=str(source_path) if isinstance(source_path, UPath) else source_path,
                source_content=source_content,
            ) from exc

    @staticmethod
    def dump_toml(data: Any, *, pretty: bool = False) -> str:
        """Dump data to TOML string using toml_rs."""
        import toml_rs

        return toml_rs.dumps(data, pretty=pretty)
