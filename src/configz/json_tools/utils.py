"""Utility functions for JSON serialization and deserialization."""

from __future__ import annotations

import datetime
import importlib.util
from typing import Any


def handle_datetimes(data: Any, naive_utc: bool) -> Any:
    """Handle datetime objects consistently across serializers.

    If naive_utc=False: Raise an error for naive datetime objects
    If naive_utc=True: Treat naive datetime objects as UTC
    """

    # Define a recursive conversion function
    def _convert(obj: Any) -> Any:
        if isinstance(obj, datetime.datetime):
            # Check if it's a naive datetime (no tzinfo)
            if obj.tzinfo is None:
                if not naive_utc:
                    msg = (
                        "Naive datetime objects are not allowed. "
                        "Set naive_utc=True or provide timezone."
                    )
                    raise ValueError(msg)
                # Interpret as UTC without changing the actual time
                return obj.replace(tzinfo=datetime.UTC)

        # Handle nested dictionaries
        elif isinstance(obj, dict):
            return {key: _convert(value) for key, value in obj.items()}
        # Handle lists, tuples, and sets
        elif isinstance(obj, list | tuple | set):
            return [_convert(item) for item in obj]

        # Return other types as-is
        return obj

    return _convert(data)


def prepare_numpy_arrays(data: Any) -> Any:
    """Recursively convert NumPy arrays to Python lists.

    This function detects if NumPy is available and, if so, handles converting
    NumPy arrays to native Python types for JSON serialization.
    """
    # Check if numpy is available
    numpy_available = importlib.util.find_spec("numpy") is not None
    if not numpy_available:
        return data

    import numpy as np  # type: ignore[import-not-found]

    # Define a recursive conversion function
    def _convert(obj: Any) -> Any:  # noqa: PLR0911
        # Convert numpy arrays to lists
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        # Convert numpy scalar types to Python scalars
        if isinstance(
            obj,
            np.integer
            | np.int_
            | np.intc
            | np.intp
            | np.int8
            | np.int16
            | np.int32
            | np.int64
            | np.uint8
            | np.uint16
            | np.uint32
            | np.uint64,
        ):
            return int(obj)
        if isinstance(obj, np.float16 | np.float32 | np.float64):  # np.float_
            return float(obj)
        if isinstance(obj, (np.bool_)):
            return bool(obj)
        # Handle nested dictionaries
        if isinstance(obj, dict):
            return {key: _convert(value) for key, value in obj.items()}
        # Handle lists, tuples, and sets
        if isinstance(obj, list | tuple | set):
            return [_convert(item) for item in obj]
        # Return other types as-is
        return obj

    return _convert(data)
