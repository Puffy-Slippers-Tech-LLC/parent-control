"""Read-only listing of the installed dispatcher's literal check bindings."""
import ast
import json
from pathlib import Path


def inventory(directory=Path(__file__).resolve().parent):
    result = []
    for path in sorted(directory.glob('check_*.py')):
        if path.is_symlink() or not path.is_file():
            continue
        description = ast.get_docstring(ast.parse(path.read_text())) or ''
        result.append({'name': path.stem, 'description': description.split('\n')[0]})
    return result


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
