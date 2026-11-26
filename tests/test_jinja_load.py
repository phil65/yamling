import os
from textwrap import dedent
from typing import TYPE_CHECKING

import minijinja
import pytest
from upath import UPath
import yaml

from configz import YAMLError, utils
from configz.yaml_tools.jinja_tag import (
    JinjaConstructionError,
    register_jinja_constructor,
)
from configz.yaml_tools.yaml_loaders import load_yaml, load_yaml_file


if TYPE_CHECKING:
    from pathlib import Path


# Test Constants
BASIC_STR = "Hello {{ name }}!"
BASIC_DICT = {"greeting": BASIC_STR}
NESTED_DICT = {"user": {"greeting": BASIC_STR, "farewell": "Goodbye {{ name }}!"}}
BASIC_LIST = ["Hello {{ name }}!", "Hi {{ name }}!"]
DICT_WITH_TEMPLATE_KEYS = {"{{ key }}": "value"}
COMPLEX_NESTED = {
    "users": [
        {"name": "{{ name }}", "age": "{{ age }}"},
        {"name": "Static Name", "age": 30},
    ],
    "{{ dynamic_key }}": {"nested": "{{ nested_value }}"},
}
PARENT_YAML = """
name: parent
parent_value: inherited
"""

INHERIT_YAML = """
INHERIT: parent.yaml
name: child
value: "{{ parent_value }}"
"""


@pytest.fixture
def basic_jinja_env() -> minijinja.Environment:
    return minijinja.Environment(
        globals={
            "name": "John",
            "age": "25",
            "key": "dynamic_key",
            "dynamic_key": "section",
            "nested_value": "test",
            "parent_value": "parent_test",
        }
    )


@pytest.fixture
def temp_yaml_files(tmp_path: Path) -> tuple[Path, Path]:
    parent = tmp_path / "parent.yaml"
    child = tmp_path / "child.yaml"
    parent.write_text(PARENT_YAML)
    child.write_text(INHERIT_YAML)
    return parent, child


