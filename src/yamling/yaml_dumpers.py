"""YAML dump functionality."""

from __future__ import annotations

import dataclasses
import importlib.util
from typing import TYPE_CHECKING, Any

from yamling import typedefs, utils


if TYPE_CHECKING:
    import os

    import yaml


def map_class_to_builtin_type(
    dumper_class: typedefs.DumperType,
    class_type: type,
    target_type: type,
):
    """Maps a Python class to use an existing PyYAML representer for a built-in type.

    The original type is preserved, only the representation format is borrowed.

    Args:
        dumper_class: The YAML Dumper class
        class_type: The custom Python class to map
        target_type: The built-in type whose representer should be used
    """
    method_name = f"represent_{target_type.__name__}"

    if hasattr(dumper_class, method_name):
        representer = getattr(dumper_class, method_name)

        def represent_as_builtin(dumper: typedefs.DumperType, data: Any) -> yaml.Node:
            return representer(dumper, data)  # Pass data directly without conversion

        dumper_class.add_representer(class_type, represent_as_builtin)
    else:
        msg = f"No representer found for type {target_type}"
        raise ValueError(msg)


def dump_yaml(
    obj: Any,
    class_mappings: dict[type, type] | None = None,
    **kwargs: Any,
) -> str:
    """Dump a data structure to a YAML string.

    Args:
        obj: Object to serialize (also accepts pydantic models)
        class_mappings: Dict mapping classes to built-in types for YAML representation
        kwargs: Additional arguments for yaml.dump

    Returns:
        YAML string representation
    """
    import yaml

    dumper_cls = utils.create_subclass(yaml.Dumper)
    if class_mappings:
        for class_type, target_type in class_mappings.items():
            map_class_to_builtin_type(dumper_cls, class_type, target_type)
    if importlib.util.find_spec("pydantic"):
        import pydantic

        if isinstance(obj, pydantic.BaseModel):
            obj = obj.model_dump()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        obj = dataclasses.asdict(obj)
    return yaml.dump(obj, Dumper=dumper_cls, **kwargs)


def dump_yaml_file(
    path: str | os.PathLike[str],
    obj: Any,
    class_mappings: dict[type, type] | None = None,
    **kwargs: Any,
):
    import upath

    string = dump_yaml(obj, class_mappings, **kwargs)
    upath.UPath(path).write_text(string)


if __name__ == "__main__":
    from collections import OrderedDict

    test_data = OrderedDict([("b", 2), ("a", 1)])
    yaml_str = dump_yaml(test_data, class_mappings={OrderedDict: dict})
    print(yaml_str)
