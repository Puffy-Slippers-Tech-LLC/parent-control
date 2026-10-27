"""Resume preserves passes and retries failures without trusting in-flight work.

All state and subprocess outputs are private pytest trees. The only real child
is a synchronously waited pytest with synthetic cases; there are no live VMs,
model sessions, displays, cleanup owners or shared launcher files.
"""

import json
import io
import os
import subprocess
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import fix_tests
import regression
import regression_events
import regression_selection
import test_commands
from test_checkpoint import Checkpoint, EXCLUDE, ONLY, request_record, resume_arguments
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


def test_resume_refuses_changed_selectors_but_can_narrow_categories(tmp_path, monkeypatch):
    checkpoint = Checkpoint(tmp_path, [('unit', ['-k', 'grant']), ('static', ['shell'])])
    checkpoint.finish([SimpleNamespace(retry_category='static', count_overall=True, state='Passed')])
    assert Checkpoint(tmp_path, [('static', ['shell'])], resume=True).complete('static')
    with pytest.raises(ValueError, match='selection differs'):
        Checkpoint(tmp_path, [('unit', ['-k', 'limit'])], resume=True)
    # A composite publishing request retains each channel's completion, so a
    # failed RPM job neither discards nor reruns the accepted DEB result.
    root = tmp_path / 'publishing'
    publishing = Checkpoint(root, [('publish', [])])
    publishing.finish([
        SimpleNamespace(retry_category='publish-deb', count_overall=True, state='Passed'),
        SimpleNamespace(retry_category='publish-rpm', count_overall=True, state='Failed'),
    ])
    resumed = Checkpoint(root, [('publish', [])], resume=True)
    assert resumed.selected == {'publish-deb', 'publish-rpm'}
    assert resumed.complete('publish-deb') and not resumed.complete('publish-rpm')
    assert Checkpoint(root, [('publish-deb', [])], resume=True).complete('publish-deb')
    calls = []
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'f' * 64)
    monkeypatch.setattr(regression, 'Admission', lambda **_: SimpleNamespace(allows=lambda *_: True))
    def execute(self, command, **kwargs):
        calls.append(command[1])
        return 0
    monkeypatch.setattr(regression.Control, 'run', execute)
    assert regression.retained_main(root, selections=[('publish', [])], checkpoint=resumed) == 0
    assert calls == ['publish-rpm']
    # Atomic integration checks commit only after the entire guarded command
    # returns successfully, including its cleanup. A sibling failure retains
    # the earlier check without marking the category complete.
    integration = [('integration', ['check_first']), ('integration', ['check_second'])]
    root = tmp_path / 'integration'
    checkpoint = Checkpoint(root, integration)
    calls.clear()
    def execute_check(self, command, **kwargs):
        calls.append(command[3])
        return 7 if command[3] == 'check_second' else 0
    monkeypatch.setattr(regression.Control, 'run', execute_check)
    assert regression.retained_main(root, selections=integration, checkpoint=checkpoint) == 1
    resumed = Checkpoint(root, integration, resume=True)
    assert resumed.passed('integration') == {'check_first'}
    assert not resumed.complete('integration')
    assert calls == ['check_first', 'check_second']
    calls.clear()
    def retry_check(self, command, **kwargs):
        calls.append(command[3])
        return 0
    monkeypatch.setattr(regression.Control, 'run', retry_check)
    assert regression.retained_main(root, selections=integration, checkpoint=resumed) == 0
    assert calls == ['check_second']
    assert Checkpoint(root, integration, resume=True).complete('integration')


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
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
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
        Checkpoint(tmp_path, [('unit', [])], resume=True)


def test_host_and_vm_checkpoints_are_independent_and_combined_retry_can_narrow(tmp_path, monkeypatch):
    from vm_selection import VARIABLE
    monkeypatch.setenv(VARIABLE, 'guest-one')
    checkpoint = Checkpoint(tmp_path, [('unit', []), ('e2e', [])])
    event(checkpoint, 'finished', 'host-pass')
    checkpoint.event('e2e', dict(kind='finished', nodeid='guest-pass'), set())
    checkpoint.finish([])
    assert Checkpoint(tmp_path, [('unit', [])], resume=True).passed('unit') == {'host-pass'}
    assert Checkpoint(tmp_path, [('e2e', [])], resume=True).passed('e2e') == {'guest-pass'}
    monkeypatch.setenv(VARIABLE, 'guest-two')
    assert Checkpoint(tmp_path, [('e2e', [])], resume=True).passed('e2e') == set()


