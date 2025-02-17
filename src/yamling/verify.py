from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar


if TYPE_CHECKING:
    from typing import TypedDict

T = TypeVar("T")


def verify_type(data: Any, type_hint: type[T]) -> T:
    """Verify that data matches the expected type using pydantic.

    Args:
        data: Data to verify
        type_hint: Type to verify against (including TypedDict)

    Returns:
        The validated data

    Raises:
        TypeError: If validation fails
    """
    from pydantic import TypeAdapter

    if isinstance(type_hint, type) and not hasattr(type_hint, "__annotations__"):  # pyright: ignores
        if isinstance(data, type_hint):
            return data  # type: ignore
        msg = f"Expected {type_hint.__name__}, got {type(data).__name__}"
        raise TypeError(msg)

    # Use pydantic for complex types
    try:
        adapter = TypeAdapter(type_hint)
        return adapter.validate_python(data)
    except Exception as e:
        msg = f"Data doesn't match type {type_hint.__name__}: {e}"
        raise TypeError(msg) from e


if __name__ == "__main__":
    from typing import TypedDict

    # Test with regular class
    class MyClass:
        def __init__(self, x: int) -> None:
            self.x = x

    obj = MyClass(42)
    result = verify_type(obj, MyClass)
    print("Class validation:", result)

    try:
        verify_type("not a class", MyClass)
    except TypeError as e:
        print("Class error (good):", e)

    # Test with TypedDict
    class Config(TypedDict):
        name: str
        value: int

    data = {"name": "test", "value": 123}
    result_2 = verify_type(data, Config)
    print("TypedDict validation:", result_2)

    try:
        verify_type({"name": "test", "value": "not an int"}, Config)
    except TypeError as e:
        print("TypedDict error (good):", e)
