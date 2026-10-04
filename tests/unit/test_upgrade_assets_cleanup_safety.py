"""Private package/files, waited children and simulated leases; no live VM/bus.

Compatible unit and cleanup overlap. The inherited envelope alone owns recovery.
"""
from contextlib import contextmanager
import builtins
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import provenance
import asset_transfer
import guest_observations
import upgrade_assets_qualification as qualification
import check_e2e_upgrade_assets as selector
import check_graphical_smoke as smoke
import installed_journey
import system_runner
from observation_transport import ReadOnlyObservations
from owned_commands import CommandError
from parent_setup_qualification import UpgradeAssetsQualification, ProductFreeEntryQualification
from private_artifacts import EvidenceError
from tests.support.e2e_provenance import source, assets, lease
from tests.support.e2e_transfer import GuestFiles
from tests.support.desktop_session import props, RUN_PROBE
from tests.support.perl import run_perl

builder = provenance.build_test_artifacts


def package(root, path, version, *, name='oh-no-parent-control', architecture='amd64'):
    root.mkdir()
    (root / 'DEBIAN').mkdir()
    (root / 'DEBIAN/control').write_text(
        f'Package: {name}\nVersion: {version}\nArchitecture: {architecture}\n'
        'Maintainer: Test <test@invalid>\nDescription: synthetic validator input\n')
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(root), str(path)],
                   check=True, capture_output=True)


def inventory(root):
    (root / 'transfer-sha256.json').write_text(json.dumps({
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file() and p != root / 'transfer-sha256.json'}))


@pytest.fixture
def upgrade(tmp_path, source, assets, lease, monkeypatch):
    (source / 'debian').mkdir()
    (source / 'debian/changelog').write_text(
        'oh-no-parent-control (1.3+ppa1~ubuntu26.04.1) resolute; urgency=medium\n\n'
        '  * Test.\n\n -- Test <test@invalid>  Mon, 28 Sep 2026 21:21:54 +0000\n')
    (source / 'Makefile').write_text('package-source-files:\n\t@printf "%s\\n" Makefile debian/changelog\n')
    released = tmp_path / 'released'
    released.mkdir()
    (released / 'Makefile').write_bytes((source / 'Makefile').read_bytes())
    (released / 'debian').mkdir()
    (released / 'debian/changelog').write_text('authentic fixture release source\n')
    @contextmanager
    def release(**kwargs): yield released
    monkeypatch.setattr(builder, 'released_source', release)
    previous = assets / 'previous'
    shutil.copytree(assets, previous)
    previous.chmod(0o700)
    for label, directory, version in (
            ('current', assets, '1.3+ppa1~ubuntu26.04.1'),
            ('previous', previous, builder.RELEASE_VERSION)):
        package(tmp_path / label, directory / 'package.deb', version)
        manifest = json.loads((directory / builder.MANIFEST_NAME).read_text())
        manifest['artifacts']['package']['sha256'] = builder._sha256(directory / 'package.deb')
        manifest['source'] = (builder.release_identity(released) if label == 'previous' else {
            'scope': 'package', 'digest_sha256': builder.package_inputs.digest(
                source, builder.package_inputs.paths(source)), 'file_count': 2, 'revision': 'c' * 40})
        (directory / builder.MANIFEST_NAME).write_text(json.dumps(manifest))
    inventory(assets)
    for path in assets.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    lease.state.update(phase='isolated', domain_id=None)
    lease.capture.state['source'] = {'layout': {'disk': '/recorded-disk'}}
    lease.state['baseline_sha256'] = provenance.digest(lease.capture.state)
    (tmp_path / 'guest/var/lib').mkdir(parents=True)
    guest = GuestFiles(tmp_path / 'guest')
    guest.path('/etc').mkdir()
    guest.path('/etc/passwd').write_bytes(b'unchanged account witness')
    return assets, source, lease, guest


def captured(upgrade):
    assets, source, lease, guest = upgrade
    builder.verify_upgrade(assets, staged=True, repository=source)
    verified = provenance.VerifiedInputs(assets=assets, root=source, lease=lease, upgrade=True)
    return verified, asset_transfer.AssetTransfer(verified), SimpleNamespace(GuestFS=Mock(return_value=guest))