def test_large_case_inventory_uses_private_snapshot_instead_of_large_environment(tmp_path):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    cases = ['tests/unit/test_core.py::test_case[' + str(index) + 'x' * 200 + ']'
             for index in range(2000)]
    checkpoint.entry('unit')['passed'] = cases
    checkpoint.save()
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    value = resumed.environment('unit')
    assert len(value) < 1024
    assert regression_events.completed_cases(value) == set(cases)


def test_oversized_completion_cannot_poison_the_next_retry(tmp_path):
    checkpoint = Checkpoint(tmp_path, [('unit', [])])
    boundary = 'p' * regression_events.MAX_CASE_ID_LENGTH
    oversized = boundary + 'x'
    event(checkpoint, 'finished', boundary)
    event(checkpoint, 'finished', oversized)
    checkpoint.save()
    resumed = Checkpoint(tmp_path, [('unit', [])], resume=True)
    assert resumed.passed('unit') == {boundary}
    assert regression_events.completed_cases(resumed.environment('unit')) == {boundary}


def test_resume_repairs_legacy_oversized_ids_without_resetting_other_passes(tmp_path):
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


def test_repair_replay_removes_only_its_case_from_the_resume_snapshot(tmp_path):
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


def test_fix_tests_repair_retries_resume_but_verification_rounds_start_fresh():
    calls = []
    failed = dict(prompt='repair', categories=['unit'])
    results = iter([failed, None, None])
    def test(category):
        calls.append(('fresh', category))
        return next(results)
    def resume(category, **kwargs):
        calls.append(('resume', category))
        return next(results)
    fix_tests.run_loop(['unit'], test, lambda *_, **__: None, lambda: None,
                       selected=True, rounds=2, resume_test=resume)
    assert calls == [('fresh', 'unit'), ('resume', 'unit'), ('fresh', 'unit')]


def test_completed_resumed_verification_round_is_skipped_before_next_fresh_round():
    test = Mock(return_value=None)
    rounds = []
    fix_tests.run_loop(['unit', 'ui'], test, Mock(), lambda: None, rounds=3,
                       start_round=2, completed=['unit', 'ui'], round_changed=rounds.append)
    assert rounds == [2, 3]
    test.assert_called_once_with('all')


def test_verification_retries_companion_failure_without_resetting_its_passes():
    calls = []
    failure = dict(prompt='repair', categories=['unit', 'ui'])
    results = iter([failure, None])
    def test(category):
        calls.append(('fresh', category))
        return next(results)
    def resume(category):
        calls.append(('resume', category))
        return None
    fix_tests.verify_round(['unit', 'ui'], test, Mock(), lambda: None,
                           selected=False, resume_test=resume)
    assert calls == [('fresh', 'all'), ('resume', 'ui'), ('fresh', 'all')]


@pytest.mark.parametrize('options, rounds', [([], 2), (['--rounds', '4'], 4)])
def test_fix_tests_bare_resume_restores_selection_and_honors_explicit_rounds(monkeypatch, options, rounds):
    import test_checkpoint
    monkeypatch.setattr(test_checkpoint, 'request_record', Mock(return_value=dict(
        categories=['unit', '-q'], rounds=2, vm=None)))
    launcher = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', launcher)
    assert fix_tests.main(['--resume', *options]) == 0
    assert launcher.call_args.kwargs['categories'] == ['unit', '-q']
    assert launcher.call_args.kwargs['rounds'] == rounds
    assert launcher.call_args.kwargs['resume'] is True


def test_resume_flag_is_coordinator_owned_and_fix_tests_receives_it(monkeypatch):
    assert test_commands.selections(ROOT, ['--resume', '--stop-on-error', 'unit', '-x']) == [('unit', ['-x'])]
    assert test_commands.host_only_request(['unit', '--resume'])
    launcher = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', launcher)
    assert fix_tests.main(['unit', '-q', '--resume']) == 0
    assert launcher.call_args.kwargs['resume'] is True
    assert launcher.call_args.kwargs['categories'] == ['unit', '-q']


def test_bare_resume_restores_original_selectors_and_failure_policy(tmp_path):
    original = ['--stop-on-error', 'unit', 'tests/unit/test_core.py', '-q']
    request_record(tmp_path, 'run-tests', dict(argv=original))
    assert resume_arguments(tmp_path, ['--resume']) == ['--resume', *original]
    assert resume_arguments(tmp_path, ['--resume', 'unit', '-x']) == ['--resume', 'unit', '-x']
    assert resume_arguments(tmp_path, ['--resume', '--help']) == ['--resume', '--help']


