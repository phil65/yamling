from __future__ import annotations

import configparser
import logging
import os
from typing import TYPE_CHECKING, Any, get_args, overload

import upath
from upathtools import to_upath

from yamling import consts, deepmerge, exceptions, typedefs, verify


if TYPE_CHECKING:
    from upath.types import JoinablePathLike

logger = logging.getLogger(__name__)


def _resolve_inherit(
    data: Any,
    base_dir: JoinablePathLike | None,
    mode: typedefs.SupportedFormats,
) -> Any:
    """Resolve INHERIT directive in YAML data.

    Args:
        data: The loaded YAML data
        base_dir: Directory to resolve inherited paths from
        mode: YAML loader mode or YAML loader class
        include_base_path: Base path for !include resolution
        jinja_env: Optional Jinja2 environment

    Returns:
        Merged configuration data
    """
    if not isinstance(data, dict) or "INHERIT" not in data or base_dir is None:
        return data

    parent_path = data.pop("INHERIT")
    if not parent_path:
        return data

    base_dir = to_upath(base_dir)
    # Convert string to list for uniform handling
    file_paths = [parent_path] if isinstance(parent_path, str) else parent_path
    context = deepmerge.DeepMerger()
    # Process inheritance in reverse order (last file is base configuration)
    for p_path in reversed(file_paths):
        parent_cfg = base_dir / p_path
        logger.debug("Loading parent configuration file %r relative to %r", parent_cfg, base_dir)
        parent_data = load_file(parent_cfg, mode=mode, resolve_inherit=True)
        data = context.merge(data, parent_data)

    return data


@overload
def load(
    text: str,
    mode: typedefs.SupportedFormats,
    verify_type: None = None,
    resolve_inherit: bool | JoinablePathLike = False,
    **kwargs: Any,
) -> Any: ...


@overload
def load[T](
    text: str,
    mode: typedefs.SupportedFormats,
    verify_type: type[T],
    resolve_inherit: bool | JoinablePathLike = False,
    **kwargs: Any,
) -> T: ...


def load[T](
    text: str,
    mode: typedefs.SupportedFormats,
    verify_type: type[T] | None = None,
    resolve_inherit: bool | JoinablePathLike = False,
    **kwargs: Any,
) -> Any | T:
    """Load data from a string in the specified format.

    Args:
        text: String containing data in the specified format
        mode: Format of the input data ("yaml", "toml", "json", or "ini")
        verify_type: Type to verify and cast the output to (supports TypedDict)
        resolve_inherit: Whether to resolve inheritance in the loaded data
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
            import anyenv

            try:
                data = anyenv.load_json(text, **kwargs)
            except anyenv.JsonLoadError as e:
                logger.exception("Failed to load JSON data with json")
                msg = f"Failed to parse JSON data: {e}"
                raise exceptions.ParsingError(msg, e) from e

        case "ini":
            try:
                parser = configparser.ConfigParser(**kwargs)
                parser.read_string(text)
                data = {section: dict(parser.items(section)) for section in parser.sections()}
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

    if resolve_inherit:
        if hasattr(text, "name"):
            base_dir = upath.UPath(text.name).parent  # pyright: ignore[reportAttributeAccessIssue]
        elif resolve_inherit is not None and not isinstance(resolve_inherit, bool):
            base_dir = to_upath(resolve_inherit)
        else:
            base_dir = None
        if base_dir:
            data = _resolve_inherit(data, base_dir, mode=mode)

    if verify_type is not None:
        try:
            return verify.verify_type(data, verify_type)
        except TypeError as e:
            msg = f"Data loaded from {mode} format doesn't match expected type: {e}"
            raise TypeError(msg) from e
    return data


@overload
def load_file(
    path: JoinablePathLike,
    mode: typedefs.FormatType = "auto",
    *,
    storage_options: dict[str, Any] | None = None,
    verify_type: None = None,
    resolve_inherit: bool = True,
) -> Any: ...


@overload
def load_file[T](
    path: JoinablePathLike,
    mode: typedefs.FormatType = "auto",
    *,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T],
    resolve_inherit: bool = True,
) -> T: ...


def load_file[T](
    path: JoinablePathLike,
    mode: typedefs.FormatType = "auto",
    *,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T] | None = None,
    resolve_inherit: bool = True,
) -> Any | T:
    """Load data from a file, automatically detecting the format from extension if needed.

    Args:
        path: Path to the file to load
        mode: Format of the file ("yaml", "toml", "json", "ini" or "auto")
        storage_options: Additional keyword arguments to pass to the fsspec backend
        verify_type: Type to verify and cast the output to (supports TypedDict)
        resolve_inherit: Whether to resolve inheritance in the loaded data

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
    import upath

    p = os.fspath(path) if isinstance(path, os.PathLike) else path

    path_obj = upath.UPath(p, **storage_options or {})

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
