from __future__ import annotations

import pytest

import yamling


def test_dump_yaml():
    data = {"a": 1, "b": [2, 3, 4], "c": {"d": 5}}
    dumped = yamling.dump_yaml(data)
    assert yamling.load_yaml(dumped) == data


def test_class_mapping():
    from collections import OrderedDict

    data = OrderedDict([("b", 2), ("a", 1)])
    # Test with OrderedDict mapping using dict's representation
    dumped = yamling.dump_yaml(data, class_mappings={OrderedDict: dict})
    assert "!!" not in dumped
    # Test without mapping (default OrderedDict representation)
    dumped_no_mapping = yamling.dump_yaml(data)
    expected_no_mapping = (
        "!!python/object/apply:collections.OrderedDict\n"
        "- - - b\n"
        "    - 2\n"
        "  - - a\n"
        "    - 1\n"
    )
    assert dumped_no_mapping == expected_no_mapping


if __name__ == "__main__":
    pytest.main([__file__])