def test_repair_replays_the_specific_case_even_after_a_passing_diagnostic():
    calls = []
    responses = iter([dict(prompt='diagnose', categories=['unit'],
                           failures=[dict(category='unit', case='case', vm='')]), None, None])
    repairs = iter(['diagnostic_ready', 'fixed'])
    def test(category):
        calls.append(('fresh', category))
        return next(responses)
    def resume(category, **options):
        calls.append(('resume', category, options['retry_case']))
        return next(responses)
    fix_tests.run_loop(['unit'], test, lambda *_, **__: dict(status=next(repairs)),
                       lambda: None, resume_test=resume)
    assert calls == [('fresh', 'unit'), ('resume', 'unit', 'case'), ('resume', 'unit', 'case')]


def test_system_resume_excludes_completed_independent_cases_and_preserves_lifecycle():
    import system_runner
    inventories = dict(package=('test_installed_package',),
                       removal=('test_remove_reboot_reinstall',), authorization=('test_a', 'test_b'),
                       enforcement=('test_enforcement',), session=('test_session',))
    selection = system_runner.resolve_selection('authorization', inventories=inventories)
    resumed = system_runner.resume_selection(selection, {'authorization::test_a'})
    assert [item.case_id for item in resumed.executions] == ['test_b']
    assert resumed.phases == ('authorization',)
    with pytest.raises(system_runner.Error, match='resume-inventory-changed'):
        system_runner.resume_selection(selection, {'authorization::unknown'})
    lifecycle = system_runner.resolve_selection('removal', inventories=inventories)
    completed = {item.phase + '::' + item.case_id for item in lifecycle.executions[:-1]}
    assert system_runner.resume_selection(lifecycle, completed).executions == lifecycle.executions
    upgrade = system_runner.resolve_selection('authorization', inventories=inventories, fresh_install=True)
    completed = {item.phase + '::' + item.case_id for item in upgrade.executions
                 if item.phase in ('installed', 'rebooted')}
    assert system_runner.resume_selection(upgrade, completed, fresh_install=True).executions == upgrade.executions


