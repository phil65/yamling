"""YAML handling utilities with enhanced loading and dumping capabilities."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, overload

import fsspec
import yaml
import yaml_include

from yamling import deepmerge, typedefs, utils
from yamling.constructors import variable


if TYPE_CHECKING:
    from collections.abc import Callable

    import jinja2

logger = logging.getLogger(__name__)

LOADERS: dict[str, typedefs.LoaderType] = {
    "unsafe": yaml.CUnsafeLoader,
    "full": yaml.CFullLoader,
    "safe": yaml.CSafeLoader,
}
T = TypeVar("T", bound=type)

_T_co = TypeVar("_T_co", covariant=True)

TVerify = TypeVar("TVerify", bound=object)


class SupportsRead(Protocol[_T_co]):
    def read(self, length: int = ..., /) -> _T_co: ...


YAMLInput = str | bytes | SupportsRead[str] | SupportsRead[bytes]


def get_env_constructor(loader: yaml.Loader, node: yaml.Node) -> Any:
    """Construct a YAML tag that references environment variables.

    Args:
        loader: YAML loader instance
        node: Current YAML node being processed

    Returns:
        The resolved environment variable value or default value

    Raises:
        ConstructorError: If node is neither scalar nor sequence
    """
    default = None

    match node:
        case yaml.nodes.ScalarNode():
            env_vars = [loader.construct_scalar(node)]

        case yaml.nodes.SequenceNode():
            child_nodes = node.value
            if len(child_nodes) > 1:
                default = loader.construct_object(child_nodes[-1])
                child_nodes = child_nodes[:-1]
            env_vars = [loader.construct_scalar(child) for child in child_nodes]

        case _:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"expected a scalar or sequence node, but found {node.tag}",
                node.start_mark,
            )

    for var in env_vars:
        if var in os.environ:
            value = os.environ[var]
            tag = loader.resolve(yaml.nodes.ScalarNode, value, (True, False))
            return loader.construct_object(yaml.nodes.ScalarNode(tag, value))

    return default


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


def get_safe_loader(base_loader_cls: typedefs.LoaderType) -> typedefs.LoaderType:
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
    base_loader_cls: typedefs.LoaderType,
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    enable_include: bool = True,
    enable_env: bool = True,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    variables: dict[str, Any] | None = None,
    jinja_env: jinja2.Environment | None = None,
) -> typedefs.LoaderType:
    """Construct an enhanced YAML loader with optional support for !env and !include tags.

    Args:
        base_loader_cls: Base loader class to extend
        include_base_path: Base path for !include tag resolution. If None, use cwd.
        enable_include: Whether to enable !include tag support
        enable_env: Whether to enable !ENV tag support
        resolve_strings: Whether to resolve strings using Jinja2
        resolve_dict_keys: Whether to resolve dictionary keys using Jinja2
        variables: An optional dictionary to resolving !var tags
        jinja_env: Optional Jinja2 environment for template resolution

    Returns:
        Enhanced loader class
    """
    loader_cls = utils.create_subclass(base_loader_cls)
    if variables:
        var_ctor = variable.ConfigConstructor(variables)
        loader_cls.add_constructor("!var", var_ctor.construct_variable)

    if enable_include:
        constructor = get_include_constructor(fs=include_base_path)
        yaml.add_constructor("!include", constructor, loader_cls)

    if enable_env:
        loader_cls.add_constructor("!ENV", get_env_constructor)

    if resolve_dict_keys or resolve_strings:
        j_ctor = get_jinja2_constructor(
            jinja_env,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
        )
        loader_cls.add_constructor("tag:yaml.org,2002:str", j_ctor)

    return loader_cls


def _resolve_inherit(
    data: Any,
    base_dir: str | os.PathLike[str] | None,
    mode: typedefs.LoaderStr | typedefs.LoaderType,
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None,
    resolve_strings: bool,
    resolve_dict_keys: bool,
    jinja_env: jinja2.Environment | None,
) -> Any:
    """Resolve INHERIT directive in YAML data.

    Args:
        data: The loaded YAML data
        base_dir: Directory to resolve inherited paths from
        mode: YAML loader mode or YAML loader class
        include_base_path: Base path for !include resolution
        resolve_strings: Whether to resolve Jinja2 strings
        resolve_dict_keys: Whether to resolve dictionary keys
        jinja_env: Optional Jinja2 environment

    Returns:
        Merged configuration data
    """
    if not isinstance(data, dict) or "INHERIT" not in data or base_dir is None:
        return data

    parent_path = data.pop("INHERIT")
    if not parent_path:
        return data

    import upath

    base_dir = upath.UPath(base_dir)
    # Convert string to list for uniform handling
    file_paths = [parent_path] if isinstance(parent_path, str) else parent_path
    context = deepmerge.DeepMerger()

    # Process inheritance in reverse order (last file is base configuration)
    for p_path in reversed(file_paths):
        parent_cfg = base_dir / p_path
        logger.debug(
            "Loading parent configuration file %r relative to %r", parent_cfg, base_dir
        )
        parent_data = load_yaml_file(
            parent_cfg,
            mode=mode,
            include_base_path=include_base_path,
            resolve_inherit=True,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
            jinja_env=jinja_env,
        )
        data = context.merge(data, parent_data)

    return data


@overload
def load_yaml(
    text: YAMLInput,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool = False,
    variables: dict[str, Any] | None = None,
    jinja_env: jinja2.Environment | None = None,
    verify_type: None = None,
) -> Any: ...


@overload
def load_yaml(
    text: YAMLInput,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool = False,
    variables: dict[str, Any] | None = None,
    jinja_env: jinja2.Environment | None = None,
    verify_type: type[TVerify] = ...,
) -> TVerify: ...


def load_yaml(
    text: YAMLInput,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool = False,
    variables: dict[str, Any] | None = None,
    jinja_env: jinja2.Environment | None = None,
    verify_type: type[TVerify] | None = None,
) -> Any | TVerify:
    r"""Load a YAML string with specified safety mode and include path support.

    Args:
        text: The YAML content to load
        mode: YAML loader safety mode ('unsafe', 'full', or 'safe')
              Custom YAML loader classes are also accepted.
        include_base_path: Base path for resolving !include directives
        resolve_strings: Whether to resolve Jinja2 template strings
        resolve_dict_keys: Whether to resolve Jinja2 templates in dictionary keys
        resolve_inherit: Whether to resolve INHERIT directives
                         (requires IO object with name attribute for text)
        jinja_env: Optional Jinja2 environment for template resolution
        variables: An optional dictionary to resolving !var tags
        verify_type: Type to verify and cast the output to

    Returns:
        The parsed YAML data, typed according to verify_type if provided

    Example:
        ```python
        # Simple YAML loading
        data = load_yaml("key: value")

        # With Jinja2 template resolution
        from jinja2 import Environment
        env = Environment()
        data = load_yaml(
            "message: Hello {{ name }}!",
            resolve_strings=True,
            jinja_env=env
        )

        # With type verification
        config = load_yaml("key: value", verify_type=dict)
        items = load_yaml("- item1\n- item2", verify_type=list)
        ```
    """
    try:
        if isinstance(mode, str):
            base_loader_cls: type = LOADERS[mode]
        else:
            base_loader_cls = mode
        loader = get_loader(
            base_loader_cls,
            include_base_path=include_base_path,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
            variables=variables,
            jinja_env=jinja_env,
        )
        data = yaml.load(text, Loader=loader)

        if resolve_inherit and hasattr(text, "name"):
            import upath

            base_dir = upath.UPath(text.name).parent
            data = _resolve_inherit(
                data,
                base_dir,
                mode=mode,
                include_base_path=include_base_path,
                resolve_strings=resolve_strings,
                resolve_dict_keys=resolve_dict_keys,
                jinja_env=jinja_env,
            )
    except yaml.YAMLError:
        logger.exception("Failed to load YAML: \n%s", text)
        raise
    except Exception:
        logger.exception("Unexpected error while loading YAML:\n%s", text)
        raise
    else:
        if verify_type is not None:
            if not isinstance(data, verify_type):
                msg = (
                    f"Data is of type {type(data).__name__}, "
                    f"expected {verify_type.__name__}"
                )
                raise TypeError(msg)
            return data  # type: ignore[no-any-return]
        return data


@overload
def load_yaml_file(
    path: str | os.PathLike[str],
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: None = None,
) -> Any: ...


@overload
def load_yaml_file(
    path: str | os.PathLike[str],
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[TVerify] = ...,
) -> TVerify: ...


def load_yaml_file(
    path: str | os.PathLike[str],
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    include_base_path: str | os.PathLike[str] | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[TVerify] | None = None,
) -> Any | TVerify:
    """Load a YAML file with specified options.

    Use verify_type to get proper output type for LSPs and a simple validation.

    Args:
        path: Path to the YAML file to load
        mode: YAML loader safety mode ('unsafe', 'full', or 'safe').
              Custom YAML loader classes are also accepted.
        include_base_path: Base path for resolving !include directives
        resolve_inherit: Whether to resolve INHERIT directives
        resolve_strings: Whether to resolve Jinja2 template strings
        resolve_dict_keys: Whether to resolve Jinja2 templates in dictionary keys
        jinja_env: Optional Jinja2 environment for template resolution
        variables: An optional dictionary to resolving !var tags
        storage_options: Additional keywords to pass to fsspec backend
        verify_type: Checks for the correct output type (eg. dict)

    Returns:
        The parsed YAML data

    Example:
        ```python
        # Load YAML file with inheritance
        data = load_yaml_file(
            "config.yml",
            resolve_inherit=True,  # Resolve INHERIT directives
            include_base_path="configs/"  # Base path for includes
        )

        # Load YAML file with type verification
        data = load_yaml_file(
            "config.yml",
            verify_type=dict  # Will return dict type
        )
        ```
    """
    try:
        import upath

        path_obj = upath.UPath(path, **storage_options or {}).resolve()
        text = path_obj.read_text("utf-8")

        data = load_yaml(
            text,
            mode=mode,
            include_base_path=include_base_path,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
            resolve_inherit=False,  # We'll handle inheritance separately
            jinja_env=jinja_env,
        )

        if resolve_inherit:
            data = _resolve_inherit(
                data,
                path_obj.parent,  # Pass the parent directory directly
                mode=mode,
                include_base_path=include_base_path,
                resolve_strings=resolve_strings,
                resolve_dict_keys=resolve_dict_keys,
                jinja_env=jinja_env,
            )
    except (OSError, yaml.YAMLError):
        logger.exception("Failed to load YAML file %r", path)
        raise
    except Exception:
        logger.exception("Unexpected error while loading YAML file %r", path)
        raise
    else:
        if verify_type is not None:
            if not isinstance(data, verify_type):
                msg = f"Expected {verify_type.__name__}, got {type(data).__name__}"
                raise TypeError(msg)
            return data  # type: ignore[no-any-return]
        return data


if __name__ == "__main__":
    obj = load_yaml("- test")
    print(obj)
