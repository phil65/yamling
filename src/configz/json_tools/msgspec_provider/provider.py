"""MsgSpec provider implementation."""

from __future__ import annotations

from io import TextIOWrapper
import re
from typing import Any

from anyenv.json_tools.base import JsonDumpError, JsonLoadError, JsonProviderBase
from anyenv.json_tools.utils import handle_datetimes, prepare_numpy_arrays


def _extract_msgspec_error_info(exc: Exception, source: str) -> tuple[str, int | None, int | None]:
    """Extract line and column info from msgspec error message.

    msgspec errors report byte position like "invalid character (byte 14)"
    """
    msg = str(exc)
    line: int | None = None
    column: int | None = None

    # Try to extract byte position
    match = re.search(r"byte (\d+)", msg)
    if match:
        pos = int(match.group(1))
        # Convert byte position to line/column
        lines = source[:pos].split("\n")
        line = len(lines)
        column = len(lines[-1]) + 1

    return msg, line, column


class MsgSpecProvider(JsonProviderBase):
    """MsgSpec implementation of the JSON provider interface."""

    @staticmethod
    def load_json(data: str | bytes | TextIOWrapper) -> Any:
        """Load JSON using msgspec."""
        import msgspec.json

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
            return msgspec.json.decode(data)
        except msgspec.DecodeError as exc:
            msg, line, column = _extract_msgspec_error_info(exc, source_content or "")
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
        """Dump data to JSON string using msgspec."""
        import msgspec.json

        try:
            # Handle datetime objects first
            data = handle_datetimes(data, naive_utc)

            # Then process numpy arrays if requested
            if serialize_numpy:
                data = prepare_numpy_arrays(data)
            result = msgspec.json.encode(data, order="sorted" if sort_keys else None)
            if indent:
                return msgspec.json.format(result, indent=2).decode()
            return result.decode()
        except (TypeError, msgspec.EncodeError) as exc:
            error_msg = f"Cannot serialize to JSON: {exc}"
            raise JsonDumpError(error_msg) from exc
