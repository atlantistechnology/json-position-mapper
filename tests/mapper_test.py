from pathlib import Path
from typing import Tuple, Union, NamedTuple, Any

import pytest
from json_mapper.mapper import JSONMapper, Position, Offset
from io import StringIO
import json

CURRENT_DIR = Path(__file__).parent


class SetupData(NamedTuple):
    io: StringIO
    mapper: JSONMapper
    data: Any


def _setup_data(file_name: Union[Path, str]) -> SetupData:
    with open(CURRENT_DIR / file_name) as f_in:
        io = StringIO(f_in.read())

    mapper = JSONMapper(io)
    io.seek(0)
    data = json.load(io)
    io.seek(0)

    return SetupData(io=io, mapper=mapper, data=data)


def test_mapper_keys():
    mapper = _setup_data("sample_1.json").mapper

    expected_keys = {(), ("food",), ("bird",)}
    actual_keys = mapper.offsets.keys()
    assert actual_keys == expected_keys


def test_root_offset():
    mapper = _setup_data("sample_1.json").mapper

    actual = mapper.offsets[()]
    expected = Offset(0, 44)
    assert actual == expected


def test_pie_offset():
    mapper = _setup_data("sample_1.json").mapper

    # The value is "pie"
    actual = mapper.offsets[("food",)]
    expected = Offset(14, 19)
    assert actual == expected


def _get_reflexive_tests(file_name: str):
    setup = _setup_data(file_name)

    for key in setup.mapper.offsets:
        yield setup, key


@pytest.mark.parametrize("setup,key", _get_reflexive_tests("complex_types.json"))
def test_reflexive(setup: SetupData, key: Tuple):
    """Test that the position offset given by the mapper is exactly
    what is needed to re-create that object"""

    def _get_value(node, remaining_path: Tuple):
        if not remaining_path:
            return node

        key = remaining_path[0]
        return _get_value(node[key], remaining_path[1:])

    json_data = setup.data
    file_data = setup.io.getvalue()

    position = setup.mapper.offsets[key]
    expected_value = _get_value(json_data, key)
    json_str = file_data[position.start : position.end]
    sub_data = json.loads(json_str)

    assert sub_data == expected_value


def test_root_positions():
    mapper = _setup_data("sample_1.json").mapper

    actual_position = mapper.get_position(())
    expected_position = Position(0, 0, 3, 1)
    assert actual_position == expected_position


def test_pie_positions():
    mapper = _setup_data("sample_1.json").mapper

    actual_position = mapper.get_position(("food",))
    expected_position = Position(1, 12, 1, 17)
    assert actual_position == expected_position


def test_pie_editor_position():
    mapper = _setup_data("sample_1.json").mapper
    position = mapper.get_position(("food",))

    assert position.editor_start_line == 2
    assert position.editor_start_col == 13
    assert position.editor_end_line == 2
    assert position.editor_end_col == 17


def test_invalid_json():
    sample_io = StringIO("{{")
    mapper = JSONMapper(sample_io)

    with pytest.raises(ValueError):
        mapper.offsets
