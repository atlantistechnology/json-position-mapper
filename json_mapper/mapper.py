"""Library that allows mapping from a file-like object to JSON offsets"""

from dataclasses import dataclass
import json
from typing import IO, Any, Dict, List, Set, Tuple, Iterable, Union
from functools import cached_property

import json_stream
from json_stream.base import TransientStreamingJSONObject, TransientStreamingJSONList

JSONKeyTuple = Tuple


@dataclass(frozen=True)
class Offset:
    start: int
    end: int


@dataclass(frozen=True)
class Position:
    """The default values in positions are designed to be zero based
    with non-inclusive ends to match Python's slice mechanics"""

    start_line: int
    start_col: int
    end_line: int
    end_col: int

    @property
    def editor_start_line(self) -> int:
        """One based inclusive start line"""

        return self.start_line + 1

    @property
    def editor_start_col(self) -> int:
        """One based inclusive start column"""

        return self.start_col + 1

    @property
    def editor_end_line(self) -> int:
        """One based inclusive end line"""

        return self.end_line + 1

    @property
    def editor_end_col(self) -> int:
        """One based inclusive end column"""

        # Going from zero based non-inclusive to one based i
        # inclusive is a noop and thus there is no change
        return self.end_col


class JSONMapper:
    def __init__(self, io: IO):
        if not io.seekable():
            raise TypeError("Input IO must be seekable")

        self._io = io

    @cached_property
    def offsets(self) -> Dict[JSONKeyTuple, Offset]:
        return {key: offset for key, offset in self._scan_json_for_offsets()}

    def get_position(self, key: JSONKeyTuple) -> Position:
        """Get the position of a given key"""

        offsets = self.offsets[key]

        start_line, start_col = self._get_line_col_for_position(offsets.start)
        end_line, end_col = self._get_line_col_for_position(offsets.end)

        return Position(
            start_line=start_line,
            start_col=start_col,
            end_line=end_line,
            end_col=end_col,
        )

    def get_json_data(self) -> Any:
        """Get the referenced JSON object"""

        self._io.seek(0)
        return json.load(self._io)

    def read(self) -> str:
        """Get the entire underlying io string, generally for testing"""

        self._io.seek(0)
        return self._io.read()

    @cached_property
    def _line_break_positions(self) -> List[int]:
        self._io.seek(0)

        out: List[int] = []
        line = self._io.readline()
        while line:
            out.append(self._io.tell() - 1)
            line = self._io.readline()
        return out

    def _scan_json_for_offsets(self) -> Iterable[Tuple[JSONKeyTuple, Offset]]:
        """Get every tuple key in the file, along with its start and end"""

        self._io.seek(0)

        stream_root = json_stream.load(self._io)
        # Where we are in the JSON file. Keys can be none (for the root),
        # strings for objects, or ints for arrays
        current_path: List[Union[None, str, int]] = [None]

        def recurse(node) -> Iterable[Tuple[JSONKeyTuple, Offset]]:
            # Note that file positions are 1 based
            started_at = self._io.tell()

            # Depending on the object type, we might need to move
            # the start or end positions. These are to make that easier.
            start_offset = -1
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
                # We want to include the quotes so that we have parity
                # mechanics with things like objects. The off-by-one issues
                # have been handled.
                start_offset -= len(node) + 1

            elif isinstance(node, bool):
                if node:
                    start_offset -= len("true") - 1
                else:
                    start_offset -= len("false") - 1

            elif isinstance(node, int):
                end_offset -= 1
                start_offset -= len(str(node))

            elif isinstance(node, float):
                end_offset -= 1
                start_offset -= len(str(node))

            elif node is None:
                start_offset -= len("null")

            else:
                # I don't think JSON has any kinds aside from those
                # defined above, so this shouldn't ever be hit
                raise TypeError(type(node))
            ended_at = self._io.tell()

            key = tuple(current_path[1:])
            yield key, Offset(
                start=(started_at + start_offset),
                end=(ended_at + end_offset),
            )
            current_path.pop()

        return recurse(stream_root)

    def _get_line_col_for_position(self, position: int) -> Tuple[int, int]:
        line_number = self._get_line_for_position(position)
        line_start = self._line_break_positions[line_number - 1] + 1

        if position == 0:
            return 0, 0

        # We are using slice mechanics where ends are not inclusive,
        # so we need to increment by 1
        col = position - line_start
        return line_number, col

    def _get_line_for_position(self, position: int) -> int:
        """Get just the line for a given position"""

        line_breaks = self._line_break_positions

        # We need to use price is right minus one rules - find the
        # highest number line break that is *less than* the given position

        # TODO: This is the naive approach that runs in O(n) time.
        # It can be substituted with an approach that treats the
        # list of line break positions as a binary tree and keeps
        # bifurcating the list to run in O(log n) time

        for i, break_position in enumerate(line_breaks):
            if break_position > position:
                return i

        return len(line_breaks) - 1
