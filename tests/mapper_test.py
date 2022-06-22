from pathlib import Path
from typing import Dict, List, Tuple

import pytest
from json_mapper.mapper import JSONMapper
from io import StringIO
import json

CURRENT_DIR = Path(__file__).parent


def _get_json_mapper(file_name: Path) -> JSONMapper:
    with open(CURRENT_DIR / file_name) as f_in:
        io = StringIO(f_in.read())

    return JSONMapper(io)


def test_mapper_keys():
    mapper = _get_json_mapper("sample_1.json")

    expected_keys = {tuple(), ("food",), ("bird",)}
    actual_keys = mapper.all_positions.keys()
    assert actual_keys == expected_keys


def test_root_offset():
    mapper = _get_json_mapper("sample_1.json")

    root = mapper.all_positions[tuple()]
    assert root.start_position == 0
    assert root.end_position == 44
    assert root.start_line == 0
    assert root.start_col == 0
    assert root.end_line == 3
    assert root.end_col == 1


def test_pie_offset():
    mapper = _get_json_mapper("sample_1.json")

    # The value is "pie"
    food = mapper.all_positions[("food",)]
    assert food.start_position == 14
    assert food.end_position == 19


def _get_reflexive_tests(file_name: str):
    mapper = _get_json_mapper(CURRENT_DIR / file_name)

    for key in mapper.all_positions:
        yield mapper, key


@pytest.mark.parametrize("mapper,key", _get_reflexive_tests("all_type_test.json"))
def test_reflexive(mapper: JSONMapper, key: Tuple):
    """Test that the position offset given by the mapper is exactly
    what is needed to re-create that object"""

    def _get_value(node, remaining_path: Tuple):
        if not remaining_path:
            return node

        key = remaining_path[0]
        return _get_value(node[key], remaining_path[1:])

    position = mapper.all_positions[key]
    expected_value = _get_value(mapper.data, key)
    json_str = mapper.json_str[position.start_position : position.end_position]
    sub_data = json.loads(json_str)

    assert sub_data == expected_value
