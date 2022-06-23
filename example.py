from io import StringIO
from json_mapper.mapper import JSONMapper, Position, Offset

with open("example.json") as f_in:
    in_memory = StringIO(f_in.read())

mapper = JSONMapper(in_memory)

# Get the entire slice offset of the 'people' key
print(mapper.offsets[("people",)])
# Output: Offset(start=16, end=488)

# Get the slice offset for people.0.name
print(mapper.offsets[("people", 0, "name")])
# Output: Offset(start=48, end=54)

# Get the line/column start and end for people.0
# This is what we would use if we were to use Python to split the file on line and then use slice mechanics
print(mapper.get_position(("people", 0)))
# Output: Position(start_line=2, start_col=8, end_line=10, end_col=9)

# This is what we would use to highlight in something like VS Code
print(mapper.get_position(("people", 0)).editor)
# Output: EditorPosition(start_line=3, start_col=9, end_line=11, end_col=9)
