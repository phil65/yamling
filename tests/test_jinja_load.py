import os
from textwrap import dedent

import fsspec
import jinja2
import pytest
import yaml

from yamling import YAMLError
from yamling.yaml_loaders import load_yaml, load_yaml_file


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
def basic_jinja_env():
    env = jinja2.Environment()
    env.globals.update({
        "name": "John",
        "age": "25",
        "key": "dynamic_key",
        "dynamic_key": "section",
        "nested_value": "test",
        "parent_value": "parent_test",
    })
    return env


@pytest.fixture
def temp_yaml_files(tmp_path):
    parent = tmp_path / "parent.yaml"
    child = tmp_path / "child.yaml"
    parent.write_text(PARENT_YAML)
    child.write_text(INHERIT_YAML)
    return parent, child


def test_basic_string_resolution(basic_jinja_env):
    result = load_yaml(yaml.dump(BASIC_STR), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == "Hello John!"


def test_basic_dict_resolution(basic_jinja_env):
    result = load_yaml(yaml.dump(BASIC_DICT), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == {"greeting": "Hello John!"}


def test_nested_dict_resolution(basic_jinja_env):
    result = load_yaml(yaml.dump(NESTED_DICT), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == {"user": {"greeting": "Hello John!", "farewell": "Goodbye John!"}}


def test_list_resolution(basic_jinja_env):
    result = load_yaml(yaml.dump(BASIC_LIST), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == ["Hello John!", "Hi John!"]


def test_dict_key_resolution(basic_jinja_env):
    result = load_yaml(
        yaml.dump(DICT_WITH_TEMPLATE_KEYS),
        resolve_strings=True,
        resolve_dict_keys=True,
        jinja_env=basic_jinja_env,
    )
    assert result == {"dynamic_key": "value"}


def test_complex_nested_resolution(basic_jinja_env):
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


def test_no_resolution_when_disabled(basic_jinja_env):
    result = load_yaml(yaml.dump(BASIC_DICT), resolve_strings=False, jinja_env=basic_jinja_env)
    assert result == BASIC_DICT


def test_resolution_without_env():
    """Should not resolve templates when no environment is provided."""
    result = load_yaml(yaml.dump(BASIC_DICT), resolve_strings=True)
    assert result == BASIC_DICT


def test_non_string_values(basic_jinja_env):
    data = {"number": 42, "bool": True, "none": None}
    result = load_yaml(yaml.dump(data), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == data


def test_empty_string(basic_jinja_env):
    result = load_yaml(yaml.dump(""), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == ""


def test_invalid_template(basic_jinja_env):
    with pytest.raises(jinja2.TemplateError):
        load_yaml(yaml.dump("{{ invalid"), resolve_strings=True, jinja_env=basic_jinja_env)


def test_file_loading_with_resolution(basic_jinja_env, temp_yaml_files):
    _parent_path, child_path = temp_yaml_files
    result = load_yaml_file(
        child_path, resolve_strings=True, resolve_inherit=True, jinja_env=basic_jinja_env
    )
    assert isinstance(result, dict)  # Add type check
    assert result.get("name") == "child"
    assert result.get("value") == "parent_test"


# Add a test for invalid YAML
def test_invalid_yaml_structure():
    invalid_yaml = """
    !!python/name:os.system
    - test
    """
    with pytest.raises(YAMLError):
        load_yaml(invalid_yaml)


def test_resolution_with_include_tag(tmp_path, basic_jinja_env):
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


def test_resolution_with_env_tag(basic_jinja_env):
    os.environ["TEST_ENV_VAR"] = "env_value"
    yaml_content = """
    env_var: !ENV TEST_ENV_VAR
    template: '{{ name }}'
    """
    result = load_yaml(dedent(yaml_content), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result["env_var"] == "env_value"
    assert result["template"] == "John"


def test_resolution_with_different_modes(basic_jinja_env):
    for mode in ["unsafe", "full", "safe"]:
        result = load_yaml(
            yaml.dump(BASIC_DICT),
            mode=mode,  # type: ignore
            resolve_strings=True,
            jinja_env=basic_jinja_env,
        )
        assert result == {"greeting": "Hello John!"}


def test_resolution_with_fsspec_filesystem(basic_jinja_env):
    fs = fsspec.filesystem("memory")
    fs.makedirs("test", exist_ok=True)
    fs.write_text("test/test.yaml", yaml.dump(BASIC_DICT))

    result = load_yaml_file(
        "memory://test/test.yaml", resolve_strings=True, jinja_env=basic_jinja_env
    )
    assert result == {"greeting": "Hello John!"}


def test_unicode_strings(basic_jinja_env):
    unicode_dict = {"greeting": "Hello {{ name }} 👋"}
    result = load_yaml(yaml.dump(unicode_dict), resolve_strings=True, jinja_env=basic_jinja_env)
    assert result == {"greeting": "Hello John 👋"}


def test_mixed_resolution(basic_jinja_env):
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
