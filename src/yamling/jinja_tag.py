"""Jinja2 template constructor for YAML loading."""

from __future__ import annotations

from collections.abc import Callable, Hashable
import logging
from typing import Any

import jinja2
import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode


logger = logging.getLogger(__name__)

# Type aliases
type YAMLConstructor = Callable[[yaml.Loader, Node], Any]
type TemplateValue = str | list[Any] | dict[Hashable, Any]


class JinjaConstructionError(ConstructorError):
    """Error raised when Jinja2 template construction fails."""


def get_jinja_constructor(
    env: jinja2.Environment | None,
) -> YAMLConstructor:
    """Create a constructor that resolves !JINJA tags using a Jinja2 environment.

    This constructor allows explicit template processing for values marked with the
    !JINJA tag in YAML documents. It supports scalar values, sequences, and mappings.

    Args:
        env: Jinja2 environment to use for template resolution. If None,
             returns the raw string without template processing.

    Returns:
        A constructor function for the YAML loader.

    Example:
        ```python
        from jinja2 import Environment
        import yaml

        # Setup environment
        env = Environment()
        env.globals['name'] = 'World'

        # Create loader with constructor
        loader = yaml.Loader
        loader.add_constructor('!JINJA', get_jinja_constructor(env))

        # Use in YAML
        yaml_text = '''
        message: !JINJA "Hello {{ name }}!"
        items: !JINJA
          - "Item {{ loop.index }}"
          - "Value {{ value }}"
        nested:
          value: !JINJA "{{ name | upper }}"
        '''
        data = yaml.load(yaml_text, Loader=loader)
        ```
    """

    def render_template(template: str) -> str:
        """Render a Jinja2 template string.

        Args:
            template: The template string to render.

        Returns:
            The rendered template string.

        Raises:
            JinjaConstructionError: If template rendering fails.
        """
        if env is None:
            return template

        try:
            return env.from_string(template).render()
        except jinja2.TemplateError as e:
            msg = f"Failed to render Jinja2 template: {e!s}"
            raise JinjaConstructionError(None, None, msg, None) from e

    def process_value(value: TemplateValue) -> TemplateValue:
        """Process a value, rendering any template strings.

        Args:
            value: The value to process.

        Returns:
            The processed value with templates rendered.
        """
        match value:
            case str():
                return render_template(value)
            case list():
                return [
                    render_template(item)
                    if isinstance(item, str)
                    else process_value(item)
                    for item in value
                ]
            case dict():
                return {
                    k: render_template(v) if isinstance(v, str) else process_value(v)
                    for k, v in value.items()
                }
            case _:
                return value

    def construct_jinja_expression(loader: yaml.Loader, node: Node) -> Any:
        """Construct a value from a YAML node, processing any Jinja2 templates.

        Args:
            loader: The YAML loader instance.
            node: The current YAML node being processed.

        Returns:
            The constructed and processed value.

        Raises:
            JinjaConstructionError: If template processing fails.
        """
        try:
            match node:
                case ScalarNode():
                    value = loader.construct_scalar(node)
                    return process_value(value)

                case SequenceNode():
                    value = loader.construct_sequence(node)
                    return process_value(value)

                case MappingNode():
                    value = loader.construct_mapping(node)
                    return process_value(value)

                case _:
                    return loader.construct_scalar(node)  # pyright: ignore[reportArgumentType]

        except JinjaConstructionError:
            raise
        except Exception as e:
            logger.exception("Unexpected error processing Jinja2 template")
            raise JinjaConstructionError(
                None,
                None,
                f"Unexpected error processing Jinja2 template: {e!s}",
                node.start_mark,
            ) from e

    return construct_jinja_expression


def register_jinja_constructor(
    loader_class: type[yaml.Loader], env: jinja2.Environment | None = None
) -> None:
    """Register the !JINJA tag constructor with a YAML loader class.

    Args:
        loader_class: The YAML loader class to register the constructor with.
        env: Optional Jinja2 environment for template resolution.

    Example:
        ```python
        from jinja2 import Environment
        import yaml

        env = Environment()
        register_jinja_constructor(yaml.Loader, env)
        ```
    """
    loader_class.add_constructor("!JINJA", get_jinja_constructor(env))
