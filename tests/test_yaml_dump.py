from __future__ import annotations

import pytest

import configz


def test_dump_yaml():
    data = {"a": 1, "b": [2, 3, 4], "c": {"d": 5}}
    dumped = configz.dump_yaml(data)
    assert configz.load_yaml(dumped) == data


def test_class_mapping():
    from collections import OrderedDict

    data = OrderedDict([("b", 2), ("a", 1)])
    # Test with OrderedDict mapping using dict's representation
    dumped = configz.dump_yaml(data, class_mappings={OrderedDict: dict})
    assert "!!" not in dumped
    # Test without mapping (default OrderedDict representation)
    dumped_no_mapping = configz.dump_yaml(data)
    expected_no_mapping = (
        "!!python/object/apply:collections.OrderedDict\n- - - b\n    - 2\n  - - a\n    - 1\n"
    )
    assert dumped_no_mapping == expected_no_mapping


if __name__ == "__main__":
    pytest.main([__file__])
