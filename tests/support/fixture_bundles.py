"""Small inert build-provenance records shared by fixture codec/lifetime tests."""
import hashlib

from tools.fixture_provenance import COMPILER_INPUTS, dependency_digest


def compiler_record(target):
    def file(name):
        return {'path': '/usr/lib/fixture-test/' + name, 'size': 12,
                'sha256': hashlib.sha256(name.encode()).hexdigest()}
    record = {'target': {'os': target, 'release': '26.04' if target == 'ubuntu' else '44',
                        'architecture': 'x86_64'},
              'compiler_version': 'inert target compiler', 'compiler_triple': 'x86_64-linux-gnu',
              'inputs': {name: file(name) for name in COMPILER_INPUTS},
              'headers': {'/usr/lib/fixture-test/header.h': file('header.h')},
              'python_runtime': {'/usr/lib/fixture-test/python.py': file('python.py')},
              'packages': ['inert-compiler\t1.0\tx86_64'], 'image_identity': None}
    record['dependency_sha256'] = dependency_digest(record)
    return record


def environment_record(target):
    prefix = ('localhost/onpc-deb-builder:ubuntu26.04-' if target == 'ubuntu'
              else 'localhost/onpc-rpm-builder:fc44-')
    return {'recipe_sha256': 'a' * 64, 'requirements_sha256': 'b' * 64,
            'image': prefix + 'c' * 20}
