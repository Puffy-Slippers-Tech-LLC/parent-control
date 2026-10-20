"""Collateral evidence refuses wrong roles, private scope and lost ownership."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest

import system_kiosk_scope as scope


@pytest.mark.parametrize('fault', [None, 'uid', 'role', 'shell'])
def test_both_ordinary_controls_require_prepared_identity(tmp_path, monkeypatch, fault):
    baseline = tmp_path / 'baseline.json'
    accounts = {name: SimpleNamespace(pw_name=name, pw_uid=1001 + index, pw_shell='/bin/bash')
                for index, name in enumerate(scope.ORDINARY_ACCOUNTS.values())}
    declared = {name: {'uid': accounts[name].pw_uid, 'role': role}
                for role, name in scope.ORDINARY_ACCOUNTS.items()}
    standard = scope.ORDINARY_ACCOUNTS['standard']
    if fault in ('uid', 'role'):
        declared[standard][fault] = 999 if fault == 'uid' else 'administrator'
    if fault == 'shell':
        accounts[standard].pw_shell = '/usr/sbin/nologin'
    baseline.write_text(json.dumps({'accounts': declared}))
    monkeypatch.setattr(scope.guest, 'BASELINE', baseline)
    monkeypatch.setattr(scope.pwd, 'getpwnam', accounts.__getitem__)
    if fault:
        with pytest.raises(scope.guest.GuestError, match='baseline-role:standard'):
            scope.ordinary_accounts()
    else:
        assert list(scope.ordinary_accounts()) == ['administrator', 'standard']


@pytest.mark.parametrize('fault', [None, 'failed-start', 'replaced', 'preexisting'])
def test_manager_cleanup_requires_its_new_invocation(monkeypatch, tmp_path, fault):
    old = dict(ActiveState='inactive', InvocationID='', MainPID='0')
    owned = dict(ActiveState='active', InvocationID='a' * 32, MainPID='4321')
    if fault == 'preexisting':
        old = owned
    current = dict(owned, InvocationID='b' * 32) if fault == 'replaced' else owned
    state = Mock(side_effect=[old, owned, current, old])
    monkeypatch.setattr(scope, 'manager', state)
    run = Mock()
    if fault == 'failed-start':
        run.side_effect = [RuntimeError('startup'), '']
    monkeypatch.setattr(scope.guest, 'run', run)
    monkeypatch.setattr(scope, 'PROC', tmp_path)
    if fault:
        expected = RuntimeError if fault == 'failed-start' else scope.guest.GuestError
        with pytest.raises(expected):
            with scope.owned_manager(SimpleNamespace(pw_uid=1001)):
                pass
    else:
        with scope.owned_manager(SimpleNamespace(pw_uid=1001)) as process:
            assert process == tmp_path / '4321'
    stopped = [call.args[0] for call in run.call_args_list if call.args[0][1] == 'stop']
    assert stopped == ([] if fault in ('preexisting', 'replaced') else
                       [['systemctl', 'stop', 'user@1001.service']])


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('fault', [None, 'unit-path', 'drop-in', 'nnp', 'filter', 'compositor',
                                 'bus', 'mask', 'missing-mask'])
def test_effective_unit_scope_rejects_collateral_changes(tmp_path, monkeypatch, backend, fault):
    monkeypatch.setattr(scope, 'PAYLOAD', tmp_path)
    units = tmp_path / 'user-units'
    units.mkdir()
    for name in scope.MASKS:
        (units / name).symlink_to('/dev/null')
    if fault == 'missing-mask':
        (units / scope.MASKS[-1]).unlink()
    monkeypatch.setattr(scope, 'user_command', lambda *args: (
        str(tmp_path) if fault == 'unit-path' else '/usr/lib/systemd/user').encode())

    def properties(account, service, names):
        executable = '/usr/bin/dbus-daemon' if backend == 'apparmor' else '/usr/bin/dbus-broker-launch'
        values = dict(LoadState='loaded', FragmentPath='/usr/lib/systemd/user/' + service,
            DropInPaths='/usr/lib/systemd/user/service.d/vendor.conf', Environment='',
            ExecStart='{ path=' + executable + ' ; argv[]=' + executable + ' --scope user ; }',
            NoNewPrivileges='yes', LockPersonality='yes', MemoryDenyWriteExecute='yes',
            SystemCallFilter='read write', SystemCallArchitectures='native')
        if fault == 'drop-in':
            values['DropInPaths'] = str(tmp_path / 'user-units/override.conf')
        if fault == 'nnp':
            values['NoNewPrivileges'] = 'no'
        if fault == 'filter':
            values['SystemCallFilter'] = '~'
        if fault == 'compositor' and service == scope.SERVICES[-1]:
            values['Environment'] = 'GIO_USE_VFS=local'
        if fault == 'bus' and service == 'dbus.service':
            values['ExecStart'] = '{ path=/usr/libexec/oh-no-parent-control-kiosk-dbus ; }'
        if fault == 'mask' and service in scope.MASKS:
            values['LoadState'], values['FragmentPath'] = 'masked', '/dev/null'
        return {name: values[name] for name in names}

    monkeypatch.setattr(scope, 'properties', properties)
    # Fedora has no private Snap masks in this scope.
    if fault in ('mask', 'missing-mask') and backend == 'selinux':
        scope.verify_units(None, backend)
    elif fault:
        with pytest.raises(scope.guest.GuestError, match='kiosk-collateral:'):
            scope.verify_units(None, backend)
    else:
        scope.verify_units(None, backend)


@pytest.mark.parametrize('fault', [None, 'vendor-option', 'manager-fallback'])
def test_vendor_callback_oracle_checks_original_bytes(tmp_path, monkeypatch, fault):
    prefix, block, credentials, guard = 'prefix\n', 'final\n', 'fallback\n', 'guard\n'
    source = 'session optional pam_gnome_keyring.so auto_start\n'
    states = {}
    for service in ('gdm-password', 'systemd-user'):
        actual = (credentials if service == 'systemd-user' else '') + prefix + guard + source + block
        if fault == 'vendor-option':
            actual = actual.replace('auto_start', 'changed')
        if fault == 'manager-fallback' and service == 'systemd-user':
            actual = actual.removeprefix(credentials)
        (tmp_path / service).write_text(actual)
        states[service] = dict(before=source, vendor=None)
    monkeypatch.setattr(scope.runpy, 'run_path', lambda path: dict(
        state=lambda: {'pam': states}, verify_pam=lambda state: None, PAM_LOCAL=tmp_path,
        MANAGER_CREDENTIALS=credentials, PREFIX=prefix, BLOCK=block, KEYRING_GUARD=guard))
    if fault:
        with pytest.raises(scope.guest.GuestError, match='kiosk-collateral:'):
            scope.verify_vendor_pam(Mock())
    else:
        record = Mock()
        scope.verify_vendor_pam(record)
        assert record.call_count == 2


def test_guard_refuses_before_any_guest_action(monkeypatch):
    monkeypatch.setattr(scope.guest, 'guard', Mock(side_effect=scope.guest.GuestError('identity')))
    diagnostics, accounts, pam = Mock(), Mock(), Mock()
    monkeypatch.setattr(scope.guest, 'enable_diagnostics', diagnostics)
    monkeypatch.setattr(scope, 'ordinary_accounts', accounts)
    monkeypatch.setattr(scope, 'verify_vendor_pam', pam)
    with pytest.raises(scope.guest.GuestError, match='identity'):
        scope.verify(Mock())
    for action in (diagnostics, accounts, pam):
        action.assert_not_called()


def test_namespace_refusal_prevents_ordinary_manager_actions(tmp_path, monkeypatch):
    (tmp_path / 'config.json').write_text('{"backend":"apparmor"}')
    monkeypatch.setattr(scope, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(scope.guest, 'guard', Mock())
    monkeypatch.setattr(scope.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(scope, 'ordinary_accounts', lambda: {'standard': object()})
    monkeypatch.setattr(scope, 'verify_vendor_pam', Mock())
    monkeypatch.setattr(scope, 'verify_namespace_guard', Mock(
        side_effect=scope.guest.GuestError('namespace-callback-refused')))
    owned = Mock()
    monkeypatch.setattr(scope, 'owned_manager', owned)
    with pytest.raises(scope.guest.GuestError, match='namespace-callback-refused'):
        scope.verify(Mock())
    owned.assert_not_called()


@pytest.mark.parametrize('backend,domain', [('apparmor', 'unconfined_t'),
    ('selinux', 'unconfined_t'), ('selinux', 'unconfined_dbusd_t')])
@pytest.mark.parametrize('fault', [None, 'uid', 'label', 'malformed-label', 'generation', 'inode'])
def test_ordinary_process_requires_measured_domain_and_global_executables(
        tmp_path, monkeypatch, backend, domain, fault):
    process = tmp_path / 'process'
    attribute = process / ('attr/apparmor/current' if backend == 'apparmor' else 'attr/current')
    attribute.parent.mkdir(parents=True)
    label = 'unconfined' if backend == 'apparmor' else 'unconfined_u:unconfined_r:' + domain + ':s0'
    if fault == 'label':
        label = 'onpc-kiosk-manager (enforce)' if backend == 'apparmor' else 'system_u:system_r:onpc_kiosk_manager_t:s0'
    if fault == 'malformed-label':
        label = 'unexpected'
    attribute.write_text(label)
    monkeypatch.setattr(scope, 'PAYLOAD', Path('/confinement'))
    generation = process / 'root/confinement/generation'
    generation.parent.mkdir(parents=True)
    generation.write_text('a' * 64 + '\n' if fault == 'generation' else 'unconfined\n')
    uid = '1002' if fault == 'uid' else '1001'
    monkeypatch.setattr(scope, 'process_identity', lambda path: ('start', 1, (uid,) * 4))
    originals = {}
    for name in ('python3', 'gjs', 'wireplumber'):
        visible = process / 'root/usr/bin' / name
        visible.parent.mkdir(parents=True, exist_ok=True)
        visible.write_text(name)
        info = visible.stat()
        originals['/usr/bin/' + name] = SimpleNamespace(stat=lambda info=info:
            SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino + (fault == 'inode')))
    monkeypatch.setattr(scope, 'Path', originals.__getitem__)
    if fault:
        with pytest.raises(scope.guest.GuestError, match='kiosk-collateral:'):
            scope.ordinary_process(process, SimpleNamespace(pw_uid=1001), backend, domain=domain)
    else:
        scope.ordinary_process(process, SimpleNamespace(pw_uid=1001), backend, domain=domain)


@pytest.fixture
def retained(tmp_path, monkeypatch):
    """Real append-only files; explicit account/lifecycle/observer boundaries."""
    import system_native_update as checkpoints
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    monkeypatch.setattr(checkpoints, 'private', lambda: private)
    # Production metadata validation has its own native-update controls. Here
    # records are owned by pytest rather than root; publication is the real API.
    monkeypatch.setattr(checkpoints, 'read_private', lambda path: json.loads(path.read_text()))
    payload = tmp_path / 'payload'
    payload.mkdir()
    (payload / 'config.json').write_text('{"backend":"apparmor"}')
    proc = tmp_path / 'proc'
    boot = proc / 'sys/kernel/random/boot_id'
    boot.parent.mkdir(parents=True)
    boot.write_text('original-boot')
    monkeypatch.setattr(scope, 'PAYLOAD', payload)
    monkeypatch.setattr(scope, 'PROC', proc)
    account = SimpleNamespace(pw_name='oh-no-parent-control', pw_uid=1001)
    monkeypatch.setattr(scope.pwd, 'getpwnam', lambda name: account)
    marker = {key: key + '-original' for key in ('run', 'machine_id', 'domain_uuid',
        'package_sha256', 'preparation_sha256', 'baseline_sha256', 'selected_inputs_sha256')}
    monkeypatch.setattr(scope.guest, 'guard', lambda: dict(marker))
    inactive = dict(ActiveState='inactive', InvocationID='', MainPID='0')
    active = dict(ActiveState='active', InvocationID='a' * 32, MainPID='4321')
    state = SimpleNamespace(unit=dict(inactive), login={'Linger': 'no', 'Sessions': ''},
        boundary={'pid': 4321, 'identity': ['start', 1, ['1001'] * 4],
                  'namespace': 'mnt:[42]', 'generation': 'original-M/V'},
        view={'material': 'original-M', 'view': 'original-V', 'sources': {'/usr/bin/a': [1, 42]}},
        commands=[], fail=None, boot=boot, marker=marker, private=private)
    monkeypatch.setattr(scope, 'manager', lambda unit: dict(state.unit))
    monkeypatch.setattr(scope, 'login_state', lambda account: dict(state.login))

    def observation(account, backend):
        scope.guest.require(state.unit['ActiveState'] == 'active', 'retained-manager:not-active')
        return json.loads(json.dumps(dict(unit=state.unit, boundary=state.boundary, view=state.view)))

    monkeypatch.setattr(scope, 'retained_observation', observation)
    owner = scope.RetainedManager('b' * 32)

    def run(argv, *, timeout):
        state.commands.append(argv)
        if argv[0:2] == ['systemctl', 'start']:
            assert owner.path('starting').exists() and timeout == 75
            state.unit = dict(active)
        elif argv[0:2] == ['loginctl', 'enable-linger']:
            assert owner.path('retention').exists() and timeout == 30
            state.login['Linger'] = 'yes'
        elif argv[0:2] == ['loginctl', 'disable-linger']:
            assert owner.path('cleanup').exists() and timeout == 30
            state.login['Linger'] = 'no'
        elif argv[0:2] == ['systemctl', 'stop']:
            assert owner.path('restored').exists() and timeout == 75
            state.unit = dict(inactive)
        else:
            raise AssertionError(argv)
        if state.fail == argv[1]:
            raise RuntimeError('uncertain-' + argv[1])
        return ''

    monkeypatch.setattr(scope.guest, 'run', run)
    state.owner = owner
    return state


def test_retained_manager_cross_call_lifetime_and_exact_restoration(retained):
    handle = retained.owner.prepare()
    assert retained.commands == []
    owner = scope.RetainedManager(handle['owner'], handle)
    ready = owner.start()
    original = owner.check()
    for session in ('first', 'second'):
        retained.login['Sessions'] = session
        assert scope.RetainedManager(ready['owner'], ready).check() == original
        retained.login['Sessions'] = ''
        assert owner.check() == original
    recovered = scope.RetainedManager(ready['owner'], ready)
    complete = recovered.cleanup()
    assert 'complete' in complete['checkpoints']
    commands = list(retained.commands)
    assert recovered.cleanup() == complete
    assert retained.commands == commands == [
        ['systemctl', 'start', 'user@1001.service'],
        ['loginctl', 'enable-linger', 'oh-no-parent-control'],
        ['loginctl', 'disable-linger', 'oh-no-parent-control'],
        ['systemctl', 'stop', 'user@1001.service']]


@pytest.mark.parametrize('fault', ['active', 'sessions', 'preexisting-after-prepare'])
def test_retained_manager_never_adopts_existing_manager(retained, fault):
    owner = retained.owner
    if fault == 'preexisting-after-prepare':
        owner.prepare()
    retained.unit.update(ActiveState='active', InvocationID='c' * 32, MainPID='9999')
    if fault == 'sessions':
        retained.unit.update(ActiveState='inactive', MainPID='0')
        retained.login['Sessions'] = 'foreign'
    with pytest.raises(scope.guest.GuestError, match='already-active|preexisting-manager'):
        owner.start() if fault == 'preexisting-after-prepare' else owner.prepare()
    assert not retained.commands


@pytest.mark.parametrize('fault', ['boot', 'binding', 'account', 'intent-inode', 'owned-inode',
    'owned-bytes', 'ready-inode', 'invocation', 'pid', 'starttime', 'namespace', 'material', 'source',
    'exited', 'session', 'linger'])
def test_retained_manager_changed_ownership_never_stops_or_restores(retained, fault):
    owner = retained.owner
    owner.prepare()
    owner.start()
    before = list(retained.commands)
    if fault == 'boot': retained.boot.write_text('other-boot')
    elif fault == 'binding': retained.marker['run'] = 'other'
    elif fault == 'account': owner.path('intent').write_text('{}')
    elif fault.endswith('-inode'):
        phase = fault.removesuffix('-inode')
        path = owner.path(phase)
        path.rename(path.with_suffix('.original'))
        path.write_bytes(path.with_suffix('.original').read_bytes())
    elif fault == 'owned-bytes': owner.path('owned').write_text('{}')
    elif fault == 'invocation': retained.unit['InvocationID'] = 'c' * 32
    elif fault == 'pid': retained.unit['MainPID'] = '9999'
    elif fault == 'starttime': retained.boundary['identity'][0] = 'new-start'
    elif fault == 'namespace': retained.boundary['namespace'] = 'mnt:[999]'
    elif fault == 'material': retained.view['material'] = 'foreign-M'
    elif fault == 'source': retained.view['sources']['/usr/bin/a'] = [1, 999]
    elif fault == 'exited': retained.unit.update(ActiveState='failed', MainPID='0')
    elif fault == 'session': retained.login['Sessions'] = 'still-public'
    elif fault == 'linger': retained.login['Linger'] = 'no'
    if fault == 'session':
        owner.check()  # a live public session is allowed during a visit
    else:
        with pytest.raises(scope.guest.GuestError):
            owner.check()
    # A session is not a manager change, but must still block destructive cleanup.
    if fault == 'linger':
        owner.cleanup()  # already restored; only the unchanged owned manager stops
        assert retained.commands[-1] == ['systemctl', 'stop', 'user@1001.service']
    else:
        with pytest.raises(scope.guest.GuestError):
            owner.cleanup()
        assert retained.commands == before


@pytest.mark.parametrize('failure', ['start', 'enable-linger', 'disable-linger', 'stop'])
def test_retained_manager_uncertain_operations_recover_without_replay(retained, failure):
    owner = retained.owner
    original_handle = owner.prepare()
    retained.fail = failure
    if failure in ('start', 'enable-linger'):
        with pytest.raises(RuntimeError, match='uncertain-' + failure):
            owner.start()
        with pytest.raises(scope.guest.GuestError, match='start-not-replayable'):
            scope.RetainedManager(owner.owner, original_handle).start()
    else:
        owner.start()
        with pytest.raises(RuntimeError, match='uncertain-' + failure):
            owner.cleanup()
    retained.fail = None
    recovered = scope.RetainedManager(owner.owner, original_handle)
    recovered.cleanup()
    recovered.cleanup()
    assert sum(command[1] == failure for command in retained.commands) == 1
    assert retained.unit['ActiveState'] == 'inactive'
    assert retained.login == {'Linger': 'no', 'Sessions': ''}


def test_retained_manager_interrupted_before_saved_identity_refuses_adoption(retained):
    owner = retained.owner
    handle = owner.prepare()
    owner.append('starting')
    retained.unit.update(ActiveState='active', InvocationID='a' * 32, MainPID='4321')
    with pytest.raises(scope.guest.GuestError, match='uncertain-start'):
        scope.RetainedManager(owner.owner, handle).cleanup()
    assert not retained.commands


def test_retained_manager_exit_is_never_restarted_or_signalled(retained):
    owner = retained.owner
    owner.prepare()
    owner.start()
    retained.unit.update(ActiveState='inactive', InvocationID='', MainPID='0')
    with pytest.raises(scope.guest.GuestError, match='not-active'):
        owner.check()
    owner.cleanup()
    assert sum(command[1] == 'start' for command in retained.commands) == 1
    assert not any(command[1] == 'stop' for command in retained.commands)
    assert retained.login == {'Linger': 'no', 'Sessions': ''}


def test_retained_manager_original_linger_is_preserved(retained):
    retained.login['Linger'] = 'yes'
    owner = retained.owner
    owner.prepare()
    owner.start()
    owner.cleanup()
    assert retained.login['Linger'] == 'yes'
    assert all(command[0] != 'loginctl' for command in retained.commands)


def test_retained_manager_failed_start_does_not_adopt_foreign_retention(retained):
    owner = retained.owner
    owner.prepare()
    retained.fail = 'start'
    with pytest.raises(RuntimeError, match='uncertain-start'):
        owner.start()
    retained.login['Linger'] = 'yes'
    with pytest.raises(scope.guest.GuestError, match='unowned-retention'):
        owner.cleanup()
    assert retained.commands == [['systemctl', 'start', 'user@1001.service']]


def test_retained_manager_preserves_start_failure_when_identity_observation_fails(retained, monkeypatch):
    owner = retained.owner
    owner.prepare()
    retained.fail = 'start'
    monkeypatch.setattr(scope, 'retained_observation', Mock(side_effect=RuntimeError('later-proof')))
    with pytest.raises(RuntimeError, match='uncertain-start') as caught:
        owner.start()
    assert caught.value.__notes__ == ['retained-manager:startup-observation-failed:RuntimeError']
    with pytest.raises(scope.guest.GuestError, match='uncertain-start'):
        owner.cleanup()
    assert retained.commands == [['systemctl', 'start', 'user@1001.service']]


def test_retained_manager_rechecks_identity_after_restoration_before_stop(retained, monkeypatch):
    owner = retained.owner
    owner.prepare()
    owner.start()
    run = scope.guest.run
    def replace(argv, **options):
        result = run(argv, **options)
        if argv[1] == 'disable-linger': retained.unit['InvocationID'] = 'c' * 32
        return result
    monkeypatch.setattr(scope.guest, 'run', replace)
    with pytest.raises(scope.guest.GuestError, match='identity-changed'):
        owner.cleanup()
    assert not any(command[1] == 'stop' for command in retained.commands)


def test_retained_manager_rechecks_checkpoint_after_live_observation_before_cleanup(retained, monkeypatch):
    owner = retained.owner
    owner.prepare()
    owner.start()
    observe = scope.retained_observation
    def replace(*args):
        result = observe(*args)
        path = owner.path('ready')
        path.rename(path.with_suffix('.original'))
        path.write_bytes(path.with_suffix('.original').read_bytes())
        return result
    monkeypatch.setattr(scope, 'retained_observation', replace)
    before = list(retained.commands)
    with pytest.raises(scope.guest.GuestError, match='checkpoint-changed'):
        owner.cleanup()
    assert retained.commands == before


@pytest.mark.parametrize('fault', [None, 'unit', 'boundary', 'view'])
def test_retained_observation_composes_independent_live_view_proof(tmp_path, monkeypatch, fault):
    import system_kiosk_confinement as confinement
    unit = dict(ActiveState='active', InvocationID='a' * 32, MainPID='4321')
    boundary = {'pid': 4321, 'identity': ['original-start'], 'namespace': 'mnt:[42]'}
    monkeypatch.setattr(scope, 'manager', Mock(side_effect=[unit,
        dict(unit, InvocationID='b' * 32) if fault == 'unit' else unit]))
    observer = Mock(side_effect=[boundary, dict(boundary, namespace='other') if fault == 'boundary' else boundary])
    monkeypatch.setattr(confinement, 'manager_boundary', observer)
    monkeypatch.setattr(confinement, 'PROC', tmp_path)
    view = Mock(return_value={'material': 'M', 'view': 'V', 'sources': {'a': [1, 42]},
                             'objects': {'a': [1, 42, 0o100444, 0, 0, 10, 20, 30, 1]}})
    if fault == 'view': view.side_effect = scope.guest.GuestError('independent-mounted-source-refusal')
    monkeypatch.setattr(confinement, 'bootstrap_view', view)
    account = SimpleNamespace(pw_uid=1001)
    if fault:
        with pytest.raises(scope.guest.GuestError):
            scope.retained_observation(account, 'apparmor')
    else:
        actual = scope.retained_observation(account, 'apparmor')
        assert actual == {'unit': unit, 'boundary': boundary, 'view': view.return_value}
        assert observer.call_count == 2
        assert all(call.kwargs == {'retained_view': True} for call in observer.call_args_list)
    view.assert_called_once_with(tmp_path / '4321')


@pytest.mark.parametrize('change,same', [('unlink', True), ('directory-child', True),
    ('inode', False), ('mode', False), ('file-bytes-metadata', False), ('mount', False)])
def test_retained_observer_keeps_source_identity_without_ambient_link_metadata(
        monkeypatch, change, same):
    import system_kiosk_confinement as confinement
    monkeypatch.setattr(scope, 'manager', lambda unit: dict(
        ActiveState='active', InvocationID='a' * 32, MainPID='4321'))
    monkeypatch.setattr(confinement, 'manager_boundary', lambda *args, **kwargs: {'pid': 4321})
    view = {'objects': {'file': [1, 42, 0o100444, 0, 0, 10, 20, 30, 1],
                        'directory': [1, 43, 0o40755, 0, 0, 10, 20, 30, 2]},
            'sources': {'native': [1, 50]}, 'mounts': {'/usr': {'id': 42, 'options': ['ro']}}}
    monkeypatch.setattr(confinement, 'bootstrap_view', lambda *args:
        json.loads(json.dumps(view)))
    account = SimpleNamespace(pw_uid=1001)
    before = scope.retained_observation(account, 'apparmor')
    if change == 'unlink': view['objects']['file'][7:] = [999, 0]
    elif change == 'directory-child': view['objects']['directory'][5:] = [20, 999, 999, 3]
    elif change == 'inode': view['objects']['file'][1] = 999
    elif change == 'mode': view['objects']['file'][2] = 0o100666
    elif change == 'file-bytes-metadata': view['objects']['file'][6] = 999
    elif change == 'mount': view['mounts']['/usr']['id'] = 999
    assert (scope.retained_observation(account, 'apparmor') == before) is same


@pytest.mark.parametrize('fault', [None, 'enter', 'exit', 'interrupt', 'replacement', 'lost-start-reply',
                                 'lost-cleanup-reply'])
def test_actual_retained_history_composes_guest_owner_and_guarded_public_visits(retained, monkeypatch, fault):
    from contextlib import nullcontext
    import kiosk_entry
    import system_runner as runner
    steps = []
    monkeypatch.setattr(runner.uuid, 'uuid4', lambda: SimpleNamespace(hex='b' * 32))
    monkeypatch.setattr(kiosk_entry.time, 'monotonic', lambda: 10)
    monkeypatch.setattr(kiosk_entry.watch_activity, 'operation', lambda label: nullcontext())

    def observer(transport):
        ui = SimpleNamespace(boot_guard='', boot_proof='a' * 64)
        def observe(operation):
            steps.append(operation)
            if operation == 'kiosk-request-cancel':
                if fault == 'exit': raise RuntimeError('uncertain-exit')
                retained.login['Sessions'] = ''
            return {'operation': operation, 'outcome': 'passed',
                    'interface': 'ApplicationUI+external-provider'}
        ui.observe = observe
        return ui

    monkeypatch.setattr(kiosk_entry, 'UiObservations', observer)
    def enter(*args):
        retained.login['Sessions'] = 'public-session'
        if fault == 'enter': raise RuntimeError('uncertain-enter')
    lease = SimpleNamespace(state={'run': 'a' * 32}, guard=Mock(), source=SimpleNamespace(
        domain=SimpleNamespace(sendKey=Mock(side_effect=enter)),
        api=SimpleNamespace(VIR_KEYCODE_SET_LINUX=0)))
    def call(argv, *, timeout):
        if argv[5].endswith('/system_kiosk_confinement.py'):
            assert argv[6] == 'census'
            return b'{"independently_doubled_census":true}'
        assert argv[5].endswith('/system_kiosk_scope.py')
        result = scope.retained_command(argv[6], argv[7],
            json.loads(argv[8]) if len(argv) == 9 else None)
        if fault == 'lost-' + argv[6] + '-reply':
            raise RuntimeError('lost-reply')
        return json.dumps(result).encode()
    vm = SimpleNamespace(call=call)
    receipt = {}
    def checkpoint(value):
        (retained.private / 'host-receipt.json').write_text(json.dumps(value))
    def history():
        with runner.owned_retained_manager(vm, lease, receipt=receipt, checkpoint=checkpoint) as lifetime:
            with lifetime.station():
                assert retained.login['Sessions'] == 'public-session'
                if fault == 'interrupt': raise KeyboardInterrupt('caller-interrupted')
            assert retained.unit['ActiveState'] == 'active'
            if fault == 'replacement': retained.unit['InvocationID'] = 'c' * 32
            with lifetime.station(): pass
    if fault:
        with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else RuntimeError):
            history()
    else:
        history()
        assert len(receipt['entries']) == 2
        assert receipt['original']['view'] == retained.view
    if fault in ('enter', 'exit', 'replacement', 'lost-cleanup-reply'):
        assert not receipt.get('cleanup_complete')
        assert receipt['cleanup_failures']
        if fault != 'lost-cleanup-reply':
            assert not any(command[1] == 'stop' for command in retained.commands)
        # Recovery follows an independently completed public exit/restoration;
        # it submits no Enter or Cancel input, and uses the original handle.
        retained.login['Sessions'] = ''
        retained.unit['InvocationID'] = 'a' * 32
        fault = 'recovered'
        recovered = json.loads((retained.private / 'host-receipt.json').read_text())
        runner.RetainedManagerHistory(vm, lease, receipt=recovered, checkpoint=checkpoint).cleanup()
        receipt.update(recovered)
    assert receipt['cleanup_complete']
    assert retained.unit['ActiveState'] == 'inactive'
    assert retained.login == {'Linger': 'no', 'Sessions': ''}
    expected_entries = len(receipt['entries'])
    assert lease.source.domain.sendKey.call_count == expected_entries
    assert steps.count('kiosk-request-cancel') == sum(
        entry.get('station_confirmed', False) for entry in receipt['entries'])


@pytest.mark.parametrize('users,values,expected', [
    ('', '', {'Linger': 'no', 'Sessions': ''}),
    ('1001 oh-no-parent-control', 'Linger=yes\nSessions=', {'Linger': 'yes', 'Sessions': ''}),
    ('1001 oh-no-parent-control', 'Linger=no\nSessions=c1 c2', {'Linger': 'no', 'Sessions': 'c1 c2'}),
    ('1001 oh-no-parent-control', 'Linger=maybe\nSessions=', None),
])
def test_retained_login_observer_uses_bounded_public_queries(monkeypatch, users, values, expected):
    run = Mock(side_effect=[users, values])
    monkeypatch.setattr(scope.guest, 'run', run)
    if expected is None:
        with pytest.raises(scope.guest.GuestError, match='login-state'):
            scope.login_state(SimpleNamespace(pw_uid=1001))
    else:
        assert scope.login_state(SimpleNamespace(pw_uid=1001)) == expected
    assert all(call.kwargs == {'timeout': 15} for call in run.call_args_list)
    assert run.call_args_list[0].args[0] == ['loginctl', 'list-users', '--no-legend', '--no-pager']
    if users:
        # loginctl accepts one property name per option (unlike systemctl's
        # comma-list extension); selected empty Sessions must remain observable.
        assert run.call_args_list[1].args[0] == ['loginctl', 'show-user', '1001',
                                              '--property=Linger', '--property=Sessions']
