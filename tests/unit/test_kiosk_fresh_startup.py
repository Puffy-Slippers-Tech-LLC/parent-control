"""Complete native fresh-manager transaction in private kernel namespaces.

The production child, authorities, binder and publisher consume real private
files and mounts. Only account/PAM/MAC policy and the root-name mapping are
fixture boundaries. No installed path, service or host mount is changed.
"""

import hashlib
import json
import os
import subprocess

import pytest

from tools import test_storage


from tests.support.kiosk_fresh_startup import (
    PAYLOAD, _put, assert_helper_private_creation, fresh_scene,
)


@pytest.mark.parametrize('mode', [
    'full-private-0777', 'full-private-new-runtime-0777',
    'private-marker-chown-cut', 'private-marker-chmod-cut',
    'healthy', 'ambient-narrow', 'helper-exit', 'helper-result-exit', 'helper-timeout', 'helper-order',
    'measurement-config-refusal', 'measurement-policy-refusal', 'measurement-helper-refusal',
    'measurement-attestation-refusal', 'measurement-production-healthy',
    'helper-identity', 'result-malformed', 'ticket-parent', 'ticket-malformed', 'copy-replacement', 'source-replacement',
    'required-drift', 'measurement-required-drift', 'bind-required-drift', 'post-attach-required-drift', 'publication-cut',
    'publication-cleanup-cut',
    'publication-partial', 'expired', 'environment-failure', 'mac-failure', 'mac-cleanup-cut', 'mac-readback', 'mac-deadline',
    'concurrent-writers', 'selection-lock-replaced', 'selection-lease-replaced',
    'writer-measurement-admission', 'writer-measurement-configuration', 'writer-measurement-loader',
    'writer-bind-admission', 'writer-bind-configuration', 'writer-bind-loader',
    'writer-final-admission', 'writer-final-configuration', 'writer-final-loader',
    'ready-lock-replaced', 'ready-lease-replaced', 'premac-lock-replaced', 'premac-lease-replaced',
    'material-fsync-cut', 'view-fsync-cut', 'pins-fsync-cut', 'pending-fsync-cut',
    'generation-rename-cut', 'generation-durability-cut', 'ready-durability-cut',
    'bind-cut', 'ambient-bind-undo-cleanup-cut', 'clone-cut', 'readonly-cut', 'attachment-cut', 'staging-detach-cut',
    'generation-three', 'generation-four',
    'ready-material-replaced', 'ready-view-replaced', 'ready-pins-replaced', 'ready-account-drift',
])
def test_complete_native_fresh_manager_transaction(fresh_scene, mode):
    directory, binary = fresh_scene
    native_private = mode.startswith('full-private-')
    if native_private:
        if mode == 'full-private-new-runtime-0777':
            (directory / 'runtime').rmdir()
        mode = 'healthy'
    (directory / 'mode').write_text(mode)
    borrowed = {name: (directory / name).stat() for name in ('lock', 'lease')}
    retained_generations = {}
    prior_count = 3 if mode == 'generation-three' else 4 if mode == 'generation-four' else 0
    if (mode.startswith('writer-') or mode == 'concurrent-writers' or
            mode in ('measurement-required-drift', 'bind-required-drift', 'post-attach-required-drift') or
            mode.endswith(('-lock-replaced', '-lease-replaced'))):
        prior_count = 1
    if prior_count:
        for index in range(prior_count):
            generation = directory / 'runtime' / f'{index:064x}'
            generation.mkdir(mode=0o700)
            _put(generation / 'foreign-record', b'previous-generation', 0o600)
            retained_generations[generation.name] = (generation.stat(), (generation / 'foreign-record').stat())
    completed = subprocess.run([str(binary), mode, str(directory)],
                               capture_output=True, text=True, timeout=20,
                               env=dict(os.environ, ONPC_FIXTURE_NATIVE_UMASK='0777') if native_private else None,
                               pass_fds=test_storage.scratch_descriptors())
    helper_error = directory / 'helper-error'
    helper_started = directory / 'helper-started'
    helper_result = directory / 'helper-result.json'
    result_summary = 'not-produced'
    if helper_result.exists():
        record = json.loads(helper_result.read_text())
        plan = record.get('plan', {})
        result_summary = json.dumps(dict(ticket=record.get('ticket'), native=plan.get('native'),
            sources={path: {key: value for key, value in source.items()
                            if key in ('kind', 'path', 'name', 'source_class', 'required', 'assertion', 'copy_identity')}
                     for path, source in plan.get('sources', {}).items()}), sort_keys=True)[:6000]
    assert completed.returncode == 0, (
        f'returncode={completed.returncode}\nstdout:{completed.stdout}\nstderr:{completed.stderr}\n'
        'helper-error:' + (helper_error.read_text() if helper_error.exists() else '') + '\n'
        'helper-started:' + (helper_started.read_text() if helper_started.exists() else 'helper-not-entered') + '\n'
        'helper-result:' + result_summary)
    assert completed.stdout == ('retained\n' if mode in ('ticket-parent', 'ticket-malformed') else 'verified\n')
    if native_private:
        assert_helper_private_creation(directory, 'manager')
    for name, original in borrowed.items():
        displaced = directory / ('original-' + name)
        selected = displaced if displaced.exists() else directory / name
        assert selected.read_bytes() == b'owned-lock'
        assert (selected.stat().st_dev, selected.stat().st_ino) == (original.st_dev, original.st_ino)
        if displaced.exists():
            # Replacement names are foreign to the production cleanup owner.
            assert (directory / name).read_bytes() == b'foreign-lock'
            assert (directory / name).stat().st_ino != original.st_ino
    if mode != 'expired':
        started = json.loads(helper_started.read_text())
        assert started['pid'] > 0
        assert started['lock'] == borrowed['lock'].st_ino
        assert started['lease'] == borrowed['lease'].st_ino
        assert started['deadline'] > 0
    else:
        assert not helper_started.exists()
    for name, (root_identity, member_identity) in retained_generations.items():
        generation = directory / 'runtime' / name
        assert {p.name for p in generation.iterdir()} == {'foreign-record'}
        assert (generation / 'foreign-record').read_bytes() == b'previous-generation'
        assert (generation.stat().st_dev, generation.stat().st_ino) == (root_identity.st_dev, root_identity.st_ino)
        actual = (generation / 'foreign-record').stat()
        assert (actual.st_dev, actual.st_ino) == (member_identity.st_dev, member_identity.st_ino)
    generations = [path for path in (directory / 'runtime').iterdir()
                   if len(path.name) == 64 and path.name not in retained_generations]
    if mode in ('measurement-config-refusal', 'measurement-policy-refusal', 'measurement-helper-refusal',
                'measurement-attestation-refusal', 'measurement-production-healthy'):
        assert (directory / 'measurement-command').read_text() == mode
        if mode.endswith('-refusal'):
            reason = ('unexpected-preserved-executable' if mode == 'measurement-helper-refusal' else
                      'policy-snapshot-not-attested' if mode == 'measurement-attestation-refusal' else 'attestation-command-failed')
            assert completed.stderr.splitlines() == [
                f'onpc.pam kiosk native-view outcome=denied role=manager stage=measurement reason={reason} errno=-1']
            assert not helper_result.exists()
        if mode == 'measurement-helper-refusal':
            assert (directory / 'measurement-inventory').read_text() == 'real-preserved-inventory'
        if mode in ('measurement-config-refusal', 'measurement-policy-refusal'):
            assert (directory / 'measurement-attestation').read_text() == 'actual-policy-digest-refusal'
    if mode.startswith('writer-') or mode in ('healthy', 'measurement-production-healthy', 'ambient-narrow', 'environment-failure', 'mac-failure', 'mac-cleanup-cut', 'mac-readback', 'mac-deadline',
                'post-attach-required-drift', 'concurrent-writers', 'ready-lock-replaced', 'ready-lease-replaced',
                'premac-lock-replaced', 'premac-lease-replaced', 'ready-durability-cut', 'generation-three',
                'ready-material-replaced', 'ready-view-replaced', 'ready-pins-replaced', 'ready-account-drift'):
        assert len(generations) == 1
        names = {path.name for path in generations[0].iterdir()}
        expected_names = {'material.json', 'view', 'pins', 'runtime.json', 'ready', 'native-0', '0', '1', '2'}
        if mode in ('ready-material-replaced', 'ready-view-replaced', 'ready-pins-replaced'):
            name, original_dev, original_ino, foreign_dev, foreign_ino = (directory / 'record-identities').read_text().split()
            owned, foreign = directory / 'displaced-record', generations[0] / name
            assert owned.read_bytes() == foreign.read_bytes()
            assert (owned.stat().st_dev, owned.stat().st_ino) == (int(original_dev), int(original_ino))
            assert (foreign.stat().st_dev, foreign.stat().st_ino) == (int(foreign_dev), int(foreign_ino))
        assert names == expected_names
        assert (generations[0] / 'native-0').read_bytes() == b'\x7fELF/usr/bin/native'
        assert { (generations[0] / str(index)).read_bytes() for index in range(3)} == {
            (directory / 'host/usr/bin/script').read_bytes(),
            (directory / ('host' + PAYLOAD) / 'config.json').read_bytes(),
            (directory / ('host' + PAYLOAD) / 'onpc-kiosk.apparmor').read_bytes()}
        ready = (generations[0] / 'ready').read_bytes().split(b'\t')
        assert ready[:2] == [b'ONPC-KIOSK-READY', b'2']
        assert ready[3].decode() == generations[0].name
        assert ready[4].decode() == hashlib.sha256((generations[0] / 'pins').read_bytes()).hexdigest()
        assert list(map(int, ready[6:8])) == [generations[0].stat().st_dev, generations[0].stat().st_ino]
        assert b'ONPC-KIOSK-RECEIPT\t2\tV\t' in (generations[0] / 'view').read_bytes()
    elif mode in ('ticket-parent', 'ticket-malformed'):
        assert not generations
        scratch = [path for path in (directory / 'runtime').iterdir() if path.name.startswith('.runtime-')]
        assert len(scratch) == 1
        assert (scratch[0] / 'runtime.json').is_file()
        assert (scratch[0] / 'native-0').read_bytes() == b'\x7fELF/usr/bin/native'
        assert not (scratch[0] / 'ready').exists()
    else:
        assert not generations
        assert not any(path.name.startswith('.runtime-')
                       for path in (directory / 'runtime').iterdir())


