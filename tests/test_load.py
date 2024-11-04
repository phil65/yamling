"""Test suite for YAML loading functionality."""

# ruff: noqa: PLR2004

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from yamling.load import load_yaml_file


if TYPE_CHECKING:
    from yamling import yamltypes


@pytest.fixture
def yaml_files(tmp_path: Path) -> Path:
    """Create test YAML files in a temporary directory.

    Args:
        tmp_path: Pytest's temporary directory fixture

    Returns:
        Path to the temporary directory containing the test files
    """
    # Base configuration
    (tmp_path / "base.yaml").write_text(
        """
name: base
version: '1.0'
settings:
  timeout: 30
  retries: 3
""".lstrip()
    )

    # Feature configuration with single inheritance
    (tmp_path / "feature.yaml").write_text(
        """
INHERIT: base.yaml
name: feature
settings:
  timeout: 60
""".lstrip()
    )

    # Multi-inheritance configuration
    (tmp_path / "multi.yaml").write_text(
        """
INHERIT: [base.yaml, feature.yaml]
name: multi
extra: value
""".lstrip()
    )

    # Nested inheritance configuration
    (tmp_path / "nested.yaml").write_text(
        """
INHERIT: feature.yaml
name: nested
settings:
  new_setting: true
""".lstrip()
    )

    # Invalid configuration with non-existent parent
    (tmp_path / "invalid.yaml").write_text(
        """
INHERIT: nonexistent.yaml
name: invalid
""".lstrip()
    )

    # Circular inheritance configurations
    (tmp_path / "circular1.yaml").write_text(
        """
INHERIT: circular2.yaml
name: circular1
""".lstrip()
    )

    (tmp_path / "circular2.yaml").write_text(
        """
INHERIT: circular1.yaml
name: circular2
""".lstrip()
    )

    return tmp_path


def test_load_basic(yaml_files):
    """Test loading a YAML file without inheritance."""
    result = load_yaml_file(yaml_files / "base.yaml")
    assert result["name"] == "base"
    assert result["version"] == "1.0"
    assert result["settings"]["timeout"] == 30
    assert result["settings"]["retries"] == 3


def test_single_inheritance(yaml_files):
    """Test loading a YAML file with single inheritance."""
    result = load_yaml_file(yaml_files / "feature.yaml", resolve_inherit=True)
    assert result["name"] == "feature"  # Overridden value
    assert result["version"] == "1.0"  # Inherited value
    assert result["settings"]["timeout"] == 60  # Overridden value
    assert result["settings"]["retries"] == 3  # Inherited value


def test_multiple_inheritance(yaml_files):
    """Test loading a YAML file with multiple inheritance."""
    result = load_yaml_file(yaml_files / "multi.yaml", resolve_inherit=True)
    assert result["name"] == "multi"  # Last override wins
    assert result["version"] == "1.0"  # From base
    assert result["settings"]["timeout"] == 60  # From feature
    assert result["settings"]["retries"] == 3  # From base
    assert result["extra"] == "value"  # Own value


def test_nested_inheritance(yaml_files):
    """Test loading a YAML file with nested inheritance."""
    result = load_yaml_file(yaml_files / "nested.yaml", resolve_inherit=True)
    assert result["name"] == "nested"  # Own value
    assert result["version"] == "1.0"  # From base through feature
    assert result["settings"]["timeout"] == 60  # From feature
    assert result["settings"]["retries"] == 3  # From base
    assert result["settings"]["new_setting"] is True  # Own value


def test_inheritance_disabled(yaml_files):
    """Test that inheritance is not resolved when disabled."""
    result = load_yaml_file(yaml_files / "feature.yaml", resolve_inherit=False)
    assert result["name"] == "feature"
    assert "version" not in result
    assert result["settings"]["timeout"] == 60
    assert "retries" not in result["settings"]


def test_different_loader_modes(yaml_files):
    """Test loading with different safety modes."""
    modes: list[yamltypes.LoaderStr] = ["unsafe", "full", "safe"]
    for mode in modes:
        result = load_yaml_file(yaml_files / "base.yaml", mode=mode)
        assert result["name"] == "base"


def test_missing_parent_file(yaml_files):
    """Test error handling when parent file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_yaml_file(yaml_files / "invalid.yaml", resolve_inherit=True)


def test_inheritance_cycle_detection(yaml_files):
    """Test that circular inheritance is handled properly."""
    with pytest.raises(RecursionError):
        load_yaml_file(yaml_files / "circular1.yaml", resolve_inherit=True)
