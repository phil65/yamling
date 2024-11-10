from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
import yaml
import yaml_include

import yamling
from yamling import yaml_loaders


if TYPE_CHECKING:
    import pathlib


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


def test_invalid_yaml():
    with pytest.raises(yamling.YAMLError):
        yamling.load_yaml("{invalid: yaml: content")


def test_empty_yaml():
    assert yamling.load_yaml("") is None
    assert yamling.load_yaml("   ") is None


def test_safe_loader():
    loader = yaml_loaders.get_safe_loader(yaml.SafeLoader)
    assert loader.yaml_constructors["!relative"] is not None


def test_get_include_constructor():
    """Test get_include_constructor with different filesystem types."""
    constructor = yaml_loaders.get_include_constructor()
    assert isinstance(constructor, yaml_include.Constructor)

    constructor = yaml_loaders.get_include_constructor(fs="file")
    assert isinstance(constructor, yaml_include.Constructor)

    with pytest.raises(TypeError):
        yaml_loaders.get_include_constructor(fs=123)  # Invalid type


def test_get_loader():
    """Test get_loader with different configurations."""
    loader = yaml_loaders.get_loader(yaml.SafeLoader)
    assert loader.yaml_constructors["!include"] is not None
    assert loader.yaml_constructors["!ENV"] is not None

    loader = yaml_loaders.get_loader(yaml.SafeLoader, enable_include=False)
    assert "!include" not in loader.yaml_constructors

    loader = yaml_loaders.get_loader(yaml.SafeLoader, enable_env=False)
    assert "!ENV" not in loader.yaml_constructors


def test_load_yaml_with_include(tmp_path: pathlib.Path):
    """Test load_yaml with include path."""
    include_file = tmp_path / "include.yaml"
    include_file.write_text("included: true")

    yaml_str = f"!include {include_file!s}"
    result = yamling.load_yaml(yaml_str, include_base_path=tmp_path)
    assert result == {"included": True}


def test_load_yaml_with_modes():
    """Test load_yaml with different modes."""
    yaml_str = "!!python/name:os.system"
    with pytest.raises(yaml.constructor.ConstructorError):
        yamling.load_yaml(yaml_str, mode="safe")

    assert yamling.load_yaml(yaml_str, mode="unsafe") is os.system


if __name__ == "__main__":
    pytest.main([__file__])
