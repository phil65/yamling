from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


T = TypeVar("T")


def merge_dict(merger: DeepMerger, source: Mapping, target: Mapping) -> Mapping:
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


def merge_list(merger: DeepMerger, source: list, target: list) -> list:
    return target + source


DEFAULT_MERGERS: dict[type, Callable] = {
    dict: merge_dict,
    list: merge_list,
}


class DeepMerger:
    mergers = DEFAULT_MERGERS

    def __init__(self, mergers: dict[type, Callable] | None = None):
        if mergers is not None:
            self.mergers = mergers

    def merge(self, source: T, target: T) -> T:
        source_type = type(source)
        target_type = type(target)
        merger = self.mergers.get(target_type)
        if source_type is not target_type or merger is None:
            msg = f"Cannot merge {source_type} with {target_type}"
            raise TypeError(msg)
        return merger(self, source, target)


if __name__ == "__main__":
    merger = DeepMerger()
    source = {"a": {"b": 1}}
    target = {"a": {"c": 2}}
    result = merger.merge(source, target)
    print(result)
    assert result == {"a": {"b": 1, "c": 2}}
