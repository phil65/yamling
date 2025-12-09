"""Demo of enhanced YAML error rendering capabilities.

This example shows how yamling now provides beautiful, informative error messages
through YAMLError that inherits from yaml.YAMLError.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import yamling


def demo_basic_enhanced_error():
    """Demonstrate enhanced YAML error that can render itself."""
    print("\n" + "=" * 80)
    print("DEMO 1: YAML Error with Self-Rendering")
    print("=" * 80)

    bad_yaml = """
config:
  host: localhost
  port: 8080
  settings: {invalid, syntax
"""

    try:
        yamling.load_yaml(bad_yaml, mode="safe")
    except yamling.YAMLError as e:  # Still catches YAMLError!
        print("Caught YAMLError - but it's actually yamling.YAMLError:")
        print(f"Type: {type(e).__name__}")
        print("\nRendering the error:")
        e.render()  # Beautiful output to stderr


def demo_format_as_string():
    """Demonstrate formatting error as a string."""
    print("\n" + "=" * 80)
    print("DEMO 2: Format YAML Error as String")
    print("=" * 80)

    bad_yaml = """
servers:
  - name: web-01
    roles: [api, worker
"""

    try:
        yamling.load_yaml(bad_yaml, mode="safe")
    except yamling.YAMLError as e:
        formatted = e.format()
        print("Formatted error as string:")
        print(formatted)


def demo_file_error_with_path():
    """Demonstrate error with file path context."""
    print("\n" + "=" * 80)
    print("DEMO 3: File Error with Path Context")
    print("=" * 80)

    with TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "app_config.yaml"

        bad_content = """
application:
  name: MyApp
  version: 1.0.0
  features:
    - authentication
    - logging
    - monitoring: [metrics, traces
  database:
    enabled: true
"""
        config_file.write_text(bad_content)

        try:
            yamling.load_yaml_file(config_file, mode="safe")
        except yamling.YAMLError as e:
            print(f"Error in {config_file.name}:")
            e.render()


def demo_custom_enhanced_error():
    """Demonstrate creating custom enhanced error with help text."""
    print("\n" + "=" * 80)
    print("DEMO 4: Custom YAML Error with Help Text")
    print("=" * 80)

    bad_yaml = """
database:
  connections:
    primary: {host: localhost, port: 5432
    replica: {host: backup.local, port: 5432}
"""

    try:
        yamling.load_yaml(bad_yaml, mode="safe")
    except yamling.YAMLError as original_error:
        # Create our own yaml error with custom context
        yaml_error = yamling.YAMLError(
            original_error,
            doc_path="config/database.yaml",
            context_lines=4,
            extra_help=[
                "Database configuration must use valid YAML syntax",
                "Check that all braces and brackets are properly matched",
                "Consider using block style instead of flow style for complex objects",
            ],
        )

        print("Custom yaml error with help text:")
        yaml_error.render()


def demo_multiple_error_scenarios():
    """Demonstrate various error scenarios."""
    print("\n" + "=" * 80)
    print("DEMO 5: Multiple Error Scenarios")
    print("=" * 80)

    error_examples = [
        ("Unclosed bracket", "data: [1, 2, 3"),
        ("Unclosed brace", "config: {key: value"),
        ("Invalid indentation", "root:\n  child:\n wrong_indent: value"),
        ("Missing colon", "key value"),
    ]

    for title, yaml_content in error_examples:
        print(f"\n--- {title} ---")
        try:
            yamling.load_yaml(yaml_content, mode="safe")
        except yamling.YAMLError as e:
            # Just show the formatted version inline
            formatted = e.format()
            print(formatted[:200] + "..." if len(formatted) > 200 else formatted)  # noqa: PLR2004


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  YAML Error Demo".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")

    print("\nYamling now throws YAMLError that:")
    print("• Inherits from yaml.YAMLError (existing code still works)")
    print("• Can render itself beautifully with .render()")
    print("• Can format itself as string with .format()")
    print("• Includes file path and context information")

    demo_basic_enhanced_error()
    demo_format_as_string()
    demo_file_error_with_path()
    demo_custom_enhanced_error()
    demo_multiple_error_scenarios()

    print("\n" + "=" * 80)
    print("Key Benefits:")
    print("• No extra parameters needed - errors are enhanced by default")
    print("• Backward compatible - still catches yaml.YAMLError")
    print("• Clean API - the error knows how to render itself")
    print("• Flexible - create custom yaml errors when needed")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
