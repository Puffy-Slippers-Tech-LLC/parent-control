"""Real-file coverage for format-independent, confined artifact inspection."""

import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess

import pytest

from tests.support.paths import ROOT
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
def test_reads_and_exports_any_format_without_changing_source(artifact, name, monkeypatch):
    checkout, original = artifact
    import test_storage
    monkeypatch.setattr(test_storage, 'ROOT', checkout)
    monkeypatch.setitem(HELPER['export'].__globals__, 'CHECKOUT', str(checkout))
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
        assert exported.is_relative_to(checkout / 'output/test-runs/host/exports')
        assert source.stat().st_mode == before.st_mode
        assert source.stat().st_mtime_ns == before.st_mtime_ns
    finally:
        # This fixture records and owns the exact export directory it removes.
        shutil.rmtree(exported.parent)


@pytest.fixture
def private_export(artifact, monkeypatch):
    import test_storage
    checkout, source = artifact
    monkeypatch.setattr(test_storage, 'ROOT', checkout)
    monkeypatch.setitem(HELPER['export'].__globals__, 'CHECKOUT', str(checkout))

    def publish(path=source):
        with HELPER['open_source'](str(path), checkout, os.getuid()) as (fd, info):
            return Path(HELPER['export'](fd, info, str(path), os.getuid(), os.getgid()))

    return checkout, source, publish


def test_identical_private_exports_reuse_without_rotating_other_reports(private_export, monkeypatch):
    import test_retention
    checkout, source, publish = private_export
    first = publish()
    other = source.with_name('other.log')
    other.write_bytes(b'other report')
    kept = publish(other)
    journal = first.parent.parent / 'retention' / 'current.json'
    before = journal.read_bytes()
    monkeypatch.setattr(test_retention.Publication, 'allocate',
                        lambda *_a, **_k: pytest.fail('identical export allocated a slot'))
    for _ in range(7):
        assert publish() == first
    assert journal.read_bytes() == before
    assert kept.read_bytes() == b'other report'
    assert first.read_bytes() == source.read_bytes()
    assert first.stat().st_ino != source.stat().st_ino


@pytest.mark.parametrize('change', ['bytes', 'replace', 'basename'])
def test_changed_source_and_equal_basenames_do_not_reuse_private_export(private_export, change):
    _, source, publish = private_export
    first = publish()
    if change == 'bytes':
        source.write_bytes(b'changed')
    elif change == 'replace':
        old = source.with_name('old')
        source.rename(old)
        source.write_bytes(first.read_bytes())
    else:
        second = source.parent / 'second'
        second.mkdir()
        second = second / source.name
        second.write_bytes(source.read_bytes())
        source = second
    fresh = publish(source)
    assert fresh != first
    assert fresh.read_bytes() == source.read_bytes()
    assert first.read_bytes() == b'0123456789\x00\xff'


@pytest.mark.parametrize('fault', ['missing', 'bytes', 'replace', 'receipt'])
def test_stale_private_export_refuses_instead_of_returning_saved_path(private_export, fault):
    _, source, publish = private_export
    first = publish()
    journal = first.parent.parent / 'retention' / 'current.json'
    before = journal.read_bytes()
    if fault == 'missing':
        first.unlink()
    elif fault == 'bytes':
        first.write_bytes(b'wrong')
    elif fault == 'replace':
        first.rename(first.with_name('previous'))
        first.write_bytes(source.read_bytes())
        first.chmod(0o600)
    else:
        (first.parent / '.onpc-export' / 'receipt.json').write_bytes(b'{}')
    with pytest.raises((ValueError, FileNotFoundError)):
        publish()
    assert journal.read_bytes() == before
    assert source.read_bytes() == b'0123456789\x00\xff'


@pytest.mark.parametrize('name', ['receipt.json', '.onpc-export', '.onpc-export-control'])
def test_private_export_metadata_preserves_original_filename(private_export, name):
    _, source, publish = private_export
    named = source.with_name(name)
    source.rename(named)
    first = publish(named)
    assert first.name == name and first.read_bytes() == named.read_bytes()
    assert publish(named) == first


def test_concurrent_identical_private_exports_commit_once(private_export):
    from concurrent.futures import ThreadPoolExecutor
    _, source, publish = private_export
    with ThreadPoolExecutor(max_workers=4) as pool:
        copies = list(pool.map(lambda _: publish(), range(8)))
    assert len(set(copies)) == 1
    journal = json.loads((copies[0].parent.parent / 'retention' / 'current.json').read_text())
    assert journal['history'] == [] and len(journal['paths']) == 1
    assert copies[0].read_bytes() == source.read_bytes()


