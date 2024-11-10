from __future__ import annotations

import dataclasses
import importlib.util
from io import StringIO
import logging
from typing import TYPE_CHECKING, Any, Literal, get_args


if TYPE_CHECKING:
    import os

logger = logging.getLogger(__name__)

SupportedFormats = Literal["yaml", "toml", "json", "ini"]
FormatType = SupportedFormats | Literal["auto"]

# Check if orjson is available
has_orjson = importlib.util.find_spec("orjson") is not None


class DumpingError(Exception):
    """Common exception for all dumping errors in yamling."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


def dump(data: Any, mode: SupportedFormats, **kwargs: Any) -> str:
    """Dump data to a string in the specified format.

    Args:
        data: Data structure to dump (also accepts pydantic v2 models and dataclasses)
        mode: Format to dump the data in ("yaml", "toml", "json", or "ini")
        **kwargs: Additional keyword arguments passed to the underlying dump functions

    Returns:
        str: String containing the formatted data

    Raises:
        ValueError: If the format is not supported
        DumpingError: If the data cannot be dumped in the specified format
    """
    # Handle pydantic models
    if importlib.util.find_spec("pydantic"):
        import pydantic

        if isinstance(data, pydantic.BaseModel):
            data = data.model_dump()

    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        data = dataclasses.asdict(data)

    match mode:
        case "yaml":
            from yaml import YAMLError

            from yamling import dump_yaml

            try:
                return dump_yaml(data, **kwargs)
            except YAMLError as e:
                logger.exception("Failed to dump YAML data")
                msg = f"Failed to dump data to YAML: {e}"
                raise DumpingError(msg, e) from e

        case "toml":
            import tomli_w

            try:
                return tomli_w.dumps(data, **kwargs)
            except Exception as e:
                logger.exception("Failed to dump TOML data")
                msg = f"Failed to dump data to TOML: {e}"
                raise DumpingError(msg, e) from e

        case "json":
            if has_orjson:
                import orjson

                try:
                    valid_kwargs = {
                        k: v
                        for k, v in kwargs.items()
                        if k in {"default", "option", "indent"}
                    }
                    return orjson.dumps(
                        data, option=orjson.OPT_INDENT_2, **valid_kwargs
                    ).decode("utf-8")
                except Exception as e:
                    logger.exception("Failed to dump JSON data with orjson")
                    msg = f"Failed to dump data to JSON: {e}"
                    raise DumpingError(msg, e) from e
            else:
                import json

                try:
                    return json.dumps(data, indent=2, **kwargs)
                except Exception as e:
                    logger.exception("Failed to dump JSON data with json")
                    msg = f"Failed to dump data to JSON: {e}"
                    raise DumpingError(msg, e) from e

        case "ini":
            import configparser

            def validate_ini_structure(data: Any) -> None:
                if not isinstance(data, dict):
                    msg = "INI format requires dict of dicts structure"
                    raise DumpingError(msg)
                for values in data.values():
                    if not isinstance(values, dict):
                        msg = "INI format requires dict of dicts structure"
                        raise DumpingError(msg)

            try:
                validate_ini_structure(data)
                parser = configparser.ConfigParser(**kwargs)
                for section, values in data.items():
                    parser[str(section)] = {str(k): str(v) for k, v in values.items()}
                output = StringIO()
                parser.write(output)
                return output.getvalue()
            except DumpingError:
                raise
            except Exception as e:
                logger.exception("Failed to dump INI data")
                msg = f"Failed to dump data to INI: {e}"
                raise DumpingError(msg, e) from e

        case _:
            msg = f"Unsupported format: {mode}"
            raise ValueError(msg)


def dump_file(
    data: Any,
    path: str | os.PathLike[str],
    mode: FormatType = "auto",
    **kwargs: Any,
) -> None:
    """Dump data to a file, automatically detecting the format from extension if needed.

    Args:
        data: Data structure to dump
        path: Path to the file to write
        mode: Format to write the file in ("yaml", "toml", "json", "ini" or "auto")
        **kwargs: Additional keyword arguments passed to the underlying dump functions

    Raises:
        ValueError: If the format cannot be determined or is not supported
        DumpingError: If the data cannot be dumped or the file cannot be written
    """
    import upath

    path_obj = upath.UPath(path)

    # Determine format from extension if auto mode
    if mode == "auto":
        ext = path_obj.suffix.lower()
        format_mapping: dict[str, SupportedFormats] = {
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".tml": "toml",
            ".json": "json",
            ".jsonc": "json",
            ".ini": "ini",
            ".cfg": "ini",
            ".conf": "ini",
            ".config": "ini",
            ".properties": "ini",
            ".cnf": "ini",
            ".env": "ini",
        }
        detected_mode = format_mapping.get(ext)
        if detected_mode is None:
            msg = f"Could not determine format from file extension: {path}"
            raise ValueError(msg)
        mode = detected_mode

    # At this point, mode can't be "auto"
    if mode not in get_args(SupportedFormats):
        msg = f"Unsupported format: {mode}"
        raise ValueError(msg)

    try:
        text = dump(data, mode, **kwargs)
        path_obj.write_text(text)
    except (OSError, PermissionError) as e:
        logger.exception("Failed to write file %r", path)
        msg = f"Failed to write file {path}: {e!s}"
        raise DumpingError(msg, e) from e
    except Exception as e:
        logger.exception("Failed to dump data to %r as %s", path, mode)
        msg = f"Failed to dump data to {path} as {mode} format: {e!s}"
        raise DumpingError(msg, e) from e
