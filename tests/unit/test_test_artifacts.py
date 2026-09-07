"""Real-file coverage for format-independent, confined artifact inspection."""

import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = runpy.run_path(str(ROOT / 'tools/onpc-test-artifacts'))


@pytest.fixture
def artifact(tmp_path):
    directory = tmp_path / 'artifacts' / 'future run' / 'nested'
    directory.mkdir(parents=True)
    source = directory / 'result.json'
    source.write_bytes(b'0123456789\x00\xff')
    source.chmod(0o600)
    return tmp_path, source


@pytest.mark.parametrize('name', ['selected-inputs.json', 'test_future.py', 'results.xml',
    'raw.log', 'image.png', 'image.webp', 'recording.webm', 'unknown-format', 'file with spaces'])
def test_reads_and_exports_any_format_without_changing_source(artifact, name):
    checkout, original = artifact
    source = original.with_name(name)
    original.rename(source)
    before = source.stat()
    with HELPER['open_source'](str(source), checkout, os.getuid()) as (fd, info):
        output = io.BytesIO()
        HELPER['copy_bytes'](fd, output, info.st_size)
        assert output.getvalue() == b'0123456789\x00\xff'
        os.lseek(fd, 0, os.SEEK_SET)
        exported = Path(HELPER['export'](fd, info, str(source), os.getuid(), os.getgid()))
    try:
        assert exported.read_bytes() == output.getvalue()
        assert exported.stat().st_mode & 0o777 == 0o600
        assert exported.parent.stat().st_mode & 0o777 == 0o700
        assert exported.stat().st_uid == exported.parent.stat().st_uid == os.getuid()
        assert exported.stat().st_gid == exported.parent.stat().st_gid == os.getgid()
        assert exported.name == name
        assert source.stat().st_mode == before.st_mode
        assert source.stat().st_mtime_ns == before.st_mtime_ns
    finally:
        # This fixture records and owns the exact export directory it removes.
        shutil.rmtree(exported.parent)


@pytest.mark.parametrize('path', ['/tmp/onpc-system-future/input/anything',
    '/tmp/onpc-another-suite/a/b/image.jpg', '/tmp/onpc-standalone.log',
    '/var/tmp/onpc-future/test', '/var/tmp/oh-no-parent-control-artifacts/run/log',
    '/var/log/oh-no-parent-control/future-component/rotated.log.1',
    '/checkout/tests/new-file', '/checkout/artifacts/arbitrary', '/checkout/output/build'])
def test_all_project_storage_categories_accept_future_names(path):
    assert HELPER['source_parts'](path, '/checkout') == path.split('/')[1:]


@pytest.mark.parametrize('path', ['/etc/shadow', '/tmp/unrelated/results.json',
    '/tmp/onpc', '/tmp/onpc-run/../secret', '/tmp/onpc-run//file',
    '/tmp/onpc-run/./file', 'relative/onpc-file', '/checkout/.git/config',
    '/checkout/artifacts-other/file', '/var/log/other/log'])
def test_refuses_paths_outside_project_storage(path):
    with pytest.raises(ValueError):
        HELPER['source_parts'](path, '/checkout')


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo', 'parent-symlink'])
def test_refuses_link_escapes_and_special_files(artifact, kind):
    checkout, source = artifact
    original = source.with_name('original')
    source.rename(original)
    if kind == 'symlink':
        source.symlink_to(original)
    elif kind == 'hardlink':
        os.link(original, source)
    elif kind == 'fifo':
        os.mkfifo(source)
    else:
        source.parent.rename(source.parent.with_name('moved'))
        source.parent.symlink_to(source.parent.with_name('moved'))
    with pytest.raises((ValueError, OSError)):
        with HELPER['open_source'](str(source), checkout, os.getuid()):
            pytest.fail('unsafe source accepted')


def test_open_descriptor_survives_path_replacement(artifact):
    checkout, source = artifact
    with HELPER['open_source'](str(source), checkout, os.getuid()) as (fd, info):
        source.rename(source.with_name('original'))
        source.symlink_to('/etc/passwd')
        output = io.BytesIO()
        HELPER['copy_bytes'](fd, output, info.st_size)
        assert output.getvalue() == b'0123456789\x00\xff'


@pytest.mark.parametrize('args,expected', [
    (['read', '--bytes', '4', '--offset', '3'], b'3456'),
    (['read', '--bytes', '0'], b''),
    (['read', '--offset', '100'], b''),
    (['tail', '--bytes', '4'], b'89\x00\xff'),
])
def test_command_reads_bounded_byte_slices(artifact, monkeypatch, args, expected):
    checkout, source = artifact
    namespace = HELPER['main'].__globals__
    monkeypatch.setitem(namespace, 'CHECKOUT', str(checkout))
    monkeypatch.setitem(namespace, 'caller', lambda: (os.getuid(), os.getgid()))
    output = io.BytesIO()
    monkeypatch.setattr(namespace['sys'], 'stdout', Mock(buffer=output))
    assert HELPER['main']([args[0], str(source), *args[1:]]) == 0
    assert output.getvalue() == expected


def test_directory_listing_and_metadata(artifact, monkeypatch, capsys):
    checkout, source = artifact
    namespace = HELPER['main'].__globals__
    monkeypatch.setitem(namespace, 'CHECKOUT', str(checkout))
    monkeypatch.setitem(namespace, 'caller', lambda: (os.getuid(), os.getgid()))
    assert HELPER['main'](['list', str(source.parent)]) == 0
    assert json.loads(capsys.readouterr().out) == ['result.json']
    assert HELPER['main'](['stat', str(source)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['kind'] == 'file' and result['mode'] == '0o600'
    assert result['bytes'] == 12
    assert HELPER['main'](['read', str(source.parent)]) == 2
    assert 'requires a regular file' in capsys.readouterr().err


@pytest.mark.parametrize('identity', ['', '0', '-1', 'invalid'])
def test_requires_pkexec_caller_identity(monkeypatch, identity):
    monkeypatch.setenv('PKEXEC_UID', identity)
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    with pytest.raises(ValueError):
        HELPER['caller']()


@pytest.mark.parametrize('override,allowed', [
    ({}, True), ({'program': '/usr/bin/head'}, False),
    ({'program': '/usr/bin/python3'}, False), ({'program': '/tmp/onpc-test-artifacts'}, False),
    ({'program': '/usr/local/libexec/onpc-test-artifacts-other'}, False),
    ({'id': 'other.action'}, False), ({'user': 'other'}, False),
    ({'local': False}, False), ({'active': False}, False), ({'admin': False}, False),
])
def test_actual_polkit_rule_authorizes_only_installed_helper(override, allowed):
    request = dict(id='org.freedesktop.policykit.exec',
                   program='/usr/local/libexec/onpc-test-artifacts',
                   user='root', local=True, active=True, admin=True)
    request.update(override)
    script = '''
const fs = require('fs'), vm = require('vm'), request = JSON.parse(process.argv[1]);
let rule;
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {
    polkit: {addRule: callback => {rule = callback;}, Result: {YES: 'yes'}}
});
const result = rule({id: request.id, lookup: key => request[key]}, {
    local: request.local, active: request.active,
    isInGroup: group => group === 'sudo' && request.admin
});
process.stdout.write(result === 'yes' ? 'allow' : 'abstain');
'''
    result = subprocess.run(['node', '-e', script, json.dumps(request),
                             str(ROOT / 'config/50-onpc-test-artifacts.rules')],
                            capture_output=True, text=True, check=True)
    assert result.stdout == ('allow' if allowed else 'abstain')