@pytest.mark.parametrize('history', [False, True])
def test_system_case_retry_selects_its_required_history_without_crediting_omissions(
        tmp_path, monkeypatch, history):
    import fix_tests_queue
    import system_runner
    from tests.support.vm_registry import vm_name
    from tests.support.vm_runner import RECOVERY_INVENTORIES
    from vm_selection import VARIABLE, vm_config

    monkeypatch.setenv(VARIABLE, vm_name())
    monkeypatch.setattr(vm_config.VMConfig, 'require_package_format', lambda _: 'deb')
    inventories = {**RECOVERY_INVENTORIES, 'authorization': ('test_a', 'test_b')}
    monkeypatch.setattr(system_runner, 'collect_area_cases', inventories.__getitem__)
    plan = system_runner.resolve_selection(inventories=inventories, target_package_format='deb')
    retry = ('rollback::test_aborted_cleanup_rollback_retry' if history else 'authorization::test_b')
    checkpoint = Checkpoint(tmp_path, [('system', [])])
    checkpoint.retry('system', retry)
    item = regression.Category('System', retry_category='system')
    command = [str(ROOT / 'tools/run-tests'), 'system', '--unattended']
    resumed = regression.Run.resume_command(SimpleNamespace(root=ROOT, checkpoint=checkpoint), item, command)
    omitted = set(json.loads(resumed[-1].split('=', 1)[1]))
    selected = system_runner.resume_selection(plan, omitted)
    assert retry in {execution.phase + '::' + execution.case_id for execution in selected.executions}
    # A focused retry retains predecessors and stops at the selected phase.
    assert (selected.phases == ('rollback-installed', 'rollback-rebooted', 'rollback') if history else
            [execution.case_id for execution in selected.executions] == ['test_b'])
    assert item.resumed_nodeids == () and checkpoint.passed('system') == set()
    if not history:
        checkpoint.retry('system', retry, area=True)
        scoped = regression.Run.resume_command(SimpleNamespace(root=ROOT, checkpoint=checkpoint),
                                               item, command)
        omitted = set(json.loads(scoped[-1].split('=', 1)[1]))
        scoped = system_runner.resume_selection(plan, omitted)
        assert scoped.phases == ('authorization',)
        assert [execution.case_id for execution in scoped.executions] == ['test_a', 'test_b']
        assert checkpoint.passed('system') == set()
        checkpoint.retry('system', retry)
        assert checkpoint.retry_area is None

    # Normal scheduling runs the complete selected history or area once. Interrupted
    # attempts retain only real passes and reconstruct predecessors on resume;
    # the exact repair retry above must still stop before later phases.
    options = (['--area=removal', '--test=test_aborted_cleanup_rollback_retry'] if history else
               ['--area=authorization'])
    plan = system_runner.resolve_selection(
        'removal' if history else 'authorization',
        'test_aborted_cleanup_rollback_retry' if history else None,
        inventories=inventories, target_package_format='deb')
    cases = [execution.phase + '::' + execution.case_id
             for execution in plan.executions if not execution.prerequisite]
    monkeypatch.setattr(fix_tests_queue, 'case_inventory', lambda *_: cases)
    monkeypatch.setattr(fix_tests_queue, 'publish_case_progress', lambda *_, **__: None)
    normal_root = tmp_path / 'normal'
    gate = fix_tests_queue.RepairGate(normal_root)
    calls = []
    status = 1

    def execute(arguments):
        assert arguments[:len(options)] == options
        assert arguments[-1] == ('--resume-case-only' if history else '--resume-area-only')
        forwarded = ['system', *arguments]
        assert test_commands.execution_arguments(forwarded) == (['system', *options], False)
        target = arguments[-2].partition('=')[2]
        calls.append(target)
        saved = Checkpoint(normal_root, [('system', options)], resume=True, binding=vm_name())
        if history:
            with pytest.raises(ValueError, match='area retry requires an independent system area'):
                saved.retry('system', target, area=True)
        saved.retry('system', target, area=not history)
        resumed = regression.Run.resume_command(
            SimpleNamespace(root=ROOT, checkpoint=saved), item,
            [str(ROOT / 'tools/run-tests'), 'system', '--unattended', *options])
        omitted = set(json.loads(resumed[-1].split('=', 1)[1]))
        actual = system_runner.resume_selection(plan, omitted)
        nodes = [execution.phase + '::' + execution.case_id for execution in actual.executions]
        assert target in nodes
        assert (nodes[-1] == target if history else actual.phases == ('authorization',))
        for node in nodes[:-1] if status else nodes:
            saved.event('system', dict(kind='finished', nodeid=node), set())
        if status:
            saved.event('system', dict(kind='failure', nodeid=nodes[-1]), {nodes[-1]})
        saved.finish([SimpleNamespace(retry_category='system', count_overall=True,
                                     state='Failed' if status else 'Passed')])
        return status

    inventory = {'system': {'args': options}}
    assert fix_tests_queue.run_cases(normal_root, 'system', options, execute, gate,
                                    inventory=inventory, round_number=1) == 1
    interrupted = Checkpoint(normal_root, [('system', options)], resume=True, binding=vm_name())
    assert cases[-1] not in interrupted.passed('system')
    assert not interrupted.complete('system')
    status = 0
    assert fix_tests_queue.run_cases(normal_root, 'system', [*options, '--resume'], execute, gate,
                                    inventory=inventory, round_number=1) == 0
    assert calls == ([cases[-1], cases[-1]] if history else [cases[0], cases[-1]])
    completed = Checkpoint(normal_root, [('system', options)], resume=True, binding=vm_name())
    assert set(cases) <= completed.passed('system') and completed.complete('system')


@pytest.mark.parametrize('pending_phase', ['rollback', 'rollback-rearmed-rebooted'])
def test_system_recovery_resume_replays_whole_unfinished_history_only(pending_phase):
    import system_runner
    from tests.support.vm_runner import RECOVERY_INVENTORIES
    selection = system_runner.resolve_selection(inventories=RECOVERY_INVENTORIES)
    completed = {item.phase + '::' + item.case_id for item in selection.executions
                 if item.phase != pending_phase}
    resumed = system_runner.resume_selection(selection, completed)
    # Replay every predecessor, but stop at the unfinished phase.
    expected_phases = system_runner.ROLLBACK_PHASES[
        :system_runner.ROLLBACK_PHASES.index(pending_phase) + 1]
    assert resumed.phases == expected_phases
    assert resumed.executions == tuple(item for item in selection.executions
                                      if item.phase in expected_phases)
    # Completed destructive histories are not replayed for an independent area.
    completed = {item.phase + '::' + item.case_id for item in selection.executions
                 if item.phase != 'authorization'}
    resumed = system_runner.resume_selection(selection, completed)
    assert resumed.phases == ('authorization',)
    focused = system_runner.resolve_selection(
        'removal', 'test_aborted_cleanup_rollback_retry', inventories=RECOVERY_INVENTORIES)
    for count in range(len(focused.executions) + 1):
        completed = {item.phase + '::' + item.case_id for item in focused.executions[:count]}
        assert system_runner.resume_selection(focused, completed) == focused


@pytest.mark.parametrize('pending_phase', [
    'rpm-posterase-installed', 'rpm-posterase-rebooted',
    'rpm-posterase', 'rpm-posterase-reinstalled-rebooted'])
