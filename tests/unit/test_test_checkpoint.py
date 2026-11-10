"""Resume preserves passes and retries failures without trusting in-flight work.

All state and subprocess outputs are private pytest trees. The only real child
is a synchronously waited pytest with synthetic cases; there are no live VMs,
model sessions, displays, cleanup owners or shared launcher files.
"""

import json
import os
import subprocess
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import regression
import regression_events
import regression_selection
import test_commands
from test_checkpoint import Checkpoint, EXCLUDE, ONLY
from tests.support.paths import ROOT



def event(checkpoint, kind, case, failed=()):
    checkpoint.event('unit', dict(kind=kind, nodeid=case), set(failed))


def test_resume_keeps_only_finished_nonfailed_cases_and_fresh_run_resets(tmp_path):
    selection = [('unit', ['-x'])]
    checkpoint = Checkpoint(tmp_path, selection)
    event(checkpoint, 'finished', 'test.py::passed')
    event(checkpoint, 'failure', 'test.py::failed')
    event(checkpoint, 'finished', 'test.py::failed', ['test.py::failed'])
    checkpoint.finish([])
    resumed = Checkpoint(tmp_path, selection, resume=True)
    assert resumed.passed('unit') == {'test.py::passed'}
    assert not resumed.complete('unit')
    assert Checkpoint(tmp_path, selection).passed('unit') == set()


def test_failed_teardown_revokes_an_earlier_completion(tmp_path):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    event(checkpoint, 'finished', 'case')
    event(checkpoint, 'failure', 'case')
    assert Checkpoint(tmp_path, [('unit', [])], resume=True).passed('unit') == set()


def test_focused_retry_preserves_other_passes_without_completing_the_category(tmp_path):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    event(checkpoint, 'finished', 'earlier')
    event(checkpoint, 'finished', 'repaired')
    checkpoint.retry('unit', 'repaired')
    assert checkpoint.passed('unit') == {'earlier'}
    event(checkpoint, 'finished', 'repaired')
    checkpoint.finish([SimpleNamespace(retry_category='unit', count_overall=True, state='Passed')])
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert resumed.passed('unit') == {'earlier', 'repaired'}
    assert not resumed.complete('unit')
    assert resumed.retry_case is None


def test_retry_filter_never_reports_unexecuted_cases_as_resumed(monkeypatch):
    monkeypatch.setenv(ONLY, 'repaired')
    monkeypatch.setenv(EXCLUDE, '["earlier"]')
    items = [SimpleNamespace(nodeid=name) for name in ('earlier', 'repaired', 'remaining')]
    session = SimpleNamespace()
    config = SimpleNamespace(hook=SimpleNamespace(pytest_deselected=Mock()))
    regression_events.pytest_collection_modifyitems(session, config, items)
    assert [item.nodeid for item in items] == ['repaired']
    assert session.onpc_resumed_nodeids == ()
    assert not session.onpc_resume_empty


