"""YAML handling utilities with enhanced loading and dumping capabilities."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, TypeVar

import fsspec
import yaml
import yaml_env_tag
import yaml_include

from yamling import deepmerge, utils, yamltypes


if TYPE_CHECKING:
    from collections.abc import Callable

    import jinja2

logger = logging.getLogger(__name__)

LOADERS: dict[str, yamltypes.LoaderType] = {
    "unsafe": yaml.CUnsafeLoader,
    "full": yaml.CFullLoader,
    "safe": yaml.CSafeLoader,
}
T = TypeVar("T", bound=type)


def get_jinja2_constructor(
    env: jinja2.Environment | None,
    resolve_strings: bool = True,
    resolve_dict_keys: bool = False,
) -> Callable[[yaml.Loader, yaml.Node], Any]:
    """Create a constructor that resolves strings using a Jinja2 environment.

    Args:
        env: Jinja2 environment to use for template resolution
        resolve_strings: Whether to resolve string values
        resolve_dict_keys: Whether to resolve dictionary keys

    Returns:
        Constructor function for YAML loader
    """
    import jinja2

    def construct_jinja2_str(loader: yaml.Loader, node: yaml.Node) -> Any:  # noqa: PLR0911
        try:
            if env is None or not resolve_strings:
                return loader.construct_scalar(node)

            match node:
                case yaml.ScalarNode():
                    value = loader.construct_scalar(node)
                    if isinstance(value, str):
                        return env.from_string(value).render()  # Remove inner try-except
                    return value

                case yaml.MappingNode():
                    value = loader.construct_mapping(node)
                    if resolve_dict_keys:
                        return {
                            (
                                env.from_string(str(k)).render()
                                if isinstance(k, str)
                                else k
                            ): v
                            for k, v in value.items()
                        }
                    return value

                case yaml.SequenceNode():
                    return loader.construct_sequence(node)

                case _:
                    return loader.construct_scalar(node)

        except jinja2.TemplateError:  # Handle Jinja2 errors separately
            raise  # Re-raise Jinja2 errors
        except Exception:  # Handle other exceptions
            logger.exception("Error in Jinja2 constructor")
            return loader.construct_scalar(node)

    return construct_jinja2_str


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
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
) -> yamltypes.LoaderType:
    """Construct an enhanced YAML loader with optional support for !env and !include tags.

    Args:
        base_loader_cls: Base loader class to extend
        include_base_path: Base path for !include tag resolution. If None, use cwd.
        enable_include: Whether to enable !include tag support
        enable_env: Whether to enable !ENV tag support
        resolve_strings: Whether to resolve strings using Jinja2
        resolve_dict_keys: Whether to resolve dictionary keys using Jinja2
        jinja_env: Optional Jinja2 environment for template resolution

    Returns:
        Enhanced loader class
    """
    loader_cls = utils.create_subclass(base_loader_cls)

    if enable_include:
        constructor = get_include_constructor(fs=include_base_path)
        yaml.add_constructor("!include", constructor, loader_cls)

    if enable_env:
        loader_cls.add_constructor("!ENV", yaml_env_tag.construct_env_tag)

    if resolve_dict_keys or resolve_strings:
        constructor = get_jinja2_constructor(
            jinja_env,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
        )
        loader_cls.add_constructor("tag:yaml.org,2002:str", constructor)

    return loader_cls


def load_yaml(
    text: str,
    mode: yamltypes.LoaderStr = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
) -> Any:
    """Load a YAML string with specified safety mode and include path support."""
    try:
        base_loader_cls: type = LOADERS[mode]
        loader = get_loader(
            base_loader_cls,
            include_base_path=include_base_path,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
            jinja_env=jinja_env,
        )
        return yaml.load(text, Loader=loader)
    except yaml.YAMLError:
        logger.exception("Failed to load YAML: \n%s", text)
        raise
    except Exception:
        logger.exception("Unexpected error while loading YAML:\n%s", text)
        raise


def load_yaml_file(
    path: str | os.PathLike[str],
    mode: yamltypes.LoaderStr = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
) -> Any:
    """Load a YAML file with specified options."""
    try:
        import upath

        path_obj = upath.UPath(path).resolve()
        text = path_obj.read_text("utf-8")

        data = load_yaml(
            text,
            mode=mode,
            include_base_path=include_base_path,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
            jinja_env=jinja_env,
        )

        if not resolve_inherit or not isinstance(data, dict) or "INHERIT" not in data:
            return data

        parent_path = data.pop("INHERIT")
        if not parent_path:
            return data

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
                resolve_strings=resolve_strings,
                resolve_dict_keys=resolve_dict_keys,
                jinja_env=jinja_env,
            )
            data = context.merge(data, parent_data)
    except (OSError, yaml.YAMLError):
        logger.exception("Failed to load YAML file %r", path)
        raise
    except Exception:
        logger.exception("Unexpected error while loading YAML file %r", path)
        raise
    else:
        return data


if __name__ == "__main__":
    obj = load_yaml("- test")
    print(obj)
