"""E2E dispatch refuses unsafe/unfinished work before privileges or VM access."""

import hashlib
import json
import runpy
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


from tests.support.paths import ROOT
runner = runpy.run_path(str(ROOT / 'tests/e2e/runner.py'))
dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
import test_commands as commands
import dev_privileges
import test_account_password
REAL_READ_PASSWORD = test_account_password.read_password


@pytest.fixture(autouse=True)
def fixture_password(monkeypatch):
    monkeypatch.setattr(test_account_password, 'read_password', lambda *args: 'fixture-password')


def test_missing_password_refuses_before_inventory_or_vm(checkout, monkeypatch):
    monkeypatch.setattr(test_account_password, 'read_password', REAL_READ_PASSWORD)
    (checkout / '.envrc').unlink()
    (checkout / 'tests/e2e/scenarios.json').write_text('must not be read')
    with pytest.raises(ValueError, match='TEST_ACCOUNT_PASSWORD'):
        runner['preflight']([], root=checkout)


@pytest.fixture
def checkout(tmp_path):
    for relative in ('tests/e2e/runner.py', 'tests/e2e/inventory.py',
                     'tests/integration/test_account_password.py',
                     'tests/e2e/scenarios.json', 'tests/e2e/controller_qualification.py',
                     'tests/e2e/parent_about.py', 'tests/e2e/parent_discovery.py',
                     'tests/e2e/command_help.py',
                     'tests/requirements.json',
                     'docs/TestAutomation/E2E-Building-Blocks.md'):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    (tmp_path / '.envrc').write_text("TEST_ACCOUNT_PASSWORD='fixture-password'\n")
    (tmp_path / '.envrc').chmod(0o600)
    return tmp_path


@pytest.fixture
def cli_checkout(checkout):
    # Public invocations now attach to the enclosing test session. Exercise
    # fresh CLI listings in an independent checkout instead of self-attaching.
    shutil.copytree(ROOT / 'tools', checkout / 'tools',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'Makefile', checkout / 'Makefile')
    inventory = json.loads((checkout / 'tests/e2e/scenarios.json').read_text())
    for scenario in inventory['scenarios']:
        paths = [reference.split('#', 1)[0] for reference in scenario['contract_refs']]
        paths.extend(variant['executable']['path'] for variant in scenario['variants']
                     if variant['executable'] is not None)
        for relative in paths:
            target = checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
    return checkout


def test_full_listing_keeps_pending_cases_and_exact_digest():
    plan = runner['preflight'](['--list'])
    assert len(plan['cases']) == 242
    assert len(plan['pending_cases']) == 235
    assert plan['scope'] == 'full'
    assert plan['mode'] == 'list-only'
    assert plan['inventory_sha256'] == hashlib.sha256(
        (ROOT / 'tests/e2e/scenarios.json').read_bytes()).hexdigest()


@pytest.mark.parametrize('option,mode', [
    ('--qualify-transfer', 'asset-transfer-qualification'),
    ('--qualify-install', 'authenticated-installation-qualification'),
    ('--qualify-install-refusal', 'deliberate-installation-refusal-qualification'),
])
def test_transfer_qualification_has_no_scenario_override(tmp_path, option, mode):
    assets = tmp_path / 'onpc-assets'
    assets.mkdir()
    # A generated /tmp/onpc-* parent meets the same public artifact boundary.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='onpc-transfer-test-') as directory:
        options = [option, '--artifacts=' + directory]
        plan = runner['preflight'](options)
        assert plan == {'mode': mode, 'artifacts': directory}
        assert dispatcher['selection'](ROOT, ['e2e', *options])[-2:] == options
        for extra in ('--list', '--ready', '--scenario=E2E-001', '--scenario='):
            with pytest.raises(ValueError, match='qualification-cannot-select-scenarios'):
                runner['preflight']([*options, extra])
        command = dispatcher['selection'](ROOT, ['e2e', *options, '--skip-backing-verification'])
        assert runner['preflight'](command[3:]) == plan
    with pytest.raises(ValueError, match='missing-artifact-directory'):
        runner['preflight'](options)


