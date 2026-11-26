"""MiniJinja template constructor for YAML loading."""

from collections.abc import Callable, Hashable
import logging
from typing import Any

import minijinja
import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from configz.yaml_tools.constructors.scalar import construct_scalar


logger = logging.getLogger(__name__)

# Type aliases
type YAMLConstructor = Callable[[yaml.Loader, Node], Any]
type TemplateValue = str | list[Any] | dict[Hashable, Any]


class JinjaConstructionError(ConstructorError):
    """Error raised when Jinja template construction fails."""


def get_jinja_constructor(env: minijinja.Environment | None) -> YAMLConstructor:
    """Create a constructor that resolves !JINJA tags using a MiniJinja environment.

    This constructor allows explicit template processing for values marked with the
    !JINJA tag in YAML documents. It supports scalar values, sequences, and mappings.

    Args:
        env: MiniJinja environment to use for template resolution. If None,
             returns the raw string without template processing.

    Returns:
        A constructor function for the YAML loader.

    Example:
        ```python
        from minijinja import Environment
        import yaml

        # Setup environment
        env = Environment(globals={"name": "World"})

        # Create loader with constructor
        loader = yaml.Loader
        loader.add_constructor('!JINJA', get_jinja_constructor(env))

        # Use in YAML
        yaml_text = '''
        message: !JINJA "Hello {{ name }}!"
        items: !JINJA
          - "Item {{ name }}"
          - "Value {{ name | upper }}"
        nested:
          value: !JINJA "{{ name | upper }}"
        '''
        data = yaml.load(yaml_text, Loader=loader)
        ```
    """

    def render_template(template: str) -> str:
        """Render a MiniJinja template string.

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
            return env.render_str(template)
        except minijinja.TemplateError as e:
            msg = f"Failed to render Jinja template: {e!s}"
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
                    render_template(item) if isinstance(item, str) else process_value(item)
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
        """Construct a value from a YAML node, processing any Jinja templates.

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
                    scalar_val = loader.construct_scalar(node)
                    return process_value(scalar_val)

                case SequenceNode():
                    seq_val = loader.construct_sequence(node)
                    return process_value(seq_val)

                case MappingNode():
                    map_val = loader.construct_mapping(node)
                    return process_value(map_val)

                case _:
                    return construct_scalar(loader, node)

        except JinjaConstructionError:
            raise
        except Exception as e:
            logger.exception("Unexpected error processing Jinja template")
            raise JinjaConstructionError(
                None,
                None,
                f"Unexpected error processing Jinja template: {e!s}",
                node.start_mark,
            ) from e

    return construct_jinja_expression


def register_jinja_constructor(
    loader_class: type[yaml.Loader], env: minijinja.Environment | None = None
) -> None:
    """Register the !JINJA tag constructor with a YAML loader class.

    Args:
        loader_class: The YAML loader class to register the constructor with.
        env: Optional MiniJinja environment for template resolution.

    Example:
        ```python
        from minijinja import Environment
        import yaml

        env = Environment()
        register_jinja_constructor(yaml.Loader, env)
        ```
    """
    loader_class.add_constructor("!JINJA", get_jinja_constructor(env))