def test_interrupted_private_copy_preserves_previous_publication(private_export, monkeypatch):
    import artifact_export
    _, source, publish = private_export
    first = publish()
    source.write_bytes(b'new result')
    original = artifact_export.checksum

    def fail(fd, size, output=None):
        if output is not None:
            output.write(b'partial')
            raise RuntimeError('interrupted copy')
        return original(fd, size)

    with monkeypatch.context() as patch:
        patch.setattr(artifact_export, 'checksum', fail)
        with pytest.raises(RuntimeError, match='interrupted'):
            publish()
    assert first.read_bytes() == b'0123456789\x00\xff'
    assert not (first.parent.parent / 'retention' / 'publication.json').exists()
    assert len(list(first.parent.parent.glob('onpc-artifact-export-*'))) == 1
    assert publish().read_bytes() == b'new result'


def test_raw_and_grouped_exports_share_verified_retention_recovery(private_export, monkeypatch):
    import evidence_bundle
    import test_retention
    checkout, source, publish = private_export
    first = publish()
    with evidence_bundle.Selection(checkout, os.getuid(), os.getgid(), [], [str(first)], []) as selection:
        grouped = evidence_bundle.export(selection, expected=selection.selection_sha256)
    assert evidence_bundle.inspect(checkout, os.getuid(), os.getgid(), grouped['path'],
                                   member=str(first)) == source.read_bytes()
    assert publish() == first
    source.write_bytes(b'deferred raw result')
    commit = test_retention.Publication.commit
    with monkeypatch.context() as patch:
        patch.setattr(test_retention.Publication, 'commit',
                      lambda transaction: commit(transaction, defer_cleanup=True))
        deferred = publish()
    assert (deferred.parent.parent / 'retention' / 'publication.json').exists()
    assert evidence_bundle.finish(checkout, os.getuid(), os.getgid())
    assert not (deferred.parent.parent / 'retention' / 'publication.json').exists()
    assert deferred.read_bytes() == source.read_bytes()


def test_exporting_oldest_saved_copy_refuses_before_source_retirement(private_export):
    _, source, publish = private_export
    first = publish()
    for index in range(2):
        other = source.with_name(f'other-{index}.log')
        other.write_bytes(str(index).encode())
        publish(other)
    journal = first.parent.parent / 'retention' / 'current.json'
    before = journal.read_bytes()
    with pytest.raises(ValueError, match='would retire the selected source'):
        publish(first)
    assert first.read_bytes() == source.read_bytes()
    assert journal.read_bytes() == before
    assert not (journal.parent / 'publication.json').exists()


def test_raw_reuse_keeps_copy_verified_through_source_revalidation(private_export, monkeypatch):
    from contextlib import contextmanager
    _, source, publish = private_export
    first = publish()
    opener = HELPER['export'].__globals__['open_source']
    calls = []

    @contextmanager
    def mutate_after_verification(*args):
        calls.append(args[0])
        if len(calls) == 3:  # Initial open, inventory check, reuse source check.
            first.write_bytes(b'changed while checking source')
        with opener(*args) as opened:
            yield opened

    monkeypatch.setitem(HELPER['export'].__globals__, 'open_source', mutate_after_verification)
    monkeypatch.setitem(HELPER, 'open_source', mutate_after_verification)
    with pytest.raises(ValueError, match='private copy changed during verification'):
        publish()
    assert len(calls) == 3 and source.read_bytes() == b'0123456789\x00\xff'


def test_scoped_bundle_helper_derives_owner_from_validated_plan(tmp_path, monkeypatch, capsys):
    import evidence_bundle
    import execution_plan
    from contextlib import contextmanager
    from types import SimpleNamespace
    namespace = HELPER['main'].__globals__
    monkeypatch.setitem(namespace, 'CHECKOUT', str(tmp_path))
    monkeypatch.setitem(namespace, 'caller', lambda: (os.geteuid(), os.getegid()))
    seen = {}
    def load(root, path):
        assert root == tmp_path and path == 'docs/Plan.md'
        return SimpleNamespace(path=path)
    monkeypatch.setattr(execution_plan.Plan, 'load', load)
    @contextmanager
    def selection(*args, **kwargs):
        seen.update(kwargs)
        yield SimpleNamespace(plan=lambda: {'selection_sha256': 'verified'})
    monkeypatch.setattr(evidence_bundle, 'Selection', selection)
    assert HELPER['main'](['bundle-plan', '--plan', 'docs/Plan.md', '--source', '/source']) == 0
    assert seen == {'plan_namespace': execution_plan.plan_namespace('docs/Plan.md'), 'references': []}
    assert json.loads(capsys.readouterr().out)['selection_sha256'] == 'verified'


