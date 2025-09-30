from __future__ import annotations

import dataclasses
import importlib.util
from io import StringIO
import logging
from typing import Any, get_args

from yamling import consts, exceptions, typedefs


logger = logging.getLogger(__name__)


def dump(data: Any, mode: typedefs.SupportedFormats, **kwargs: Any) -> str:
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
                raise exceptions.DumpingError(msg, e) from e

        case "toml":
            import tomli_w

            try:
                assert isinstance(data, dict)
                return tomli_w.dumps(data, **kwargs)
            except Exception as e:
                logger.exception("Failed to dump TOML data")
                msg = f"Failed to dump data to TOML: {e}"
                raise exceptions.DumpingError(msg, e) from e

        case "json":
            import anyenv

            try:
                return anyenv.dump_json(data, indent=True, **kwargs)
            except anyenv.JsonDumpError as e:
                logger.exception("Failed to dump JSON data with json")
                msg = f"Failed to dump data to JSON: {e}"
                raise exceptions.DumpingError(msg, e) from e

        case "ini":
            import configparser

            def validate_ini_structure(data: Any) -> None:
                if not isinstance(data, dict):
                    msg = "INI format requires dict of dicts structure"
                    raise exceptions.DumpingError(msg)
                for values in data.values():
                    if not isinstance(values, dict):
                        msg = "INI format requires dict of dicts structure"
                        raise exceptions.DumpingError(msg)

            try:
                assert isinstance(data, dict)
                validate_ini_structure(data)
                parser = configparser.ConfigParser(**kwargs)
                for section, values in data.items():
                    parser[str(section)] = {str(k): str(v) for k, v in values.items()}
                output = StringIO()
                parser.write(output)
                return output.getvalue()
            except exceptions.DumpingError:
                raise
            except Exception as e:
                logger.exception("Failed to dump INI data")
                msg = f"Failed to dump data to INI: {e}"
                raise exceptions.DumpingError(msg, e) from e

        case _:
            msg = f"Unsupported format: {mode}"
            raise ValueError(msg)


def dump_file(
    data: Any,
    path: typedefs.StrPath,
    mode: typedefs.FormatType = "auto",
    overwrite: bool = False,
    create_dirs: bool = False,
    **kwargs: Any,
) -> None:
    """Dump data to a file, automatically detecting the format from extension if needed.

    Args:
        data: Data structure to dump
        path: Path to the file to write
        mode: Format to write the file in ("yaml", "toml", "json", "ini" or "auto")
        overwrite: Whether to overwrite the file if it already exists
        create_dirs: Whether to create parent directories if they don't exist
        **kwargs: Additional keyword arguments passed to the underlying dump functions

    Raises:
        ValueError: If the format cannot be determined or is not supported
        DumpingError: If the data cannot be dumped or the file cannot be written
    """
    from upathtools import to_upath

    path_obj = to_upath(path)

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
        text = dump(data, mode, **kwargs)
        file_path = to_upath(path)
        if file_path.exists() and not overwrite:
            msg = f"File already exists: {path}"
            raise FileExistsError(msg)  # noqa: TRY301
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        elif not file_path.parent.exists():
            msg = f"Directory does not exist: {file_path.parent}"
            raise exceptions.DumpingError(msg)  # noqa: TRY301
        file_path.write_text(text)

    except (OSError, PermissionError) as e:
        logger.exception("Failed to write file %r", path)
        msg = f"Failed to write file {path}: {e!s}"
        raise exceptions.DumpingError(msg, e) from e
    except Exception as e:
        logger.exception("Failed to dump data to %r as %s", path, mode)
        msg = f"Failed to dump data to {path} as {mode} format: {e!s}"
        raise exceptions.DumpingError(msg, e) from e
