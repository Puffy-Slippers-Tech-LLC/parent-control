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
from test_checkpoint import Checkpoint, EXCLUDE, request_record, resume_arguments
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


def test_resume_refuses_changed_selectors_but_can_narrow_categories(tmp_path):
    checkpoint = Checkpoint(tmp_path, [('unit', ['-k', 'grant']), ('static', ['shell'])])
    checkpoint.finish([SimpleNamespace(retry_category='static', count_overall=True, state='Passed')])
    assert Checkpoint(tmp_path, [('static', ['shell'])], resume=True).complete('static')
    with pytest.raises(ValueError, match='selection differs'):
        Checkpoint(tmp_path, [('unit', ['-k', 'limit'])], resume=True)


def test_resume_checks_every_repeated_category_selection(tmp_path):
    selection = [('unit', ['-k', 'first']), ('unit', ['-k', 'second'])]
    checkpoint = Checkpoint(tmp_path, selection)
    event(checkpoint, 'finished', 'passed')
    checkpoint.save()
    assert Checkpoint(tmp_path, selection, resume=True).passed('unit') == {'passed'}
    with pytest.raises(ValueError, match='selection differs'):
        Checkpoint(tmp_path, [('unit', ['-k', 'changed']), selection[1]], resume=True)


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
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed')
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
                       removal=('test_removal',), authorization=('test_a', 'test_b'),
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


def test_vm_queue_preserves_resume_and_first_failure_policy():
    from vm_test_queue import split
    host, guests = split(ROOT, ['--resume', '--stop-on-error', 'host', 'vm'])
    assert host == ['--resume', '--stop-on-error', 'host']
    assert guests == ['--resume', '--stop-on-error', 'system', 'e2e']


def test_fresh_vm_queue_resets_queued_progress_even_when_host_fails(tmp_path, monkeypatch):
    import vm_test_queue as queue
    from vm_selection import BATCH
    vm = SimpleNamespace(name='guest')
    monkeypatch.setenv(BATCH, json.dumps(dict(vms=['guest'], concurrency=1)))
    monkeypatch.setattr(queue.vm_config, 'registry', lambda: {'guest': vm})
    monkeypatch.setattr(test_commands, '_main', lambda *_, **__: 1)
    selection = [('system', []), ('e2e', [])]
    previous = Checkpoint(tmp_path, selection, binding='guest')
    previous.event('e2e', dict(kind='finished', nodeid='old-pass'), set())
    previous.save()
    assert queue.run(tmp_path, ['host', 'vm']) == 1
    assert Checkpoint(tmp_path, selection, resume=True, binding='guest').passed('e2e') == set()


@pytest.mark.parametrize('selectors', [('--scenario', 'selected'), ('--id=1,2',)])
def test_e2e_resume_filters_passed_cases_and_preserves_execution_options(tmp_path, monkeypatch, selectors):
    import runpy
    checkpoint = Checkpoint(tmp_path, [('e2e', [])])
    checkpoint.event('e2e', dict(kind='finished', nodeid='passed'), set())
    runner = SimpleNamespace(root=ROOT, checkpoint=checkpoint)
    item = regression.Category('E2E', retry_category='e2e')
    preflight = Mock(return_value={'cases': [dict(case_id='passed', coverage_id=1),
                                           dict(case_id='retry', coverage_id=2)]})
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
