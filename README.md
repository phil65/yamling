# yamling

[![PyPI License](https://img.shields.io/pypi/l/yamling.svg)](https://pypi.org/project/yamling/)
[![Package status](https://img.shields.io/pypi/status/yamling.svg)](https://pypi.org/project/yamling/)
[![Daily downloads](https://img.shields.io/pypi/dd/yamling.svg)](https://pypi.org/project/yamling/)
[![Weekly downloads](https://img.shields.io/pypi/dw/yamling.svg)](https://pypi.org/project/yamling/)
[![Monthly downloads](https://img.shields.io/pypi/dm/yamling.svg)](https://pypi.org/project/yamling/)
[![Distribution format](https://img.shields.io/pypi/format/yamling.svg)](https://pypi.org/project/yamling/)
[![Wheel availability](https://img.shields.io/pypi/wheel/yamling.svg)](https://pypi.org/project/yamling/)
[![Python version](https://img.shields.io/pypi/pyversions/yamling.svg)](https://pypi.org/project/yamling/)
[![Implementation](https://img.shields.io/pypi/implementation/yamling.svg)](https://pypi.org/project/yamling/)
[![Releases](https://img.shields.io/github/downloads/phil65/yamling/total.svg)](https://github.com/phil65/yamling/releases)
[![Github Contributors](https://img.shields.io/github/contributors/phil65/yamling)](https://github.com/phil65/yamling/graphs/contributors)
[![Github Discussions](https://img.shields.io/github/discussions/phil65/yamling)](https://github.com/phil65/yamling/discussions)
[![Github Forks](https://img.shields.io/github/forks/phil65/yamling)](https://github.com/phil65/yamling/forks)
[![Github Issues](https://img.shields.io/github/issues/phil65/yamling)](https://github.com/phil65/yamling/issues)
[![Github Issues](https://img.shields.io/github/issues-pr/phil65/yamling)](https://github.com/phil65/yamling/pulls)
[![Github Watchers](https://img.shields.io/github/watchers/phil65/yamling)](https://github.com/phil65/yamling/watchers)
[![Github Stars](https://img.shields.io/github/stars/phil65/yamling)](https://github.com/phil65/yamling/stars)
[![Github Repository size](https://img.shields.io/github/repo-size/phil65/yamling)](https://github.com/phil65/yamling)
[![Github last commit](https://img.shields.io/github/last-commit/phil65/yamling)](https://github.com/phil65/yamling/commits)
[![Github release date](https://img.shields.io/github/release-date/phil65/yamling)](https://github.com/phil65/yamling/releases)
[![Github language count](https://img.shields.io/github/languages/count/phil65/yamling)](https://github.com/phil65/yamling)
[![Github commits this week](https://img.shields.io/github/commit-activity/w/phil65/yamling)](https://github.com/phil65/yamling)
[![Github commits this month](https://img.shields.io/github/commit-activity/m/phil65/yamling)](https://github.com/phil65/yamling)
[![Github commits this year](https://img.shields.io/github/commit-activity/y/phil65/yamling)](https://github.com/phil65/yamling)
[![Package status](https://codecov.io/gh/phil65/yamling/branch/main/graph/badge.svg)](https://codecov.io/gh/phil65/yamling/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyUp](https://pyup.io/repos/github/phil65/yamling/shield.svg)](https://pyup.io/repos/github/phil65/yamling/)

[Read the documentation!](https://phil65.github.io/yamling/)


Yamling is a YAML handling library that provides enhanced loading and dumping capabilities for YAML files. It builds upon [PyYAML](https://pyyaml.org/) to offer additional features like environment variable support, file inclusion, and Jinja2 template resolution.
Special mentions also to `pyyaml_env_tag` as well as `pyyaml-include`, this library exposes these YAML extensions with a unified interface.

## Loading YAML

### Basic Loading

To load YAML content from a string:

```python
from yamling import load_yaml

# Simple YAML loading
data = load_yaml("""
name: John
age: 30
""")
```

To load from a file:

```python
from yamling import load_yaml_file

# Load from local file
config = load_yaml_file("config.yaml")

# Load from remote file (S3, HTTP, etc.)
remote_config = load_yaml_file("s3://bucket/config.yaml")
```

### Safety Modes

Yamling supports three safety modes when loading YAML:

```python
# Safe mode - most restrictive, recommended for untrusted input
data = load_yaml(content, mode="safe")

# Full mode - allows some additional types but restricts dangerous ones
data = load_yaml(content, mode="full")

# Unsafe mode - allows all YAML features (default)
data = load_yaml(content, mode="unsafe")
```

> **Warning**
> Always use "safe" mode when loading untrusted YAML content to prevent code execution vulnerabilities.

### File Inclusion

Yamling supports including other YAML files using the `!include` tag:

```yaml
# main.yaml
database:
  !include db_config.yaml
logging:
  !include logging_config.yaml
```

When loading, specify the base path for includes:

```python
config = load_yaml_file("main.yaml", include_base_path="configs/")
```

### Environment Variables

Use the `!ENV` tag to reference environment variables:

```yaml
database:
  password: !ENV DB_PASSWORD
  host: !ENV ${DB_HOST:localhost}  # with default value
```

### Template Resolution

Yamling can resolve [Jinja2](https://jinja.palletsprojects.com/) templates in YAML:

```python
from jinja2 import Environment
import yamling

env = Environment()
yaml_content = """
message: "Hello {{ name }}!"
"""

data = load_yaml(
    yaml_content,
    resolve_strings=True,
    jinja_env=env
)
```

### Inheritance

YAML files can inherit from other files using the `INHERIT` key:

```yaml
# base.yaml
database:
  host: localhost
  port: 5432

# prod.yaml
INHERIT: base.yaml
database:
  host: prod.example.com
```

Load with inheritance enabled:

```python
config = load_yaml_file("prod.yaml", resolve_inherit=True)
```

## Dumping YAML

To serialize Python objects to YAML:

```python
from yamling import dump_yaml

data = {
    "name": "John",
    "scores": [1, 2, 3],
    "active": True
}

yaml_string = dump_yaml(data)
```
Dataclasses and Pydantic v2 models can also get dumped.

### Custom Class Mapping

Map custom classes to built-in types for YAML representation:

```python
from collections import OrderedDict

data = OrderedDict([("b", 2), ("a", 1)])
yaml_string = dump_yaml(data, class_mappings={OrderedDict: dict})
```

## Custom Loader Configuration

For advanced use cases, you can create a custom loader:

```python
from yamling import get_loader
import yaml

# Create custom loader with specific features
loader_cls = get_loader(
    yaml.SafeLoader,
    include_base_path="configs/",
    enable_include=True,
    enable_env=True,
    resolve_strings=True,
    jinja_env=jinja_env,
    type_converters={int: str}
)

# Use custom loader
data = yaml.load(content, Loader=loader_cls)
```

## Custom Tag Handling

Yamling provides a `YAMLParser` class for handling custom YAML tags. This allows you to define how specific tagged values should be processed during YAML loading.

### Basic Tag Registration

You can register tag handlers using either a decorator or explicit registration:

```python
from yamling import YAMLParser
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int

# Create parser instance
yaml_parser = YAMLParser()

# Register handler using decorator
@yaml_parser.register("person")
def handle_person(data: dict) -> Person:
    return Person(**data)

# Or register handler explicitly
def handle_uppercase(data: str) -> str:
    return data.upper()

yaml_parser.register_handler("uppercase", handle_uppercase)
```

### Using Custom Tags

Once registered, you can use the custom tags in your YAML:

```yaml
# config.yaml
user: !person
  name: John Doe
  age: 30
message: !uppercase "hello world"
```

Load the YAML using the parser:

```python
# Load from string
data = yaml_parser.load_yaml("""
user: !person
  name: John Doe
  age: 30
message: !uppercase "hello world"
""")

# Or load from file
data = yaml_parser.load_yaml_file("config.yaml")

print(data["user"])  # Person(name='John Doe', age=30)
print(data["message"])  # "HELLO WORLD"
```

### Complex Structures

Custom tags can be used in nested structures and lists:

```yaml
team:
  manager: !person
    name: Alice Smith
    age: 45
  members:
    - !person
      name: Bob Johnson
      age: 30
    - !person
      name: Carol White
      age: 28
messages:
  - !uppercase "welcome"
  - !uppercase "goodbye"
```

### Combining with Other Features

The `YAMLParser` class supports all of Yamling's standard features:

```python
data = yaml_parser.load_yaml_file(
    "config.yaml",
    mode="safe",                    # Safety mode
    include_base_path="configs/",   # For !include directives
    resolve_strings=True,           # Enable Jinja2 template resolution
    resolve_inherit=True,           # Enable inheritance
    jinja_env=jinja_env           # Custom Jinja2 environment
)
```

### Available Tags

You can list all registered tags:

```python
tags = yaml_parser.list_tags()
print(tags)  # ['!person', '!uppercase']
```


## Universal load / dump interface

Yamling provides a universal load function that can handle YAML, JSON, TOML, and INI files.
Apart from yaml, only stdlib modules are used, so no additional dependencies are required.
Here's a simple example:

```python
import yamling

# Load files based on their extension
config = yamling.load_file("config.yaml")    # YAML
settings = yamling.load_file("settings.json") # JSON
params = yamling.load_file("params.toml")    # TOML

# Or explicitly specify the format
data = yamling.load_file("config.txt", mode="yaml")

# Load directly from strings
yaml_text = """
name: John
age: 30
"""
data = yamling.load(yaml_text, mode="yaml")
# same in other direction
json_text = yamling.dump(data, mode="json")
yaml.dump_file("config.yaml", data)
```

> **Note**
> If [orjson](https://github.com/ijl/orjson) is installed, the loader will automatically use it for JSON parsing / dumping, offering significantly better performance compared to the standard `json` module.
