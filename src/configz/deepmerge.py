from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


def merge_dict(
    merger: DeepMerger, source: Mapping[Any, Any], target: Mapping[Any, Any]
) -> Mapping[Any, Any]:
    result = dict(target)
    for key, source_value in source.items():
        target_value = result[key] if key in result else type(source_value)()
        try:
            value = merger.merge(source_value, target_value)
        except TypeError:
            # can't merge, so overwrite
            value = source_value
        result[key] = value
    return result


def merge_list[T, V](merger: DeepMerger, source: list[T], target: list[V]) -> list[T | V]:
    return target + source


DEFAULT_MERGERS: dict[type, Callable[..., Any]] = {
    dict: merge_dict,
    list: merge_list,
}


class DeepMerger:
    mergers = DEFAULT_MERGERS

    def __init__(self, mergers: dict[type, Callable[..., Any]] | None = None) -> None:
        if mergers is not None:
            self.mergers = mergers

    def merge[T](self, source: T, target: T) -> T:
        source_type = type(source)
        target_type = type(target)
        merger = self.mergers.get(target_type)
        if source_type is not target_type or merger is None:
            msg = f"Cannot merge {source_type} with {target_type}"
            raise TypeError(msg)
        return merger(self, source, target)  # type: ignore[no-any-return]


if __name__ == "__main__":
    merger = DeepMerger()
    source = {"a": {"b": 1}}
    target = {"a": {"c": 2}}
    result = merger.merge(source, target)
    print(result)
    assert result == {"a": {"b": 1, "c": 2}}
