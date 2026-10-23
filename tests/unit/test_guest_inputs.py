"""Frozen selected executable bytes cannot be replaced during an attempt."""

import pytest

from guest_inputs import Bundle, InputError


def write(root, name, text):
    path = root / 'tests/integration' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def bundle(root):
    return Bundle(root, [('tests/integration/entry.py', 'entry.py')])


def test_staged_source_mutation_is_never_accepted_as_a_new_input(tmp_path):
    import json
    write(tmp_path, 'entry.py', 'value = 1\n')
    payload = tmp_path / 'payload'
    files = bundle(tmp_path).stage(payload)
    (payload / 'selected-inputs.json').write_text(json.dumps({'files': files}))
    (payload / 'entry.py').write_text('value = 2\n')
    with pytest.raises(InputError, match='staged-digest'):
        Bundle.from_staged(tmp_path, payload)
