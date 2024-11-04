"""YAML handling utilities with enhanced loading and dumping capabilities."""

from __future__ import annotations

import os
from typing import Any, TypeVar

import fsspec
import yaml
import yaml_env_tag
import yaml_include

from yamling import utils, yamltypes


LOADERS: dict[str, yamltypes.LoaderType] = {
    "unsafe": yaml.CUnsafeLoader,
    "full": yaml.CFullLoader,
    "safe": yaml.CSafeLoader,
}
T = TypeVar("T", bound=type)


# def resolve_inherit_tag(self, path, mode: yamltypes.LoaderStr = "unsafe"):
#     """Resolve INHERIT key-value pair for this YAML file.

#     If this YAML file contains a key-value pair like "INHERIT: path_to_config.yml",
#     this method will resolve that tag by using the config at given path as the
#     "parent config".

#     Also supports a list of files for INHERIT.

#     Args:
#         mode: The Yaml loader type
#     """
#     abspath = upath.UPath(path).resolve()
#     if "INHERIT" not in self._data:
#         return None
#     file_path = self._data.pop("INHERIT")
#     file_paths = [file_path] if isinstance(file_path, str) else file_path
#     for path in file_paths:
#         parent_cfg = abspath.parent / path
#         logger.debug("Loading inherited configuration file: %s", parent_cfg)
#         text = parent_cfg.read_text("utf-8")
#         parent = load_yaml(text, mode)
#         return serializefilters.merge(parent, self._data)


def get_include_constructor(
    fs: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    **kwargs: Any,
) -> yaml_include.Constructor:
    """Create a YAML include constructor with fsspec filesystem support.

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


if __name__ == "__main__":
    obj = load_yaml("- test")
    print(obj)
