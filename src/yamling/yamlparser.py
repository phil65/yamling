from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, overload

import yaml

from yamling import yaml_loaders


if TYPE_CHECKING:
    import os

    import fsspec
    import jinja2
    from yaml import Node

    from yamling import typedefs


# Type for the handler function
T = TypeVar("T", bound=object)
HandlerFunc = Callable[[Any], T]


class YAMLParser:
    """Manages custom YAML tags and provides YAML loading capabilities."""

    def __init__(self) -> None:
        self._tag_handlers: dict[str, HandlerFunc] = {}
        self._tag_prefix: str = "!"  # Default prefix for tags

    def register(
        self, tag_name: str | None = None
    ) -> Callable[[HandlerFunc[T] | type[T]], HandlerFunc[T] | type[T]]:
        """Decorator to register a new tag handler or class.

        Args:
            tag_name: Optional name of the tag. If None and decorating a class,
                    the lowercase class name will be used.

        Returns:
            Decorator function that registers the handler or the original class

        Usage:
            # Function registration
            @yaml_parser.register("person")
            def handle_person(data: dict) -> Person:
                return Person(**data)

            # Class registration
            @yaml_parser.register()  # will use "person" as tag
            class Person:
                def __init__(self, name: str, age: int):
                    self.name = name
                    self.age = age
        """

        def decorator(func_or_cls: HandlerFunc[T] | type[T]) -> HandlerFunc[T] | type[T]:
            nonlocal tag_name

            if isinstance(func_or_cls, type):
                # It's a class
                cls = func_or_cls
                tag = tag_name or cls.__name__.lower()

                def class_handler(data: Any) -> T:
                    if not isinstance(data, dict):
                        msg = f"Data for {tag} must be a mapping, got {type(data)}"
                        raise TypeError(msg)
                    return cls(**data)

                self.register_handler(tag, class_handler)
                return cls  # Return the original class instead of the handler

            # It's a function
            if tag_name is None:
                msg = "tag_name is required when decorating functions"
                raise ValueError(msg)
            self.register_handler(tag_name, func_or_cls)
            return func_or_cls

        return decorator

    def register_handler(self, tag_name: str, handler: HandlerFunc[T]):
        """Explicitly register a tag handler function.

        Args:
            tag_name: Name of the tag without prefix
            handler: Function that processes the tagged data
        """
        full_tag = f"{self._tag_prefix}{tag_name}"
        self._tag_handlers[full_tag] = handler

    def register_class(self, cls: type[T], tag_name: str | None = None) -> None:
        """Register a class as a tag handler.

        The class will be instantiated with the YAML data as kwargs.
        If no tag_name is provided, the lowercase class name will be used.

        Args:
            cls: The class to register
            tag_name: Optional custom tag name. If None, lowercase class name is used

        Example:
            @dataclass
            class Person:
                name: str
                age: int

            # Using class name as tag (will use "person" as tag name)
            yaml_parser.register_class(Person)

            # Using custom tag name
            yaml_parser.register_class(Person, "user")
        """
        if tag_name is None:
            tag_name = cls.__name__.lower()

        def class_handler(data: Any) -> T:
            if not isinstance(data, dict):
                msg = f"Data for {tag_name} must be a mapping, got {type(data)}"
                raise TypeError(msg)
            return cls(**data)

        self.register_handler(tag_name, class_handler)

    def process_tag(self, tag: str, data: Any) -> Any:
        """Process data with the registered handler for the given tag.

        Args:
            tag: Full tag name (including prefix)
            data: Data to be processed

        Raises:
            ValueError: If no handler is registered for the tag
        """
        if tag not in self._tag_handlers:
            msg = f"No handler registered for tag: {tag}"
            raise ValueError(msg)
        return self._tag_handlers[tag](data)

    def get_handler(self, tag: str) -> HandlerFunc | None:
        """Get the handler function for a specific tag.

        Args:
            tag: Full tag name (including prefix)

        Returns:
            Handler function if found, None otherwise
        """
        return self._tag_handlers.get(tag)

    def list_tags(self) -> list[str]:
        """Return a list of registered tags.

        Returns:
            List of registered tag names
        """
        return list(self._tag_handlers.keys())

    def create_constructor(self, tag_name: str) -> Callable[[yaml.Loader, Node], Any]:
        """Create a YAML constructor function for a specific tag.

        Args:
            tag_name: Name of the tag without prefix

        Returns:
            Constructor function for the YAML loader
        """
        from yaml import MappingNode, ScalarNode, SequenceNode

        full_tag = f"{self._tag_prefix}{tag_name}"

        def constructor(loader: yaml.Loader, node: Node) -> Any:
            match node:
                case ScalarNode():
                    value = loader.construct_scalar(node)
                case SequenceNode():
                    value = loader.construct_sequence(node)
                case MappingNode():
                    value = loader.construct_mapping(node)
                case _:
                    msg = f"Unsupported node type for tag {full_tag}"
                    raise TypeError(msg)

            return self.process_tag(full_tag, value)

        return constructor

    def register_with_loader(
        self,
        loader_class: typedefs.LoaderType | None = None,
    ) -> None:
        """Register all tags with a YAML loader class.

        Args:
            loader_class: The YAML loader class to register with
        """
        from yaml import SafeLoader

        loader_class = loader_class or SafeLoader
        for tag in self._tag_handlers:
            loader_class.add_constructor(tag, self.create_constructor(tag[1:]))

    @overload
    def load_yaml(
        self,
        text: yaml_loaders.YAMLInput,
        *,
        mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
        include_base_path: str
        | os.PathLike[str]
        | fsspec.AbstractFileSystem
        | None = None,
        resolve_strings: bool = False,
        resolve_dict_keys: bool = False,
        resolve_inherit: bool = False,
        variables: dict[str, Any] | None = None,
        jinja_env: jinja2.Environment | None = None,
        verify_type: None = None,
    ) -> Any: ...

    @overload
    def load_yaml[TVerify](
        self,
        text: yaml_loaders.YAMLInput,
        *,
        mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
        include_base_path: str
        | os.PathLike[str]
        | fsspec.AbstractFileSystem
        | None = None,
        resolve_strings: bool = False,
        resolve_dict_keys: bool = False,
        resolve_inherit: bool = False,
        variables: dict[str, Any] | None = None,
        jinja_env: jinja2.Environment | None = None,
        verify_type: type[TVerify],
    ) -> TVerify: ...

    def load_yaml[TVerify](
        self,
        text: yaml_loaders.YAMLInput,
        *,
        mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
        include_base_path: str
        | os.PathLike[str]
        | fsspec.AbstractFileSystem
        | None = None,
        resolve_strings: bool = False,
        resolve_dict_keys: bool = False,
        resolve_inherit: bool = False,
        variables: dict[str, Any] | None = None,
        jinja_env: jinja2.Environment | None = None,
        verify_type: type[TVerify] | None = None,
    ) -> Any | TVerify:
        """Load YAML content with custom tag handlers.

        Args:
            text: The YAML content to load
            mode: YAML loader safety mode ('unsafe', 'full', or 'safe')
                Custom YAML loader classes are also accepted
            include_base_path: Base path for resolving !include directives
            resolve_strings: Whether to resolve Jinja2 template strings
            resolve_dict_keys: Whether to resolve Jinja2 templates in dictionary keys
            resolve_inherit: Whether to resolve INHERIT directives
            variables: An optional dictionary to resolving !var tags
            jinja_env: Optional Jinja2 environment for template resolution
            verify_type: Type to verify and cast the output to

        Returns:
            Parsed YAML data with custom tag handling,
            typed according to verify_type if provided

        Example:
            ```python
            yaml_parser = YAMLParser()

            @yaml_parser.register("person")
            def handle_person(data: dict) -> Person:
                return Person(**data)

            # Without type verification
            data = yaml_parser.load_yaml(
                "person: !person {name: John, age: 30}",
                mode="safe",
                resolve_strings=True
            )

            # With type verification
            data = yaml_parser.load_yaml(
                "config: {key: value}",
                mode="safe",
                verify_type=dict
            )
            ```
        """
        loader_class = yaml_loaders.LOADERS[mode] if isinstance(mode, str) else mode
        self.register_with_loader(loader_class)
        try:
            return yaml_loaders.load_yaml(
                text,
                mode=loader_class,
                include_base_path=include_base_path,
                resolve_strings=resolve_strings,
                resolve_dict_keys=resolve_dict_keys,
                resolve_inherit=resolve_inherit,
                variables=variables,
                jinja_env=jinja_env,
                verify_type=verify_type,  # type: ignore[arg-type]
            )
        except yaml.constructor.ConstructorError as e:
            tag = e.problem.split()[-1] if e.problem else "unknown"
            msg = f"No handler registered for tag: {tag}"
            raise ValueError(msg) from e

    @overload
    def load_yaml_file(
        self,
        path: str | os.PathLike[str],
        *,
        mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
        include_base_path: str
        | os.PathLike[str]
        | fsspec.AbstractFileSystem
        | None = None,
        resolve_inherit: bool = False,
        resolve_strings: bool = False,
        resolve_dict_keys: bool = False,
        jinja_env: jinja2.Environment | None = None,
        variables: dict[str, Any] | None = None,
        storage_options: dict[str, Any] | None = None,
        verify_type: None = None,
    ) -> Any: ...

    @overload
    def load_yaml_file[TVerify](
        self,
        path: str | os.PathLike[str],
        *,
        mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
        include_base_path: str
        | os.PathLike[str]
        | fsspec.AbstractFileSystem
        | None = None,
        resolve_inherit: bool = False,
        resolve_strings: bool = False,
        resolve_dict_keys: bool = False,
        jinja_env: jinja2.Environment | None = None,
        variables: dict[str, Any] | None = None,
        storage_options: dict[str, Any] | None = None,
        verify_type: type[TVerify],
    ) -> TVerify: ...

    def load_yaml_file[TVerify](
        self,
        path: str | os.PathLike[str],
        *,
        mode: typedefs.LoaderStr | typedefs.LoaderType = "unsafe",
        include_base_path: str
        | os.PathLike[str]
        | fsspec.AbstractFileSystem
        | None = None,
        resolve_inherit: bool = False,
        resolve_strings: bool = False,
        resolve_dict_keys: bool = False,
        jinja_env: jinja2.Environment | None = None,
        variables: dict[str, Any] | None = None,
        storage_options: dict[str, Any] | None = None,
        verify_type: type[TVerify] | None = None,
    ) -> Any | TVerify:
        """Load YAML file with custom tag handlers.

        Args:
            path: Path to the YAML file
            mode: YAML loader safety mode ('unsafe', 'full', or 'safe')
                Custom YAML loader classes are also accepted
            include_base_path: Base path for resolving !include directives
            resolve_inherit: Whether to resolve INHERIT directives
            resolve_strings: Whether to resolve Jinja2 template strings
            resolve_dict_keys: Whether to resolve Jinja2 templates in dictionary keys
            jinja_env: Optional Jinja2 environment for template resolution
            variables: An optional dictionary to resolving !var tags
            storage_options: Additional keywords to pass to fsspec backend
            verify_type: Type to verify and cast the output to

        Returns:
            Parsed YAML data with custom tag handling,
            typed according to verify_type if provided

        Example:
            ```python
            yaml_parser = YAMLParser()

            @yaml_parser.register("config")
            def handle_config(data: dict) -> Config:
                return Config(**data)

            # Without type verification
            data = yaml_parser.load_yaml_file(
                "config.yml",
                resolve_inherit=True,
                include_base_path="configs/"
            )

            # With type verification
            config = yaml_parser.load_yaml_file(
                "config.yml",
                resolve_inherit=True,
                verify_type=dict
            )
            ```
        """
        loader = yaml_loaders.LOADERS[mode] if isinstance(mode, str) else mode
        self.register_with_loader(loader)
        try:
            return yaml_loaders.load_yaml_file(
                path,
                mode=loader,
                include_base_path=include_base_path,
                resolve_inherit=resolve_inherit,
                resolve_strings=resolve_strings,
                resolve_dict_keys=resolve_dict_keys,
                jinja_env=jinja_env,
                variables=variables,
                storage_options=storage_options,
                verify_type=verify_type,  # type: ignore
            )
        except yaml.constructor.ConstructorError as e:
            tag = e.problem.split()[-1] if e.problem else "unknown"
            msg = f"No handler registered for tag: {tag}"
            raise ValueError(msg) from e


# Usage example:
if __name__ == "__main__":
    from dataclasses import dataclass

    @dataclass
    class Person:
        name: str
        age: int

    yaml_parser = YAMLParser()

    @yaml_parser.register("person")
    def handle_person(data: dict[str, Any]) -> Person:
        return Person(**data)

    def handle_uppercase(data: str) -> str:
        return data.upper()

    yaml_parser.register_handler("uppercase", handle_uppercase)

    yaml_content = """
    person: !person
      name: John Doe
      age: 30
    message: !uppercase "hello world"
    """

    data = yaml_parser.load_yaml(yaml_content)
    print("Parsed data:", data)
    print("Available tags:", yaml_parser.list_tags())
