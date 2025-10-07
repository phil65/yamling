from __future__ import annotations

from contextlib import contextmanager
import sys
from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from contextlib import AbstractContextManager


@contextmanager
def temporary_recursion_limit(limit: int) -> Generator[None]:
    """Context manager to temporarily set recursion limit.

    Args:
        limit: The recursion limit to set

    Yields:
        None

    Example:
        >>> with temporary_recursion_limit(20):
        ...     # Code that might cause recursion
        ...     pass
    """
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(limit)
    try:
        yield
    finally:
        sys.setrecursionlimit(old_limit)


@pytest.fixture
def recursion_limit() -> Callable[[int], AbstractContextManager[None]]:
    """Fixture providing a context manager for temporary recursion limit.

    Yields:
        Context manager that temporarily sets recursion limit

    Example:
        def test_something(recursion_limit):
            with recursion_limit(20):
                # Test code that might cause recursion
                pass
    """
    return temporary_recursion_limit