def test_two_packages_keep_separate_sources_bytes_and_single_use_cleanup(upgrade):
    assets, source, lease, guest = upgrade
    verified, transfer, api = captured(upgrade)
    expected = verified.upgrade_inputs
    assert expected['sources']['previous']['revision'] == builder.RELEASE_COMMIT
    assert expected['packages']['current']['sha256'] != expected['packages']['previous']['sha256']
    expected['sources']['previous']['revision'] = 'changed'
    assert verified.upgrade_inputs['sources']['previous']['revision'] == builder.RELEASE_COMMIT
    receipt = transfer.provision(lease, api)
    assert guest.uploads == len(verified.asset_files) and guest.closed
    assert guest.path('/etc/passwd').read_bytes() == b'unchanged account witness'
    observations = Mock(read=Mock(return_value=copy.deepcopy(receipt)))
    assert transfer.observe(observations) == transfer.observe(observations) == receipt
    assert observations.read.call_args_list == [(('assets-upgrade',), {}), (('assets-upgrade',), {})]
    assert qualification.provisioning_refusals(verified, lease, api, transfer) == {
        'wrong_attempt_refused': True, 'collision_refused': True, 'replay_refused': True}
    assert guest.uploads == len(verified.asset_files)


@pytest.mark.parametrize('fault', ['', 'canonical-bytes', 'alias-replaced', 'wrong-target', 'other-link',
                                  'missing-canonical', 'canonical-link', 'canonical-fifo'])
def test_ubuntu_locale_alias_preserves_link_and_canonical_file(upgrade, fault):
    verified, transfer, api = captured(upgrade)
    guest = upgrade[3]
    guest.path('/etc/default').mkdir()
    canonical = guest.path('/etc/locale.conf')
    canonical.write_bytes(b'LANG=en_US.UTF-8\n')
    alias = guest.path('/etc/default/locale')
    alias.symlink_to('../locale.conf')
    before = asset_transfer.preservation_witness(guest) if not fault else None
    if fault == 'wrong-target':
        alias.unlink()
        alias.symlink_to('../passwd')
    elif fault == 'other-link':
        guest.path('/etc/hostname').symlink_to('locale.conf')
    elif fault in ('missing-canonical', 'canonical-link', 'canonical-fifo'):
        canonical.unlink()
        if fault == 'canonical-link':
            canonical.symlink_to('passwd')
        elif fault == 'canonical-fifo':
            os.mkfifo(canonical)
    elif fault:
        upload = guest.upload
        def mutate(*args):
            upload(*args)
            if fault == 'canonical-bytes':
                canonical.write_bytes(b'LANG=zh_CN.UTF-8\n')
            else:
                alias.unlink()
                alias.write_bytes(b'LANG=en_US.UTF-8\n')
        guest.upload = mutate
    if fault:
        with pytest.raises(EvidenceError, match='unsafe-preservation-file|preservation-changed'):
            transfer.provision(upgrade[2], api)
        assert guest.closed
        if fault in ('wrong-target', 'other-link', 'missing-canonical', 'canonical-link', 'canonical-fifo'):
            assert guest.uploads == 0
        with pytest.raises(EvidenceError, match='already-attempted'):
            transfer.provision(upgrade[2], api)
        with pytest.raises(EvidenceError, match='verified-provisioning-required'):
            transfer.observe(Mock())
    else:
        transfer.provision(upgrade[2], api)
        assert alias.is_symlink() and alias.readlink().as_posix() == '../locale.conf'
        assert canonical.read_bytes() == b'LANG=en_US.UTF-8\n'
        assert asset_transfer.preservation_witness(guest) == before