def test_basic_string_resolution(basic_jinja_env: minijinja.Environment) -> None:
    result = load_yaml(yaml.dump(BASIC_STR), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == "Hello John!"


def test_basic_dict_resolution(basic_jinja_env: minijinja.Environment) -> None:
    result = load_yaml(yaml.dump(BASIC_DICT), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == {"greeting": "Hello John!"}


def test_nested_dict_resolution(basic_jinja_env: minijinja.Environment) -> None:
    result = load_yaml(yaml.dump(NESTED_DICT), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == {"user": {"greeting": "Hello John!", "farewell": "Goodbye John!"}}


def test_list_resolution(basic_jinja_env: minijinja.Environment) -> None:
    result = load_yaml(yaml.dump(BASIC_LIST), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == ["Hello John!", "Hi John!"]


def test_dict_key_resolution(basic_jinja_env: minijinja.Environment) -> None:
    result = load_yaml(
        yaml.dump(DICT_WITH_TEMPLATE_KEYS),
        resolve_strings=True,
        resolve_dict_keys=True,
        jinja_env=basic_jinja_env,
    )
    assert result == {"dynamic_key": "value"}


def test_complex_nested_resolution(basic_jinja_env: minijinja.Environment) -> None:
    result = load_yaml(
        yaml.dump(COMPLEX_NESTED),
        resolve_strings=True,
        resolve_dict_keys=True,
        jinja_env=basic_jinja_env,
    )
    expected = {
        "users": [{"name": "John", "age": "25"}, {"name": "Static Name", "age": 30}],
        "section": {"nested": "test"},
    }
    assert result == expected


def test_no_resolution_when_disabled(basic_jinja_env: minijinja.Environment) -> None:
    result = load_yaml(yaml.dump(BASIC_DICT), resolve_strings=False, jinja_env=basic_jinja_env)
    assert result == BASIC_DICT


def test_resolution_without_env() -> None:
    """Should not resolve templates when no environment is provided."""
    result = load_yaml(yaml.dump(BASIC_DICT), resolve_strings=True)
    assert result == BASIC_DICT


def test_non_string_values(basic_jinja_env: minijinja.Environment) -> None:
    data = {"number": 42, "bool": True, "none": None}
    result = load_yaml(yaml.dump(data), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == data


def test_empty_string(basic_jinja_env: minijinja.Environment) -> None:
    result = load_yaml(yaml.dump(""), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == ""


def test_invalid_template(basic_jinja_env: minijinja.Environment) -> None:
    with pytest.raises(minijinja.TemplateError):
        load_yaml(yaml.dump("{{ invalid"), resolve_strings=True, jinja_env=basic_jinja_env)


def test_file_loading_with_resolution(
    basic_jinja_env: minijinja.Environment, temp_yaml_files: tuple[Path, Path]
) -> None:
    _parent_path, child_path = temp_yaml_files
    result = load_yaml_file(
        child_path, resolve_strings=True, resolve_inherit=True, jinja_env=basic_jinja_env
    )
    assert isinstance(result, dict)  # Add type check
    assert result.get("name") == "child"
    assert result.get("value") == "parent_test"


# Add a test for invalid YAML
def test_invalid_yaml_structure() -> None:
    invalid_yaml = """
    !!python/name:os.system
    - test
    """
    with pytest.raises(YAMLError):
        load_yaml(invalid_yaml)


def test_resolution_with_include_tag(
    tmp_path: Path, basic_jinja_env: minijinja.Environment
) -> None:
    include_file = tmp_path / "include.yaml"
    include_file.write_text("included_value: '{{ name }}'")

    main_yaml = f"""
    main: !include {include_file}
    direct: '{{{{ name }}}}'
    """

    result = load_yaml(
        dedent(main_yaml),
        resolve_strings=True,
        include_base_path=tmp_path,
        jinja_env=basic_jinja_env,
    )
    assert result["main"]["included_value"] == "John"
    assert result["direct"] == "John"


def test_resolution_with_env_tag(basic_jinja_env: minijinja.Environment) -> None:
    os.environ["TEST_ENV_VAR"] = "env_value"
    yaml_content = """
    env_var: !ENV TEST_ENV_VAR
    template: '{{ name }}'
    """
    result = load_yaml(dedent(yaml_content), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result["env_var"] == "env_value"
    assert result["template"] == "John"


def test_resolution_with_different_modes(basic_jinja_env: minijinja.Environment) -> None:
    for mode in ["unsafe", "full", "safe"]:
        result = load_yaml(
            yaml.dump(BASIC_DICT),
            mode=mode,  # type: ignore
            resolve_strings=True,
            jinja_env=basic_jinja_env,
        )
        assert result == {"greeting": "Hello John!"}


def test_resolution_with_fsspec_filesystem(basic_jinja_env: minijinja.Environment) -> None:
    # Write and load through the same path object: memory:// may be backed by a
    # per-instance store (upathtools registers IsolatedMemoryFileSystem).
    path = UPath("memory://test/test.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(BASIC_DICT))

    result = load_yaml_file(path, resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == {"greeting": "Hello John!"}


def test_unicode_strings(basic_jinja_env: minijinja.Environment) -> None:
    unicode_dict = {"greeting": "Hello {{ name }} 👋"}
    result = load_yaml(yaml.dump(unicode_dict), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == {"greeting": "Hello John 👋"}


def test_mixed_resolution(basic_jinja_env: minijinja.Environment) -> None:
    """Test mixing template and non-template strings."""
    mixed_dict = {
        "template": "Hello {{ name }}!",
        "static": "Hello World!",
        "nested": {"template": "{{ name }}", "static": "static"},
    }
    result = load_yaml(yaml.dump(mixed_dict), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == {
        "template": "Hello John!",
        "static": "Hello World!",
        "nested": {"template": "John", "static": "static"},
    }


def test_jinja_tag_constructor(basic_jinja_env: minijinja.Environment) -> None:
    """Test !JINJA tag constructor for scalars, sequences, and mappings."""
    loader_cls = utils.create_subclass(yaml.SafeLoader)
    register_jinja_constructor(loader_cls, basic_jinja_env)  # type: ignore[arg-type]

    yaml_text = dedent("""
        message: !JINJA "Hello {{ name }}!"
        items: !JINJA
          - "{{ name }}"
          - "{{ name | upper }}"
        mapping: !JINJA
          greeting: "Hi {{ name }}"
          age: "{{ age }}"
        untouched: "{{ name }}"
    """)
    result = yaml.load(yaml_text, Loader=loader_cls)
    assert result == {
        "message": "Hello John!",
        "items": ["John", "JOHN"],
        "mapping": {"greeting": "Hi John", "age": "25"},
        "untouched": "{{ name }}",
    }


def test_jinja_tag_constructor_without_env() -> None:
    """Test !JINJA tag returns raw template strings when env is None."""
    loader_cls = utils.create_subclass(yaml.SafeLoader)
    register_jinja_constructor(loader_cls, None)  # type: ignore[arg-type]

    result = yaml.load('message: !JINJA "Hello {{ name }}!"', Loader=loader_cls)
    assert result == {"message": "Hello {{ name }}!"}


def test_jinja_tag_constructor_error(basic_jinja_env: minijinja.Environment) -> None:
    """Test !JINJA tag wraps MiniJinja template errors in JinjaConstructionError."""
    loader_cls = utils.create_subclass(yaml.SafeLoader)
    register_jinja_constructor(loader_cls, basic_jinja_env)  # type: ignore[arg-type]

    with pytest.raises(JinjaConstructionError):
        yaml.load('bad: !JINJA "{{ invalid"', Loader=loader_cls)
