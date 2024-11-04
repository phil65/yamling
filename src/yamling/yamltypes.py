from __future__ import annotations

from typing import Any, Literal

import yaml


YAMLPrimitive = str | int | float | bool | None
YAMLValue = YAMLPrimitive | dict[str, Any] | list[Any]

LoaderType = type[
    yaml.Loader
    | yaml.CLoader
    | yaml.UnsafeLoader
    | yaml.CUnsafeLoader
    | yaml.FullLoader
    | yaml.CFullLoader
    | yaml.SafeLoader
    | yaml.CSafeLoader
]
LoaderStr = Literal["unsafe", "full", "safe"]

DumperType = type[yaml.Dumper | yaml.CDumper | yaml.SafeDumper | yaml.CSafeDumper]