@pytest.mark.parametrize('fault', ['', 'bytes', 'identity', 'mode', 'owner', 'extra'])
def test_exact_booted_guest_program_reads_real_package_metadata_and_tree(upgrade, tmp_path, capsys, fault):
    verified, transfer, api = captured(upgrade)
    guest = upgrade[3]
    receipt = transfer.provision(upgrade[2], api)
    old = guest.path(asset_transfer.DESTINATION + '/previous/package.deb')
    if fault == 'bytes': old.write_bytes(b'changed')
    if fault == 'identity': package(tmp_path / 'booted-wrong-package', old, '1.1')
    if fault == 'mode': old.chmod(0o666)
    if fault == 'extra': guest.path(asset_transfer.DESTINATION + '/extra').mkdir()
    class GuestPath(type(guest.root)):
        def lstat(self):
            info = super().lstat()
            return SimpleNamespace(st_uid=1 if fault == 'owner' else 0, st_gid=0,
                                   st_mode=info.st_mode, st_nlink=info.st_nlink)
    def imported(name, *args, **kwargs):
        if name == 'pathlib':
            return SimpleNamespace(Path=lambda value: GuestPath(guest.path(value)),
                                   PurePosixPath=__import__('pathlib').PurePosixPath)
        return builtins.__import__(name, *args, **kwargs)
    capsys.readouterr()
    def execute():
        exec(compile(guest_observations.UPGRADE_ASSETS, '<upgrade-asset-oracle>', 'exec'),
             {'__builtins__': {**vars(builtins), '__import__': imported}})
        return json.loads(capsys.readouterr().out)
    if fault:
        with pytest.raises((AssertionError, ValueError, subprocess.CalledProcessError)): execute()
    else:
        assert execute() == receipt


@pytest.mark.parametrize('fault', ['name', 'architecture', 'old-version', 'current-version',
                                  'reversed', 'same', 'old-source', 'current-source',
                                  'changed', 'missing', 'symlink', 'hardlink', 'fifo', 'owner', 'writable'])
