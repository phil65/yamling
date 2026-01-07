"""Package for TOML-related tools with validation support.

Provides a unified interface for TOML serialization/deserialization
with automatic selection of the best available backend and type validation.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Literal, TYPE_CHECKING

from anyenv.toml_tools.base import TomlDumpError, TomlLoadError
from anyenv.parse_errors import ParseErrorInfo

if TYPE_CHECKING:
    from anyenv.toml_tools.base import TomlProviderBase
    from io import TextIOWrapper
    from pathlib import Path

# Determine the best available provider
_provider: type[TomlProviderBase]

if importlib.util.find_spec("toml_rs") is not None:
    from anyenv.toml_tools.toml_rs_provider.provider import TomlRsProvider

    _provider = TomlRsProvider
elif importlib.util.find_spec("rtoml") is not None:
    from anyenv.toml_tools.rtoml_provider.provider import RtomlProvider

    _provider = RtomlProvider
elif importlib.util.find_spec("pytomlpp") is not None:
    from anyenv.toml_tools.pytomlpp_provider.provider import PytomlppProvider

    _provider = PytomlppProvider
else:
    from anyenv.toml_tools.tomllib_provider.provider import TomlLibProvider

    _provider = TomlLibProvider

# Backend type for TOML providers
BackendType = Literal["auto", "toml_rs", "rtoml", "pytomlpp", "tomllib"]


def get_toml_provider(backend: BackendType = "auto") -> type[TomlProviderBase]:
    """Get the specified TOML provider or the best available one.

    Args:
        backend: The TOML backend to use. If "auto", uses the best available.

    Returns:
        A TOML provider implementation

    Raises:
        ImportError: If the requested backend is not available
    """
    if backend == "auto":
        return _provider

    if backend == "toml_rs":
        if importlib.util.find_spec("toml_rs") is not None:
            from anyenv.toml_tools.toml_rs_provider.provider import TomlRsProvider

            return TomlRsProvider
        msg = "toml_rs backend requested but not installed"
        raise ImportError(msg)

    if backend == "rtoml":
        if importlib.util.find_spec("rtoml") is not None:
            from anyenv.toml_tools.rtoml_provider.provider import RtomlProvider

            return RtomlProvider
        msg = "rtoml backend requested but not installed"
        raise ImportError(msg)

    if backend == "pytomlpp":
        if importlib.util.find_spec("pytomlpp") is not None:
            from anyenv.toml_tools.pytomlpp_provider.provider import PytomlppProvider

            return PytomlppProvider
        msg = "pytomlpp backend requested but not installed"
        raise ImportError(msg)

    if backend == "tomllib":
        from anyenv.toml_tools.tomllib_provider.provider import TomlLibProvider

        return TomlLibProvider

    msg = f"Unknown backend: {backend}"
    raise ValueError(msg)


def load_toml[T = dict[str, Any]](
    data: str | bytes | TextIOWrapper | Path,
    return_type: type[T] | None = None,
    backend: BackendType = "auto",
) -> T:
    """Load TOML data with optional type validation.

    Args:
        data: The TOML data to parse (string, bytes, file-like object, or Path)
        return_type: Optional type to validate the data against
        backend: TOML backend to use for parsing

    Returns:
        The parsed and validated data

    Raises:
        TomlLoadError: If parsing fails
        TypeError: If validation against return_type fails
    """
    provider = get_toml_provider(backend)
    parsed_data = provider.load_toml(data)

    if return_type is not None:
        from anyenv.validate import validate_json_data

        return validate_json_data(parsed_data, return_type)
    return parsed_data  # type: ignore[no-any-return]


def dump_toml(data: Any, *, pretty: bool = False, backend: BackendType = "auto") -> str:
    """Serialize data to a TOML string.

    Args:
        data: The data to serialize
        pretty: Whether to format the output with pretty formatting
        backend: TOML backend to use for serialization

    Returns:
        The serialized TOML string

    Raises:
        TomlDumpError: If serialization fails
    """
    provider = get_toml_provider(backend)
    return provider.dump_toml(data, pretty=pretty)


# Export the exception classes for user code
__all__ = [
    "BackendType",
    "ParseErrorInfo",
    "TomlDumpError",
    "TomlLoadError",
    "dump_toml",
    "load_toml",
]