def test_system_rpm_posterase_resume_replays_all_predecessors(pending_phase):
    import system_runner
    from tests.support.vm_runner import RECOVERY_INVENTORIES
    selection = system_runner.resolve_selection(inventories=RECOVERY_INVENTORIES,
                                                target_package_format='rpm')
    focused = system_runner.resolve_selection('removal', 'test_rpm_posterase_recovery',
                                              inventories=RECOVERY_INVENTORIES,
                                              target_package_format='rpm')
    completed = {item.phase + '::' + item.case_id for item in selection.executions
                 if item.phase != pending_phase}
    resumed = system_runner.resume_selection(selection, completed)
    # Replay every required predecessor, stopping at the unfinished phase.
    expected_phases = focused.phases[:focused.phases.index(pending_phase) + 1]
    assert resumed.phases == expected_phases
    assert resumed.executions == tuple(item for item in focused.executions
                                      if item.phase in expected_phases)


@pytest.mark.parametrize('resume', [False, True])
@pytest.mark.parametrize('scope', ['independent', 'focused', 'history'])
@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_grouped_system_passes_and_counts_stay_with_their_selection(
        tmp_path, monkeypatch, resume, scope, package_format):
    import system_runner
    from tests.support.vm_registry import vm_name
    from tests.support.vm_runner import RECOVERY_INVENTORIES
    from vm_selection import VARIABLE, vm_config

    monkeypatch.setenv(VARIABLE, vm_name())
    monkeypatch.setattr(vm_config.VMConfig, 'require_package_format', lambda _: package_format)
    inventories = {**RECOVERY_INVENTORIES, 'authorization': ('test_a', 'test_b', 'test_c')}
    monkeypatch.setattr(system_runner, 'collect_area_cases', inventories.__getitem__)
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed-inputs')
    monkeypatch.setattr(regression.Run, 'wait_for_resources', lambda *_: None)
    history = scope == 'history'
    second = {'history': ('removal', 'test_aborted_cleanup_rollback_retry'),
              'independent': ('enforcement', None),
              'focused': ('authorization', 'test_b')}[scope]
    selectors = [('authorization', 'test_a'), second]
    inventories['enforcement'] = ('test_b', 'test_c')
    selections = [('system', ['--area', area, *(['--test=' + case] if case else [])])
                  for area, case in selectors]
    plans = [system_runner.resolve_selection(area, case, inventories=inventories,
                target_package_format=vm_config.load(vm_name()).require_package_format())
             for area, case in selectors]
    ids = [tuple(item.phase + '::' + item.case_id for item in plan.executions) for plan in plans]
    checkpoint = Checkpoint(tmp_path, selections)
    if resume:
        retained = [ids[0][0], *(ids[1][:-1] if history else ids[1][:1])]
        for node in retained:
            checkpoint.event('system', dict(kind='finished', nodeid=node), set())
        checkpoint.save()
        checkpoint = Checkpoint(tmp_path, selections, resume=True)
    commands = []
    replayed = []

    def execute(command, *, output, **kwargs):
        index = len(commands)
        commands.append(command)
        completed = next((json.loads(arg.split('=', 1)[1]) for arg in command
                          if arg.startswith('--completed-cases=')), [])
        assert set(completed) <= set(ids[index])
        expected = (set(ids[index][:-1] if history and index else ids[index][:1])
                    if resume else set())
        assert set(completed) == expected
        selected = system_runner.resume_selection(plans[index], set(completed)) if completed else plans[index]
        nodes = [item.phase + '::' + item.case_id for item in selected.executions]
        replayed.append(nodes)
        output((regression.PREFIX + json.dumps(dict(
            kind='collection', total=len(nodes), nodeids=nodes)) + '\n').encode())
        for node in nodes:
            output((regression.PREFIX + json.dumps(dict(kind='finished', nodeid=node)) + '\n').encode())
        return 0

    with closing(regression.Report(tmp_path)) as report:
        run = regression_selection.SelectedRun(ROOT, report, regression.Control(), selections)
        run.checkpoint = checkpoint
        run.dashboard.stream = io.StringIO()
        monkeypatch.setattr(run.control, 'run', execute)
        run.run()
        assert run.result_status() == 0 and len(commands) == 2
        assert [(item.progress_done, item.progress_total) for item in run.categories] == [
            (len(nodes), len(nodes)) for nodes in ids]
        assert replayed[1] == (list(ids[1][1:]) if scope == 'independent' and resume else list(ids[1]))
        assert run.categories[1].resumed_nodeids == (ids[1][:1] if scope == 'independent' and resume else ())
        report.snapshot(run.categories)
        progress = json.loads((report.directory / 'progress.json').read_text())
        assert [(item['done'], item['total']) for item in progress] == [
            (len(nodes), len(nodes)) for nodes in ids]
        frame = regression.Dashboard.ANSI.sub('', '\n'.join(run.dashboard.render(run.dashboard.started)))
        total = sum(map(len, ids))
        assert f'Overall - 100% ({total}/{total})' in frame
        checkpoint.finish(run.categories)
        completed = regression_selection.SelectedRun(ROOT, report, regression.Control(), selections)
        completed.checkpoint = Checkpoint(tmp_path, selections, resume=True)
        completed.dashboard.stream = io.StringIO()
        controller = Mock(side_effect=AssertionError('completed categories must not execute'))
        monkeypatch.setattr(completed.control, 'run', controller)
        completed.run()
        assert completed.result_status() == 0
        assert [(item.done, item.total) for item in completed.categories] == [
            (len(nodes), len(nodes)) for nodes in ids]
        controller.assert_not_called()


