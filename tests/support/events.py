"""Read completed JSON-lines events from test-owned preview recordings."""

import json


def read_events(path):
    """Return complete records; a writer's unfinished final line is not an event yet."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in text.splitlines(keepends=True)
            if line.endswith("\n")]
