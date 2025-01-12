from __future__ import annotations

import configparser
import json
import logging
from typing import TYPE_CHECKING, Any, TypeVar, get_args, overload

import upath

from yamling import consts, exceptions, typedefs, verify


if TYPE_CHECKING:
    import os

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Generic for any type
TVerify = TypeVar("TVerify")  # Specific for verification types


@overload
def load(
    text: str, mode: typedefs.SupportedFormats, verify_type: None = None, **kwargs: Any
) -> Any: ...


@overload
def load(
    text: str, mode: typedefs.SupportedFormats, verify_type: type[T], **kwargs: Any
) -> T: ...


def load(
    text: str,
    mode: typedefs.SupportedFormats,
    verify_type: type[T] | None = None,
    **kwargs: Any,
) -> Any | T:
    """Load data from a string in the specified format.

    Args:
        text: String containing data in the specified format
        mode: Format of the input data ("yaml", "toml", "json", or "ini")
        verify_type: Type to verify and cast the output to (supports TypedDict)
        **kwargs: Additional keyword arguments passed to the underlying load functions

    Returns:
        Parsed data structure, typed according to verify_type if provided

    Raises:
        ValueError: If the format is not supported
        ParsingError: If the text cannot be parsed in the specified format
        TypeError: If verify_type is provided and the loaded data doesn't match

    Example:
        ```python
        from typing import TypedDict

        class Config(TypedDict):
            name: str
            port: int

        # Without type verification
        data = load("key: value", mode="yaml")

        # With TypedDict verification
        config = load('{"name": "test", "port": 8080}', mode="json", verify_type=Config)
        ```
    """
    match mode:
        case "yaml":
            from yaml import YAMLError

            from yamling.yaml_loaders import load_yaml

            try:
                data = load_yaml(text, **kwargs)
            except YAMLError as e:
                logger.exception("Failed to load YAML data")
                msg = f"Failed to parse YAML data: {e}"
                raise exceptions.ParsingError(msg, e) from e

        case "toml":
            import tomllib

            try:
                data = tomllib.loads(text, **kwargs)
            except tomllib.TOMLDecodeError as e:
                logger.exception("Failed to load TOML data")
                msg = f"Failed to parse TOML data: {e}"
                raise exceptions.ParsingError(msg, e) from e

        case "json":
            if consts.has_orjson:
                import orjson

                try:
                    valid_kwargs = {
                        k: v for k, v in kwargs.items() if k in {"default", "option"}
                    }
                    data = orjson.loads(text, **valid_kwargs)
                except orjson.JSONDecodeError as e:
                    logger.exception("Failed to load JSON data with orjson")
                    msg = f"Failed to parse JSON data: {e}"
                    raise exceptions.ParsingError(msg, e) from e
            else:
                try:
                    data = json.loads(text, **kwargs)
                except json.JSONDecodeError as e:
                    logger.exception("Failed to load JSON data with json")
                    msg = f"Failed to parse JSON data: {e}"
                    raise exceptions.ParsingError(msg, e) from e

        case "ini":
            try:
                parser = configparser.ConfigParser(**kwargs)
                parser.read_string(text)
                data = {
                    section: dict(parser.items(section)) for section in parser.sections()
                }
            except (
                configparser.Error,
                configparser.ParsingError,
                configparser.MissingSectionHeaderError,
            ) as e:
                logger.exception("Failed to load INI data")
                msg = f"Failed to parse INI data: {e}"
                raise exceptions.ParsingError(msg, e) from e

        case _:
            msg = f"Unsupported format: {mode}"
            raise ValueError(msg)

    if verify_type is not None:
        try:
            return verify.verify_type(data, verify_type)
        except TypeError as e:
            msg = f"Data loaded from {mode} format doesn't match expected type: {e}"
            raise TypeError(msg) from e
    return data


@overload
def load_file(
    path: str | os.PathLike[str],
    mode: typedefs.FormatType = "auto",
    storage_options: dict[str, Any] | None = None,
    verify_type: None = None,
) -> Any: ...


@overload
def load_file(
    path: str | os.PathLike[str],
    mode: typedefs.FormatType = "auto",
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T] = ...,
) -> T: ...


def load_file(
    path: str | os.PathLike[str],
    mode: typedefs.FormatType = "auto",
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T] | None = None,
) -> Any | T:
    """Load data from a file, automatically detecting the format from extension if needed.

    Args:
        path: Path to the file to load
        mode: Format of the file ("yaml", "toml", "json", "ini" or "auto")
        storage_options: Additional keyword arguments to pass to the fsspec backend
        verify_type: Type to verify and cast the output to (supports TypedDict)

    Returns:
        Parsed data structure, typed according to verify_type if provided

    Raises:
        ValueError: If the format cannot be determined or is not supported
        OSError: If the file cannot be read
        FileNotFoundError: If the file does not exist
        PermissionError: If file permissions prevent reading
        ParsingError: If the text cannot be parsed in the specified format
        TypeError: If verify_type is provided and the loaded data doesn't match

    Example:
        ```python
        from typing import TypedDict

        class ServerConfig(TypedDict):
            host: str
            port: int
            debug: bool

        # Auto-detect format and return as Any
        data = load_file("config.yml")

        # Specify format and verify as TypedDict
        config = load_file(
            "config.json",
            mode="json",
            verify_type=ServerConfig
        )
        ```
    """
    path_obj = upath.UPath(path, **storage_options or {})

    # Determine format from extension if auto mode
    if mode == "auto":
        ext = path_obj.suffix.lower()
        detected_mode = consts.FORMAT_MAPPING.get(ext)
        if detected_mode is None:
            msg = f"Could not determine format from file extension: {path}"
            raise ValueError(msg)
        mode = detected_mode

    # At this point, mode can't be "auto"
    if mode not in get_args(typedefs.SupportedFormats):
        msg = f"Unsupported format: {mode}"
        raise ValueError(msg)

    try:
        text = path_obj.read_text(encoding="utf-8")
        return load(text, mode, verify_type=verify_type)
    except (OSError, FileNotFoundError, PermissionError) as e:
        logger.exception("Failed to read file %r", path)
        msg = f"Failed to read file {path}: {e!s}"
        raise
    except Exception as e:
        logger.exception("Failed to load file %r as %s", path, mode)
        msg = f"Failed to load {path} as {mode} format: {e!s}"
        raise


if __name__ == "__main__":
    from typing import TypedDict

    class Config(TypedDict):
        host: str
        port: int
        debug: bool

    json_str = '{"host": "localhost", "port": 8080, "debug": true}'
    config = load(json_str, mode="json", verify_type=Config)
