"""Package for JSON-related tools with validation support.

Provides a unified interface for JSON serialization/deserialization
with automatic selection of the best available backend and type validation.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Literal, TYPE_CHECKING

from anyenv.json_tools.base import JsonDumpError, JsonLoadError
from anyenv.parse_errors import ParseErrorInfo

if TYPE_CHECKING:
    from anyenv.json_tools.base import JsonProviderBase
    from io import TextIOWrapper

# Determine the best available provider
_provider: type[JsonProviderBase]

if importlib.util.find_spec("orjson") is not None:
    from anyenv.json_tools.orjson_provider.provider import OrJsonProvider

    _provider = OrJsonProvider
elif importlib.util.find_spec("pydantic_core") is not None:
    from anyenv.json_tools.pydantic_provider.provider import PydanticProvider

    _provider = PydanticProvider
elif importlib.util.find_spec("msgspec") is not None:
    from anyenv.json_tools.msgspec_provider.provider import MsgSpecProvider

    _provider = MsgSpecProvider
else:
    from anyenv.json_tools.stdlib_provider.provider import StdLibProvider

    _provider = StdLibProvider

# Backend type for JSON providers
BackendType = Literal["auto", "orjson", "pydantic", "msgspec", "stdlib"]


def get_json_provider(backend: BackendType = "auto") -> type[JsonProviderBase]:
    """Get the specified JSON provider or the best available one.

    Args:
        backend: The JSON backend to use. If "auto", uses the best available.

    Returns:
        A JSON provider implementation

    Raises:
        ImportError: If the requested backend is not available
    """
    if backend == "auto":
        return _provider

    if backend == "orjson":
        if importlib.util.find_spec("orjson") is not None:
            from anyenv.json_tools.orjson_provider.provider import OrJsonProvider

            return OrJsonProvider
        msg = "orjson backend requested but not installed"
        raise ImportError(msg)

    if backend == "pydantic":
        if importlib.util.find_spec("pydantic_core") is not None:
            from anyenv.json_tools.pydantic_provider.provider import PydanticProvider

            return PydanticProvider
        msg = "pydantic backend requested but pydantic_core not installed"
        raise ImportError(msg)

    if backend == "msgspec":
        if importlib.util.find_spec("msgspec") is not None:
            from anyenv.json_tools.msgspec_provider.provider import MsgSpecProvider

            return MsgSpecProvider
        msg = "msgspec backend requested but not installed"
        raise ImportError(msg)

    if backend == "stdlib":
        from anyenv.json_tools.stdlib_provider.provider import StdLibProvider

        return StdLibProvider

    msg = f"Unknown backend: {backend}"
    raise ValueError(msg)


def load_json[T = Any](
    data: str | bytes | TextIOWrapper,
    return_type: type[T] | None = None,
    backend: BackendType = "auto",
) -> T:
    """Load JSON data with optional type validation.

    Args:
        data: The JSON data to parse (string, bytes, or file-like object)
        return_type: Optional type to validate the data against
        backend: JSON backend to use for parsing

    Returns:
        The parsed and validated data

    Raises:
        JsonLoadError: If parsing fails
        TypeError: If validation against return_type fails
    """
    provider = get_json_provider(backend)
    parsed_data = provider.load_json(data)

    if return_type is not None:
        from anyenv.validate import validate_json_data

        return validate_json_data(parsed_data, return_type)
    return parsed_data  # type: ignore[no-any-return]


def dump_json(
    data: Any,
    indent: bool = False,
    naive_utc: bool = False,
    serialize_numpy: bool = False,
    sort_keys: bool = False,
    backend: BackendType = "auto",
) -> str:
    """Serialize data to a JSON string.

    Args:
        data: The data to serialize
        indent: Whether to format the output with indentation
        naive_utc: Whether to interpret naive datetime objects as UTC
        serialize_numpy: Whether to serialize numpy arrays
        sort_keys: Sort dictionary keys
        backend: JSON backend to use for serialization

    Returns:
        The serialized JSON string

    Raises:
        JsonDumpError: If serialization fails
    """
    provider = get_json_provider(backend)
    return provider.dump_json(
        data,
        indent=indent,
        naive_utc=naive_utc,
        serialize_numpy=serialize_numpy,
        sort_keys=sort_keys,
    )


# Export the exception classes for user code
__all__ = [
    "BackendType",
    "JsonDumpError",
    "JsonLoadError",
    "ParseErrorInfo",
    "dump_json",
    "load_json",
]
