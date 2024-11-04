"""YAML handling utilities with enhanced loading and dumping capabilities."""

from __future__ import annotations

import logging
import os
from typing import Any, TypeVar

import fsspec
import yaml
import yaml_env_tag
import yaml_include

from yamling import utils, yamltypes


logger = logging.getLogger(__name__)

LOADERS: dict[str, yamltypes.LoaderType] = {
    "unsafe": yaml.CUnsafeLoader,
    "full": yaml.CFullLoader,
    "safe": yaml.CSafeLoader,
}
T = TypeVar("T", bound=type)


def get_include_constructor(
    fs: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    **kwargs: Any,
) -> yaml_include.Constructor:
    """Create a YAML include (!include) constructor with fsspec filesystem support.

    Args:
        fs: Filesystem specification (path or fsspec filesystem object)
        kwargs: Additional arguments for the Constructor

    Returns:
        Configured YAML include constructor
    """
    match fs:
        case str() | os.PathLike():
            filesystem, _ = fsspec.url_to_fs(str(fs))
        case None:
            filesystem = fsspec.filesystem("file")
        case fsspec.AbstractFileSystem():
            filesystem = fs
        case _:
            msg = f"Unsupported filesystem type: {type(fs)}"
            raise TypeError(msg)

    return yaml_include.Constructor(fs=filesystem, **kwargs)


def get_safe_loader(base_loader_cls: yamltypes.LoaderType) -> yamltypes.LoaderType:
    """Create a SafeLoader with dummy constructors for common tags.

    Args:
        base_loader_cls: Base loader class to extend

    Returns:
        Enhanced safe loader class
    """
    loader_cls = utils.create_subclass(base_loader_cls)

    # Add dummy constructors for simple tags
    for tag in ("!include", "!relative"):
        loader_cls.add_constructor(tag, lambda loader, node: None)

    # Add dummy constructors for complex tags
    python_tags = (
        "tag:yaml.org,2002:python/name:",
        "tag:yaml.org,2002:python/object/apply:",
    )
    for tag in python_tags:
        loader_cls.add_multi_constructor(tag, lambda loader, suffix, node: None)
    # https://github.com/smart-home-network-security/pyyaml-loaders/
    # loader_cls.add_multi_constructor("!", lambda loader, suffix, node: None)
    return loader_cls


def get_loader(
    base_loader_cls: yamltypes.LoaderType,
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    enable_include: bool = True,
    enable_env: bool = True,
) -> yamltypes.LoaderType:
    """Construct an enhanced YAML loader with optional support for !env and !include tags.

    Args:
        base_loader_cls: Base loader class to extend
        include_base_path: Base path for !include tag resolution. If None, use cwd.
        enable_include: Whether to enable !include tag support. Defaults to True
        enable_env: Whether to enable !ENV tag support. Defaults to True

    Returns:
        Enhanced loader class
    """
    loader_cls = utils.create_subclass(base_loader_cls)

    if enable_include:
        constructor = get_include_constructor(fs=include_base_path)
        yaml.add_constructor("!include", constructor, loader_cls)

    if enable_env:
        loader_cls.add_constructor("!ENV", yaml_env_tag.construct_env_tag)

    return loader_cls


def load_yaml(
    text: str,
    mode: yamltypes.LoaderStr = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
) -> Any:
    """Load a YAML string with specified safety mode and include path support.

    Args:
        text: YAML content to parse
        mode: Loading mode determining safety level
        include_base_path: Base path for resolving !include tags

    Returns:
        Parsed YAML content
    """
    base_loader_cls: type = LOADERS[mode]
    loader = get_loader(base_loader_cls, include_base_path=include_base_path)
    return yaml.load(text, Loader=loader)


def load_yaml_file(
    path: str | os.PathLike[str],
    mode: yamltypes.LoaderStr = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
) -> Any:
    """Load a YAML string with specified safety mode and !include path support.

    Args:
        path: Path to YAML file (supports upath paths (github://... etc.))
        mode: Loading mode determining safety level
        include_base_path: Base path for resolving !include tags
        resolve_inherit: Whether to resolve !INHERIT tags.

    Returns:
        Parsed YAML content
    """
    import upath

    from yamling import deepmerge

    path_obj = upath.UPath(path).resolve()
    text = path_obj.read_text("utf-8")
    data = load_yaml(text, mode, include_base_path=include_base_path)
    if not resolve_inherit or "INHERIT" not in data:
        return data
    parent_path = data.pop("INHERIT")
    file_paths = [parent_path] if isinstance(parent_path, str) else parent_path
    context = deepmerge.DeepMerger()
    for p_path in reversed(file_paths):
        parent_cfg = path_obj.parent / p_path
        logger.debug("Loading parent configuration file %r for %r", parent_cfg, path)
        parent_data = load_yaml_file(
            parent_cfg,
            mode=mode,
            include_base_path=include_base_path,
            resolve_inherit=resolve_inherit,
        )
        data = context.merge(data, parent_data)
    return data


if __name__ == "__main__":
    obj = load_yaml("- test")
    print(obj)
