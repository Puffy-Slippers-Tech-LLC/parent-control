#!/usr/bin/python3 -I -S -B
"""Compile a frozen minimal fixture runtime inside a declared target environment.

The outer fixture builder owns target selection, producer lifetime and publication.
This helper neither creates build images nor installs target prerequisites.
"""
from __future__ import annotations

import argparse
from contextvars import ContextVar
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import stat
import subprocess
import sys


TARGETS = {'ubuntu': '26.04', 'fedora': '44'}
IDENTITIES = ('mechanical', 'A', 'H', 'S', 'N', 'trusted-hard', 'trusted-soft',
              'trusted-activity')
READY = b'ONPC_TEST_APPLICATION_READY\n'
_LEASE_FDS = ContextVar('fixture_target_lease_fds', default=())


def _environment():
    result = {'PATH': os.defpath, 'LANG': 'C', 'LC_ALL': 'C', 'SOURCE_DATE_EPOCH': '0'}
    for name in ('TMPDIR', 'TMP', 'TEMP'):
        if name in os.environ:
            result[name] = os.environ[name]
    return result


def _run(command, *, timeout=30):
    return subprocess.run(command, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout,
                          pass_fds=_LEASE_FDS.get(),
                          env=_environment())


def _text(command):
    return _run(command).stdout.decode('utf-8').strip()


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _release():
    result = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator:
            if key in result:
                raise ValueError('duplicate target release field')
            result[key] = value.strip('"\'')
    return result


def _input(path):
    candidate = Path(path)
    if not candidate.is_absolute():
        found = shutil.which(str(candidate), path=os.defpath)
        if found is None:
            raise ValueError('target compiler input unavailable: ' + str(path))
        candidate = Path(found)
    candidate = candidate.resolve(strict=True)
    if not candidate.is_file():
        raise ValueError('target compiler input is not regular')
    return {'path': str(candidate), 'size': candidate.stat().st_size,
            'sha256': _hash(candidate)}


def _packages(target, inputs):
    paths = sorted({item['path'] for item in inputs.values()})
    if target == 'ubuntu':
        names = set()
        for path in paths:
            # usrmerge aliases can be listed under either package spelling.
            try:
                result = _text(['dpkg-query', '--search', path])
                spellings = {path}
            except subprocess.CalledProcessError:
                if not path.startswith('/usr/'):
                    raise
                alias = path.removeprefix('/usr')
                result = _text(['dpkg-query', '--search', alias])
                spellings = {alias}
            owners = set()
            for line in result.splitlines():
                owner, separator, owned = line.partition(': ')
                if separator and owned in spellings:
                    owners.update(owner.split(', '))
            if not owners:
                raise ValueError('target compiler input has no package owner')
            names.update(owners)
        if not names:
            raise ValueError('target compiler packages unavailable')
        rows = _text(['dpkg-query', '--show',
                      '--showformat=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n',
                      *sorted(names)]).splitlines()
        if any(len(row.split('\t')) != 4 or row.split('\t')[3].strip() != 'ii'
               for row in rows):
            raise ValueError('target compiler package is not installed')
    else:
        rows = _text(['rpm', '--query', '--file', '--queryformat',
                      '%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\t%{ARCH}\n',
                      *paths]).splitlines()
        if not rows or any(len(row.split('\t')) != 3 for row in rows):
            raise ValueError('target compiler packages unavailable')
    return sorted(set(rows))


