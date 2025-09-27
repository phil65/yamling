"""Utility functions."""

from __future__ import annotations

from typing import TypeVar


T = TypeVar("T", bound=type)


def create_subclass[T: type](base_cls: T) -> T:
    """Create a subclass of the given base class to avoid modifying original classes.

    Args:
        base_cls: Base class to inherit from

    Returns:
        New subclass of the base class
    """
    return type("SubClass", (base_cls,), {})  # type: ignore[return-value]
