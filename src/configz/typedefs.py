from __future__ import annotations

from typing import Any, Literal

import yaml


YAMLPrimitive = str | int | float | bool | None
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