def test_retry_filter_runs_only_the_case_and_missing_case_is_not_a_pass(tmp_path):
    (tmp_path / 'test_sample.py').write_text(
        'def test_repaired():\n    pass\ndef test_remaining():\n    assert False\n')
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                       ONPC_REGRESSION_EVENTS='1', ONPC_REGRESSION_INVENTORY='1')
    environment.pop(EXCLUDE, None)
    command = ['/usr/bin/python3', '-B', '-m', 'pytest', '-p', 'no:cacheprovider',
               '-p', 'tools.regression_events', '--rootdir=.', '-q', 'test_sample.py']
    for case, expected in [('test_repaired', 0), ('test_missing', 5)]:
        environment[ONLY] = 'test_sample.py::' + case
        result = subprocess.run(command, cwd=tmp_path, env=environment,
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == expected, result.stdout + result.stderr
        events = [json.loads(line[len(regression_events.PREFIX):])
                  for line in result.stdout.splitlines() if line.startswith(regression_events.PREFIX)]
        assert [event['nodeid'] for event in events if event['kind'] == 'finished'] == (
            [environment[ONLY]] if expected == 0 else [])


def test_large_resume_checkpoint_batches_passes_but_saves_failure_and_shutdown(
        tmp_path, monkeypatch):
    import test_checkpoint

    clock = [0.0]
    monkeypatch.setattr(test_checkpoint, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    initial = [f'tests/unit/test_sample.py::test_case[{index}-' + 'x' * 200 + ']'
               for index in range(2000)]
    checkpoint.entry('unit')['passed'] = initial
    checkpoint.save()
    saves = []
    save = checkpoint.store.save

    def persist(fd, value, **kwargs):
        saves.append(clock[0])
        return save(fd, value, **kwargs)

    monkeypatch.setattr(checkpoint.store, 'save', persist)
    for index in range(1, 601):
        clock[0] = index / 10
        event(checkpoint, 'finished', f'new-{index}')
    assert saves == list(range(5, 61, 5))
    path = checkpoint.store.path / checkpoint.name
    assert set(json.loads(path.read_text())['categories']['unit']['passed']) == (
        set(initial) | {f'new-{index}' for index in range(1, 601)})

    clock[0] = 60.1
    event(checkpoint, 'failure', initial[0])
    assert saves[-1] == 60.1
    assert initial[0] not in json.loads(path.read_text())['categories']['unit']['passed']
    event(checkpoint, 'finished', 'pending-at-shutdown')
    assert 'pending-at-shutdown' not in json.loads(path.read_text())['categories']['unit']['passed']
    checkpoint.finish([])
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert resumed.passed('unit') == checkpoint.passed('unit')
    assert 'pending-at-shutdown' in resumed.passed('unit')
    assert not resumed.complete('unit')


def test_failed_resume_checkpoint_sync_keeps_pending_passes_for_retry(tmp_path, monkeypatch):
    import test_checkpoint

    clock = [0.0]
    monkeypatch.setattr(test_checkpoint, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    clock[0] = 5

    def broken(*_args, **_kwargs):
        raise OSError('checkpoint sync failed')

    with monkeypatch.context() as local:
        local.setattr(checkpoint.store, 'save', broken)
        with pytest.raises(OSError, match='checkpoint sync failed'):
            event(checkpoint, 'finished', 'first')
    assert checkpoint.dirty and checkpoint.synced == 0
    event(checkpoint, 'finished', 'second')
    assert not checkpoint.dirty
    assert Checkpoint(tmp_path, [('unit', [])], resume=True).passed('unit') == {'first', 'second'}


def test_resume_checks_every_repeated_category_selection(tmp_path):
    selection = [('unit', ['-k', 'first']), ('unit', ['-k', 'second'])]
    checkpoint = Checkpoint(tmp_path, selection)
    event(checkpoint, 'finished', 'passed')
    checkpoint.save()
    assert Checkpoint(tmp_path, selection, resume=True).passed('unit') == {'passed'}
    with pytest.raises(ValueError, match='selection differs'):
        Checkpoint(tmp_path, [('unit', ['-k', 'changed']), selection[1]], resume=True)


@pytest.mark.parametrize('invalid', ['passed', 'round', 'pending'])
def test_changed_selection_does_not_mask_invalid_saved_progress(tmp_path, invalid):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    if invalid == 'passed':
        checkpoint.entry('unit')['passed'] = [None]
    else:
        checkpoint.state[invalid] = 0 if invalid == 'round' else 'missing-category'
    checkpoint.save()
    path = checkpoint.store.path / checkpoint.name
    original = path.read_bytes()
    with pytest.raises(ValueError, match='invalid resume'):
        Checkpoint(tmp_path, [('ui', [])], resume=True)
    assert path.read_bytes() == original


@pytest.mark.parametrize('replacement', ['symlink', 'hardlink', 'mode', 'malformed'])
def test_checkpoint_refuses_unsafe_or_malformed_state(tmp_path, replacement):
    checkpoint = Checkpoint(tmp_path, [('e2e', [])], binding='guest-one')
    path = checkpoint.store.path / checkpoint.name
    if replacement == 'symlink':
        path.rename(path.with_name('original'))
        path.symlink_to(path.with_name('original'))
    elif replacement == 'hardlink':
        os.link(path, path.with_name('alias'))
    elif replacement == 'mode':
        path.chmod(0o644)
    else:
        path.write_text('{')
    with pytest.raises((ValueError, OSError)):
        Checkpoint(tmp_path, [('system', ['check_first'])], resume=True,
                   binding='guest-one', recover_missing=True)


def test_large_case_inventory_uses_private_snapshot_instead_of_large_environment(tmp_path, monkeypatch):
    # This private checkpoint must not inherit the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    cases = ['tests/unit/test_core.py::test_case[' + str(index) + 'x' * 200 + ']'
             for index in range(2000)]
    checkpoint.entry('unit')['passed'] = cases
    checkpoint.save()
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    value = resumed.environment('unit')
    assert len(value) < 1024
    assert regression_events.completed_cases(value) == set(cases)


def test_oversized_completion_cannot_poison_the_next_retry(tmp_path, monkeypatch):
    # Keep the synthetic retry independent of the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    boundary = 'p' * regression_events.MAX_CASE_ID_LENGTH
    oversized = boundary + 'x'
    event(checkpoint, 'finished', boundary)
    event(checkpoint, 'finished', oversized)
    checkpoint.save()
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert resumed.passed('unit') == {boundary}
    assert regression_events.completed_cases(resumed.environment('unit')) == {boundary}


def test_resume_repairs_legacy_oversized_ids_without_resetting_other_passes(tmp_path, monkeypatch):
    # Keep this private checkpoint independent of the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    selection = [('unit', []), ('static', ['shell'])]
    checkpoint = Checkpoint(tmp_path, selection)
    oversized = 'tests/unit/test_progress.py::test_case[' + 'x' * 120000 + ']'
    checkpoint.entry('unit').update(passed=['valid-pass', oversized], complete=True)
    checkpoint.entry('static')['complete'] = True
    checkpoint.save()
    resumed = Checkpoint(tmp_path, selection, resume=True)
    assert resumed.passed('unit') == {'valid-pass'}
    assert not resumed.complete('unit')
    assert resumed.complete('static')
    assert regression_events.completed_cases(resumed.environment('unit')) == {'valid-pass'}
    saved = json.loads((resumed.store.path / resumed.name).read_text())
    assert saved['categories']['unit']['passed'] == ['valid-pass']
    assert Checkpoint(tmp_path, selection, resume=True).state == saved


@pytest.mark.parametrize('invalid', [None, '', '\n', 123, 'duplicate'])
def test_oversized_recovery_still_refuses_malformed_inventory(tmp_path, invalid):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    oversized = 'x' * (regression_events.MAX_CASE_ID_LENGTH + 1)
    passed = [oversized, oversized] if invalid == 'duplicate' else [oversized, invalid]
    checkpoint.entry('unit')['passed'] = passed
    checkpoint.save()
    original = (checkpoint.store.path / checkpoint.name).read_bytes()
    with pytest.raises(ValueError, match='invalid resume case inventory'):
        Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert (checkpoint.store.path / checkpoint.name).read_bytes() == original


def test_pytest_resume_snapshot_still_refuses_oversized_ids(tmp_path):
    oversized = 'x' * (regression_events.MAX_CASE_ID_LENGTH + 1)
    with pytest.raises(ValueError, match='invalid resume case inventory'):
        regression_events.completed_cases(json.dumps([oversized]))
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_text(json.dumps([oversized]))
    snapshot.chmod(0o600)
    with pytest.raises(ValueError, match='invalid resume case inventory'):
        regression_events.completed_cases('@' + str(snapshot))


def test_repair_replay_removes_only_its_case_from_the_resume_snapshot(tmp_path, monkeypatch):
    # Keep this private checkpoint independent of the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    checkpoint.entry('unit').update(passed=['previous', 'diagnostic'], complete=True)
    checkpoint.save()
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    resumed.event('unit', dict(kind='failure', nodeid='diagnostic'), set())
    assert not resumed.complete('unit')
    assert regression_events.completed_cases(resumed.environment('unit')) == {'previous'}


@pytest.mark.parametrize('oversized', [False, True])
@pytest.mark.parametrize('interrupted', [False, True])
def test_real_pytest_resume_retries_failed_or_interrupted_case(tmp_path, interrupted, oversized):
    source = tmp_path / 'test_sample.py'
    source.write_text('''from pathlib import Path
import pytest
def record(name):
    with Path('calls').open('a') as stream:
        stream.write(name + '\\n')
@pytest.mark.parametrize('value', [None], ids=['PASSED_ID'])
def test_passed(value):
    record('passed')
def test_retry():
    record('retry')
    if not Path('fixed').exists():
        EXCEPTION
def test_pending():
    record('pending')
'''.replace('EXCEPTION', 'raise KeyboardInterrupt()' if interrupted else 'assert False')
   .replace('PASSED_ID', 'p' * 70000 if oversized else 'passed'))
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                       ONPC_REGRESSION_EVENTS='1', ONPC_REGRESSION_INVENTORY='1')
    environment.pop(EXCLUDE, None)
    command = ['/usr/bin/python3', '-B', '-m', 'pytest', '-p', 'no:cacheprovider',
               '-p', 'tools.regression_events', '-x', '-q', 'test_sample.py']
    first = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True,
                           text=True, timeout=30)
    assert first.returncode == (2 if interrupted else 1), first.stdout + first.stderr
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    failed = set()
    for line in first.stdout.splitlines():
        if line.startswith(regression_events.PREFIX):
            value = json.loads(line[len(regression_events.PREFIX):])
            if value['kind'] == 'failure':
                failed.add(value['nodeid'])
            checkpoint.event('unit', value, failed)
    checkpoint.finish([])
    source.with_name('fixed').touch()
    environment[EXCLUDE] = json.dumps(sorted(Checkpoint(tmp_path, [('unit', [])], resume=True).passed('unit')))
    second = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True,
                            text=True, timeout=30)
    assert second.returncode == 0, second.stdout + second.stderr
    assert (tmp_path / 'calls').read_text().splitlines() == (
        ['passed', 'retry', 'passed', 'retry', 'pending'] if oversized else
        ['passed', 'retry', 'retry', 'pending'])
    events = [json.loads(line[len(regression_events.PREFIX):])
              for line in second.stdout.splitlines() if line.startswith(regression_events.PREFIX)]
    collection = next(value for value in events if value['kind'] == 'collection')
    assert collection['total'] == (3 if oversized else 2)
    assert collection.get('resumed_nodeids', []) == json.loads(environment[EXCLUDE])
    if not oversized:
        assert collection['resumed_nodeids'][0].endswith('test_sample.py::test_passed[passed]')


