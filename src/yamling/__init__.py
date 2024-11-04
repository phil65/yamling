__version__ = "0.0.1"

import yaml
from yamling.load import load_yaml
from yamling.dump import dump_yaml


YAMLError = yaml.YAMLError  # Reference for external libs that need to catch this error


__all__ = ["load_yaml", "dump_yaml", "YAMLError"]