@pytest.mark.parametrize('failure', ['missing', 'permission', 'integrity'])
def test_scoped_helper_distinguishes_missing_references_from_refusals(tmp_path, monkeypatch, capsys, failure):
    import evidence_bundle
    import execution_plan
    from types import SimpleNamespace
    namespace = HELPER['main'].__globals__
    monkeypatch.setitem(namespace, 'CHECKOUT', str(tmp_path))
    monkeypatch.setitem(namespace, 'caller', lambda: (os.geteuid(), os.getegid()))
    monkeypatch.setattr(execution_plan.Plan, 'load', lambda *_: SimpleNamespace(path='docs/Plan.md'))
    path = str(tmp_path / 'output/test-runs/privileged/allocations/onpc-expired/result.json')
    def selection(*_, **kwargs):
        assert kwargs['references'] == [path]
        if failure == 'missing':
            raise evidence_bundle.EvidenceUnavailable([path])
        if failure == 'permission':
            raise PermissionError('private')
        raise ValueError('bundle: allocation identity or mount changed')
    monkeypatch.setattr(evidence_bundle, 'Selection', selection)
    status = HELPER['main'](['bundle-plan', '--plan', 'docs/Plan.md', '--reference', path])
    captured = capsys.readouterr()
    assert not captured.out
    if failure == 'missing':
        assert status == 3
        assert json.loads(captured.err) == dict(error='evidence_unavailable', paths=[path])
    else:
        assert status == 2 and captured.err.startswith('test-artifacts: ')


@pytest.fixture
def bundle_helper(tmp_path, monkeypatch):
    namespace = HELPER['main'].__globals__
    monkeypatch.setitem(namespace, 'CHECKOUT', str(tmp_path))
    monkeypatch.setitem(namespace, 'caller', lambda: (os.geteuid(), os.getegid()))
    return tmp_path


@pytest.mark.parametrize('arguments', [
    [], ['--record-id', 'a' * 64], ['--member-id', 'b' * 64],
    ['--record-id', 'a' * 64, '--member-id', 'b' * 64],
    ['--record-id', 'a' * 64, '--closure-sha256', 'c' * 64],
    ['--path', '/original', '--member-id', 'b' * 64],
    ['--path', '/original', '--closure-sha256', 'c' * 64],
    ['--path', '/original', '--record-id', 'a' * 64,
     '--member-id', 'b' * 64, '--closure-sha256', 'c' * 64],
    ['--record-id', 'A' * 64, '--member-id', 'b' * 64, '--closure-sha256', 'c' * 64],
    ['--record-id', 'a' * 64, '--member-id', 'short', '--closure-sha256', 'c' * 64],
])
def test_bundle_read_refuses_incomplete_conflicting_or_malformed_selector(monkeypatch, arguments):
    monkeypatch.setitem(HELPER['main'].__globals__, 'caller',
                        lambda: pytest.fail('invalid selector reached authenticated dispatch'))
    with pytest.raises(SystemExit) as failure:
        HELPER['main'](['bundle-read', '/bundle/evidence.zip', *arguments])
    assert failure.value.code == 2


@pytest.mark.parametrize('structured', [False, True])
def test_bundle_read_dispatches_exact_selector_and_bounded_slice(bundle_helper, monkeypatch, capsys, structured):
    import evidence_bundle
    seen = []
    def inspect(*args, **kwargs):
        seen.append((args, kwargs))
        return {'verified': True}
    monkeypatch.setattr(evidence_bundle, 'inspect', inspect)
    selector = (['--record-id', 'a' * 64, '--member-id', 'b' * 64, '--closure-sha256', 'c' * 64]
                if structured else ['--path', '/original/file'])
    assert HELPER['main'](['bundle-read', '/bundle/evidence.zip', *selector,
                           '--offset', '3', '--bytes', '9']) == 0
    expected = (dict(record_id='a' * 64, member_id='b' * 64, closure_sha256='c' * 64)
                if structured else dict(member='/original/file'))
    assert seen == [((str(bundle_helper), os.geteuid(), os.getegid(), '/bundle/evidence.zip'),
                     dict(offset=3, count=9, **expected))]
    assert json.loads(capsys.readouterr().out) == {'verified': True}


@pytest.mark.parametrize('failure', ['absent', 'wrong-context', 'wrong-member', 'closure', 'permission'])
def test_bundle_read_keeps_exact_resolution_refusals_distinct_from_renewal(
        bundle_helper, monkeypatch, capsys, failure):
    import evidence_bundle
    def refused(*args, **kwargs):
        assert kwargs == dict(record_id='a' * 64, member_id='b' * 64,
                              closure_sha256='c' * 64, offset=0, count=8000)
        if failure == 'permission':
            raise PermissionError('private source')
        raise ValueError('bundle: ' + failure)
    monkeypatch.setattr(evidence_bundle, 'inspect', refused)
    assert HELPER['main'](['bundle-read', '/bundle/evidence.zip', '--record-id', 'a' * 64,
                           '--member-id', 'b' * 64, '--closure-sha256', 'c' * 64]) == 2
    captured = capsys.readouterr()
    assert not captured.out and captured.err.startswith('test-artifacts: ')
    assert 'evidence_unavailable' not in captured.err


