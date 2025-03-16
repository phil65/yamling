from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from yamling.typedefs import SupportedFormats


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
