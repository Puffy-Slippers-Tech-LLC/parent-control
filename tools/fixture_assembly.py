#!/usr/bin/python3 -I -S -B
"""Assemble native fixture bytes using only a frozen source closure."""
import argparse
from pathlib import Path
import sys


def assemble(source, compiled, output, inputs_path):
    source = source.resolve(strict=True)
    compiled = compiled.resolve(strict=True)
    output = output.resolve(strict=True)
    sys.path.insert(0, str(source))
    from tools import fixture_manifest
    raw = inputs_path.read_bytes()
    if len(raw) > fixture_manifest.MAX_MANIFEST:
        raise ValueError('fixture assembly inputs exceed manifest limit')
    inputs = fixture_manifest._decode(raw)
    payloads = {}
    for member, declaration in fixture_manifest.declarations().items():
        key = declaration['source']
        if isinstance(key, bytes):
            payloads[member] = key
        elif key in ('onpc-test-gui.py', 'gtk_automation.py'):
            name = ('tests/fixtures/gui_application.py' if key == 'onpc-test-gui.py'
                    else 'common/oh_no_parent_control_ui/gtk_automation.py')
            payloads[member] = (source / name).read_bytes()
        else:
            payloads[member] = (compiled / key).read_bytes()
    fixture_manifest.write(output, inputs, payloads)
    return fixture_manifest.verify(output, target=inputs['target']['os'])


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for option in ('source', 'compiled', 'output', 'inputs'):
        parser.add_argument('--' + option, type=Path, required=True)
    arguments = parser.parse_args()
    try:
        assemble(arguments.source, arguments.compiled, arguments.output, arguments.inputs)
    except (OSError, ValueError) as error:
        parser.exit(1, 'fixture assembly: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
