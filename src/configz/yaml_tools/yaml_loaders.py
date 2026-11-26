"""YAML handling utilities with enhanced loading and dumping capabilities."""

import logging
import os
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, overload

import upath
from upathtools import core, to_upath
import yaml

from configz import deepmerge, typedefs, utils, verify
from configz.yaml_tools.constructors import variable
from configz.yaml_tools.constructors.scalar import construct_scalar


if TYPE_CHECKING:
    from collections.abc import Callable

    import fsspec  # type: ignore[import-untyped]
    import minijinja
    from upath.types import JoinablePathLike
    import yaml_include


logger = logging.getLogger(__name__)

# The C loaders only exist when PyYAML was built with libyaml.
LOADERS: dict[str, typedefs.LoaderType] = (
    {"unsafe": yaml.CUnsafeLoader, "full": yaml.CFullLoader, "safe": yaml.CSafeLoader}
    if yaml.__with_libyaml__
    else {"unsafe": yaml.UnsafeLoader, "full": yaml.FullLoader, "safe": yaml.SafeLoader}
)

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
            tag = loader.resolve(yaml.nodes.ScalarNode, value, (True, False))  # type: ignore[no-untyped-call]
            return loader.construct_object(yaml.nodes.ScalarNode(tag, value))

    return default


def get_jinja_constructor(
    env: minijinja.Environment | None,
    resolve_strings: bool = True,
    resolve_dict_keys: bool = False,
) -> Callable[[yaml.Loader, yaml.Node], Any]:
    """Create a constructor that resolves strings using a MiniJinja environment.

    Args:
        env: MiniJinja environment to use for template resolution
        resolve_strings: Whether to resolve string values
        resolve_dict_keys: Whether to resolve dictionary keys

    Returns:
        Constructor function for YAML loader
    """
    import minijinja

    def construct_jinja_str(loader: yaml.Loader, node: yaml.Node) -> Any:  # noqa: PLR0911
        try:
            if env is None or not resolve_strings:
                return construct_scalar(loader, node)

            match node:
                case yaml.ScalarNode():
                    scalar_val = loader.construct_scalar(node)
                    if isinstance(scalar_val, str):
                        return env.render_str(scalar_val)
                    return scalar_val

                case yaml.MappingNode():
                    map_val = loader.construct_mapping(node)
                    if resolve_dict_keys:
                        return {
                            (env.render_str(k) if isinstance(k, str) else k): v
                            for k, v in map_val.items()
                        }
                    return map_val

                case yaml.SequenceNode():
                    return loader.construct_sequence(node)

                case _:
                    return construct_scalar(loader, node)

        except minijinja.TemplateError:  # Handle MiniJinja errors separately
            raise  # Re-raise MiniJinja errors
        except Exception:  # Handle other exceptions
            logger.exception("Error in MiniJinja constructor")
            return construct_scalar(loader, node)

    return construct_jinja_str


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
            filesystem, _ = core.url_to_fs(str(fs))
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
    jinja_env: minijinja.Environment | None = None,
) -> typedefs.LoaderType:
    """Construct an enhanced YAML loader with optional support for !env and !include tags.

    Args:
        base_loader_cls: Base loader class to extend
        include_base_path: Base path for !include tag resolution. If None, use cwd.
        enable_include: Whether to enable !include tag support
        enable_env: Whether to enable !ENV tag support
        resolve_strings: Whether to resolve strings using MiniJinja
        resolve_dict_keys: Whether to resolve dictionary keys using MiniJinja
        variables: An optional dictionary to resolving !var tags
        jinja_env: Optional MiniJinja environment for template resolution

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
        j_ctor = get_jinja_constructor(
            jinja_env,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
        )
        loader_cls.add_constructor("tag:yaml.org,2002:str", j_ctor)

    return loader_cls


def _resolve_inherit[T](
    data: T,
    base_dir: JoinablePathLike | None,
    mode: typedefs.LoaderStr | typedefs.LoaderType,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None,
    resolve_strings: bool,
    resolve_dict_keys: bool,
    jinja_env: minijinja.Environment | None,
    enable_env: bool = True,
    variables: dict[str, Any] | None = None,
    inherit_from: list[str] | str | None = None,
) -> T:
    """Resolve INHERIT directive in YAML data.

    Args:
        data: The loaded YAML data
        base_dir: Directory to resolve inherited paths from
        mode: YAML loader mode
        include_base_path: Base path for !include resolution
        resolve_strings: Whether to resolve MiniJinja template strings
        resolve_dict_keys: Whether to resolve MiniJinja templates in dictionary keys
        jinja_env: Optional MiniJinja environment
        enable_env: Whether to enable !ENV tag
        variables: Variables for !var tag resolution
        inherit_from: Additional paths to inherit from. These form the base layer,
                      meaning explicit INHERIT directives in the file take precedence.

    Returns:
        Merged configuration data
    """
    import upath

    if not isinstance(data, dict) or base_dir is None:
        return data

    parent_path = data.pop("INHERIT", None)

    # Build combined inheritance chain: inherit_from is base, INHERIT has priority
    file_paths: list[str] = []

    # Add inherit_from first (processed last = true base layer)
    if inherit_from:
        if isinstance(inherit_from, str):
            file_paths.append(inherit_from)
        else:
            file_paths.extend(inherit_from)

    # Add explicit INHERIT paths (higher priority, processed earlier)
    if parent_path:
        if isinstance(parent_path, str):
            file_paths.append(parent_path)
        else:
            file_paths.extend(parent_path)

    if not file_paths:
        return data

    from upathtools import to_upath

    base_dir = to_upath(base_dir)
    context = deepmerge.DeepMerger()

    # Process inheritance in reverse order (last file is base configuration)
    for p_path in reversed(file_paths):
        # Handle absolute vs relative paths
        p_upath = upath.UPath(p_path)
        parent_cfg = p_upath if p_upath.is_absolute() else base_dir / p_path
        logger.debug("Loading parent configuration file %r relative to %r", parent_cfg, base_dir)
        parent_data = load_yaml_file(
            parent_cfg,
            mode=mode,
            include_base_path=include_base_path,
            resolve_inherit=True,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
            jinja_env=jinja_env,
            enable_env=enable_env,
            variables=variables,
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
    jinja_env: minijinja.Environment | None = None,
    verify_type: None = None,
    enable_env: bool = True,
) -> Any: ...


@overload
def load_yaml[T](
    text: YAMLInput,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool | JoinablePathLike = False,
    variables: dict[str, Any] | None = None,
    jinja_env: minijinja.Environment | None = None,
    verify_type: type[T],
    enable_env: bool = True,
) -> T: ...


@overload
def load_yaml[T](
    text: YAMLInput,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool | JoinablePathLike = False,
    variables: dict[str, Any] | None = None,
    jinja_env: minijinja.Environment | None = None,
    verify_type: type[T] | None = None,
    enable_env: bool = True,
) -> T | Any: ...


def load_yaml[T](
    text: YAMLInput,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    resolve_inherit: bool | JoinablePathLike = False,
    variables: dict[str, Any] | None = None,
    jinja_env: minijinja.Environment | None = None,
    verify_type: type[T] | None = None,
    enable_env: bool = True,
) -> Any | T:
    r"""Load a YAML string with specified safety mode and include path support.

    Args:
        text: The YAML content to load
        mode: YAML loader safety mode ('unsafe', 'full', or 'safe')
              Custom YAML loader classes are also accepted.
        include_base_path: Base path for resolving !include directives
        resolve_strings: Whether to resolve MiniJinja template strings
        resolve_dict_keys: Whether to resolve MiniJinja templates in dictionary keys
        resolve_inherit: Whether to resolve INHERIT directives
                         If True, then requires IO object with name attribute for text
                         If str or PathLike, its interpreted as the base path
        jinja_env: Optional MiniJinja environment for template resolution
        variables: An optional dictionary to resolving !var tags
        verify_type: Type to verify and cast the output to (supports TypedDict)
        enable_env: Whether to enable the !ENV tag


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

        # With MiniJinja template resolution
        from minijinja import Environment
        env = Environment(globals={"name": "World"})
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
            enable_env=enable_env,
        )
        data = yaml.load(text, Loader=loader)
        if resolve_inherit:
            if isinstance(text, typedefs.NamedStream) and isinstance(text.name, str):
                base_dir = upath.UPath(text.name).parent
            elif resolve_inherit is not None and not isinstance(resolve_inherit, bool):
                base_dir = to_upath(resolve_inherit)
            else:
                base_dir = None
            if base_dir:
                data = _resolve_inherit(
                    data,
                    base_dir,
                    mode=mode,
                    include_base_path=include_base_path,
                    resolve_strings=resolve_strings,
                    resolve_dict_keys=resolve_dict_keys,
                    jinja_env=jinja_env,
                    enable_env=enable_env,
                    variables=variables,
                )
    except yaml.YAMLError as e:
        logger.exception("Failed to load YAML: \n%s", text)
        from configz.yaml_tools.yaml_errors import YAMLError

        doc_path = getattr(text, "name", None) if hasattr(text, "name") else None
        raise YAMLError(e, doc_path=doc_path) from e
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
    jinja_env: minijinja.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: None = None,
    enable_env: bool = True,
    inherit_from: list[str] | str | None = None,
) -> Any: ...


