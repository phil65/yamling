"""Test suite for YAML loading functionality.

This module tests the YAML loading capabilities including:
- Basic YAML loading
- Single and multiple inheritance
- Nested inheritance
- Different loader safety modes
- Error handling for missing files and circular dependencies
"""

# ruff: noqa: PLR2004

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from yamling.yaml_loaders import load_yaml_file


if TYPE_CHECKING:
    from yamling import yamltypes


@pytest.fixture
def yaml_files(tmp_path: Path) -> Path:
    """Create test YAML files in a temporary directory.

    Creates a test suite of YAML files with different inheritance patterns:
    - base.yaml: Base configuration without inheritance
    - feature.yaml: Single inheritance from base
    - multi.yaml: Multiple inheritance from base and feature
    - nested.yaml: Nested inheritance through feature
    - invalid.yaml: Invalid inheritance (missing parent)
    - circular1.yaml/circular2.yaml: Circular inheritance pattern

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


def test_load_basic(yaml_files: Path) -> None:
    """Test loading a YAML file without inheritance."""
    result = load_yaml_file(yaml_files / "base.yaml")
    assert result["name"] == "base"
    assert result["version"] == "1.0"
    assert result["settings"]["timeout"] == 30
    assert result["settings"]["retries"] == 3


def test_single_inheritance(yaml_files: Path) -> None:
    """Test loading a YAML file with single inheritance.

    !!! note
        Tests both value inheritance and override behavior.
    """
    result = load_yaml_file(yaml_files / "feature.yaml", resolve_inherit=True)
    assert result["name"] == "feature"  # Overridden value
    assert result["version"] == "1.0"  # Inherited value
    assert result["settings"]["timeout"] == 60  # Overridden value
    assert result["settings"]["retries"] == 3  # Inherited value


def test_multiple_inheritance(yaml_files: Path) -> None:
    """Test loading a YAML file with multiple inheritance.

    !!! note
        Verifies the inheritance precedence: last inherited file wins.
    """
    result = load_yaml_file(yaml_files / "multi.yaml", resolve_inherit=True)
    assert result["name"] == "multi"  # Last override wins
    assert result["version"] == "1.0"  # From base
    assert result["settings"]["timeout"] == 60  # From feature
    assert result["settings"]["retries"] == 3  # From base
    assert result["extra"] == "value"  # Own value


def test_nested_inheritance(yaml_files: Path) -> None:
    """Test loading a YAML file with nested inheritance.

    !!! note
        Verifies that multi-level inheritance works correctly.
    """
    result = load_yaml_file(yaml_files / "nested.yaml", resolve_inherit=True)
    assert result["name"] == "nested"  # Own value
    assert result["version"] == "1.0"  # From base through feature
    assert result["settings"]["timeout"] == 60  # From feature
    assert result["settings"]["retries"] == 3  # From base
    assert result["settings"]["new_setting"] is True  # Own value


def test_inheritance_disabled(yaml_files: Path) -> None:
    """Test that inheritance is not resolved when disabled.

    !!! note
        Ensures that INHERIT directives are ignored when resolve_inherit=False.
    """
    result = load_yaml_file(yaml_files / "feature.yaml", resolve_inherit=False)
    assert result["name"] == "feature"
    assert "version" not in result
    assert result["settings"]["timeout"] == 60
    assert "retries" not in result["settings"]


def test_different_loader_modes(yaml_files: Path) -> None:
    """Test loading with different safety modes.

    Tests all available loader modes:
    - unsafe: Allows all YAML tags and constructs
    - full: Allows safe YAML tags and constructs
    - safe: Most restrictive, only basic YAML constructs
    """
    modes: list[yamltypes.LoaderStr] = ["unsafe", "full", "safe"]
    for mode in modes:
        result = load_yaml_file(yaml_files / "base.yaml", mode=mode)
        assert result["name"] == "base"


def test_missing_parent_file(yaml_files: Path) -> None:
    """Test error handling when parent file doesn't exist.

    !!! warning
        Should raise FileNotFoundError when trying to resolve inheritance
        from non-existent files.
    """
    with pytest.raises(FileNotFoundError):
        load_yaml_file(yaml_files / "invalid.yaml", resolve_inherit=True)


def test_inheritance_cycle_detection(yaml_files: Path) -> None:
    """Test that circular inheritance is handled properly.

    !!! warning
        Should raise RecursionError when detecting circular inheritance
        relationships.
    """
    with pytest.raises(RecursionError):
        load_yaml_file(yaml_files / "circular1.yaml", resolve_inherit=True)


def test_nonexistent_file() -> None:
    """Test loading a non-existent file.

    !!! warning
        Should raise FileNotFoundError when the target file doesn't exist.
    """
    with pytest.raises(FileNotFoundError):
        load_yaml_file(Path("nonexistent.yaml"))
