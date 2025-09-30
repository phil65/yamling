from __future__ import annotations

import os
from typing import Any, Literal

from upath.types import JoinablePathLike
import yaml


StrPath = JoinablePathLike | os.PathLike[str]

YAMLPrimitive = str | int | float | bool | None
YAMLValue = YAMLPrimitive | dict[str, Any] | list[Any]

try:
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
    DumperType = type[yaml.Dumper | yaml.CDumper | yaml.SafeDumper | yaml.CSafeDumper]
except Exception:  # noqa: BLE001
    LoaderType = type[yaml.Loader | yaml.UnsafeLoader | yaml.FullLoader | yaml.SafeLoader]
    DumperType = type[yaml.Dumper | yaml.SafeDumper]

LoaderStr = Literal["unsafe", "full", "safe"]


SupportedFormats = Literal["yaml", "toml", "json", "ini"]
FormatType = SupportedFormats | Literal["auto"]