@pytest.mark.parametrize('unknown', ['authorization::unknown',
                                   'rpm-posterase::test_rpm_posterase_recovery'])
def test_grouped_system_filter_keeps_unknown_and_incompatible_ids_for_controller_refusal(
        tmp_path, monkeypatch, unknown):
    import system_runner
    from tests.support.vm_registry import vm_name
    from tests.support.vm_runner import RECOVERY_INVENTORIES
    from vm_selection import VARIABLE, vm_config

    monkeypatch.setenv(VARIABLE, vm_name())
    # The synthetic target deliberately excludes RPM-only histories.
    monkeypatch.setattr(vm_config.VMConfig, 'require_package_format', lambda _: 'deb')
    inventories = {**RECOVERY_INVENTORIES, 'package': (
        *RECOVERY_INVENTORIES['package'], system_runner.PREVIOUS_POLICY_CASE,
        system_runner.TRUSTED_FIXTURES_CASE)}
    monkeypatch.setattr(system_runner, 'collect_area_cases', inventories.__getitem__)
    selections = [('system', ['--area', 'authorization']), ('system', [])]
    checkpoint = Checkpoint(tmp_path, selections)
    checkpoint.event('system', dict(kind='finished', nodeid=unknown), set())
    runner = SimpleNamespace(root=ROOT, checkpoint=checkpoint)
    item = regression.Category('System', retry_category='system')
    command = [str(ROOT / 'tools/run-tests'), 'system', '--unattended', '--area=authorization']
    command = regression.Run.resume_command(runner, item, command)
    assert command[-1] == '--completed-cases=' + json.dumps([unknown])
    assert item.resumed_nodeids == ()
    selection = system_runner.resolve_selection('authorization', inventories=RECOVERY_INVENTORIES)
    with pytest.raises(system_runner.Error, match='resume-inventory-changed'):
        system_runner.resume_selection(selection, {unknown})
    checkpoint.entry('system')['complete'] = True
    item.selection_args = ('--area=authorization',)
    with closing(regression.Report(tmp_path)) as report:
        run = regression.Run(ROOT, report, regression.Control(), host_only=True)
        run.checkpoint = checkpoint
        with pytest.raises(ValueError, match='resume-inventory-changed'):
            run.resume_category(item)


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_grouped_system_upgrade_resume_preserves_installation_predecessors(
        tmp_path, monkeypatch, package_format):
    import system_runner
    from tests.support.vm_registry import vm_name
    from tests.support.vm_runner import RECOVERY_INVENTORIES
    from vm_selection import VARIABLE, vm_config

    monkeypatch.setenv(VARIABLE, vm_name())
    monkeypatch.setattr(vm_config.VMConfig, 'require_package_format', lambda _: package_format)
    inventories = {**RECOVERY_INVENTORIES, 'authorization': ('test_a', 'test_b')}
    monkeypatch.setattr(system_runner, 'collect_area_cases', inventories.__getitem__)
    options = ['--area=authorization', '--test', 'test_b',
               '--previous-artifacts=/tmp/onpc-prior', '--artifacts', '/tmp/onpc-current']
    selections = [('system', ['--area', 'authorization', '--test=test_a']), ('system', options)]
    checkpoint = Checkpoint(tmp_path, selections)
    selection = system_runner.resolve_selection('authorization', 'test_b', inventories=inventories,
        fresh_install=True, target_package_format=package_format)
    predecessors = {item.phase + '::' + item.case_id for item in selection.executions
                    if item.phase in ('installed', 'rebooted')}
    for node in predecessors | {'authorization::test_a'}:
        checkpoint.event('system', dict(kind='finished', nodeid=node), set())
    item = regression.Category('Upgrade', retry_category='system')
    command = [str(ROOT / 'tools/run-tests'), 'system', '--unattended', *options,
               '--vm', vm_name(), '--skip-backing-verification']
    resumed = regression.Run.resume_command(SimpleNamespace(root=ROOT, checkpoint=checkpoint), item, command)
    assert resumed[:-1] == command
    assert json.loads(resumed[-1].split('=', 1)[1]) == sorted(predecessors)
    # The default category owns three attempts. A case retry must select its
    # own isolated upgrade rather than fail in, or certify, an earlier sibling.
    inventories['package'] = (*inventories['package'], system_runner.PREVIOUS_POLICY_CASE,
                              system_runner.TRUSTED_FIXTURES_CASE)
    checkpoint = Checkpoint(tmp_path / 'aggregate', [('system', [])])
    case = 'trusted-fixtures::' + system_runner.TRUSTED_FIXTURES_CASE
    checkpoint.retry('system', case)
    with closing(regression.Report(tmp_path)) as report:
        run = regression.Run(ROOT, report, regression.Control(), host_only=True)
        run.checkpoint = checkpoint
        sibling = regression.Category('Current', retry_category='system', selection_args=())
        assert run.resume_category(sibling)
        assert sibling.done == 0 and not sibling.count_overall
        args = ('--id', '288', '--upgrade-inputs')
        selected = regression.Category('Upgrade', retry_category='system', selection_args=args)
        assert not run.resume_category(selected)
        command = run.command('system', *args)
        scoped = run.resume_command(selected, command)
        assert scoped[:len(command)] == command
        assert json.loads(scoped[-1].partition('=')[2]) == []
    assert set(item.resumed_nodeids) == predecessors
    assert system_runner.resume_selection(selection, predecessors, fresh_install=True) == selection


