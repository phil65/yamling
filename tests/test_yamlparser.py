from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from yamling import YAMLError
from yamling.yamlparser import YAMLParser


if TYPE_CHECKING:
    import pathlib


@dataclass
class Person:
    name: str
    age: int


@pytest.fixture
def yaml_parser():
    """Create a fresh YAMLParser instance for each test."""
    return YAMLParser()


@pytest.fixture
def setup_basic_handlers(yaml_parser: YAMLParser):
    """Setup basic handlers for common test cases."""

    @yaml_parser.register("person")
    def handle_person(data: dict[str, Any]) -> Person:
        return Person(**data)

    @yaml_parser.register("uppercase")
    def handle_uppercase(data: str) -> str:
        return data.upper()

    return yaml_parser


def test_register_decorator(yaml_parser: YAMLParser):
    """Test handler registration using decorator syntax."""

    @yaml_parser.register("test")
    def handle_test(data: str) -> str:
        return f"Test: {data}"

    assert "!test" in yaml_parser.list_tags()

    yaml_content = "value: !test hello"
    result = yaml_parser.load_yaml(yaml_content)
    assert result["value"] == "Test: hello"


def test_register_handler_method(yaml_parser: YAMLParser):
    """Test explicit handler registration using register_handler method."""

    def handle_lowercase(data: str) -> str:
        return data.lower()

    yaml_parser.register_handler("lowercase", handle_lowercase)
    assert "!lowercase" in yaml_parser.list_tags()

    yaml_content = "value: !lowercase HELLO"
    result = yaml_parser.load_yaml(yaml_content)
    assert result["value"] == "hello"


def test_multiple_tags(setup_basic_handlers: YAMLParser):
    """Test handling multiple custom tags in the same YAML document."""
    yaml_content = """
    person: !person
      name: John Doe
      age: 30
    greeting: !uppercase hello
    """

    result = setup_basic_handlers.load_yaml(yaml_content)
    assert isinstance(result["person"], Person)
    assert result["person"].name == "John Doe"
    assert result["person"].age == 30  # noqa: PLR2004
    assert result["greeting"] == "HELLO"


def test_nested_tags(setup_basic_handlers: YAMLParser):
    """Test handling nested tags in complex structures."""
    yaml_content = """
    people:
      - !person
        name: John Doe
        age: 30
      - !person
        name: Jane Doe
        age: 25
    messages:
      - !uppercase hello
      - !uppercase world
    """

    result = setup_basic_handlers.load_yaml(yaml_content)
    assert len(result["people"]) == 2  # noqa: PLR2004
    assert all(isinstance(p, Person) for p in result["people"])
    assert result["messages"] == ["HELLO", "WORLD"]


def test_load_yaml_file(setup_basic_handlers: YAMLParser, tmp_path: pathlib.Path):
    """Test loading YAML from a file."""
    yaml_content = """
    person: !person
      name: John Doe
      age: 30
    """

    # Create temporary YAML file
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    result = setup_basic_handlers.load_yaml_file(yaml_file)
    assert isinstance(result["person"], Person)
    assert result["person"].name == "John Doe"
    assert result["person"].age == 30  # noqa: PLR2004


def test_invalid_tag(yaml_parser: YAMLParser):
    """Test handling of unregistered tags."""
    yaml_content = "value: !invalid_tag data"

    with pytest.raises(YAMLError):
        yaml_parser.load_yaml(yaml_content)


def test_list_tags(setup_basic_handlers: YAMLParser):
    """Test listing registered tags."""
    tags = setup_basic_handlers.list_tags()
    assert "!person" in tags
    assert "!uppercase" in tags
    assert len(tags) == 2  # noqa: PLR2004


def test_different_node_types(yaml_parser: YAMLParser):
    """Test handling different YAML node types (scalar, sequence, mapping)."""

    @yaml_parser.register("process")
    def handle_process(data: Any) -> str:
        return str(data)

    yaml_content = """
    scalar: !process value
    sequence: !process [1, 2, 3]
    mapping: !process
      key: value
    """

    result = yaml_parser.load_yaml(yaml_content)
    assert result["scalar"] == "value"
    assert result["sequence"] == "[1, 2, 3]"
    assert result["mapping"] == "{'key': 'value'}"


def test_register_class_automatic_tag(yaml_parser: YAMLParser):
    """Test class registration using automatic tag name."""
    yaml_parser.register_class(Person)

    yaml_content = """
    user: !person
      name: John Doe
      age: 30
    """

    result = yaml_parser.load_yaml(yaml_content)
    assert isinstance(result["user"], Person)
    assert result["user"].name == "John Doe"
    assert result["user"].age == 30  # noqa: PLR2004


def test_register_class_custom_tag(yaml_parser: YAMLParser):
    """Test class registration using custom tag name."""
    yaml_parser.register_class(Person, "user")

    yaml_content = """
    person: !user
      name: John Doe
      age: 30
    """

    result = yaml_parser.load_yaml(yaml_content)
    assert isinstance(result["person"], Person)
    assert result["person"].name == "John Doe"
    assert result["person"].age == 30  # noqa: PLR2004


def test_register_class_invalid_data(yaml_parser: YAMLParser):
    """Test class registration with invalid data type."""
    yaml_parser.register_class(Person)

    yaml_content = "user: !person invalid"

    with pytest.raises(TypeError, match="Data for person must be a mapping"):
        yaml_parser.load_yaml(yaml_content)


def test_register_decorator_with_class(yaml_parser: YAMLParser):
    """Test decorator registration with a class."""

    @yaml_parser.register()
    class User:
        def __init__(self, name: str, role: str):
            self.name = name
            self.role = role

    yaml_content = """
    admin: !user
      name: John Doe
      role: admin
    """

    result = yaml_parser.load_yaml(yaml_content)
    assert isinstance(result["admin"], User)
    assert result["admin"].name == "John Doe"
    assert result["admin"].role == "admin"


def test_register_decorator_class_custom_tag(yaml_parser: YAMLParser):
    """Test decorator registration with a class and custom tag."""

    @yaml_parser.register("employee")
    class User:
        def __init__(self, name: str, role: str):
            self.name = name
            self.role = role

    yaml_content = """
    staff: !employee
      name: John Doe
      role: manager
    """

    result = yaml_parser.load_yaml(yaml_content)
    assert isinstance(result["staff"], User)
    assert result["staff"].name == "John Doe"
    assert result["staff"].role == "manager"


def test_register_decorator_requires_tag_for_function(yaml_parser: YAMLParser):
    """Test that decorator requires tag name when used with functions."""
    with pytest.raises(ValueError, match="tag_name is required when decorating functions"):

        @yaml_parser.register()
        def handle_test(data: str) -> str:
            return data.upper()
