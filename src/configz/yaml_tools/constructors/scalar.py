"""Typed scalar construction for nodes of unknown kind."""

from typing import TYPE_CHECKING, Any

from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, ScalarNode


if TYPE_CHECKING:
    from yaml.constructor import SafeConstructor
    from yaml.nodes import Node


def construct_scalar(loader: SafeConstructor, node: Node) -> Any:
    """Construct a scalar from `node`, failing like PyYAML for other node kinds.

    `SafeConstructor.construct_scalar` accepts scalar nodes and mappings with a
    `value` key; any other node raises the same `ConstructorError` PyYAML would.
    """
    if not isinstance(node, ScalarNode | MappingNode):
        msg = f"expected a scalar node, but found {type(node).__name__}"
        raise ConstructorError(None, None, msg, node.start_mark)
    return loader.construct_scalar(node)