def test_all_completed_inventory_succeeds_but_genuinely_empty_inventory_does_not(monkeypatch):
    monkeypatch.setenv(EXCLUDE, '["case"]')
    config = SimpleNamespace(hook=SimpleNamespace(pytest_deselected=Mock()))
    session = SimpleNamespace(exitstatus=5)
    items = [SimpleNamespace(nodeid='case')]
    regression_events.pytest_collection_modifyitems(session, config, items)
    regression_events.pytest_sessionfinish(session, 5)
    assert items == [] and session.exitstatus == 0
    empty = SimpleNamespace(exitstatus=5)
    regression_events.pytest_collection_modifyitems(empty, config, [])
    regression_events.pytest_sessionfinish(empty, 5)
    assert empty.exitstatus == 5
    session.exitstatus = 1
    regression_events.pytest_sessionfinish(session, 5)
    assert session.exitstatus == 1


def test_repository_pytest_configuration_registers_resume_hooks():
    cases = ['tests/unit/test_test_checkpoint.py::' + name for name in (
        'test_resume_keeps_only_finished_nonfailed_cases_and_fresh_run_resets',
        'test_failed_teardown_revokes_an_earlier_completion')]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'tools'))),
                       PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', ONPC_REGRESSION_EVENTS='1',
                       ONPC_REGRESSION_INVENTORY='1', **{EXCLUDE: json.dumps([cases[0]])})
    result = subprocess.run(['/usr/bin/python3', '-B', '-m', 'pytest',
                             '-p', 'no:cacheprovider', '--collect-only', '-q', *cases],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    events = [json.loads(line[len(regression_events.PREFIX):])
              for line in result.stdout.splitlines() if line.startswith(regression_events.PREFIX)]
    assert [value['nodeids'] for value in events if value['kind'] == 'collection'] == [[cases[1]]]
    assert [value['resumed_nodeids'] for value in events if value['kind'] == 'collection'] == [[cases[0]]]


@pytest.mark.parametrize('selector', [['-k', 'teardown'], ['-m', 'contract']])
def test_resume_counts_only_completed_cases_matching_original_selectors(selector):
    cases = ['tests/unit/test_test_checkpoint.py::' + name for name in (
        'test_failed_teardown_revokes_an_earlier_completion',
        'test_resume_keeps_only_finished_nonfailed_cases_and_fresh_run_resets')]
    # This module is classified as unit; -m contract excludes both cases.
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'tools'))),
                       PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', ONPC_REGRESSION_EVENTS='1',
                       ONPC_REGRESSION_INVENTORY='1', **{EXCLUDE: json.dumps(cases)})
    result = subprocess.run(['/usr/bin/python3', '-B', '-m', 'pytest',
                             '-p', 'no:cacheprovider', '--collect-only', '-q', *selector, *cases],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == (0 if selector[0] == '-k' else 5), result.stdout + result.stderr
    events = [json.loads(line[len(regression_events.PREFIX):])
              for line in result.stdout.splitlines() if line.startswith(regression_events.PREFIX)]
    collection = next(value for value in events if value['kind'] == 'collection')
    assert collection.get('resumed_nodeids', []) == (cases[:1] if selector[0] == '-k' else [])


def test_selected_run_skips_completed_category_and_retains_serial_failure_limit(tmp_path, monkeypatch):
    # Keep this private checkpoint independent of the outer repair run's exclusions.
    monkeypatch.delenv('ONPC_REPAIR_FAILED_CASES', raising=False)
    selection = [('static', ['shell']), ('unit', ['-x'])]
    checkpoint = Checkpoint(tmp_path, selection)
    checkpoint.finish([SimpleNamespace(retry_category='static', count_overall=True, state='Passed')])
    event(checkpoint, 'finished', 'tests/unit/test_core.py::passed')
    checkpoint.finish([])
    calls = []
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'f' * 64)
    monkeypatch.setattr(regression.host, 'environment', lambda _: {})
    monkeypatch.setattr(regression_selection, 'pytest_command',
                        lambda *_: ['pytest', 'no:cacheprovider', '-x', '--'])

    def run(self, command, *, output, env, **kwargs):
        calls.append(command)
        assert regression_events.completed_cases(env[EXCLUDE]) == {'tests/unit/test_core.py::passed'}
        value = dict(kind='collection', total=1, nodeids=['tests/unit/test_core.py::retry'])
        output((regression_events.PREFIX + json.dumps(value) + '\n').encode())
        if '--collect-only' not in command:
            output((regression_events.PREFIX + json.dumps(dict(kind='finished',
                    nodeid='tests/unit/test_core.py::retry')) + '\n').encode())
        return 0

    monkeypatch.setattr(regression.Control, 'run', run)
    assert regression.retained_main(tmp_path, selections=selection, checkpoint=Checkpoint(
        tmp_path, selection, resume=True)) == 0
    assert len(calls) == 2 and all(command[1] == 'unit' and '-x' in command for command in calls)


