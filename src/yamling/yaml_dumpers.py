"""YAML dump functionality."""

from __future__ import annotations

import dataclasses
import importlib.util
from typing import TYPE_CHECKING, Any

from yamling import exceptions, utils
from yamling.exceptions import DumpingError


if TYPE_CHECKING:
    from upath.types import JoinablePathLike
    import yaml

    from yamling import typedefs


def map_class_to_builtin_type(
    dumper_class: typedefs.DumperType,
    class_type: type,
    target_type: type,
) -> Any:
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
            return representer(dumper, data)  # type: ignore[no-any-return]

        dumper_class.add_representer(class_type, represent_as_builtin)  # type: ignore[arg-type]
    else:
        msg = f"No representer found for type {target_type}"
        raise ValueError(msg)


def dump_yaml(
    obj: Any,
    class_mappings: dict[type, type] | None = None,
    indent: int | None = None,
    default_flow_style: bool | None = None,
    allow_unicode: bool | None = None,
    **kwargs: Any,
) -> str:
    """Dump a data structure to a YAML string.

    Args:
        obj: Object to serialize (also accepts pydantic models)
        class_mappings: Dict mapping classes to built-in types for YAML representation
        indent: Indentation level for YAML output
        default_flow_style: Whether to use flow style for YAML output
        allow_unicode: Whether to allow unicode characters in YAML output
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
    kwargs = kwargs or {}
    if default_flow_style is not None:
        kwargs["default_flow_style"] = default_flow_style
    return yaml.dump(  # type: ignore[no-any-return]
        obj,
        Dumper=dumper_cls,
        indent=indent,
        allow_unicode=allow_unicode,
        **kwargs,
    )


def dump_yaml_file(
    path: JoinablePathLike,
    obj: Any,
    class_mappings: dict[type, type] | None = None,
    overwrite: bool = False,
    create_dirs: bool = False,
    **kwargs: Any,
) -> None:
    from upathtools import to_upath

    yaml_str = dump_yaml(obj, class_mappings, **kwargs)
    try:
        file_path = to_upath(path)
        if file_path.exists() and not overwrite:
            msg = f"File already exists: {path}"
            raise FileExistsError(msg)  # noqa: TRY301
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        elif not file_path.parent.exists():
            msg = f"Directory does not exist: {file_path.parent}"
            raise exceptions.DumpingError(msg)  # noqa: TRY301
        file_path.write_text(yaml_str)
    except Exception as exc:
        msg = f"Failed to save configuration to {path}"
        raise DumpingError(msg) from exc


if __name__ == "__main__":
    from collections import OrderedDict

    test_data = OrderedDict([("b", 2), ("a", 1)])
    text = dump_yaml(test_data, class_mappings={OrderedDict: dict})
    print(text)