@pytest.mark.parametrize('selector,count', [('E2E-001', 1), ('E2E-023/fullscreen', 1)])
def test_selected_listing_uses_exact_inventory_scope(selector, count):
    plan = runner['preflight'](['--list', '--scenario=' + selector])
    assert plan['scope'] == 'partial'
    assert len(plan['cases']) == count


@pytest.mark.parametrize('skip', [True, False])
def test_dispatcher_preserves_execution_verification_policy(skip, checkout):
    path = checkout / 'tests/e2e/scenarios.json'
    document = json.loads(path.read_text())
    document['scenarios'] = document['scenarios'][:1]
    executable = checkout / 'tests/e2e/synthetic.py'
    executable.write_text('raise AssertionError("must not execute")\n')
    document['scenarios'][0]['variants'][0].update(
        status='ready', pending_reason=None,
        executable={'path': 'tests/e2e/synthetic.py', 'test_id': 'synthetic-smoke'})
    path.write_text(json.dumps(document))
    import tempfile
    with tempfile.TemporaryDirectory(prefix='onpc-verification-test-') as directory:
        options = ['--scenario=E2E-001', '--artifacts=' + directory]
        if skip:
            options.append('--skip-backing-verification')
        command = dispatcher['selection'](checkout, ['e2e', *options])
        plan = runner['preflight'](command[3:], root=checkout)
        assert 'verify_backing_bytes' not in plan
        assert ('--skip-backing-verification' in command) == skip


@pytest.mark.parametrize('options,code', [
    (['--ready', '--scenario=E2E-030/parent'], 'invalid-arguments'),
    (['--scenario=E2E-002'], 'selection:pending'),
    (['--scenario=E2E-028/startup-enforcement'], 'selection:unknown'),
    (['--scenario=E2E-029/failed-save'], 'selection:unknown'),
    (['--scenario=E2E-023/fullscreen', '--artifacts=/tmp/onpc-absent'], 'selection:pending'),
    (['--scenario=E2E-999'], 'selection:unknown'),
    (['--scenario=E2E-023/*'], 'selection:unknown'),
    (['--scenario='], 'selection:empty'),
    (['--scenario=E2E-001,E2E-002'], 'selection:unknown'),
    (['--list', '--artifacts=/tmp/onpc-absent'], 'listing-does-not-use-artifacts'),
    (['--lis'], 'invalid-arguments'),
    (['--qualify-transfer', '--qualify-install'], 'invalid-arguments'),
    (['--qualify-install', '--qualify-install-refusal'], 'invalid-arguments'),
    (['--resume=private-value'], 'invalid-arguments'),
    (['--checkpoint=private-value'], 'invalid-arguments'),
    (['--command=private-value'], 'invalid-arguments'),
    (['--vm-image=private-value'], 'invalid-arguments'),
])
def test_refusals_precede_privilege_checks_and_execution(monkeypatch, capsys, options, code):
    privilege = Mock(side_effect=AssertionError('must not check privilege'))
    execute = Mock(side_effect=AssertionError('must not execute'))
    safety = Mock(side_effect=AssertionError('must not run cleanup'))
    monkeypatch.setattr(dev_privileges, 'check', privilege)
    monkeypatch.setattr(commands.os, 'execve', execute)
    monkeypatch.setattr(commands.host, 'prerequisites', safety)
    assert commands._main(['e2e', *options], detached=True) == 2
    error = capsys.readouterr().err
    assert code in error
    assert 'private-value' not in error
    privilege.assert_not_called()
    execute.assert_not_called()
    safety.assert_not_called()


def test_installed_dispatcher_refuses_pending_before_safety_or_root_execution(monkeypatch):
    execute = Mock(side_effect=AssertionError('must not execute'))
    monkeypatch.setattr(dispatcher['subprocess'], 'run', execute)
    with pytest.raises(ValueError, match='selection:pending'):
        dispatcher['run'](ROOT, ['e2e', '--scenario=E2E-002', '--artifacts=/tmp/onpc-absent'], None)
    execute.assert_not_called()


