from pathlib import Path
from json_mapper.mapper import JSONMapper
from io import StringIO

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
