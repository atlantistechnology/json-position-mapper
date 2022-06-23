"""Library that allows mapping from a file-like object to JSON offsets"""

import json
from typing import IO, Any, Dict, List, Set, Tuple, Iterable, Union, NamedTuple
from functools import cached_property
from bisect import bisect_left

import json_stream
from json_stream.base import TransientStreamingJSONObject, TransientStreamingJSONList

JSONKeyTuple = Tuple


class Offset(NamedTuple):
    """A zero-based set of offsets into a file, which could be used as
    the parameters in a Python slice to get just this object back"""

    start: int
    end: int


class EditorPosition(NamedTuple):
    """The one-based line/column positions for a given key with inclusive starts and
    ends, which could be used for highlighting in an editor such as VS Code"""

    start_line: int
    start_col: int
    end_line: int
    end_col: int


class Position(NamedTuple):
    """The zero-based line/column positions for a given key with inclusive starts
    and non-inclusive ends, which could be used in Python slices"""

    start_line: int
    start_col: int
    end_line: int
    end_col: int

    @property
    def editor(self) -> EditorPosition:
        return EditorPosition(
            start_line=self.start_line + 1,
            start_col=self.start_col + 1,
            end_line=self.end_line + 1,
            end_col=self.end_col,
        )


class JSONMapper:
    """Entry point into the JSON mapper, which can map JSON keys to
    locations in the source file for slicing or highlighting"""

    def __init__(self, io: IO):
        if not io.seekable():
            raise TypeError("Input IO must be seekable")

        self._io = io

    @cached_property
    def offsets(self) -> Dict[JSONKeyTuple, Offset]:
        """The offsets of every key tuple in the source file"""

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

        # We need to use price is right minus one rules - find the
        # highest number line break that is *less than* the given position.
        # As luck would happen, the bisect module can do almost exactly this already.

        # If the position we are searching for is beyond the bound
        # of our list, bisect will give me back an index beyond the list.
        # This is used to bound it to within the appropriate values.
        max_index = len(self._line_break_positions) - 1

        return bisect_left(self._line_break_positions, position, hi=max_index)
