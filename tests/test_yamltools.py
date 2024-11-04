import os
import pathlib

import pytest
import yaml

import yamling
from yamling import load


def test_basic_load():
    assert yamling.load_yaml("foo: bar") == {"foo": "bar"}
    assert yamling.load_yaml("[1, 2, 3]") == [1, 2, 3]
    assert yamling.load_yaml("42") == 42  # noqa: PLR2004


def test_load_modes():
    yaml_str = "!!python/name:os.system"
    with pytest.raises(yaml.constructor.ConstructorError):
        yamling.load_yaml(yaml_str, mode="safe")
    assert yamling.load_yaml(yaml_str, mode="unsafe") is os.system


def test_env_tag():
    os.environ["TEST_VAR"] = "42"
    assert yamling.load_yaml("!ENV TEST_VAR") == 42  # noqa: PLR2004
    assert yamling.load_yaml("!ENV [NONEXISTENT]") is None
    assert yamling.load_yaml("!ENV [NONEXISTENT, 'default']") == "default"


@pytest.fixture
def temp_yaml_file(tmp_path: pathlib.Path) -> pathlib.Path:
    content = "test: value"
    file_path = tmp_path / "test.yaml"
    file_path.write_text(content)
    return file_path


def test_include_constructor(temp_yaml_file: pathlib.Path):
    yaml_str = f"!include {temp_yaml_file!s}"
    result = yamling.load_yaml(yaml_str)
    assert result == {"test": "value"}


def test_dump_yaml():
    data = {"a": 1, "b": [2, 3, 4], "c": {"d": 5}}
    dumped = yamling.dump_yaml(data)
    assert yamling.load_yaml(dumped) == data


def test_class_mapping():
    from collections import OrderedDict

    data = OrderedDict([("b", 2), ("a", 1)])
    # Test with OrderedDict mapping using dict's representation
    dumped = yamling.dump_yaml(data, class_mappings={OrderedDict: dict})
    assert "!!" not in dumped
    # Test without mapping (default OrderedDict representation)
    dumped_no_mapping = yamling.dump_yaml(data)
    expected_no_mapping = (
        "!!python/object/apply:collections.OrderedDict\n"
        "- - - b\n"
        "    - 2\n"
        "  - - a\n"
        "    - 1\n"
    )
    assert dumped_no_mapping == expected_no_mapping


# Remove or update test_object_roundtrip since it's now covered by test_class_mapping
def test_object_roundtrip():
    from collections import OrderedDict

    data = OrderedDict([("b", 2), ("a", 1)])
    dumped = yamling.dump_yaml(data)
    assert isinstance(yamling.load_yaml(dumped), OrderedDict)


def test_invalid_yaml():
    with pytest.raises(yamling.YAMLError):
        yamling.load_yaml("{invalid: yaml: content")


def test_empty_yaml():
    assert yamling.load_yaml("") is None
    assert yamling.load_yaml("   ") is None


def test_safe_loader():
    loader = load.get_safe_loader(yaml.SafeLoader)
    assert loader.yaml_constructors["!relative"] is not None


if __name__ == "__main__":
    pytest.main([__file__])
