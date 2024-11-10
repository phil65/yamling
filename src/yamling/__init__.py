__version__ = "0.0.3"

import yaml
from yamling.yaml_loaders import load_yaml, load_yaml_file, get_loader
from yamling.load_universal import load, load_file
from yamling.dump import dump_yaml


YAMLError = yaml.YAMLError  # Reference for external libs that need to catch this error


__all__ = [
    "load_yaml",
    "dump_yaml",
    "YAMLError",
    "load_yaml_file",
    "get_loader",
    "load",
    "load_file",
]
