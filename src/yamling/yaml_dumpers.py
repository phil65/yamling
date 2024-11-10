"""YAML dump functionality."""

from __future__ import annotations

from typing import Any

import yaml

from yamling import utils, yamltypes


def map_class_to_builtin_type(
    dumper_class: yamltypes.DumperType,
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

        def represent_as_builtin(dumper: yamltypes.DumperType, data: Any) -> yaml.Node:
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
        obj: Object to serialize
        class_mappings: Dict mapping classes to built-in types for YAML representation
        kwargs: Additional arguments for yaml.dump

    Returns:
        YAML string representation
    """
    dumper_cls = utils.create_subclass(yaml.Dumper)
    if class_mappings:
        for class_type, target_type in class_mappings.items():
            map_class_to_builtin_type(dumper_cls, class_type, target_type)
    return yaml.dump(obj, Dumper=dumper_cls, **kwargs)


if __name__ == "__main__":
    from collections import OrderedDict

    test_data = OrderedDict([("b", 2), ("a", 1)])
    yaml_str = dump_yaml(test_data, class_mappings={OrderedDict: dict})
    print(yaml_str)