def test_invalid_packages_sources_and_file_identities_refuse_before_any_transfer(upgrade, tmp_path, fault, monkeypatch):
    assets, source, lease, guest = upgrade
    old = assets / 'previous/package.deb'
    if fault in ('name', 'architecture', 'old-version', 'current-version'):
        target = assets / 'package.deb' if fault == 'current-version' else old
        package(tmp_path / 'wrong-package', target,
            '1.1' if fault == 'old-version' else builder.RELEASE_VERSION,
            name='wrong-product' if fault == 'name' else 'oh-no-parent-control',
            architecture='arm64' if fault == 'architecture' else 'amd64')
    elif fault == 'reversed':
        current = (assets / 'package.deb').read_bytes()
        (assets / 'package.deb').write_bytes(old.read_bytes())
        old.write_bytes(current)
    elif fault == 'same': (assets / 'package.deb').write_bytes(old.read_bytes())
    elif fault == 'old-source':
        path = assets / 'previous/artifact-manifest.json'
        value = json.loads(path.read_text())
        value['source']['revision'] = 'f' * 40
        path.write_text(json.dumps(value))
    elif fault == 'current-source': (source / 'debian/changelog').write_text('changed source')
    elif fault == 'changed': old.write_bytes(b'changed')
    elif fault == 'missing': old.unlink()
    elif fault == 'symlink':
        old.unlink()
        old.symlink_to(assets / 'package.deb')
    elif fault == 'hardlink': os.link(old, assets / 'linked')
    elif fault == 'fifo': os.mkfifo(assets / 'special')
    elif fault == 'owner':
        original = Path.lstat
        def lstat(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            return SimpleNamespace(st_uid=info.st_uid + 1, st_mode=info.st_mode,
                                   st_nlink=info.st_nlink) if path == old else info
        monkeypatch.setattr(Path, 'lstat', lstat)
    elif fault == 'writable': old.chmod(0o666)
    # Digest-consistent bad metadata must still be rejected by identity/source checks.
    if fault in ('name', 'architecture', 'old-version', 'current-version', 'reversed', 'same'):
        for directory in (assets, assets / 'previous'):
            path = directory / 'artifact-manifest.json'
            value = json.loads(path.read_text())
            value['artifacts']['package']['sha256'] = builder._sha256(directory / 'package.deb')
            path.write_text(json.dumps(value))
    with pytest.raises((EvidenceError, builder.ArtifactError, OSError, ValueError)):
        captured(upgrade)
    assert guest.uploads == 0


@pytest.mark.parametrize('fault', ['changed', 'replaced', 'partial', 'preservation'])
def test_changed_and_uncertain_transfer_is_consumed_with_outer_cleanup(upgrade, fault):
    assets, source, lease, guest = upgrade
    verified, transfer, api = captured(upgrade)
    if fault == 'changed': (assets / 'previous/package.deb').write_bytes(b'changed')
    elif fault == 'replaced':
        path = assets / 'previous/package.deb'
        raw = path.read_bytes()
        path.unlink()
        path.write_bytes(raw)
    else:
        upload = guest.upload
        def partial(*args):
            upload(*args)
            if fault == 'partial': raise OSError('uncertain transfer')
            guest.path('/etc/passwd').write_bytes(b'changed unrelated state')
        guest.upload = partial
    with pytest.raises((EvidenceError, OSError)): transfer.provision(lease, api)
    with pytest.raises(EvidenceError, match='already-attempted'): transfer.provision(lease, api)
    with pytest.raises(EvidenceError, match='verified-provisioning-required'): transfer.observe(Mock())
    assert guest.closed if fault in ('partial', 'preservation') else not api.GuestFS.called


@pytest.mark.parametrize('fault', ['', 'package', 'second', 'private-field', 'wrong-attempt', 'large'])
def test_real_observation_decoder_checks_package_fields_and_repeated_reads(upgrade, fault):
    verified, transfer, api = captured(upgrade)
    receipt = transfer.provision(upgrade[2], api)
    bad = copy.deepcopy(receipt)
    if fault == 'package': bad['packages']['previous']['architecture'] = 'arm64'
    if fault == 'private-field': bad['packages']['current']['path'] = '/private-canary'
    if fault == 'second': bad['packages']['current']['sha256'] = '0' * 64
    raw = lambda value: (json.dumps(value, sort_keys=True) + '\n').encode()
    transport = SimpleNamespace(config={'run': 'owned'}, guard=Mock(), call=Mock(
        side_effect=[raw(receipt), raw(bad)]))
    observations = ReadOnlyObservations(transport)
    assert transfer.observe(observations) == receipt
    if fault == 'wrong-attempt': transport.config['run'] = 'foreign'
    if fault == 'large': transport.call.side_effect = [b'x' * 1025]
    if fault:
        with pytest.raises(EvidenceError): transfer.observe(observations)
        with pytest.raises(EvidenceError): transfer.observe(observations)
    else:
        assert transfer.observe(observations) == receipt


def test_selector_real_constructor_and_shared_worker_order(monkeypatch):
    entry = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', entry)
    monkeypatch.setattr(selector, 'named_input', Mock(return_value='owned-input'))
    assert selector.main() == 0
    entry.assert_called_once_with(assets='owned-input', provision_credentials=True, upgrade_assets=True)
    selector.named_input.assert_called_once_with(upgrade_source=True)
    assert UpgradeAssetsQualification.__bases__ == (ProductFreeEntryQualification,)
    context = SimpleNamespace(product_free=True, asset_transfer=Mock())
    owner = UpgradeAssetsQualification.journey(context, Mock())
    assert owner.plan is qualification.PLAN
    assert set(owner.actions) == set(owner.plan.stage_actions.values())
    with pytest.raises(CommandError, match='upgrade-assets-prerequisites'):
        smoke.main(upgrade_assets=True, package_install=True, assets='inputs', provision_credentials=True)
    probe = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_product_free_entry;')
    probe = probe.replace('onpc_desktop_session::run', 'onpc_product_free_entry::run').replace('}, $action);', '});')
    result = json.loads(run_perl(probe, '').stdout)
    assert result['ok']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == list(owner.plan.screen_tags)


def test_released_source_refuses_retargeted_or_missing_release_without_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, '_run', Mock(return_value=SimpleNamespace(stdout='f' * 40)))
    archive = Mock(side_effect=AssertionError('unverified archive read'))
    monkeypatch.setattr(builder.subprocess, 'run', archive)
    with pytest.raises(builder.ArtifactError, match='authentic v1.2'):
        with builder.released_source(repository=tmp_path): pass
    archive.assert_not_called()


