__version__ = "1.1.1"

import yaml
from yamling.yaml_loaders import load_yaml, load_yaml_file, get_loader, YAMLInput
from yamling.load_universal import load, load_file, ParsingError
from yamling.yaml_dumpers import dump_yaml
from yamling.dump_universal import DumpingError, dump, dump_file

YAMLError = yaml.YAMLError  # Reference for external libs that need to catch this error


__all__ = [
    "load_yaml",
    "dump_yaml",
    "dump",
    "dump_file",
    "YAMLError",
    "load_yaml_file",
    "get_loader",
    "load",
    "load_file",
    "ParsingError",
    "DumpingError",
    "YAMLInput",
]
