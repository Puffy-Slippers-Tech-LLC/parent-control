"""Small inert build-provenance records shared by fixture codec/lifetime tests."""
import hashlib
import struct

from tools.fixture_provenance import COMPILER_INPUTS, dependency_digest


def inert_elf(identity):
    """A never-executed finite ELF64 fixture accepted by the real ABI reader."""
    data, base = bytearray(768), 0x400000
    loader = b'/lib64/ld-linux-x86-64.so.2\0'
    strings = b'\0libc.so.6\0GLIBC_2.2.5\0'
    struct.pack_into('<16sHHIQQQIHHHHHH', data, 0,
                     b'\x7fELF\x02\x01\x01' + bytes(9), 2, 62, 1,
                     base + 700, 64, 0, 0, 64, 56, 3, 0, 0, 0)
    for index, segment in enumerate((
            (1, 5, 0, base, base, len(data), len(data), 1),
            (3, 4, 256, base + 256, base + 256, len(loader), len(loader), 1),
            (2, 4, 320, base + 320, base + 320, 96, 96, 1))):
        struct.pack_into('<IIQQQQQQ', data, 64 + index * 56, *segment)
    data[256:256 + len(loader)] = loader
    for index, entry in enumerate(((5, base + 512), (10, len(strings)), (1, 1),
                                   (0x6fffffff, 1), (0x6ffffffe, base + 600), (0, 0))):
        struct.pack_into('<qQ', data, 320 + index * 16, *entry)
    data[512:512 + len(strings)] = strings
    struct.pack_into('<HHIII', data, 600, 1, 1, 1, 16, 0)
    struct.pack_into('<IHHII', data, 616, 0, 0, 2, 11, 0)
    data[700:700 + len(identity)] = identity.encode()
    return bytes(data)


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