def test_grouped_system_sibling_target_refusal_preserves_current_binding(tmp_path, monkeypatch):
    import system_runner
    from tests.support.vm_registry import vm_name
    from tests.support.vm_runner import RECOVERY_INVENTORIES
    from vm_selection import VARIABLE, vm_config

    current, other = vm_name(), vm_name(1)
    monkeypatch.setenv(VARIABLE, current)
    monkeypatch.setattr(system_runner, 'collect_area_cases', RECOVERY_INVENTORIES.__getitem__)
    selections = [('system', ['--area=authorization']),
                  ('system', ['--area=enforcement', '--vm', other])]
    checkpoint = Checkpoint(tmp_path, selections)
    runner = SimpleNamespace(root=ROOT, checkpoint=checkpoint)
    with pytest.raises(ValueError, match='resume target differs'):
        regression.Run.system_resume_cases(runner, ['--area=authorization', '--vm', current])
    assert vm_config.selected().name == current


def test_single_system_resume_keeps_existing_route_without_sibling_resolution(tmp_path):
    options = ['--area=authorization']
    checkpoint = Checkpoint(tmp_path, [('system', options)])
    checkpoint.event('system', dict(kind='finished', nodeid='authorization::test_a'), set())
    runner = SimpleNamespace(root=tmp_path, checkpoint=checkpoint, report=Mock())
    item = regression.Category('System', retry_category='system', selection_args=tuple(options))
    command = [str(tmp_path / 'tools/run-tests'), 'system', '--unattended', *options]
    assert regression.Run.resume_command(runner, item, command) == [
        *command, '--completed-cases=' + json.dumps(['authorization::test_a'])]
    assert item.resumed_nodeids == ('authorization::test_a',)
    checkpoint.entry('system')['complete'] = True
    item = regression.Category('System', retry_category='system', selection_args=tuple(options))
    assert regression.Run.resume_category(runner, item)
    assert item.state == 'Passed' and item.progress_done == item.progress_total == 1


def test_vm_queue_preserves_resume_and_first_failure_policy():
    from vm_test_queue import split
    host, guests = split(ROOT, ['--resume', '--stop-on-error', 'host', 'vm'])
    assert host == ['--resume', '--stop-on-error', 'host']
    assert guests == ['--resume', '--stop-on-error', 'system', 'integration', 'e2e']
    assert split(ROOT, ['all', '--continue-on-errors']) == (
        ['host', '--continue-on-errors'],
        ['system', 'integration', 'e2e', '--continue-on-errors'])


