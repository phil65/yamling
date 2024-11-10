# test_load_universal.py
from pathlib import Path

import pytest

from yamling.load_universal import ParsingError, load, load_file


# Test Constants
VALID_YAML = """
key: value
nested:
  inner: data
list:
  - item1
  - item2
"""

VALID_TOML = """
key = "value"
nested = { inner = "data" }
list = ["item1", "item2"]
"""


VALID_JSON = """
{
    "key": "value",
    "nested": {
        "inner": "data"
    },
    "list": ["item1", "item2"]
}
"""

VALID_INI = """
[section1]
key = value
key2 = value2

[section2]
other = data
"""

INVALID_YAML = "key: [invalid:"
INVALID_TOML = "key = invalid["
INVALID_JSON = "{invalid json"
INVALID_INI = "invalid ini"

EXPECTED_DATA = {"key": "value", "nested": {"inner": "data"}, "list": ["item1", "item2"]}

TEMP_DIR = "test_files"


# Fixtures
@pytest.fixture
def setup_temp_files(tmp_path: Path) -> Path:
    """Create temporary test files with different formats."""
    test_dir = tmp_path / TEMP_DIR
    test_dir.mkdir()

    # Create valid files
    (test_dir / "test.yaml").write_text(VALID_YAML)
    (test_dir / "test.yml").write_text(VALID_YAML)
    (test_dir / "test.toml").write_text(VALID_TOML)
    (test_dir / "test.json").write_text(VALID_JSON)
    (test_dir / "test.ini").write_text(VALID_INI)

    # Create invalid files
    (test_dir / "invalid.yaml").write_text(INVALID_YAML)
    (test_dir / "invalid.toml").write_text(INVALID_TOML)
    (test_dir / "invalid.json").write_text(INVALID_JSON)
    (test_dir / "invalid.ini").write_text(INVALID_INI)

    return test_dir


# Test load() function
def test_load_valid_yaml():
    result = load(VALID_YAML, "yaml")
    assert result == EXPECTED_DATA


def test_load_valid_toml():
    result = load(VALID_TOML, "toml")
    assert result == EXPECTED_DATA


def test_load_valid_json():
    result = load(VALID_JSON, "json")
    assert result == EXPECTED_DATA


def test_load_valid_ini():
    result = load(VALID_INI, "ini")
    assert isinstance(result, dict)
    assert "section1" in result
    assert "section2" in result
    assert result["section1"]["key"] == "value"


def test_load_invalid_yaml():
    with pytest.raises(ParsingError):
        load(INVALID_YAML, "yaml")


def test_load_invalid_toml():
    with pytest.raises(ParsingError):
        load(INVALID_TOML, "toml")


def test_load_invalid_json():
    with pytest.raises(ParsingError):
        load(INVALID_JSON, "json")


def test_load_invalid_ini():
    with pytest.raises(ParsingError):
        load(INVALID_INI, "ini")


def test_load_unsupported_format():
    with pytest.raises(ValueError, match="Unsupported format"):
        load(VALID_YAML, "unsupported")  # type: ignore


# Test load_file() function
def test_load_file_yaml(setup_temp_files: Path):
    result = load_file(setup_temp_files / "test.yaml")
    assert result == EXPECTED_DATA


def test_load_file_yml(setup_temp_files: Path):
    result = load_file(setup_temp_files / "test.yml")
    assert result == EXPECTED_DATA


def test_load_file_toml(setup_temp_files: Path):
    result = load_file(setup_temp_files / "test.toml")
    assert result == EXPECTED_DATA


def test_load_file_json(setup_temp_files: Path):
    result = load_file(setup_temp_files / "test.json")
    assert result == EXPECTED_DATA


def test_load_file_ini(setup_temp_files: Path):
    result = load_file(setup_temp_files / "test.ini")
    assert isinstance(result, dict)
    assert "section1" in result
    assert "section2" in result


def test_load_file_explicit_format(setup_temp_files: Path):
    result = load_file(setup_temp_files / "test.yaml", mode="yaml")
    assert result == EXPECTED_DATA


def test_load_file_nonexistent():
    with pytest.raises(FileNotFoundError):
        load_file("nonexistent.yaml")


def test_load_file_invalid_extension():
    with pytest.raises(ValueError, match="Could not determine format"):
        load_file("test.invalid")


def test_load_file_invalid_explicit_format():
    with pytest.raises(ValueError, match="Unsupported format"):
        load_file("test.yaml", mode="invalid")  # type: ignore


def test_load_file_invalid_content(setup_temp_files: Path):
    with pytest.raises(ParsingError):
        load_file(setup_temp_files / "invalid.yaml")


# Test edge cases
def test_load_empty_string():
    assert load("", "yaml") is None  # YAML treats empty string as None
    assert load("", "toml") == {}


def test_load_whitespace_only():
    assert load("   \n   ", "yaml") is None  # YAML treats whitespace as None
    assert load("   \n   ", "toml") == {}


def test_load_null_characters():
    with pytest.raises(ParsingError):
        load("key: value\0", "yaml")


# Test with various path types
def test_load_file_with_different_path_types(setup_temp_files: Path):
    # Test with string path
    result1 = load_file(str(setup_temp_files / "test.yaml"))
    assert result1 == EXPECTED_DATA

    # Test with Path object
    result2 = load_file(Path(setup_temp_files / "test.yaml"))
    assert result2 == EXPECTED_DATA