@pytest.mark.parametrize('permissions', [0o000, 0o770, 0o2700])
def test_existing_runtime_metadata_is_never_normalized(fresh_scene, permissions):
    directory, binary = fresh_scene
    runtime = directory / 'runtime'
    runtime.chmod(permissions)
    original = runtime.stat()
    (directory / 'mode').write_text('private-runtime-existing-mode')
    try:
        completed = subprocess.run([str(binary), 'private-runtime-existing-mode', str(directory)],
                                   capture_output=True, text=True, timeout=20,
                                   pass_fds=test_storage.scratch_descriptors())
        actual = runtime.stat()
    finally:
        runtime.chmod(0o700)
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    assert completed.stdout == 'verified\n'
    assert (actual.st_dev, actual.st_ino, actual.st_mode, actual.st_uid, actual.st_gid, actual.st_ctime_ns) == (
        original.st_dev, original.st_ino, original.st_mode, original.st_uid, original.st_gid, original.st_ctime_ns)
    assert not (directory / 'helper-started').exists()


@pytest.mark.parametrize('cut', ['mount', 'identity'])
def test_new_runtime_refuses_substitution_before_initialization(fresh_scene, cut):
    directory, binary = fresh_scene
    (directory / 'runtime').rmdir()
    foreign = directory / 'foreign-runtime'
    foreign.mkdir()
    foreign.chmod(0o2770)
    _put(foreign / 'sentinel', b'foreign-runtime-state', 0o660)
    original = foreign.stat()
    original_member = (foreign / 'sentinel').stat()
    mode = f'native-private-runtime-{cut}-cut'
    (directory / 'mode').write_text(mode)
    completed = subprocess.run([str(binary), mode, str(directory)],
                               capture_output=True, text=True, timeout=20,
                               pass_fds=test_storage.scratch_descriptors())
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    assert completed.stdout == 'verified\n'
    selected = foreign if cut == 'mount' else directory / 'runtime'
    actual = selected.stat()
    actual_member = (selected / 'sentinel').stat()
    assert (actual.st_dev, actual.st_ino, actual.st_mode, actual.st_uid, actual.st_gid) == (
        original.st_dev, original.st_ino, original.st_mode, original.st_uid, original.st_gid)
    assert (actual_member.st_dev, actual_member.st_ino, actual_member.st_mode, actual_member.st_uid, actual_member.st_gid) == (
        original_member.st_dev, original_member.st_ino, original_member.st_mode, original_member.st_uid, original_member.st_gid)
    assert (selected / 'sentinel').read_bytes() == b'foreign-runtime-state'
    assert not (directory / 'helper-started').exists()


