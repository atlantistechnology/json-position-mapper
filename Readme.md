# JSON Mapper

Tooling that can map a given JSON key to either a file offset or a line/column pair

This tooling is still in beta and the API is subject to change.

## Purpose

This was designed to support a custom VS code JSON validator in an unrelated product. We needed to be able to know information such as `people.0.name` started at line 8 column 2 and ended at line 8 column 12, or that `people.0` (the entire sub-object) spanned from line 6 column 1 through line 18 column 1.

## Interface

The primary interface to the JSON mapper is `json_mapper.mapper.JSONMapper`. This is initialized with a seekable IO object (such as a file or StringIO) and has the following public properties and methods:

- `JSONMapper.offsets`: A cached property that contains a mapping of all the keys in the object to their relative file positions. The keys are tuples representing the path to get to a given JSON object(`('people', 0, 'name')`) in my example above and the offsets are named tuples with `start` and `end` parameters. The offsets are inclusive at the start and non-inclusive at the end - the same as Python slice mechanics. 
- `JSONMapper.get_position(key: Tuple)`: Get the start and end line/column offsets for a given JSON key. A `json_mapper.mapper.Position` object is returned which has `start_line`, `start_col`, `end_line`, and `end_col` stored values, and an `editor` calculated property, which returns a `json_mapper.mapper.EditorPosition`
- `JSONMapper.get_position(key: Tuple).editor`: Get the `json_mapper.mapper.EditorPosition` object for a given JSON key. This is very similar to the non-editor based object, except that it uses inclusive starts and ends and all values are one based. This is what you will want to use if you are trying to use this library to write a VS Code task that highlights JSON files for problems.

## Example

Installation: `pip install json-position-mapper`

Sample JSON file: `example.json`

```json
{
    "people": [
        {
            "name": "Adam",
            "favoriteFood": "pie",
            "attributes": {
                "eyeColor": "orange",
                "height": "12 foot",
                "happy": true
            }
        },
        {
            "name": "David",
            "favoriteFood": "sushi",
            "attributes": {
                "eyeColor": "fuscha",
                "height": "4 inches",
                "happy": null
            }
        }
    ]
}
```

Example Python file: `example.py`

```python
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

```
