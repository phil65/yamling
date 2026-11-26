"""configz must work with a PyYAML build that lacks the libyaml C extension.

Python versions without PyYAML wheels (e.g. 3.15 at the time of writing) get
a source build that silently falls back to pure Python when libyaml headers
are missing, so ``yaml.CDumper`` & co. don't exist.
"""

import subprocess
import sys
import textwrap


def test_import_and_roundtrip_without_libyaml() -> None:
    script = textwrap.dedent(
        """
        import sys
        sys.modules["yaml._yaml"] = None  # make PyYAML's C extension unimportable
        import yaml
        assert not yaml.__with_libyaml__
        assert not hasattr(yaml, "CDumper")

        import configz
        from configz.yaml_tools import yaml_loaders

        assert yaml_loaders.LOADERS["safe"] is yaml.SafeLoader
        assert configz.load_yaml("a: [1, 2]", mode="safe") == {"a": [1, 2]}
        assert configz.load_yaml(configz.dump_yaml({"b": 1})) == {"b": 1}
        print("ok")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