def test_fresh_vm_queue_resets_queued_progress_even_when_host_fails(tmp_path, monkeypatch):
    import vm_test_queue as queue
    from vm_selection import BATCH
    vm = SimpleNamespace(name='guest')
    monkeypatch.setenv(BATCH, json.dumps(dict(vms=['guest'], concurrency=1)))
    monkeypatch.setattr(queue.vm_config, 'registry', lambda: {'guest': vm})
    monkeypatch.setattr(test_commands, '_main', lambda *_, **__: 1)
    expand = test_commands.execution_selections
    monkeypatch.setattr(test_commands, 'execution_selections', lambda root, groups: expand(ROOT, groups))
    selection = [('system', []), ('integration', []), ('e2e', [])]
    previous = Checkpoint(tmp_path, selection, binding='guest')
    previous.event('e2e', dict(kind='finished', nodeid='old-pass'), set())
    previous.save()
    assert queue.run(tmp_path, ['host', 'vm']) == 1
    assert Checkpoint(tmp_path, selection, resume=True, binding='guest').passed('e2e') == set()


@pytest.mark.parametrize('selectors', [('--scenario', 'selected'), ('--id=1,2',)])
@pytest.mark.parametrize('retry', [False, True])
def test_e2e_resume_filters_passed_cases_and_preserves_execution_options(tmp_path, monkeypatch, selectors, retry):
    import runpy
    checkpoint = Checkpoint(tmp_path, [('e2e', [])])
    checkpoint.event('e2e', dict(kind='finished', nodeid='passed'), set())
    if retry:
        checkpoint.retry('e2e', 'retry')
    runner = SimpleNamespace(root=ROOT, checkpoint=checkpoint)
    item = regression.Category('E2E', retry_category='e2e')
    preflight = Mock(return_value={'cases': [dict(case_id='passed', coverage_id=1),
                                           dict(case_id='retry', coverage_id=2),
                                           *([dict(case_id='remaining', coverage_id=3)] if retry else [])]})
    monkeypatch.setattr(runpy, 'run_path', lambda _: {'preflight': preflight})
    command = [str(ROOT / 'tools/run-tests'), 'e2e', '--unattended', *selectors,
               '--artifacts=/private/artifacts', '--vm', 'guest']
    resumed = regression.Run.resume_command(runner, item, command)
    assert resumed == [*command[:3], '--artifacts=/private/artifacts', '--vm', 'guest', '--id=2']
    assert item.nodeids == ('retry',) and item.total == 1
    assert item.resumed_nodeids == ('passed',)
    assert (item.progress_done, item.progress_total) == (1, 2)
    assert preflight.call_args.kwargs == dict(root=ROOT, allow_missing_artifacts=True)


@pytest.mark.parametrize('kind', ['unit', 'system', 'e2e'])
def test_resumed_dashboard_and_saved_progress_keep_original_counts(tmp_path, kind):
    retained = tuple(f'case-{index}' for index in range(9))
    pending = tuple(f'case-{index}' for index in range(9, 100))
    with closing(regression.Report(tmp_path)) as report:
        run = regression.Run(tmp_path, report, regression.Control(), host_only=True)
        item = regression.Category('Resumed tests', retry_category=kind)
        run.categories[:] = [item]
        run.dashboard.stream = io.StringIO()
        if kind == 'system':
            run.checkpoint = Checkpoint(tmp_path, [(kind, [])])
            run.checkpoint.entry(kind)['passed'] = list(retained)
            # resume_command scopes retained system IDs before collection.
            item.resumed_nodeids = retained
        elif kind == 'e2e':
            item.resumed_nodeids = retained
        execution = regression.Execution(run, item, events=True)
        collection = dict(kind='collection', total=len(pending), nodeids=list(pending))
        if kind == 'unit':
            collection['resumed_nodeids'] = list(retained)
        try:
            execution.line((regression_events.PREFIX + json.dumps(collection)).encode())
            assert (item.progress_done, item.progress_total) == (9, 100)
            execution.line((regression_events.PREFIX + json.dumps(
                dict(kind='finished', nodeid=pending[0]))).encode())
            assert (item.done, item.total) == (1, 91)
            frame = run.dashboard.ANSI.sub('', '\n'.join(run.dashboard.render(run.dashboard.started)))
            assert 'Resumed tests - 10% (10/100)' in frame
            assert 'Overall - 10% (10/100)' in frame
            report.checkpoint(force=True)
            progress = json.loads((report.directory / 'progress.json').read_text())
            assert (progress[0]['done'], progress[0]['total']) == (10, 100)
            for node in pending[1:]:
                execution.line((regression_events.PREFIX + json.dumps(
                    dict(kind='finished', nodeid=node))).encode())
            execution.finish(0)
            assert item.state == 'Passed' and item.progress_done == item.progress_total == 100
        finally:
            execution.close()


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
