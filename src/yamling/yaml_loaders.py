"""YAML handling utilities with enhanced loading and dumping capabilities."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, overload

import yaml

from yamling import deepmerge, utils, verify
from yamling.constructors import variable


if TYPE_CHECKING:
    from collections.abc import Callable

    import fsspec
    import jinja2
    from upath.types import JoinablePathLike
    import yaml_include

    from yamling import typedefs

logger = logging.getLogger(__name__)

try:
    LOADERS: dict[str, typedefs.LoaderType] = {  # pyright: ignore[reportAttributeAccessIssue, reportRedeclaration]
        "unsafe": yaml.CUnsafeLoader,
        "full": yaml.CFullLoader,
        "safe": yaml.CSafeLoader,
    }
except Exception:  # noqa: BLE001
    LOADERS: dict[str, typedefs.LoaderType] = {  # type: ignore
        "unsafe": yaml.UnsafeLoader,
        "full": yaml.FullLoader,
        "safe": yaml.SafeLoader,
    }

_T_co = TypeVar("_T_co", covariant=True)


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
                return loader.construct_scalar(node)  # pyright: ignore[reportArgumentType]

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
                    return loader.construct_scalar(node)  # pyright: ignore[reportArgumentType]

        except jinja2.TemplateError:  # Handle Jinja2 errors separately
            raise  # Re-raise Jinja2 errors
        except Exception:  # Handle other exceptions
            logger.exception("Error in Jinja2 constructor")
            return loader.construct_scalar(node)  # pyright: ignore[reportArgumentType]

    return construct_jinja2_str


def get_include_constructor(
    fs: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    **kwargs: Any,
) -> yaml_include.Constructor:
    """Create a YAML include (!include) constructor with fsspec filesystem support.

    Args:
        fs: Filesystem specification (path or fsspec filesystem object)
        kwargs: Additional arguments for the Constructor

    Returns:
        Configured YAML include constructor
    """
    import fsspec
    import yaml_include

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
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
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
    base_dir: JoinablePathLike | None,
    mode: typedefs.LoaderStr | typedefs.LoaderType,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None,
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

    from upathtools import to_upath

    base_dir = to_upath(base_dir)
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
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool | JoinablePathLike = False,
    variables: dict[str, Any] | None = None,
    jinja_env: jinja2.Environment | None = None,
    verify_type: None = None,
) -> Any: ...


@overload
def load_yaml[T: type](
    text: YAMLInput,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool | JoinablePathLike = False,
    variables: dict[str, Any] | None = None,
    jinja_env: jinja2.Environment | None = None,
    verify_type: type[T],
) -> T: ...


def load_yaml[T: type](
    text: YAMLInput,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool | JoinablePathLike = False,
    variables: dict[str, Any] | None = None,
    jinja_env: jinja2.Environment | None = None,
    verify_type: type[T] | None = None,
) -> Any | T:
    r"""Load a YAML string with specified safety mode and include path support.

    Args:
        text: The YAML content to load
        mode: YAML loader safety mode ('unsafe', 'full', or 'safe')
              Custom YAML loader classes are also accepted.
        include_base_path: Base path for resolving !include directives
        resolve_strings: Whether to resolve Jinja2 template strings
        resolve_dict_keys: Whether to resolve Jinja2 templates in dictionary keys
        resolve_inherit: Whether to resolve INHERIT directives
                         If True, then requires IO object with name attribute for text
                         If str or PathLike, its interpreted as the base path
        jinja_env: Optional Jinja2 environment for template resolution
        variables: An optional dictionary to resolving !var tags
        verify_type: Type to verify and cast the output to (supports TypedDict)

    Returns:
        The parsed YAML data, typed according to verify_type if provided

    Example:
        ```python
        # Simple YAML loading
        data = load_yaml("key: value")

        # With TypedDict verification
        from typing import TypedDict

        class Config(TypedDict):
            host: str
            port: int

        config = load_yaml('''
            host: localhost
            port: 8080
        ''', verify_type=Config)

        # With Jinja2 template resolution
        from jinja2 import Environment
        env = Environment()
        data = load_yaml(
            "message: Hello {{ name }}!",
            resolve_strings=True,
            jinja_env=env
        )
        ```
    """
    try:
        base_loader_cls: type = LOADERS[mode] if isinstance(mode, str) else mode
        loader = get_loader(
            base_loader_cls,
            include_base_path=include_base_path,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
            variables=variables,
            jinja_env=jinja_env,
        )
        data = yaml.load(text, Loader=loader)

        if resolve_inherit:
            import upath
            from upathtools import to_upath

            if hasattr(text, "name"):
                base_dir = upath.UPath(text.name).parent  # pyright: ignore[reportAttributeAccessIssue]
                data = _resolve_inherit(
                    data,
                    base_dir,
                    mode=mode,
                    include_base_path=include_base_path,
                    resolve_strings=resolve_strings,
                    resolve_dict_keys=resolve_dict_keys,
                    jinja_env=jinja_env,
                )
            elif resolve_inherit is not None and not isinstance(resolve_inherit, bool):
                base_dir = to_upath(resolve_inherit)
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
            try:
                return verify.verify_type(data, verify_type)
            except TypeError as e:
                msg = f"YAML data doesn't match expected type: {e}"
                raise TypeError(msg) from e
        return data


@overload
def load_yaml_file(
    path: JoinablePathLike,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: None = None,
) -> Any: ...


@overload
def load_yaml_file[T: type](
    path: JoinablePathLike,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T],
) -> T: ...


def load_yaml_file[T: type](
    path: JoinablePathLike,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: jinja2.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T] | None = None,
) -> Any | T:
    """Load a YAML file with specified options.

    Use verify_type to get proper output type for LSPs and runtime validation.

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
        verify_type: Type to verify and cast the output to (supports TypedDict)

    Returns:
        The parsed YAML data

    Example:
        ```python
        from typing import TypedDict

        class Config(TypedDict):
            database: str
            port: int
            debug: bool

        # Load YAML file with inheritance and TypedDict verification
        config = load_yaml_file(
            "config.yml",
            resolve_inherit=True,  # Resolve INHERIT directives
            include_base_path="configs/",  # Base path for includes
            verify_type=Config  # Verify against TypedDict
        )
        ```
    """
    try:
        import upath

        p = os.fspath(path) if isinstance(path, os.PathLike) else path
        path_obj = upath.UPath(p, **storage_options or {}).resolve()
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
            try:
                return verify.verify_type(data, verify_type)
            except TypeError as e:
                msg = f"YAML data doesn't match expected type: {e}"
                raise TypeError(msg) from e
        return data


if __name__ == "__main__":
    obj = load_yaml("- test")
    print(obj)
