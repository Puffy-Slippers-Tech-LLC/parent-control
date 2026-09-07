"""Real file/Git/artifact provenance with a host-only simulated held VM lease."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_e2e_evidence import attempt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import provenance
sys.path.pop(0)


def git(root, *args):
    subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)


def test_source_git_trust_is_scoped_to_the_selected_checkout(tmp_path):
    from unittest.mock import patch, Mock
    (tmp_path / 'file').write_text('source input')
    with patch.object(provenance.subprocess, 'run', return_value=Mock(stdout=b'file\0')) as run:
        assert provenance.source_paths(tmp_path) == ['file']
    args = run.call_args.args[0]
    assert args[:3] == ['git', '-c', 'safe.directory=' + str(tmp_path)]
    assert '*' not in args and run.call_args.kwargs['cwd'] == tmp_path


def test_real_checkout_provenance_matches_artifact_builder():
    builder = provenance.build_test_artifacts
    paths = builder._source_paths()
    captured = provenance.snapshot(ROOT, source=True)
    assert list(captured['files']) == [p.as_posix() for p in paths]
    assert captured['sha256'] == builder._source_digest(paths)


@pytest.fixture
def lease():
    state = {'phase': 'finalized', 'proof': {'disk': 'retained-proof'},
             'guest': {'ubuntu_version': '26.04', 'accounts': 'private-fixture-account'}}
    capture = SimpleNamespace(state=state, read_state=lambda: copy.deepcopy(state),
                              verify_snapshot=lambda: copy.deepcopy(state['proof']))
    return SimpleNamespace(fd=42, guard=Mock(), capture=capture,
                           state={'baseline_sha256': provenance.digest(state)})


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'checkout'
    root.mkdir()
    git(root, 'init', '-q')
    for name in ('tests/e2e/scenarios.json', 'tests/e2e/runner.py', 'tests/requirements.json',
                 'docs/TestAutomation/E2E-Coverage.md',
                 'tests/integration/graphical_smoke/main.pm',
                 'tests/integration/graphical_smoke/tests/smoke.pm'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    (root / '.codex').mkdir()
    (root / '.codex/rules').write_text('fixture input\n')
    (root / '.codex-staged').write_text('sibling input\n')
    git(root, 'add', '.')
    # Include a real untracked input and a real uncommitted tracked edit.
    (root / 'local-change.py').write_text('current input\n')
    with (root / 'tests/e2e/runner.py').open('a') as stream:
        stream.write('\n# local change\n')
    return root


@pytest.fixture
def assets(tmp_path, source):
    root = tmp_path / 'assets'
    root.mkdir(mode=0o700)
    (root / 'package.deb').write_bytes(b'test package bytes')
    fixtures = root / 'fixtures'
    fixtures.mkdir()
    (fixtures / 'payload').write_bytes(b'fixture payload')
    (fixtures / 'onpc-test-application.flatpak').write_bytes(b'flatpak container')
    files = {'payload': hashlib.sha256(b'fixture payload').hexdigest()}
    (fixtures / 'SHA256SUMS.json').write_text(json.dumps({'algorithm': 'sha256', 'files': files}))
    manifest = {
        'schema_version': 1,
        'source': {'digest_sha256': provenance.snapshot(source, source=True)['sha256']},
        'artifacts': {
            'package': {'path': 'package.deb', 'sha256': hashlib.sha256(b'test package bytes').hexdigest()},
            'fixtures': {'path': 'fixtures', 'sha256': hashlib.sha256(
                json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()},
        },
    }
    (root / 'artifact-manifest.json').write_text(json.dumps(manifest))
    return root


def test_captures_current_source_compatible_with_builder_and_returns_copies(source, lease, monkeypatch):
    captured = provenance.VerifiedInputs(root=source, lease=lease)
    monkeypatch.setattr(provenance.build_test_artifacts, 'REPOSITORY', source)
    builder = provenance.build_test_artifacts
    assert captured.inputs['source_sha256'] == builder._source_digest(builder._source_paths())
    assert 'local-change.py' in captured.source_files
    assert captured.inputs['package_sha256'] is None
    assert captured.inputs['baseline_sha256'] == lease.state['baseline_sha256']
    assert captured.inputs['environment_id'].startswith('ubuntu26-04-')
    assert 'private-fixture-account' not in json.dumps(captured.inputs)
    captured.inputs['source_sha256'] = 'forged'
    captured.source_files.clear()
    captured.recheck()
    assert captured.source_files and captured.inputs['source_sha256'] != 'forged'


@pytest.mark.parametrize('change', ['delete', 'delete-directory', 'staged-delete', 'rename'])
def test_removed_source_matches_artifact_builder(source, lease, monkeypatch, tmp_path, change):
    builder = provenance.build_test_artifacts
    monkeypatch.setattr(builder, 'REPOSITORY', source)
    original = provenance.snapshot(source, source=True)
    target = source / '.codex/rules'
    if change == 'rename':
        target.rename(source / 'renamed-input')
    else:
        target.unlink()
    if change == 'delete-directory':
        target.parent.rmdir()
    elif change == 'staged-delete':
        git(source, 'add', '-u')
    captured = provenance.snapshot(source, source=True)
    paths = builder._source_paths()
    assert '.codex/rules' not in captured['files']
    assert captured['sha256'] != original['sha256']
    assert list(captured['files']) == [p.as_posix() for p in paths]
    assert captured['sha256'] == builder._source_digest(paths)
    if change == 'rename':
        assert 'renamed-input' in captured['files']
    destination = tmp_path / 'source-copy'
    builder._copy_source(paths, destination)
    assert not (destination / '.codex/rules').exists()
    assert sorted(p.relative_to(destination) for p in destination.rglob('*') if p.is_file()) == paths
    verified = provenance.VerifiedInputs(root=source, lease=lease)
    target.parent.mkdir(exist_ok=True)
    target.write_text('restored input')
    with pytest.raises(provenance.EvidenceError, match='source-changed'):
        verified.recheck()


def test_dangling_source_link_is_not_treated_as_deleted(source, lease, monkeypatch):
    target = source / '.codex/rules'
    target.unlink()
    target.symlink_to(source / 'missing')
    builder = provenance.build_test_artifacts
    monkeypatch.setattr(builder, 'REPOSITORY', source)
    assert '.codex/rules' in provenance.source_paths(source)
    paths = builder._source_paths()
    assert Path('.codex/rules') in paths
    with pytest.raises(builder.ArtifactError, match='not a regular file'):
        builder._source_digest(paths)
    with pytest.raises(provenance.EvidenceError, match='unsafe-file'):
        provenance.VerifiedInputs(root=source, lease=lease)


@pytest.mark.parametrize('name', ['tests/requirements.json', 'tests/e2e/runner.py',
                                  'tests/e2e/scenarios.json', 'local-change.py'])
@pytest.mark.parametrize('mutation', ['edit', 'remove', 'mode', 'replace'])
def test_input_changes_cannot_be_accepted_or_cleared(source, lease, name, mutation):
    captured = provenance.VerifiedInputs(root=source, lease=lease)
    path = source / name
    original = path.read_bytes()
    if mutation == 'edit':
        path.write_bytes(original + b'changed')
    elif mutation == 'remove':
        path.unlink()
    elif mutation == 'mode':
        path.chmod(0o700)
    else:
        path.unlink()
        path.write_bytes(original)
    with pytest.raises(provenance.EvidenceError, match='provenance:'):
        captured.recheck()
    path.write_bytes(original)
    with pytest.raises(provenance.EvidenceError, match='provenance:'):
        captured.recheck()


def test_new_source_file_is_detected(source, lease):
    captured = provenance.VerifiedInputs(root=source, lease=lease)
    (source / 'new-test.py').write_text('new input')
    with pytest.raises(provenance.EvidenceError, match='source-changed'):
        captured.recheck()


def test_source_preflight_accepts_current_package_without_vm(source, assets):
    result = provenance.preflight_source(assets, root=source)
    assert result == {'source_sha256': provenance.snapshot(source, source=True)['sha256'],
                      'scope': 'before-lease-diagnostic'}


@pytest.mark.parametrize('change', ['edit', 'remove', 'during-verification'])
def test_source_preflight_refuses_changed_inputs_without_exposing_paths(
        source, assets, change, monkeypatch, capsys):
    target = source / 'tests/e2e/runner.py'
    if change == 'remove':
        target.unlink()
    elif change == 'edit':
        target.write_text('private-canary')
    else:
        original = provenance.build_test_artifacts.verify
        def verify(path):
            result = original(path)
            target.write_text('private-canary')
            return result
        monkeypatch.setattr(provenance.build_test_artifacts, 'verify', verify)
    with pytest.raises(provenance.EvidenceError, match='provenance:') as failure:
        provenance.preflight_source(assets, root=source)
    output = capsys.readouterr().err + str(failure.value)
    assert 'source-preflight-rejected' in output
    assert 'private-canary' not in output and str(target) not in output


@pytest.mark.parametrize('kind', ['symlink', 'parent-symlink', 'hardlink', 'fifo'])
def test_unsafe_sources_refuse_before_opening_or_following(source, lease, kind):
    target = source / 'unsafe'
    if kind == 'symlink':
        target.symlink_to(source / 'local-change.py')
    elif kind == 'parent-symlink':
        (source / 'tests/e2e').rename(source / 'moved')
        (source / 'tests/e2e').symlink_to(source / 'moved', target_is_directory=True)
    elif kind == 'hardlink':
        os.link(source / 'local-change.py', target)
    else:
        target.write_text('tracked input')
        git(source, 'add', 'unsafe')
        target.unlink()
        os.mkfifo(target)
    with pytest.raises(provenance.EvidenceError, match='(unsafe-file|capture-failed)'):
        provenance.VerifiedInputs(root=source, lease=lease)


def test_package_and_actual_fixture_payload_are_verified(source, assets, lease):
    captured = provenance.VerifiedInputs(root=source, assets=assets, lease=lease)
    assert captured.inputs['package_sha256'] == hashlib.sha256(b'test package bytes').hexdigest()
    captured.recheck()


@pytest.mark.parametrize('name', ['package.deb', 'fixtures/payload',
                                  'fixtures/onpc-test-application.flatpak', 'artifact-manifest.json'])
def test_changed_assets_cannot_pass(source, assets, lease, name):
    captured = provenance.VerifiedInputs(root=source, assets=assets, lease=lease)
    (assets / name).write_bytes(b'changed')
    with pytest.raises(provenance.EvidenceError, match='assets-changed'):
        captured.recheck()


def test_stale_package_is_rejected_even_if_its_bytes_match_manifest(source, assets, lease):
    (source / 'tests/requirements.json').write_text('new requirements')
    with pytest.raises(provenance.EvidenceError, match='package-source-mismatch'):
        provenance.VerifiedInputs(root=source, assets=assets, lease=lease)


def test_fixture_manifest_digest_does_not_substitute_for_payload_verification(source, assets, lease):
    (assets / 'fixtures/payload').write_bytes(b'wrong payload')
    with pytest.raises(provenance.EvidenceError, match='capture-failed'):
        provenance.VerifiedInputs(root=source, assets=assets, lease=lease)


@pytest.mark.parametrize('change', ['state', 'proof', 'identity', 'environment', 'released', 'guard'])
def test_baseline_and_lease_changes_are_rejected(source, lease, change):
    captured = provenance.VerifiedInputs(root=source, lease=lease)
    if change == 'state':
        lease.capture.read_state = lambda: {'phase': 'changed'}
    elif change == 'proof':
        lease.capture.verify_snapshot = lambda: {'disk': 'different'}
    elif change == 'identity':
        lease.state['baseline_sha256'] = 'a' * 64
    elif change == 'environment':
        lease.capture.state['guest']['ubuntu_version'] = 'other'
    elif change == 'released':
        lease.fd = None
    else:
        lease.guard.side_effect = RuntimeError('private fixture diagnostic')
    with pytest.raises(provenance.EvidenceError, match='provenance:') as error:
        captured.recheck()
    assert 'private fixture' not in str(error.value)


def test_edit_during_capture_refuses_before_contract(source, assets, lease, monkeypatch):
    original = provenance.build_test_artifacts.verify
    def changing_verify(path):
        manifest = original(path)
        (source / 'local-change.py').write_text('changed during verification')
        return manifest
    monkeypatch.setattr(provenance.build_test_artifacts, 'verify', changing_verify)
    with pytest.raises(provenance.EvidenceError, match='source-changed'):
        provenance.VerifiedInputs(root=source, assets=assets, lease=lease)


def test_parent_replacement_between_stat_and_open_is_refused(source, lease, monkeypatch):
    original = provenance.os.open
    parent = source / 'tests/e2e'
    swapped = False
    def replacing_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == 'runner.py' and not swapped:
            swapped = True
            parent.rename(source / 'moved-e2e')
            parent.symlink_to(source / 'moved-e2e', target_is_directory=True)
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(provenance.os, 'open', replacing_open)
    with pytest.raises(provenance.EvidenceError, match='file-replaced'):
        provenance.VerifiedInputs(root=source, lease=lease)
    assert swapped


def test_source_changes_during_result_validation_refuse_success(attempt, lease):
    _, collector, result, inventory_path, _ = attempt
    root = inventory_path.parent
    (root / 'tests/e2e/scenarios.json').write_bytes(inventory_path.read_bytes())
    (root / '.gitignore').write_text(collector.path.name + '/\n')
    git(root, 'init', '-q')
    captured = provenance.VerifiedInputs(root=root, lease=lease)
    contract = captured.contract(run_id='run-one', selector='E2E-001')
    result.update(captured.inputs)
    validate = contract.validate
    def changed_validation(records, destination):
        summary = validate(records, destination)
        (root / 'tests/e2e/synthetic.py').write_text('changed after validation')
        return summary
    contract.validate = changed_validation
    with pytest.raises(provenance.EvidenceError, match='source-changed'):
        captured.validate(contract, [result], collector)


def test_verified_contract_accepts_real_collector_records_and_rejects_later_source_edit(attempt, lease):
    _, collector, result, inventory_path, _ = attempt
    root = inventory_path.parent
    target = root / 'tests/e2e/scenarios.json'
    target.write_bytes(inventory_path.read_bytes())
    (root / '.gitignore').write_text(collector.path.name + '/\n')
    git(root, 'init', '-q')
    captured = provenance.VerifiedInputs(root=root, lease=lease)
    contract = captured.contract(run_id='run-one', selector='E2E-001')
    result.update(captured.inputs)
    assert captured.validate(contract, [result], collector)['outcome'] == 'passed'
    (root / 'tests/requirements.json').write_text('changed')
    with pytest.raises(provenance.EvidenceError, match='source-changed'):
        captured.validate(contract, [result], collector)


def test_worker_constructed_contract_is_not_trusted(source, lease):
    captured = provenance.VerifiedInputs(root=source, lease=lease)
    foreign = Mock()
    with pytest.raises(provenance.EvidenceError, match='foreign-contract'):
        captured.validate(foreign, [], Mock())
    foreign.validate.assert_not_called()


def test_pending_inventory_still_cannot_execute(source, lease):
    path = source / 'tests/e2e/scenarios.json'
    document = json.loads(path.read_bytes())
    document['scenarios'] = document['scenarios'][:1]
    path.write_text(json.dumps(document))
    captured = provenance.VerifiedInputs(root=source, lease=lease)
    with pytest.raises(ValueError, match='selection:pending'):
        captured.contract(run_id='run-one', selector='E2E-001')
