"""Utility functions."""

from typing import cast


def create_subclass[T: type](base_cls: T) -> T:
    """Create a subclass of the given base class to avoid modifying original classes.

    Args:
        base_cls: Base class to inherit from

    Returns:
        New subclass of the base class
    """
    return cast("T", type("SubClass", (base_cls,), {}))