@overload
def load_yaml_file[T](
    path: JoinablePathLike,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: minijinja.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T],
    enable_env: bool = True,
    inherit_from: list[str] | str | None = None,
) -> T: ...


@overload
def load_yaml_file[T](
    path: JoinablePathLike,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: minijinja.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T] | None = None,
    enable_env: bool = True,
    inherit_from: list[str] | str | None = None,
) -> T | Any: ...


def load_yaml_file[T](
    path: JoinablePathLike,
    mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
    *,
    include_base_path: JoinablePathLike | fsspec.AbstractFileSystem | None = None,
    resolve_inherit: bool = False,
    resolve_strings: bool = False,
    resolve_dict_keys: bool = False,
    jinja_env: minijinja.Environment | None = None,
    variables: dict[str, Any] | None = None,
    storage_options: dict[str, Any] | None = None,
    verify_type: type[T] | None = None,
    enable_env: bool = True,
    inherit_from: list[str] | str | None = None,
) -> Any | T:
    """Load a YAML file with specified options.

    Use verify_type to get proper output type for LSPs and runtime validation.

    Args:
        path: Path to the YAML file to load
        mode: YAML loader safety mode ('unsafe', 'full', or 'safe').
              Custom YAML loader classes are also accepted.
        include_base_path: Base path for resolving !include directives
        resolve_inherit: Whether to resolve INHERIT directives
        resolve_strings: Whether to resolve MiniJinja template strings
        resolve_dict_keys: Whether to resolve MiniJinja templates in dictionary keys
        jinja_env: Optional MiniJinja environment for template resolution
        variables: An optional dictionary to resolving !var tags
        storage_options: Additional keywords to pass to fsspec backend
        verify_type: Type to verify and cast the output to (supports TypedDict)
        enable_env: Whether to enable the !ENV tag
        inherit_from: Additional paths to inherit from. These form the base layer,
                      meaning explicit INHERIT directives in the file take precedence.


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
    import upath

    if isinstance(path, upath.UPath) and not storage_options:
        # Keep the caller's filesystem instance; rebuilding the path from its
        # string would lose it (and stores like isolated memory:// with it).
        path_obj = path.resolve()
    else:
        p = os.fspath(path) if isinstance(path, os.PathLike) else path
        path_obj = upath.UPath(p, **storage_options or {}).resolve()

    try:
        text = path_obj.read_text("utf-8")

        data = load_yaml(
            text,
            mode=mode,
            include_base_path=include_base_path,
            resolve_strings=resolve_strings,
            resolve_dict_keys=resolve_dict_keys,
            resolve_inherit=False,  # We'll handle inheritance separately
            variables=variables,
            jinja_env=jinja_env,
            enable_env=enable_env,
        )

        if resolve_inherit or inherit_from:
            data = _resolve_inherit(
                data,
                path_obj.parent,  # Pass the parent directory directly
                mode=mode,
                include_base_path=include_base_path,
                resolve_strings=resolve_strings,
                resolve_dict_keys=resolve_dict_keys,
                jinja_env=jinja_env,
                enable_env=enable_env,
                variables=variables,
                inherit_from=inherit_from,
            )
    except yaml.YAMLError as e:
        logger.exception("Failed to load YAML file %r", path)
        from configz.yaml_tools.yaml_errors import YAMLError

        raise YAMLError(e, doc_path=path_obj) from e
    except OSError:
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
