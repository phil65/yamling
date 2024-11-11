from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

import yaml
from yaml import MappingNode, Node, SafeLoader, ScalarNode, SequenceNode

from yamling import yaml_loaders


if TYPE_CHECKING:
    import os

    import fsspec
    import jinja2

    from yamling import yamltypes


# Type for the handler function
T = TypeVar("T")
HandlerFunc = Callable[[Any], T]


class YAMLParser:
    """Manages custom YAML tags and provides YAML loading capabilities."""

    def __init__(self) -> None:
        self._tag_handlers: dict[str, HandlerFunc] = {}
        self._tag_prefix: str = "!"  # Default prefix for tags

    def register(self, tag_name: str) -> Callable[[HandlerFunc[T]], HandlerFunc[T]]:
        """Decorator to register a new tag handler.

        Args:
            tag_name: Name of the tag without prefix

        Returns:
            Decorator function that registers the handler

        Usage:
            @yaml_parser.register("person")
            def handle_person(data: dict) -> Person:
                return Person(**data)
        """

        def decorator(func: HandlerFunc[T]) -> HandlerFunc[T]:
            full_tag = f"{self._tag_prefix}{tag_name}"
            self._tag_handlers[full_tag] = func

            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> T:
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def register_handler(self, tag_name: str, handler: HandlerFunc[T]) -> None:
        """Explicitly register a tag handler function.

        Args:
            tag_name: Name of the tag without prefix
            handler: Function that processes the tagged data
        """
        full_tag = f"{self._tag_prefix}{tag_name}"
        self._tag_handlers[full_tag] = handler

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
        full_tag = f"{self._tag_prefix}{tag_name}"

        def constructor(loader: yaml.Loader, node: Node) -> Any:
            if isinstance(node, ScalarNode):
                value = loader.construct_scalar(node)
            elif isinstance(node, SequenceNode):
                value = loader.construct_sequence(node)
            elif isinstance(node, MappingNode):
                value = loader.construct_mapping(node)
            else:
                msg = f"Unsupported node type for tag {full_tag}"
                raise TypeError(msg)

            return self.process_tag(full_tag, value)

        return constructor

    def register_with_loader(
        self, loader_class: yamltypes.LoaderType = SafeLoader
    ) -> None:
        """Register all tags with a YAML loader class.

        Args:
            loader_class: The YAML loader class to register with
        """
        for tag in self._tag_handlers:
            loader_class.add_constructor(tag, self.create_constructor(tag[1:]))

    def load_yaml(
        self,
        text: yaml_loaders.YAMLInput,
        *,
        mode: yamltypes.LoaderStr | yamltypes.LoaderType = "unsafe",
        include_base_path: str
        | os.PathLike[str]
        | fsspec.AbstractFileSystem
        | None = None,
        resolve_strings: bool = False,
        resolve_dict_keys: bool = False,
        resolve_inherit: bool = False,
        jinja_env: jinja2.Environment | None = None,
    ) -> Any:
        """Load YAML content with custom tag handlers.

        Args:
            text: The YAML content to load
            mode: YAML loader safety mode ('unsafe', 'full', or 'safe')
                  Custom YAML loader classes are also accepted
            include_base_path: Base path for resolving !include directives
            resolve_strings: Whether to resolve Jinja2 template strings
            resolve_dict_keys: Whether to resolve Jinja2 templates in dictionary keys
            resolve_inherit: Whether to resolve INHERIT directives
            jinja_env: Optional Jinja2 environment for template resolution

        Returns:
            Parsed YAML data with custom tag handling

        Example:
            ```python
            yaml_parser = YAMLParser()

            @yaml_parser.register("person")
            def handle_person(data: dict) -> Person:
                return Person(**data)

            data = yaml_parser.load_yaml(
                "person: !person {name: John, age: 30}",
                mode="safe",
                resolve_strings=True
            )
            ```
        """
        loader = yaml_loaders.LOADERS[mode] if isinstance(mode, str) else mode
        self.register_with_loader(loader)
        try:
            return yaml_loaders.load_yaml(
                text,
                mode=loader,
                include_base_path=include_base_path,
                resolve_strings=resolve_strings,
                resolve_dict_keys=resolve_dict_keys,
                resolve_inherit=resolve_inherit,
                jinja_env=jinja_env,
            )
        except yaml.constructor.ConstructorError as e:
            # Convert YAML ConstructorError to ValueError
            msg = f"No handler registered for tag: {e.problem.split()[-1]}"
            raise ValueError(msg) from e

    def load_yaml_file(
        self,
        path: str | os.PathLike[str],
        *,
        mode: yamltypes.LoaderStr | yamltypes.LoaderType = "unsafe",
        include_base_path: str
        | os.PathLike[str]
        | fsspec.AbstractFileSystem
        | None = None,
        resolve_inherit: bool = False,
        resolve_strings: bool = False,
        resolve_dict_keys: bool = False,
        jinja_env: jinja2.Environment | None = None,
    ) -> Any:
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

        Returns:
            Parsed YAML data with custom tag handling

        Example:
            ```python
            yaml_parser = YAMLParser()

            @yaml_parser.register("config")
            def handle_config(data: dict) -> Config:
                return Config(**data)

            data = yaml_parser.load_yaml_file(
                "config.yml",
                resolve_inherit=True,
                include_base_path="configs/"
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
            )
        except yaml.constructor.ConstructorError as e:
            msg = f"No handler registered for tag: {e.problem.split()[-1]}"
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