def test_installed_listing_drops_privilege_without_safety(monkeypatch):
    execute = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(dispatcher['subprocess'], 'run', execute)
    monkeypatch.setattr(dispatcher['os'], 'getgrouplist', lambda *args: [1000])
    caller = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture', pw_dir='/tmp')
    assert dispatcher['run'](ROOT, ['e2e', '--list'], caller) == 0
    execute.assert_called_once()
    assert execute.call_args.kwargs['user'] == 1000
    assert execute.call_args.kwargs['group'] == 1000
    assert execute.call_args.args[0][-1] == '--list'


@pytest.mark.parametrize('relative', ['tests/e2e/runner.py', 'tests/e2e/inventory.py',
                                     'tests/e2e/scenarios.json'])
def test_symlinked_entry_or_inventory_is_refused(checkout, relative):
    target = checkout / relative
    target.unlink()
    target.symlink_to(ROOT / relative)
    with pytest.raises(ValueError, match='unsafe-input|invalid-test-path'):
        dispatcher['selection'](checkout, ['e2e', '--list'])


def test_malformed_inventory_is_refused_without_echoing_contents(checkout):
    (checkout / 'tests/e2e/scenarios.json').write_text('{private-value')
    with pytest.raises(ValueError, match='inventory:unreadable-json'):
        runner['preflight'](['--list'], root=checkout)


@pytest.mark.parametrize('artifact,code', [
    (None, 'artifacts-required'), ('relative', 'invalid-artifact-directory'),
    ('/tmp/unscoped', 'invalid-artifact-directory'),
    ('/tmp/onpc-test/../other', 'invalid-artifact-directory'),
    ('/tmp/onpc-future', 'missing-artifact-directory'),
])
def test_ready_declaration_still_requires_valid_artifacts(checkout, artifact, code):
    path = checkout / 'tests/e2e/scenarios.json'
    document = json.loads(path.read_text())
    document['scenarios'] = document['scenarios'][:1]
    executable = checkout / 'tests/e2e/synthetic.py'
    executable.write_text('raise AssertionError("must not execute")\n')
    document['scenarios'][0]['variants'][0].update(
        status='ready', pending_reason=None,
        executable={'path': 'tests/e2e/synthetic.py', 'test_id': 'synthetic-smoke'})
    path.write_text(json.dumps(document))
    options = [] if artifact is None else ['--artifacts=' + artifact]
    with pytest.raises(ValueError, match=code):
        runner['preflight'](options, root=checkout)


