"""Library that allows mapping from a file-like object to JSON offsets"""

from dataclasses import dataclass
from typing import IO, Dict, List, Set, Tuple, Iterable, Union

import json_stream
from json_stream.base import TransientStreamingJSONObject, TransientStreamingJSONList


@dataclass
class Position:
    start_position: int
    start_line: int
    start_col: int
    end_position: int
    end_line: int
    end_col: int


def key_map(io: IO) -> Dict[Tuple, Position]:
    """High level function interface to get all the key positions for an input"""

    io.seek(0)
    offsets_by_key = {item[0]: (item[1], item[2]) for item in map_to_file_positions(io)}

    needed_offsets: Set[int] = set()
    for start, end in offsets_by_key.values():
        needed_offsets.add(start)
        needed_offsets.add(end)

    offset_to_positions = get_offset_positions(needed_offsets)
    out: Dict[Tuple, Position] = {}

    for key, (start_pos, end_pos) in offsets_by_key.items():
        start_line, start_col = offset_to_positions[start_pos]
        end_line, end_col = offset_to_positions[end_pos]
        out[key] = Position(
            start_position=start_pos,
            start_line=start_line,
            start_col=start_col,
            end_position=end_pos,
            end_line=end_line,
            end_col=end_col,
        )

    return out


def map_to_file_positions(io: IO) -> Iterable[Tuple[Tuple, int, int]]:
    """Low level interface to get JSON paths to file offsets.
    io input should already be at the position to start reading from"""

    io.seek(0)

    root = json_stream.load(io)
    # Where we are in the JSON file. Keys can be none (for the root),
    # strings for objects, or ints for arrays
    current_path: List[Union[None, str, int]] = [None]

    def recurse(node) -> Iterable[Tuple[Tuple, int, int]]:
        # Note that file positions are 1 based
        started_at = io.tell()

        # Depending on the object type, we might need to move
        # the start or end positions. These are to make that easier.
        start_offset = 0
        end_offset = 0

        if isinstance(node, TransientStreamingJSONObject):
            for key, elem in node.items():
                current_path.append(key)
                yield from recurse(elem)

        elif isinstance(node, TransientStreamingJSONList):
            for i, elem in enumerate(node):
                current_path.append(i)
                yield from recurse(elem)

        elif isinstance(node, str):
            start_offset -= len(node)

        elif isinstance(node, int):
            end_offset -= 1
            start_offset -= len(str(node))

        elif isinstance(node, float):
            end_offset -= 1
            start_offset -= len(str(node))

        elif isinstance(node, bool):
            end_offset -= 1
            start_offset -= len(str(node))

        else:
            # I don't think JSON has any kinds aside from those
            # defined above, so this shouldn't ever be hit
            raise TypeError(type(node))
        ended_at = io.tell()

        key = tuple(current_path[1:])
        yield key, started_at + start_offset, ended_at + end_offset
        current_path.pop()

    yield from recurse(root)


def get_offset_positions(offsets: Iterable[int]) -> Dict[int, Tuple[int, int]]:
    """Find the line/column (1 indexed) for every provided offset"""

    last_line_no = 0
    last_offset = 0

    out: Dict[int, Tuple[int, int]] = {}

    for line_no, offset in enumerate(sorted(offsets)):
        if offset > last_offset:
            out[offset] = last_line_no, offset - last_offset

        last_line_no = line_no
        last_offset = offset

    return out
