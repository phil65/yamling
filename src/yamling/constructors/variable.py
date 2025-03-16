from collections.abc import Mapping
from typing import Any

from yaml.constructor import Constructor


class VariableReference:
    """Represents a variable reference in YAML."""

    def __init__(self, name: str) -> None:
        self.name = name

    def resolve(self, variables: Mapping[str, Any]) -> Any:
        """Resolve variable value."""
        if self.name not in variables:
            msg = f"Missing variable: {self.name}"
            raise KeyError(msg)
        return variables[self.name]


class ConfigConstructor(Constructor):
    """Custom YAML constructor with variable support."""

    def __init__(self, variables: Mapping[str, Any] | None = None) -> None:
        super().__init__()
        self.variables: Mapping[str, Any] = variables or {}

    def construct_variable(self, loader: Any, node: Any) -> Any:
        """Construct a variable reference."""
        value = loader.construct_scalar(node)
        if not isinstance(value, str):
            msg = f"Invalid variable reference: {value}"
            raise TypeError(msg)
        return self.variables.get(value, VariableReference(value))


if __name__ == "__main__":
    import anyenv

    import yamling

    text = """
llm_settings:
    temperature: !var temperature
    max_tokens: !var max_tokens
"""
    variables = {"temperature": 0.5, "max_tokens": 50}
    dct = yamling.load_yaml(text, variables=variables)
    print(anyenv.dump_json(dct))
