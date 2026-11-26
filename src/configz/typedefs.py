from typing import Any, Literal, Protocol, runtime_checkable

import yaml


YAMLPrimitive = str | int | float | bool | None


@runtime_checkable
class NamedStream(Protocol):
    """A stream that knows where it was opened from (e.g. a file object)."""

    name: object  # str or bytes path, or an int for file descriptors


YAMLValue = YAMLPrimitive | dict[str, Any] | list[Any]

# `type` aliases are evaluated lazily: the C classes only exist when PyYAML
# was built with libyaml (e.g. not on Python versions without PyYAML wheels).
type DumperType = type[yaml.Dumper | yaml.CDumper | yaml.SafeDumper | yaml.CSafeDumper]
LoaderStr = Literal["unsafe", "full", "safe"]

SupportedFormats = Literal["yaml", "toml", "json", "ini", "toon"]
FormatType = SupportedFormats | Literal["auto"]

type LoaderType = type[
    yaml.Loader
    | yaml.CLoader
    | yaml.UnsafeLoader
    | yaml.CUnsafeLoader
    | yaml.FullLoader
    | yaml.CFullLoader
    | yaml.SafeLoader
    | yaml.CSafeLoader
]
