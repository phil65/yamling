"""Tests for YAML loading functionality."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Any

import fsspec
import pytest

from yamling import yaml_loaders


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def temp_yaml_files(tmp_path: Path) -> dict[str, Path]:
    """Create temporary YAML files for testing."""
    files = {
        "base": dedent("""
            name: base
            value: 1
            nested:
              key: base_value
        """).strip(),
        "simple_inherit": dedent("""
            INHERIT: base.yaml
            name: child
            nested:
              new_key: child_value
        """).strip(),
        "multiple_inherit": dedent("""
            INHERIT:
              - base.yaml
              - other.yaml
            name: multi_child
        """).strip(),
        "other": dedent("""
            name: other
            other_value: 2
        """).strip(),
        "nested/nested_config": dedent("""
            INHERIT: ../base.yaml
            name: nested_child
        """).strip(),
    }

    # Create the files in the temporary directory
    for name, content in files.items():
        file_path = tmp_path / f"{name}.yaml"
        file_path.parent.mkdir(exist_ok=True, parents=True)
        file_path.write_text(content)

    return {name: tmp_path / f"{name}.yaml" for name in files}


def test_load_yaml_simple():
    """Test basic YAML loading without inheritance."""
    data = yaml_loaders.load_yaml("key: value")
    assert data == {"key": "value"}


def test_load_yaml_with_inherit_no_name():
    """Test that INHERIT is ignored when loading YAML without a file name."""
    yaml_content = dedent("""
        INHERIT: base.yaml
        key: value
    """).strip()
    data = yaml_loaders.load_yaml(yaml_content, resolve_inherit=True)
    assert data == {"INHERIT": "base.yaml", "key": "value"}


def test_load_yaml_file_simple(temp_yaml_files: dict[str, Path]):
    """Test loading a simple YAML file without inheritance."""
    data = yaml_loaders.load_yaml_file(temp_yaml_files["base"])
    assert data["name"] == "base"
    assert data["value"] == 1


def test_load_yaml_file_with_inherit(temp_yaml_files: dict[str, Path]):
    """Test loading a YAML file with single inheritance."""
    data = yaml_loaders.load_yaml_file(temp_yaml_files["simple_inherit"], resolve_inherit=True)
    assert data["name"] == "child"  # Overridden value
    assert data["value"] == 1  # Inherited value
    assert data["nested"]["key"] == "base_value"  # Inherited nested value
    assert data["nested"]["new_key"] == "child_value"  # New nested value
    assert "INHERIT" not in data  # INHERIT directive should be removed


def test_load_yaml_file_with_multiple_inherit(temp_yaml_files: dict[str, Path]):
    """Test loading a YAML file with multiple inheritance."""
    data = yaml_loaders.load_yaml_file(temp_yaml_files["multiple_inherit"], resolve_inherit=True)
    assert data["name"] == "multi_child"  # Last override wins
    assert data["value"] == 1  # From base
    assert data["other_value"] == 2  # From other  # noqa: PLR2004
    assert "INHERIT" not in data


def test_load_yaml_file_with_nested_inherit(temp_yaml_files: dict[str, Path]):
    """Test loading a YAML file with inheritance from a different directory."""
    data = yaml_loaders.load_yaml_file(
        temp_yaml_files["nested/nested_config"], resolve_inherit=True
    )
    assert data["name"] == "nested_child"
    assert data["value"] == 1  # Inherited from parent directory
    assert "INHERIT" not in data


def test_load_yaml_file_invalid_inherit(tmp_path: Path):
    """Test loading a YAML file with invalid inheritance path."""
    yaml_content = dedent("""
        INHERIT: nonexistent.yaml
        key: value
    """).strip()

    test_file = tmp_path / "test.yaml"
    test_file.write_text(yaml_content)

    with pytest.raises(FileNotFoundError):  # Should raise when file not found
        yaml_loaders.load_yaml_file(test_file, resolve_inherit=True)


def test_load_yaml_with_file_object(temp_yaml_files: dict[str, Path]):
    """Test loading YAML with inheritance using a file object."""
    with temp_yaml_files["simple_inherit"].open() as f:
        data = yaml_loaders.load_yaml(f, resolve_inherit=True)
        assert data["name"] == "child"
        assert data["value"] == 1
        assert "INHERIT" not in data


def test_empty_inherit(tmp_path: Path):
    """Test handling of empty INHERIT directive."""
    yaml_content = dedent("""
        INHERIT:
        key: value
    """).strip()

    test_file = tmp_path / "test.yaml"
    test_file.write_text(yaml_content)

    data = yaml_loaders.load_yaml_file(test_file, resolve_inherit=True)
    assert data == {"key": "value"}


def test_inherit_cycle_detection(tmp_path: Path, recursion_limit: Any):
    """Test that circular inheritance is handled properly."""
    # Create files that inherit from each other
    file1_content = dedent("""
        INHERIT: file2.yaml
        key1: value1
    """).strip()

    file2_content = dedent("""
        INHERIT: file1.yaml
        key2: value2
    """).strip()

    (tmp_path / "file1.yaml").write_text(file1_content)
    (tmp_path / "file2.yaml").write_text(file2_content)

    with recursion_limit(100), pytest.raises(RecursionError):
        yaml_loaders.load_yaml_file(tmp_path / "file1.yaml", resolve_inherit=True)


def test_load_yaml_file_with_fsspec(temp_yaml_files: dict[str, Path]):
    """Test loading YAML files using fsspec filesystem."""
    fs = fsspec.filesystem("file")
    data = yaml_loaders.load_yaml_file(
        temp_yaml_files["simple_inherit"], resolve_inherit=True, include_base_path=fs
    )
    assert data["name"] == "child"
    assert data["value"] == 1


def test_load_yaml_with_named_stringio(temp_yaml_files: dict[str, Path]):
    """Test loading YAML from a string buffer with a name attribute."""
    from io import StringIO

    # Create a StringIO object with a name attribute
    yaml_content = dedent("""
        INHERIT: base.yaml
        name: from_stringio
        custom: value
    """).strip()

    # Create a custom StringIO-like class with name attribute
    class NamedStringIO(StringIO):
        def __init__(self, content: str, name: str):
            super().__init__(content)
            self.name = name

    # Create the buffer with name pointing to the directory of simple_inherit.yaml
    buffer = NamedStringIO(
        yaml_content,
        str(temp_yaml_files["simple_inherit"]),  # This sets the base directory context
    )

    data = yaml_loaders.load_yaml(buffer, resolve_inherit=True)
    assert data["name"] == "from_stringio"  # Our override
    assert data["value"] == 1  # Inherited from base.yaml
    assert data["custom"] == "value"  # Our new value
    assert "INHERIT" not in data


def test_load_yaml_with_file_object_inheritance(temp_yaml_files: dict[str, Path]):
    """Test loading YAML using a file object with inheritance."""
    with temp_yaml_files["simple_inherit"].open() as f:
        data = yaml_loaders.load_yaml(f, resolve_inherit=True)
        assert data["name"] == "child"
        assert data["value"] == 1  # Inherited from base.yaml
        assert data["nested"]["key"] == "base_value"  # Inherited nested value
        assert data["nested"]["new_key"] == "child_value"
        assert "INHERIT" not in data


def test_load_yaml_with_pathlib_path(temp_yaml_files: dict[str, Path]):
    """Test loading YAML from a Path object with inheritance."""
    path = temp_yaml_files["simple_inherit"]
    with path.open() as f:
        data = yaml_loaders.load_yaml(f, resolve_inherit=True)
        assert data["name"] == "child"
        assert data["value"] == 1
        assert "INHERIT" not in data


def test_load_yaml_without_name_attribute():
    """Test that INHERIT is ignored for objects without name attribute."""
    from io import StringIO

    yaml_content = dedent("""
        INHERIT: base.yaml
        name: test
        value: 1
    """).strip()

    # Regular StringIO without name attribute
    buffer = StringIO(yaml_content)

    data = yaml_loaders.load_yaml(buffer, resolve_inherit=True)
    assert data["INHERIT"] == "base.yaml"  # INHERIT should remain in data
    assert data["name"] == "test"
    assert data["value"] == 1


def test_load_yaml_with_invalid_named_file():
    """Test handling of invalid file paths in named file objects."""
    from io import StringIO

    class NamedStringIO(StringIO):
        def __init__(self, content: str, name: str):
            super().__init__(content)
            self.name = name

    yaml_content = dedent("""
        INHERIT: base.yaml
        name: test
    """).strip()

    # Create buffer with non-existent path
    buffer = NamedStringIO(yaml_content, "/nonexistent/path/file.yaml")

    with pytest.raises(FileNotFoundError):  # Should raise when trying to resolve INHERIT
        yaml_loaders.load_yaml(buffer, resolve_inherit=True)


def test_load_yaml_with_bytes_io(temp_yaml_files: dict[str, Path]):
    """Test loading YAML from BytesIO with name attribute."""
    from io import BytesIO

    class NamedBytesIO(BytesIO):
        def __init__(self, content: bytes, name: str):
            super().__init__(content)
            self.name = name

    yaml_content = dedent("""
        INHERIT: base.yaml
        name: from_bytesio
        custom: value
    """).strip()

    buffer = NamedBytesIO(yaml_content.encode("utf-8"), str(temp_yaml_files["simple_inherit"]))

    data = yaml_loaders.load_yaml(buffer, resolve_inherit=True)
    assert data["name"] == "from_bytesio"
    assert data["value"] == 1  # Inherited from base.yaml
    assert data["custom"] == "value"
    assert "INHERIT" not in data


def test_load_yaml_multiple_inherit_order(tmp_path: Path):
    """Test that multiple inheritance follows the correct merge order."""
    # Create test files
    base_content = dedent("""
        name: base
        value: 1
        nested:
          key1: base
          key2: base
    """).strip()

    middle_content = dedent("""
        name: middle
        nested:
          key2: middle
          key3: middle
    """).strip()

    top_content = dedent("""
        INHERIT:
          - base.yaml
          - middle.yaml
        nested:
          key3: top
          key4: top
    """).strip()

    (tmp_path / "base.yaml").write_text(base_content)
    (tmp_path / "middle.yaml").write_text(middle_content)
    (tmp_path / "top.yaml").write_text(top_content)

    data = yaml_loaders.load_yaml_file(tmp_path / "top.yaml", resolve_inherit=True)

    # Check merge order (last file in INHERIT list is merged last)
    assert data["name"] == "middle"  # From middle.yaml
    assert data["value"] == 1  # From base.yaml
    assert data["nested"] == {
        "key1": "base",  # From base.yaml
        "key2": "middle",  # Overridden by middle.yaml
        "key3": "top",  # Overridden by top.yaml
        "key4": "top",  # Added by top.yaml
    }


def test_load_yaml_multiple_inherit_empty_list(tmp_path: Path):
    """Test handling of empty list in multiple inheritance."""
    yaml_content = dedent("""
        INHERIT: []
        key: value
    """).strip()

    test_file = tmp_path / "test.yaml"
    test_file.write_text(yaml_content)

    data = yaml_loaders.load_yaml_file(test_file, resolve_inherit=True)
    assert data == {"key": "value"}


def test_load_yaml_multiple_inherit_mixed_types(tmp_path: Path):
    """Test that inheritance fails gracefully with mixed types in INHERIT list."""
    yaml_content = dedent("""
        INHERIT:
          - base.yaml
          - 123
          - null
        key: value
    """).strip()

    base_content = "name: base"

    (tmp_path / "base.yaml").write_text(base_content)
    test_file = tmp_path / "test.yaml"
    test_file.write_text(yaml_content)

    with pytest.raises(TypeError):
        yaml_loaders.load_yaml_file(test_file, resolve_inherit=True)


def test_load_yaml_multiple_inherit_nested(tmp_path: Path):
    """Test nested multiple inheritance."""
    # Create test files
    base_content = dedent("""
        name: base
        value: 1
    """).strip()

    middle_content = dedent("""
        INHERIT: base.yaml
        name: middle
        middle_value: 2
    """).strip()

    top_content = dedent("""
        INHERIT:
          - base.yaml
          - middle.yaml
        top_value: 3
    """).strip()

    (tmp_path / "base.yaml").write_text(base_content)
    (tmp_path / "middle.yaml").write_text(middle_content)
    (tmp_path / "top.yaml").write_text(top_content)

    data = yaml_loaders.load_yaml_file(tmp_path / "top.yaml", resolve_inherit=True)

    assert data["name"] == "middle"
    assert data["value"] == 1
    assert data["middle_value"] == 2  # noqa: PLR2004
    assert data["top_value"] == 3  # noqa: PLR2004
    assert "INHERIT" not in data


def test_load_yaml_multiple_inherit_nonexistent(tmp_path: Path):
    """Test handling of nonexistent files in multiple inheritance."""
    yaml_content = dedent("""
        INHERIT:
          - base.yaml
          - nonexistent.yaml
        key: value
    """).strip()

    base_content = "name: base"

    (tmp_path / "base.yaml").write_text(base_content)
    test_file = tmp_path / "test.yaml"
    test_file.write_text(yaml_content)

    with pytest.raises(FileNotFoundError):
        yaml_loaders.load_yaml_file(test_file, resolve_inherit=True)