@pytest.mark.parametrize('mode', ['selinux-healthy', 'selinux-disabled', 'selinux-permissive',
                                'selinux-symbol', 'selinux-transition', 'selinux-readback',
                                'selinux-gate-healthy', 'selinux-gate-symbol',
                                'selinux-gate-transition', 'selinux-gate-readback'])
def test_native_fresh_selinux_security_transition(fresh_scene, mode):
    directory, binary = fresh_scene
    completed = subprocess.run([str(binary), mode, str(directory)],
                               capture_output=True, text=True, timeout=5,
                               pass_fds=test_storage.scratch_descriptors())
    assert completed.returncode == 0, (completed.returncode, completed.stdout, completed.stderr)
    assert completed.stdout == 'mac verified\n'


@pytest.mark.parametrize('mode', ['inherited', 'zero', 'get-before', 'set', 'ambient', 'get-after',
                                 'inheritable-drift', 'effective-drift', 'permitted-drift', 'expired'])
def test_native_admission_clears_only_inheritable_and_ambient_capabilities(fresh_scene, mode):
    directory, binary = fresh_scene
    completed = subprocess.run([str(binary), 'capabilities-' + mode, str(directory)],
                               capture_output=True, text=True, timeout=5,
                               pass_fds=test_storage.scratch_descriptors())
    assert completed.returncode == 0, (completed.returncode, completed.stdout, completed.stderr)
    assert completed.stdout == 'capabilities verified\n'
