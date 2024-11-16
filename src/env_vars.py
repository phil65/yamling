"""Module for dictionary flattening and environment variable manipulation."""

from __future__ import annotations

import os
from typing import Any


def flatten_dict(
    data: dict[str, Any],
    separator: str = "_",
    parent_key: str = "",
) -> dict[str, str]:
    """Flatten a nested dictionary into a single level dictionary.

    Args:
        data: Dictionary to flatten
        separator: Separator between nested keys
        parent_key: Key from parent recursion level

    Returns:
        Flattened dictionary with string values
    """
    result: dict[str, str] = {}

    for key, value in data.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key

        if isinstance(value, dict):
            result.update(flatten_dict(value, separator, new_key))
        else:
            result[new_key] = str(value)

    return result


def unflatten_dict(
    data: dict[str, Any],
    separator: str = "_",
) -> dict[str, Any]:
    """Convert a flat dictionary with separated keys back into a nested dictionary.

    Args:
        data: Flattened dictionary to convert
        separator: Separator used between nested keys

    Returns:
        Nested dictionary
    """
    result: dict[str, Any] = {}

    for key, value in data.items():
        parts = key.split(separator)
        target = result

        # Navigate to the final nesting level
        for part in parts[:-1]:
            target = target.setdefault(part, {})

        # Set the value at the final level
        target[parts[-1]] = value

    return result


def dict_to_env_vars(
    data: dict[str, Any],
    prefix: str = "",
    separator: str = "_",
) -> dict[str, str]:
    """Convert a nested dictionary into environment variables format.

    Args:
        data: Dictionary to convert
        prefix: Optional prefix for env var names
        separator: Separator between nested keys

    Returns:
        Dictionary with env var names as keys and string values
    """
    flat_dict = flatten_dict(data, separator)
    return {f"{prefix}{k}".upper(): v for k, v in flat_dict.items()}


def env_vars_to_dict(
    prefix: str,
    separator: str = "_",
    unflatten: bool = False,
) -> dict[str, Any]:
    """Read environment variables with given prefix into a dictionary.

    Args:
        prefix: Prefix to filter environment variables
        separator: Separator used between nested keys
        unflatten: Whether to convert flat dict back to nested structure

    Returns:
        Dictionary with env var names (without prefix) as keys and their values
    """
    normalized_prefix = prefix.upper()
    result: dict[str, str] = {}

    for key, value in os.environ.items():
        if key.startswith(normalized_prefix):
            # Remove prefix from key
            clean_key = key[len(normalized_prefix) :].lstrip("_")
            result[clean_key] = value

    return unflatten_dict(result, separator) if unflatten else result


if __name__ == "__main__":
    nested_dict = {
        "database": {
            "host": "localhost",
            "port": 5432,
            "credentials": {"username": "admin", "password": "secret"},
        },
        "debug": True,
    }

    flat = flatten_dict(nested_dict)
    nested_again = unflatten_dict(flat)
    # Back to original structure

    # Environment variables
    env_vars = dict_to_env_vars(nested_dict, prefix="APP_")
    # Set some env vars
    os.environ["APP_HOST"] = "example.com"
    os.environ["APP_DB_USER"] = "admin"
    os.environ["APP_DB_PASS"] = "secret"

    # Read env vars back
    flat_config = env_vars_to_dict("APP_")
    # {'HOST': 'example.com', 'DB_USER': 'admin', 'DB_PASS': 'secret'}

    nested_config = env_vars_to_dict("APP_", unflatten=True)
