from __future__ import annotations

import configparser
import json
import logging
from typing import TYPE_CHECKING, Any, get_args

import upath

from yamling import consts, exceptions, typedefs


if TYPE_CHECKING:
    import os


logger = logging.getLogger(__name__)


def load(text: str, mode: typedefs.SupportedFormats, **kwargs: Any) -> Any:
    """Load data from a string in the specified format.

    Args:
        text: String containing data in the specified format
        mode: Format of the input data ("yaml", "toml", "json", or "ini")
        **kwargs: Additional keyword arguments passed to the underlying load functions

    Returns:
        Parsed data structure

    Raises:
        ValueError: If the format is not supported
        ParsingError: If the text cannot be parsed in the specified format
    """
    match mode:
        case "yaml":
            from yaml import YAMLError

            from yamling.yaml_loaders import load_yaml

            try:
                return load_yaml(text, **kwargs)
            except YAMLError as e:
                logger.exception("Failed to load YAML data")
                msg = f"Failed to parse YAML data: {e}"
                raise exceptions.ParsingError(msg, e) from e

        case "toml":
            import tomllib

            try:
                return tomllib.loads(text, **kwargs)
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
                    return orjson.loads(text, **valid_kwargs)
                except orjson.JSONDecodeError as e:
                    logger.exception("Failed to load JSON data with orjson")
                    msg = f"Failed to parse JSON data: {e}"
                    raise exceptions.ParsingError(msg, e) from e
            else:
                try:
                    return json.loads(text, **kwargs)
                except json.JSONDecodeError as e:
                    logger.exception("Failed to load JSON data with json")
                    msg = f"Failed to parse JSON data: {e}"
                    raise exceptions.ParsingError(msg, e) from e

        case "ini":
            try:
                parser = configparser.ConfigParser(**kwargs)
                parser.read_string(text)
                return {
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


def load_file(
    path: str | os.PathLike[str],
    mode: typedefs.FormatType = "auto",
    storage_options: dict[str, Any] | None = None,
) -> Any:
    """Load data from a file, automatically detecting the format from extension if needed.

    Args:
        path: Path to the file to load
        mode: Format of the file ("yaml", "toml", "json", "ini" or "auto")
        storage_options: Additional keyword arguments to pass to the fsspec backend

    Returns:
        Parsed data structure

    Raises:
        ValueError: If the format cannot be determined or is not supported
        OSError: If the file cannot be read
        FileNotFoundError: If the file does not exist
        PermissionError: If file permissions prevent reading
        ParsingError: If the text cannot be parsed in the specified format
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
        return load(text, mode)
    except (OSError, FileNotFoundError, PermissionError) as e:
        logger.exception("Failed to read file %r", path)
        msg = f"Failed to read file {path}: {e!s}"
        raise
    except Exception as e:
        logger.exception("Failed to parse file %r as %s", path, mode)
        msg = f"Failed to parse {path} as {mode} format: {e!s}"
        raise