@pytest.mark.parametrize('kind', ['unit', 'ui'])
def test_parallel_resume_preserves_completed_buckets_without_executing_them(tmp_path, monkeypatch, kind):
    retained = f'tests/{kind}/test_completed.py::test_passed'
    pending = f'tests/{kind}/test_pending.py::test_retry'
    bucket = lambda name, node: SimpleNamespace(
        name=name, nodeids=(node,), paths=(node.split('::')[0],), kind=kind, estimate=1)
    partition = Mock(return_value=[bucket('Completed bucket', retained), bucket('Pending bucket', pending)])
    monkeypatch.setattr(regression, kind + '_buckets', partition)
    with closing(regression.Report(tmp_path)) as report:
        run = regression.Run(tmp_path, report, regression.Control(), host_only=True)
        inventory = regression.Category('Inventory', 1, nodeids=(pending,), resumed_nodeids=(retained,))
        run.categories[:] = [inventory]
        jobs = run.pytest_jobs(kind, inventory, [], exact=True)
        assert set(partition.call_args.args[0]) == {retained, pending}
        assert len(jobs) == 1 and jobs[0].item.nodeids == (pending,)
        assert pending in jobs[0].command and retained not in jobs[0].command
        assert run.categories[0].state == 'Passed'
        frame = run.dashboard.ANSI.sub('', '\n'.join(run.dashboard.render(run.dashboard.started)))
        assert 'Completed bucket - 100% (1/1)' in frame
        assert 'Overall - 50% (1/2)' in frame
