"""Pydantic provider implementation."""

from __future__ import annotations

from io import TextIOWrapper
import logging
from typing import Any

from anyenv.json_tools.base import JsonDumpError, JsonLoadError, JsonProviderBase
from anyenv.json_tools.stdlib_provider.provider import StdLibProvider
from anyenv.json_tools.utils import handle_datetimes, prepare_numpy_arrays


logger = logging.getLogger(__name__)


def _extract_pydantic_error_info(exc: Exception) -> tuple[str, int | None, int | None]:
    """Extract line and column info from pydantic_core error message.

    pydantic_core errors have format like "expected value at line 1 column 15"
    """
    import re

    msg = str(exc)
    line: int | None = None
    column: int | None = None

    # Pattern: "at line X column Y"
    match = re.search(r"at line (\d+) column (\d+)", msg)
    if match:
        line = int(match.group(1))
        column = int(match.group(2))

    return msg, line, column


class PydanticProvider(JsonProviderBase):
    """Pydantic implementation of the JSON provider interface."""

    @staticmethod
    def load_json(data: str | bytes | TextIOWrapper) -> Any:
        """Load JSON using pydantic_core."""
        from pydantic_core import from_json

        try:
            source_content: str | None = None
            match data:
                case TextIOWrapper():
                    data = data.read()
                    source_content = data
                case str():
                    source_content = data
                case bytes():
                    source_content = data.decode(errors="replace")
            return from_json(data)
        except Exception as exc:
            msg, line, column = _extract_pydantic_error_info(exc)
            raise JsonLoadError(  # noqa: TRY003
                f"Invalid JSON: {msg}",
                line=line,
                column=column,
                source_content=source_content,
            ) from exc

    @staticmethod
    def dump_json(
        data: Any,
        indent: bool = False,
        naive_utc: bool = False,
        serialize_numpy: bool = False,
        sort_keys: bool = False,
    ) -> str:
        """Dump data to JSON string using pydantic_core."""
        from pydantic_core import to_json

        if sort_keys:
            # https://github.com/pydantic/pydantic-core/pull/1637
            logger.warning("Sorting dicts not yet supported with pydantic serializer")
            return StdLibProvider().dump_json(
                data,
                indent=indent,
                naive_utc=naive_utc,
                serialize_numpy=serialize_numpy,
                sort_keys=sort_keys,
            )
        try:
            # Handle datetime objects first
            data = handle_datetimes(data, naive_utc)

            # Then process numpy arrays if requested
            if serialize_numpy:
                data = prepare_numpy_arrays(data)

            return to_json(data, indent=2 if indent else None).decode()
        except Exception as exc:
            error_msg = f"Cannot serialize to JSON: {exc}"
            raise JsonDumpError(error_msg) from exc