def _toolchain(target, source):
    compiler = shutil.which('cc', path=os.defpath)
    if compiler is None:
        raise ValueError('target C compiler unavailable')
    inputs = {'cc': _input(compiler), 'readelf': _input('readelf'),
              'loader': _input('/lib64/ld-linux-x86-64.so.2')}
    for name in ('cc1', 'collect2', 'as', 'ld'):
        inputs[name] = _input(_text([compiler, '-print-prog-name=' + name]))
    for name in ('crt1.o', 'Scrt1.o', 'crti.o', 'crtn.o', 'crtbegin.o', 'crtbeginS.o',
                 'crtend.o', 'crtendS.o', 'libc.so', 'libc.so.6'):
        path = _text([compiler, '-print-file-name=' + name])
        if path == name:
            raise ValueError('target compiler sysroot input unavailable: ' + name)
        inputs[name] = _input(path)
    inputs['libgcc'] = _input(_text([compiler, '-print-libgcc-file-name']))
    inputs['python'] = _input(sys.executable)
    c_source = source / 'tests/fixtures/onpc_test_application.c'
    dependencies = _text([compiler, '-std=c11', '-O2', '-M', '-MT', 'fixture', str(c_source)])
    label, separator, dependencies = dependencies.replace('\\\n', ' ').partition(':')
    if not separator or label != 'fixture':
        raise ValueError('target compiler header dependency scan failed')
    headers = {}
    for name in shlex.split(dependencies):
        path = Path(name.replace('$$', '$')).resolve(strict=True)
        if path != c_source:
            headers[str(path)] = _input(path)
    if not headers:
        raise ValueError('target compiler header dependency closure unavailable')
    python_runtime = {}
    for module in tuple(sys.modules.values()):
        for attribute in ('__file__', '__cached__'):
            filename = getattr(module, attribute, None)
            if not filename:
                continue
            candidate = Path(filename)
            if not candidate.exists():
                continue
            path = candidate.resolve(strict=True)
            if path.is_relative_to(source) or not path.is_file():
                continue
            python_runtime[str(path)] = _input(path)
    python_sources = {name: value for name, value in python_runtime.items()
                      if Path(name).suffix != '.pyc'}
    packages = _packages(target, {**inputs, **headers, **python_sources})
    triple = _text([compiler, '-dumpmachine'])
    if not triple.startswith('x86_64-'):
        raise ValueError('fixture target compiler architecture mismatch')
    return {'target': {'os': target, 'release': TARGETS[target], 'architecture': 'x86_64'},
            'compiler_version': _text([compiler, '--version']),
            'compiler_triple': triple,
            'inputs': inputs, 'headers': headers, 'python_runtime': python_runtime,
            'packages': packages,
            'dependency_sha256': hashlib.sha256(json.dumps(
                {'inputs': inputs, 'headers': headers, 'python_runtime': python_runtime,
                 'packages': packages}, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest()}


def _abi(path):
    header = _text(['readelf', '--file-header', str(path)])
    program = _text(['readelf', '--program-headers', '--wide', str(path)])
    dynamic = _text(['readelf', '--dynamic', '--wide', str(path)])
    versions = _text(['readelf', '--version-info', '--wide', str(path)])
    if (not re.search(r'Class:\s+ELF64\b', header)
            or not re.search(r'Data:\s+2.s complement, little endian', header)
            or not re.search(r'Machine:\s+Advanced Micro Devices X86-64\b', header)):
        raise ValueError('fixture target ELF architecture mismatch')
    interpreters = re.findall(r'Requesting program interpreter:\s*([^\]]+)\]', program)
    needed = re.findall(r'\(NEEDED\).*Shared library: \[([^\]]+)\]', dynamic)
    if interpreters != ['/lib64/ld-linux-x86-64.so.2'] or needed != ['libc.so.6']:
        raise ValueError('fixture target ELF runtime dependency mismatch')
    loader = _input(interpreters[0])
    loaded = _text([interpreters[0], '--list', str(path)])
    if 'not found' in loaded or 'libc.so.6 =>' not in loaded:
        raise ValueError('fixture target ELF runtime dependency unavailable')
    return {'class': 'ELF64', 'machine': 'x86_64', 'interpreter': interpreters[0],
            'needed': needed, 'glibc_versions': sorted(set(re.findall(
                r'Name: (GLIBC_[A-Za-z0-9_.]+)', versions))), 'loader': loader,
            'sha256': _hash(path)}


def _witness(path, *, mechanical):
    if mechanical:
        result = _run([str(path)], timeout=5)
        if result.stdout != READY or result.stderr:
            raise ValueError('fixture target runtime witness failed')
        return
    process = subprocess.Popen([str(path), '--stay-alive'], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, pass_fds=_LEASE_FDS.get(),
                               env=_environment())
    try:
        ready, _, _ = select.select([process.stdout], [], [], 5)
        if not ready or os.read(process.stdout.fileno(), len(READY) + 1) != READY:
            raise ValueError('fixture target runtime witness failed')
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        if process.returncode != 0 or stdout or stderr:
            raise ValueError('fixture target runtime witness exit failed')
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


def build(source: Path, output: Path, target: str, *, lease_fds=()):
    descriptors = tuple(lease_fds)
    if (len(descriptors) != len(set(descriptors))
            or any(type(fd) is not int or fd < 3 for fd in descriptors)):
        raise ValueError('invalid fixture producer lease descriptors')
    for fd in descriptors:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('fixture producer lease descriptor must be a regular file')
    token = _LEASE_FDS.set(descriptors)
    try:
        return _build(source, output, target)
    finally:
        _LEASE_FDS.reset(token)


def _build(source: Path, output: Path, target: str):
    if target not in TARGETS:
        raise ValueError('unsupported fixture build target')
    release = _release()
    if (release.get('ID') != target or release.get('VERSION_ID') != TARGETS[target]
            or os.uname().machine != 'x86_64'):
        raise ValueError('fixture build requires the exact declared target environment')
    source = source.resolve(strict=True)
    output = output.resolve(strict=True)
    if not source.is_dir() or not output.is_dir() or any(output.iterdir()):
        raise ValueError('fixture target source/output must be directories; output must be empty')
    # Execute the frozen builder; its module path binds all declaration imports.
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location(
        'onpc_frozen_fixture_builder', source / 'tests/fixtures/build_test_applications.py')
    if spec is None or spec.loader is None:
        raise ValueError('frozen fixture builder unavailable')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    toolchain = _toolchain(target, source)
    workspace = output / 'build'
    workspace.mkdir(mode=0o700)
    previous_cc = os.environ.get('CC')
    os.environ['CC'] = toolchain['inputs']['cc']['path']
    try:
        proofs = {}
        for identity in IDENTITIES:
            headless = identity in ('mechanical', 'trusted-hard', 'trusted-soft')
            compiled = builder._compile_native(
                workspace, identity='default' if identity == 'mechanical' else identity,
                headless=headless, source_root=source, linker_flags=(), run=_run)
            destination = output / identity
            shutil.copyfile(compiled, destination)
            destination.chmod(0o755)
            proofs[identity] = _abi(destination)
            _witness(destination, mechanical=headless)
        if len({proof['sha256'] for proof in proofs.values()}) != len(IDENTITIES):
            raise ValueError('fixture target identities are not distinct')
        if _toolchain(target, source) != toolchain:
            raise ValueError('fixture target toolchain changed during compilation')
        toolchain['abi'] = proofs
        (output / 'toolchain.json').write_text(json.dumps(toolchain, sort_keys=True) + '\n')
        shutil.rmtree(workspace)
        return toolchain
    finally:
        if previous_cc is None:
            os.environ.pop('CC', None)
        else:
            os.environ['CC'] = previous_cc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=TARGETS, required=True)
    parser.add_argument('--lease-fd', type=int, action='append', default=[])
    arguments = parser.parse_args()
    try:
        build(arguments.source, arguments.output, arguments.target,
              lease_fds=arguments.lease_fd)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, 'fixture target build: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
