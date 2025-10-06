"""yamling: Enhanced YAML loading and dumping."""

from __future__ import annotations

from importlib.metadata import version

__version__ = version("yamling")
__title__ = "yamling"
__description__ = "Enhanced YAML loading and dumping."
__author__ = "Philipp Temminghoff"
__author_email__ = "philipptemminghoff@googlemail.com"
__copyright__ = "Copyright (c) 2024 Philipp Temminghoff"
__license__ = "MIT"
__url__ = "https://github.com/phil65/yamling"

import yaml
from yamling.yaml_loaders import load_yaml, load_yaml_file, get_loader, YAMLInput
from yamling.load_universal import load, load_file
from yamling.yaml_dumpers import dump_yaml
from yamling.dump_universal import dump, dump_file
from yamling.yamlparser import YAMLParser
from yamling.exceptions import DumpingError, ParsingError
from yamling.typedefs import SupportedFormats, FormatType, LoaderType

YAMLError = yaml.YAMLError  # Reference for external libs that need to catch this error


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
