from pathlib import Path
from json_mapper.mapper import key_map

CURRENT_DIR = Path(__file__).parent


def test_mapper_keys():
    with open(CURRENT_DIR / "sample_1.json") as f_in:
        data = key_map(f_in)

    expected_keys = {tuple(), ("food",), ("bird",)}
    assert data.keys() == expected_keys
