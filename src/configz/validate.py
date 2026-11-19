"""Type validation functionality with graceful Pydantic fallbacks."""

from __future__ import annotations

import collections.abc
import importlib.util
from typing import TYPE_CHECKING, Any, cast, get_args, get_origin


if TYPE_CHECKING:
    from collections.abc import Callable
    import types


_has_pydantic = importlib.util.find_spec("pydantic") is not None

# `typing.get_origin` maps typing aliases (List, Set, Dict, ...) to these.
_SEQUENCE_ORIGINS: frozenset[object] = frozenset({
    list,
    set,
    tuple,
    collections.abc.Sequence,
    collections.abc.Set,
})
_MAPPING_ORIGINS: frozenset[object] = frozenset({dict, collections.abc.Mapping})


def get_object_name(fn: Callable[..., Any] | types.ModuleType, fallback: str = "<unknown>") -> str:
    """Get the name of a function."""
    name = getattr(fn, "__name__", None)
    if name is None:
        return fallback
    assert isinstance(name, str)
    return name


def validate_json_data[T](data: Any, return_type: type[T] | None = None) -> T:  # noqa: PLR0911
    """Validate and convert data to the requested return type.

    Supports a wide range of types including:
    - Basic types (dict, list, str, int, float, bool, None)
    - Pydantic models
    - Generic types (List[str], Dict[str, int], etc.)
    - TypedDict
    - Any type supported by Pydantic's TypeAdapter

    Falls back to simpler validation when Pydantic isn't available.

    Args:
        data: The data to validate
        return_type: The expected return type, or None for no validation

    Returns:
        The validated data

    Raises:
        TypeError: If validation fails
    """
    # No type validation requested
    if return_type is None:
        return cast(T, data)

    # Handle simple built-in types directly for efficiency
    simple_types = (str, int, float, bool, list, dict, tuple, set)

    if return_type in simple_types and not hasattr(return_type, "__origin__"):
        if isinstance(data, return_type):
            return data
        error_msg = f"Expected {return_type.__name__}, got {type(data).__name__}"
        raise TypeError(error_msg)

    # For Pydantic validation path
    if _has_pydantic:
        # First check for Pydantic model with model_validate method (direct instance)
        if hasattr(return_type, "model_validate"):
            from pydantic import ValidationError

            try:
                return return_type.model_validate(data)  # type: ignore
            except ValidationError as e:
                error_msg = f"Validation error for {return_type.__name__}: {e}"
                raise TypeError(error_msg) from e

        # Otherwise use TypeAdapter for advanced typing constructs
        from pydantic import TypeAdapter

        try:
            adapter = TypeAdapter(return_type)
            return adapter.validate_python(data)
        except Exception as e:
            expected = get_object_name(return_type, str(return_type))
            error_msg = f"Data doesn't match type {expected}: {e}"
            raise TypeError(error_msg) from e

    # Fallback path when Pydantic isn't available or for other types

    # For generic types without Pydantic, attempt basic validation
    # This is limited but better than nothing
    origin = get_origin(return_type)
    args = get_args(return_type)
    if origin is not None:
        # Handle List[T], Sequence[T], Set[T], Tuple[T, ...], etc.
        if origin in _SEQUENCE_ORIGINS:
            if not isinstance(data, list | tuple | set):
                error_msg = f"Expected sequence type, got {type(data).__name__}"
                raise TypeError(error_msg)

            # If homogeneous collection with one type arg, validate elements
            if len(args) == 1 and args[0] is not Ellipsis:
                validated_items: list[Any] = [validate_json_data(item, args[0]) for item in data]
                # Convert to the right container type
                if origin is tuple:
                    return cast(T, tuple(validated_items))
                if origin in (set, collections.abc.Set):
                    return cast(T, set(validated_items))
                return cast(T, validated_items)

            return cast(T, data)

        # Handle Dict[K, V], Mapping[K, V]
        if origin in _MAPPING_ORIGINS:
            if not isinstance(data, dict):
                error_msg = f"Expected dict type, got {type(data).__name__}"
                raise TypeError(error_msg)

            # For Dict[str, ValueType], validate values
            if len(args) == 2 and args[0] is str:  # noqa: PLR2004
                validated_dict: dict[Any, Any] = {}
                for key, value in data.items():
                    if not isinstance(key, str):
                        error_msg = f"Expected string dict keys, got {type(key).__name__}"
                        raise TypeError(error_msg)
                    validated_dict[key] = validate_json_data(value, args[1])
                return cast(T, validated_dict)

            return cast(T, data)

    # Last resort - simple isinstance check
    if isinstance(data, return_type):
        return data
    expected = get_object_name(return_type, str(return_type))
    error_msg = f"Expected {expected}, got {type(data).__name__}"
    raise TypeError(error_msg)