@pytest.mark.parametrize('assignments,code', [
    (['LIST=0'], 'LIST-must-be-1'),
    (['LIST=1', 'VM_IMAGE=unused'], 'VM_IMAGE-refused'),
    (['LIST=1', 'ARTIFACT_DIR=/tmp/onpc-unused'], 'listing-does-not-use-artifacts'),
    (['SCENARIO=E2E-002', 'ARTIFACT_DIR=/tmp/onpc-unused'], 'selection:pending'),
])
def test_make_target_refusals(cli_checkout, assignments, code):
    result = subprocess.run(['/usr/bin/make', '--no-print-directory', 'check-e2e', *assignments],
                            cwd=cli_checkout, capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert code in result.stderr


def test_make_listing_matches_category_listing(cli_checkout):
    options = dict(cwd=cli_checkout, capture_output=True, text=True, timeout=15)
    direct = subprocess.run([str(cli_checkout / 'tools/run-tests'), 'e2e', '--list',
                             '--scenario=E2E-023/fullscreen'], **options)
    make = subprocess.run(['/usr/bin/make', '--no-print-directory', 'check-e2e',
                           'LIST=1', 'SCENARIO=E2E-023/fullscreen'], **options)
    assert direct.returncode == make.returncode == 0
    assert json.loads(direct.stdout) == json.loads(make.stdout)


def test_public_ready_listing_and_installed_dispatcher_share_selection(cli_checkout):
    result = subprocess.run([str(cli_checkout / 'tools/run-tests'), 'e2e', '--list', '--ready'],
                            cwd=cli_checkout, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    listing = json.loads(result.stdout)
    assert listing == runner['preflight'](['--list', '--ready'])
    assert listing['scope'] == 'partial' and listing['ready_only'] is True
    assert [c['case_id'] for c in listing['cases']] == [
        'E2E-001/gdm-observation', 'E2E-003/existing-and-new', 'E2E-003/none',
        'E2E-004/app-grid', 'E2E-004/terminal', 'E2E-030/parent', 'E2E-042/command-help']
    assert len(listing['excluded_pending_cases']) == 235
    import tempfile
    with tempfile.TemporaryDirectory(prefix='onpc-ready-test-') as directory:
        command = dispatcher['selection'](ROOT, ['e2e', '--ready', '--artifacts=' + directory])
        plan = runner['preflight'](command[3:])
        assert plan['cases'] == listing['cases']
        assert plan['excluded_pending_cases'] == listing['excluded_pending_cases']
        assert 'verify_backing_bytes' not in plan


def test_default_execution_selects_every_ready_e2e_case():
    listing = runner['preflight'](['--list', '--ready'])
    plan = runner['preflight']([], allow_missing_artifacts=True)
    assert plan['cases'] == listing['cases']
    assert plan['excluded_pending_cases'] == listing['excluded_pending_cases']
    commands_to_run, safety = commands.plan(ROOT, 'e2e', [])
    assert commands_to_run == [['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner', 'e2e']]
    assert safety is False


def test_comma_separated_ids_keep_exact_selection_through_dispatch():
    ids = [1, 3, 4]
    value = ','.join(map(str, ids))
    command = dispatcher['selection'](ROOT, ['e2e', '--list', '--id', value])
    plan = runner['preflight'](command[3:])
    assert [case['coverage_id'] for case in plan['cases']] == ids
    assert plan['scope'] == 'partial'
    duplicate = runner['preflight'](['--list', '--id', value + ',' + str(ids[0])])
    assert duplicate['cases'] == plan['cases']


@pytest.mark.parametrize('value', ['', ',', '1,', ',1', '1,,2', '1, 2', '1,x', '1,0', '1,-2', '1,999999'])
def test_invalid_id_list_refuses_before_execution(value):
    with pytest.raises(ValueError, match='selection:invalid-id|selection:unknown-id'):
        commands.plan(ROOT, 'e2e', ['--id', value])


@pytest.mark.parametrize('status', [0, 7])
def test_ready_selection_builds_artifacts_then_dispatches_only_e2e(monkeypatch, status):
    import tempfile
    import regression
    # Bare e2e now belongs to the complete-phase aggregate. Keep this direct
    # launcher check on the explicit ready selection and forbid a real aggregate
    # from acquiring the enclosing test run's retention lock.
    aggregate = Mock(side_effect=AssertionError('unexpected aggregate dispatch'))
    monkeypatch.setattr(regression, 'main', aggregate)
    with tempfile.TemporaryDirectory(prefix='onpc-e2e-command-test-') as directory:
        build = Mock(return_value=SimpleNamespace(returncode=status))
        execute = Mock()
        monkeypatch.setattr(commands.tempfile, 'mkdtemp', lambda **kwargs: directory)
        monkeypatch.setattr(commands.subprocess, 'run', build)
        monkeypatch.setattr(commands.os, 'execve', execute)
        monkeypatch.setattr(dev_privileges, 'check', Mock())
        result = commands._main(['e2e', '--ready'])
        aggregate.assert_not_called()
        build.assert_called_once()
        assert build.call_args.args[0] == [
            '/usr/bin/python3', '-B', str(ROOT / 'tools/build_test_artifacts.py'),
            '--reuse', '--output', directory]
        if status:
            assert result == status
            execute.assert_not_called()
        else:
            execute.assert_called_once()
            assert execute.call_args.args[1] == [
                '/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner',
                'e2e', '--ready', '--artifacts=' + directory]


def test_make_selector_never_becomes_recipe_shell_code(tmp_path, cli_checkout):
    marker = tmp_path / 'injected'
    selector = f"E2E-001'; touch {marker}; echo '"
    result = subprocess.run(['/usr/bin/make', '--no-print-directory', 'check-e2e',
                             'LIST=1', 'SCENARIO=' + selector], cwd=cli_checkout,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert 'selection:unknown' in result.stderr
    assert not marker.exists()
    assert selector not in result.stderr