@pytest.mark.parametrize('changed', [False, True])
def test_actual_dual_staging_preserves_manifests_and_refuses_changed_source(upgrade, tmp_path, monkeypatch, changed):
    assets, source, lease, guest = upgrade
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    shutil.copytree(assets, bundle / 'current', ignore=shutil.ignore_patterns('previous'))
    shutil.copytree(assets / 'previous', bundle / 'previous')
    for root in (bundle / 'current', bundle / 'previous'):
        (root / 'transfer-sha256.json').unlink(missing_ok=True)
        (root / 'package').mkdir()
        (root / 'package.deb').rename(root / 'package/product.deb')
        path = root / 'artifact-manifest.json'
        manifest = json.loads(path.read_text())
        manifest['artifacts']['package']['path'] = 'package/product.deb'
        path.write_text(json.dumps(manifest))
    for path in (bundle, *bundle.rglob('*')):
        path.chmod(0o755 if path.is_dir() else 0o644)
    monkeypatch.setattr(system_runner, 'ROOT', source)
    def execute(command, **kwargs):
        result = subprocess.run(command, check=True, capture_output=True).stdout
        if changed and command[0:2] == ['dpkg-deb', '-f']:
            (bundle / 'previous/package/product.deb').write_bytes(b'changed while staging')
        return result
    commands = SimpleNamespace(run=execute)
    destination = tmp_path / 'staged'
    if changed:
        with pytest.raises((builder.ArtifactError, CommandError)):
            system_runner.stage_upgrade_assets(bundle, destination, commands)
    else:
        system_runner.stage_upgrade_assets(bundle, destination, commands)
        destination.chmod(0o700)
        verified = provenance.VerifiedInputs(root=source, lease=lease, assets=destination, upgrade=True)
        assert verified.upgrade_inputs['packages']['previous']['sha256'] == builder._sha256(
            destination / 'previous/package.deb')
        files = verified.asset_files
        assert json.loads((destination / 'transfer-sha256.json').read_bytes()) == {
            name: value for name, value in files.items() if name != 'transfer-sha256.json'}


@pytest.mark.parametrize('fault', ['', 'readback', 'accounts', 'provider', 'storage'])
def test_upgrade_desktop_assertions_run_through_real_recorder_before_reply(upgrade, tmp_path, monkeypatch, fault):
    verified, transfer, api = captured(upgrade)
    transfer.provision(upgrade[2], api)
    state = {'accounts': {'1001': {'name': 'child', 'language': 'en'}}, 'sessions': {'7': props()},
             'system_locale': ['LANG=en'], 'observer_locale': {'LANG': 'C'}, 'product_free': True,
             'target_uid': '1001'}
    preservation = SimpleNamespace(read=Mock(return_value=copy.deepcopy(state)))
    if fault == 'accounts': preservation.read.return_value['accounts']['1001']['language'] = 'zh'
    context = SimpleNamespace(directory=tmp_path, product_free=True, asset_transfer=transfer,
                              verified=verified, lease=upgrade[2])
    context.lease.state['phase'] = 'running'
    progress = Mock(side_effect=OSError('private storage failed') if fault == 'storage' else None)
    owner = qualification.journey(context, progress)
    owner.upgrade_preservation, owner.upgrade_entry = preservation, copy.deepcopy(state)
    owner.steps = [{'stage': stage} for stage in owner.plan.stages[:owner.plan.stages.index('desktop')]]
    receipt = copy.deepcopy(transfer._receipt)
    bad = copy.deepcopy(receipt)
    if fault == 'readback': bad['packages']['current']['sha256'] = '0' * 64
    owner.vm = Mock(read=Mock(side_effect=[receipt, bad]))
    provider = {'locale': 'en_US.UTF-8', 'version': '50.1', 'keyboard': [['xkb', 'us']]}
    owner.ui = SimpleNamespace(boot_proof='a' * 64, observe=Mock(side_effect=[
        {'outcome': 'passed'}, {'provider': provider}, {'provider': provider},
        {'provider': {**provider, 'locale': 'zh'}} if fault == 'provider' else {'provider': provider}]))
    owner.transport = Mock()
    monkeypatch.setattr(installed_journey.session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    (tmp_path / 'desktop.request.json').write_text(json.dumps({'stage': 'desktop', 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): owner.step(Mock())
        assert not (tmp_path / 'desktop.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'): owner.step(Mock())
    else:
        owner.step(Mock())
        assert owner.progress.call_args.args[1]['fixture']['independent_readback']
        assert json.loads((tmp_path / 'desktop.reply.json').read_text()) == {'observed': 'desktop'}
