from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from yamling.typedefs import SupportedFormats


# Check if orjson is available
has_orjson = importlib.util.find_spec("orjson") is not None

FORMAT_MAPPING: dict[str, SupportedFormats] = {
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".tml": "toml",
    ".json": "json",
    ".jsonc": "json",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".config": "ini",
    ".properties": "ini",
    ".cnf": "ini",
    ".env": "ini",
}
