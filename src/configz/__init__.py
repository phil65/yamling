"""configz: main package.

Serialization stuff for config files.
"""

from __future__ import annotations

from importlib.metadata import version

__version__ = version("configz")
__title__ = "configz"

__author__ = "Philipp Temminghoff"
__author_email__ = "philipptemminghoff@googlemail.com"
__copyright__ = "Copyright (c) 2024 Philipp Temminghoff"
__license__ = "MIT"
__url__ = "https://github.com/phil65/configz"


from configz.yaml_loaders import load_yaml, load_yaml_file, get_loader, YAMLInput
from configz.load_universal import load, load_file
from configz.yaml_dumpers import dump_yaml
from configz.dump_universal import dump, dump_file
from configz.yamlparser import YAMLParser
from configz.exceptions import DumpingError, ParsingError
from configz.typedefs import SupportedFormats, FormatType, LoaderType
from configz.yaml_errors import YAMLError


__all__ = [
    "DumpingError",
    "FormatType",
    "LoaderType",
    "ParsingError",
    "SupportedFormats",
    "YAMLError",
    "YAMLInput",
    "YAMLParser",
    "__version__",
    "dump",
    "dump_file",
    "dump_yaml",
    "get_loader",
    "load",
    "load_file",
    "load_yaml",
    "load_yaml_file",
]