@pytest.mark.parametrize('action', ['bundle-plan', 'bundle-export'])
@pytest.mark.parametrize('arguments', [
    ['--record-reference', 'locator#selector'], ['--consumer', '{}'],
    ['--record-reference', 'locator#selector', '--consumer', '{}', '--consumer', '{}'],
    ['--capture', 'unregistered-capture'],
])
def test_structured_bundle_parser_requires_one_consumer_and_references(action, arguments, monkeypatch):
    monkeypatch.setitem(HELPER['main'].__globals__, 'caller',
                        lambda: pytest.fail('invalid selection reached authenticated dispatch'))
    with pytest.raises(SystemExit) as failure:
        HELPER['main']([action, *(['--expect', 'digest'] if action == 'bundle-export' else []),
                        *arguments])
    assert failure.value.code == 2


@pytest.mark.parametrize('value', ['{', '[]', '{"role":"example", "version":1}',
    '{"role":"example","role":"required_evidence"}', '{"version":NaN}'])
def test_structured_bundle_refuses_noncanonical_or_ambiguous_consumer(bundle_helper, monkeypatch, capsys, value):
    import evidence_bundle
    monkeypatch.setattr(evidence_bundle, 'Selection',
                        lambda *_args, **_kwargs: pytest.fail('invalid JSON reached Selection'))
    assert HELPER['main'](['bundle-plan', '--record-reference', 'locator#selector',
                           '--consumer', value]) == 2
    captured = capsys.readouterr()
    assert not captured.out and captured.err.startswith('test-artifacts: ')


@pytest.mark.parametrize('action', ['bundle-plan', 'bundle-export'])
def test_structured_bundle_dispatch_preserves_legacy_selections(bundle_helper, monkeypatch, capsys, action):
    import evidence_bundle
    import execution_plan
    from contextlib import contextmanager
    from types import SimpleNamespace
    consumer = dict(role='required_evidence', version=1)
    wire = evidence_bundle.encoded(consumer).decode()
    monkeypatch.setattr(execution_plan.Plan, 'load', lambda *_: SimpleNamespace(path='docs/Plan.md'))
    seen = []
    @contextmanager
    def selection(*args, **kwargs):
        seen.append((args, kwargs))
        yield SimpleNamespace(plan=lambda: {'selection_sha256': 'verified'})
    monkeypatch.setattr(evidence_bundle, 'Selection', selection)
    monkeypatch.setattr(evidence_bundle, 'export',
        lambda selected, **kwargs: {'export': kwargs})
    arguments = ['--plan', 'docs/Plan.md', '--source', '/source', '--bundle', '/bundle',
        '--reference', '/legacy', '--record-reference', 'first#selector',
        '--record-reference', 'second#selector', '--consumer', wire]
    if action == 'bundle-export':
        arguments += ['--expect', 'digest', '--defer-cleanup']
    assert HELPER['main']([action, *arguments]) == 0
    assert seen == [((str(bundle_helper), os.geteuid(), os.getegid(), [], ['/source'], ['/bundle']),
        dict(plan_namespace=execution_plan.plan_namespace('docs/Plan.md'), references=['/legacy'],
             record_references=['first#selector', 'second#selector'], consumer=consumer))]
    result = json.loads(capsys.readouterr().out)
    assert result == ({'selection_sha256': 'verified'} if action == 'bundle-plan' else
                      {'export': {'expected': 'digest', 'defer_cleanup': True}})


def test_structured_consumer_role_cannot_override_selection_refusal(bundle_helper, monkeypatch, capsys):
    import evidence_bundle
    consumer = dict(role='example', version=1)
    def refused(*args, **kwargs):
        assert kwargs['consumer'] == consumer
        raise ValueError('bundle: consumer owner or expected context is not authenticated')
    monkeypatch.setattr(evidence_bundle, 'Selection', refused)
    assert HELPER['main'](['bundle-plan', '--record-reference', 'locator#selector',
                           '--consumer', evidence_bundle.encoded(consumer).decode()]) == 2
    captured = capsys.readouterr()
    assert not captured.out and 'not authenticated' in captured.err


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
    # A real text stream implements fileno/isatty as argparse's public color
    # detection expects, including with a clean launcher environment.
    monkeypatch.setattr(namespace['sys'], 'stdout', io.TextIOWrapper(output))
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
    request = dict(id='com.puffyslippers.onpc.development.test-artifacts',
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
