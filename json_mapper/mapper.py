"""Library that allows mapping from a file-like object to JSON offsets"""

from dataclasses import dataclass
import json
from typing import IO, Any, Dict, List, Set, Tuple, Iterable, Union
from functools import cached_property

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

    for_editor: bool = False

    @cached_property
    def editor_positions(self):
        """The editor positions use the common mechanics for highlighting
        ranges in editors. All indexes become 1 based and the end becomes
        inclusive.
        """

        if self.for_editor:
            return self

        return Position(
            start_position=self.start_position + 1,
            start_line=self.start_line + 1,
            start_col=self.start_col + 1,
            # Our end positions were non-inclusive.
            # Editor positions are inclusive.
            # The two cancel each other out and we can return the original values
            end_position=self.end_position,
            # Ignore the above since a line is an intermediary calculated value
            end_line=self.end_line + 1,
            end_col=self.end_col,
        )


class JSONMapper:
    def __init__(self, io: IO):
        if not io.seekable():
            raise TypeError("Input IO must be seekable")

        self._io = io

    @cached_property
    def all_positions(self) -> Dict[Tuple, Position]:
        out: Dict[Tuple, Position] = {}

        for key, start, end in self._get_key_positions_ranges:
            start_line, start_col = self._get_line_col_for_position(start)
            end_line, end_col = self._get_line_col_for_position(end - 1)

            out[key] = Position(
                start_position=start,
                start_line=start_line,
                start_col=start_col,
                end_position=end,
                end_line=end_line,
                end_col=end_col,
            )

        return out

    @cached_property
    def data(self) -> Any:
        self._reset_io()
        return json.load(self._io)

    @cached_property
    def json_str(self) -> str:
        """Get the entire underlying io string, generally for testing"""

        self._reset_io()
        return self._io.read()

    @cached_property
    def _line_break_positions(self) -> List[int]:
        self._reset_io()

        out: List[int] = []
        line = self._io.readline()
        while line:
            out.append(self._io.tell() - 1)
            line = self._io.readline()
        return out

    @cached_property
    def _get_key_positions_ranges(self) -> List[Tuple[Tuple, int, int]]:
        """Get every tuple key in the file, along with its start and end"""

        self._reset_io()

        root = json_stream.load(self._io)
        # Where we are in the JSON file. Keys can be none (for the root),
        # strings for objects, or ints for arrays
        current_path: List[Union[None, str, int]] = [None]

        def recurse(node) -> Iterable[Tuple[Tuple, int, int]]:
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
            yield key, started_at + start_offset, ended_at + end_offset
            current_path.pop()

        return list(recurse(root))

    def _get_line_col_for_position(self, position: int) -> Tuple[int, int]:
        line_number = self._get_line_for_position(position)
        line_offset = self._line_break_positions[line_number]

        # We are using slice mechanics where ends are not inclusive,
        # so we need to increment by 1
        col = position - line_offset + 1
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

        line_no = len(line_breaks)
        for break_position in reversed(line_breaks):
            # There are a bunch of off-by-one edge cases around here.
            # They all cancel out.

            if break_position < position:
                return line_no

            line_no -= 1

        return line_no

    def _reset_io(self):
        self._io.seek(0)
