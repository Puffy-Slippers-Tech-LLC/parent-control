"""Strict native fixture build-input records, independent of output identity."""
import hashlib
import json
from pathlib import PurePosixPath
import re

IDENTITIES = ('mechanical', 'A', 'H', 'S', 'N', 'trusted-hard', 'trusted-soft',
              'trusted-activity')
COMPILER_INPUTS = frozenset(('cc', 'readelf', 'loader', 'cc1', 'collect2', 'as', 'ld',
    'crt1.o', 'Scrt1.o', 'crti.o', 'crtn.o', 'crtbegin.o', 'crtbeginS.o',
    'crtend.o', 'crtendS.o', 'libc.so', 'libc.so.6', 'libgcc', 'python'))


def require(condition, reason):
    if not condition:
        raise ValueError('fixture:provenance-' + reason)


def keys(value, names):
    return type(value) is dict and set(value) == set(names)


def sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def record(value):
    require(keys(value, ('path', 'size', 'sha256')), 'file-fields')
    path = value['path']
    require(type(path) is str and len(path) <= 4096 and
            path.startswith(('/usr/', '/lib/', '/lib64/')) and
            str(PurePosixPath(path)) == path and
            '..' not in PurePosixPath(path).parts, 'file-path')
    require(type(value['size']) is int and 0 <= value['size'] <= 512 * 1024 * 1024
            and sha(value['sha256']), 'file-values')


def dependency_digest(compiler):
    selected = {key: compiler[key] for key in ('inputs', 'headers', 'python_runtime', 'packages')}
    return hashlib.sha256(json.dumps(selected, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate(toolchain, target):
    require(keys(toolchain, ('environment', 'compiler')), 'fields')
    environment = toolchain['environment']
    require(keys(environment, ('recipe_sha256', 'requirements_sha256', 'image')),
            'environment-fields')
    require(sha(environment['recipe_sha256']) and sha(environment['requirements_sha256']),
            'environment-digest')
    prefix = ('localhost/onpc-deb-builder:ubuntu26.04-' if target['os'] == 'ubuntu'
              else 'localhost/onpc-rpm-builder:fc44-')
    require(type(environment['image']) is str and
            re.fullmatch(re.escape(prefix) + '[0-9a-f]{20}', environment['image']) is not None,
            'environment-image')
    compiler = toolchain['compiler']
    require(keys(compiler, ('target', 'compiler_version', 'compiler_triple', 'inputs', 'headers',
            'python_runtime', 'packages', 'dependency_sha256', 'image_identity')),
            'compiler-fields')
    require(compiler['target'] == target, 'target')
    require(type(compiler['compiler_version']) is str and
            0 < len(compiler['compiler_version']) <= 16384 and
            type(compiler['compiler_triple']) is str and
            re.fullmatch('x86_64-[a-z0-9_-]{1,100}', compiler['compiler_triple']) is not None,
            'compiler-version')
    require(keys(compiler['inputs'], COMPILER_INPUTS), 'compiler-inputs')
    for item in compiler['inputs'].values():
        record(item)
    for name in ('headers', 'python_runtime'):
        files = compiler[name]
        require(type(files) is dict and 0 < len(files) <= 2048, name)
        for path, item in files.items():
            record(item)
            require(path == item['path'], name + '-path')
    packages = compiler['packages']
    require(type(packages) is list and 0 < len(packages) <= 512 and
            all(type(item) is str and 0 < len(item) <= 4096 for item in packages)
            and packages == sorted(set(packages)), 'packages')
    require(sha(compiler['dependency_sha256']) and
            compiler['dependency_sha256'] == dependency_digest(compiler), 'dependency-digest')
    image = compiler['image_identity']
    require(image is None or type(image) is str and image.startswith('sha256:')
            and sha(image[7:]), 'image-identity')
