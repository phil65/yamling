from __future__ import annotations

import json
import tomllib
from typing import TYPE_CHECKING

import pytest
import yaml

from yamling.dump_universal import DumpingError, dump, dump_file


if TYPE_CHECKING:
    from pathlib import Path


# Constants
SAMPLE_DICT = {"key": "value", "nested": {"inner": "content"}}
SAMPLE_LIST = [1, 2, 3, {"key": "value"}]
SAMPLE_INI_DICT = {"section1": {"key1": "value1"}, "section2": {"key2": "value2"}}
INVALID_INI_DICT = {"not_nested": "invalid"}
NESTED_DICT = {"level1": {"level2": {"level3": "value"}}}
SPECIAL_CHARS_DICT = {"special": "!@#$%^&*()"}
UNICODE_DICT = {"unicode": "こんにちは"}
EMPTY_DICT: dict[str, str] = {}
LARGE_DICT = {str(i): i for i in range(1000)}

# File extension mappings for testing
EXTENSION_TEST_CASES = [
    (".yaml", "yaml"),
    (".yml", "yaml"),
    (".toml", "toml"),
    (".tml", "toml"),
    (".json", "json"),
    (".jsonc", "json"),
    (".ini", "ini"),
    (".cfg", "ini"),
    (".conf", "ini"),
    (".config", "ini"),
    (".properties", "ini"),
    (".cnf", "ini"),
    (".env", "ini"),
]


@pytest.fixture
def temp_file(tmp_path) -> Path:
    """Fixture that provides a temporary file path."""
    return tmp_path / "test_file"


def test_dump_yaml_basic():
    result = dump(SAMPLE_DICT, "yaml")
    assert yaml.safe_load(result) == SAMPLE_DICT


def test_dump_yaml_list():
    result = dump(SAMPLE_LIST, "yaml")
    assert yaml.safe_load(result) == SAMPLE_LIST


def test_dump_yaml_nested():
    result = dump(NESTED_DICT, "yaml")
    assert yaml.safe_load(result) == NESTED_DICT


def test_dump_toml_basic():
    result = dump(SAMPLE_DICT, "toml")
    assert tomllib.loads(result) == SAMPLE_DICT


def test_dump_json_basic():
    result = dump(SAMPLE_DICT, "json")
    assert json.loads(result) == SAMPLE_DICT


def test_dump_ini_basic():
    result = dump(SAMPLE_INI_DICT, "ini")
    assert "[section1]" in result
    assert "key1 = value1" in result
    assert "[section2]" in result
    assert "key2 = value2" in result


def test_dump_ini_invalid_structure():
    with pytest.raises(DumpingError, match="INI format requires dict of dicts structure"):
        dump(INVALID_INI_DICT, "ini")


def test_dump_unsupported_format():
    with pytest.raises(ValueError, match="Unsupported format: invalid"):
        dump(SAMPLE_DICT, "invalid")  # type: ignore


def test_dump_special_characters():
    for format_type in ["yaml", "json", "toml"]:
        result = dump(SPECIAL_CHARS_DICT, format_type)  # type: ignore
        assert "!@#$%^&*()" in result


def test_dump_unicode():
    for format_type in ["yaml", "json", "toml"]:
        result = dump(UNICODE_DICT, format_type)  # type: ignore
        # Check if the value is present either as Unicode or encoded
        assert "こんにちは" in result or "\\u3053\\u3093\\u306B\\u3061\\u306F" in result


def test_dump_empty_dict():
    for format_type in ["yaml", "json", "toml"]:
        result = dump(EMPTY_DICT, format_type)  # type: ignore
        # Different formats might represent empty dict differently
        assert result.strip() in ["{}", "{}\\n", ""]


def test_dump_large_dict():
    for format_type in ["yaml", "json", "toml"]:
        result = dump(LARGE_DICT, format_type)  # type: ignore
        assert result


@pytest.mark.parametrize(("extension", "expected_format"), EXTENSION_TEST_CASES)
def test_dump_file_auto_detection(temp_file: Path, extension: str, expected_format: str):
    file_path = temp_file.with_suffix(extension)
    test_data = SAMPLE_INI_DICT if expected_format == "ini" else SAMPLE_DICT
    dump_file(test_data, file_path)
    assert file_path.exists()
    content = file_path.read_text()
    assert content.strip()


def test_dump_file_unknown_extension(temp_file: Path):
    file_path = temp_file.with_suffix(".unknown")
    with pytest.raises(ValueError, match="Could not determine format"):
        dump_file(SAMPLE_DICT, file_path)


def test_dump_file_explicit_format(temp_file: Path):
    file_path = temp_file.with_suffix(".txt")
    dump_file(SAMPLE_DICT, file_path, mode="json")
    content = file_path.read_text()
    assert json.loads(content) == SAMPLE_DICT


def test_dump_file_permission_error(tmp_path: Path):
    test_file = tmp_path / "test.yaml"
    test_file.touch(mode=0o000)  # Create file with no permissions
    try:
        with pytest.raises(DumpingError, match="Failed to write file"):
            dump_file(SAMPLE_DICT, test_file)
    finally:
        test_file.chmod(0o666)  # Reset permissions for cleanup


def test_dump_file_directory_not_exists():
    with pytest.raises(DumpingError):
        dump_file(SAMPLE_DICT, "/nonexistent/directory/file.yaml")


@pytest.mark.parametrize("format_type", ["yaml", "json", "toml", "ini"])
def test_dump_file_with_kwargs(format_type: str, tmp_path: Path):
    test_file = tmp_path / f"test.{format_type}"
    if format_type == "json":
        # Remove indent parameter as orjson doesn't support it
        dump_file(SAMPLE_DICT, test_file)
    elif format_type == "yaml":
        dump_file(SAMPLE_DICT, test_file, default_flow_style=False)
    elif format_type == "ini":
        dump_file(SAMPLE_INI_DICT, test_file, default_section="DEFAULT")
    else:
        dump_file(SAMPLE_DICT, test_file)
    assert test_file.exists()


def test_dump_invalid_data():
    class UnserializableObject:
        pass

    with pytest.raises(DumpingError):
        dump(UnserializableObject(), "json")


def test_dump_file_with_path_object(temp_file: Path):
    file_path = temp_file.with_suffix(".yaml")
    dump_file(SAMPLE_DICT, file_path)
    assert file_path.exists()
    assert yaml.safe_load(file_path.read_text()) == SAMPLE_DICT


def test_dump_nested_lists():
    nested_list = [[1, 2], [3, 4], {"key": [5, 6]}]
    # Test only YAML and JSON which support top-level lists
    for format_type in ["yaml", "json"]:
        result = dump(nested_list, format_type)  # type: ignore
        assert result

    # For TOML, wrap the list in a dictionary
    result = dump({"array": nested_list}, "toml")
    assert result
