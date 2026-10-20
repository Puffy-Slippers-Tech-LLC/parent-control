"""Bounded ordinary-account collateral checks for kiosk PAM and policy."""

from contextlib import contextmanager
import json
from pathlib import Path
import pwd
import re
import runpy
import shlex
import stat
import sys

import system_guest as guest
from system_kiosk_accounts import ORDINARY_ACCOUNTS
from system_kiosk_confinement import process_identity, user_command, verify_namespace_guard
from system_kiosk_platform import environment
from system_wellbeing_qualification import manager, valid_invocation


PAYLOAD = Path('/usr/share/oh-no-parent-control/confinement')
PROC = Path('/proc')
SERVICES = ('wireplumber.service', 'pipewire.service',
            'oh-no-parent-control-wellbeing.service', 'dbus.service',
            'org.gnome.Kiosk@wayland.service')
MASKS = ('snapd.session-agent.service', 'snapd.session-agent.socket',
         'snap.snapd-desktop-integration.snapd-desktop-integration.service',
         'snap.prompting-client.daemon.service',
         'snap.firmware-updater.firmware-notifier.service',
         'snap.firmware-updater.firmware-notifier.timer')


def ordinary_accounts():
    """Bind collateral controls to both unchanged prepared account roles."""
    baseline = json.loads(guest.BASELINE.read_bytes())
    result = {}
    for role, name in ORDINARY_ACCOUNTS.items():
        account = pwd.getpwnam(name)
        guest.require(baseline['accounts'].get(name) ==
                      {'uid': account.pw_uid, 'role': role} and
                      account.pw_uid > 0 and account.pw_shell == '/bin/bash',
                      'kiosk-collateral:baseline-role:' + role)
        result[role] = account
    return result


def verify_vendor_pam(record):
    integration = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement-integration')
    saved = integration['state']()
    guest.require(saved is not None, 'kiosk-collateral:pam-record-missing')
    integration['verify_pam'](saved)
    for service, state in saved['pam'].items():
        source = state['before'] if state['before'] is not None else state['vendor']
        actual = (integration['PAM_LOCAL'] / service).read_text()
        if service == 'systemd-user':
            guest.require(actual.startswith(integration['MANAGER_CREDENTIALS']),
                          'kiosk-collateral:manager-fallback')
            actual = actual.removeprefix(integration['MANAGER_CREDENTIALS'])
        guest.require(actual.startswith(integration['PREFIX']) and
                      actual.endswith(integration['BLOCK']), 'kiosk-collateral:pam-boundaries')
        original = actual.removeprefix(integration['PREFIX']).removesuffix(integration['BLOCK'])
        original = original.replace(integration['KEYRING_GUARD'], '')
        guest.require(original == source.rstrip('\n') + '\n',
                      'kiosk-collateral:vendor-callbacks-changed')
        record('onpc.kiosk.collateral.pam.' + service + '.vendor-callbacks-preserved', True)


@contextmanager
def owned_manager(account):
    """Stop only the invocation created here, including a failed startup."""
    unit = f'user@{account.pw_uid}.service'
    before = manager(unit)
    guest.require(before['ActiveState'] == 'inactive', 'kiosk-collateral:manager-already-active')
    identity = None
    try:
        try:
            guest.run(['systemctl', 'start', unit], timeout=75)
        finally:
            current = manager(unit)
            if (valid_invocation(current['InvocationID']) and
                    current['InvocationID'] != before['InvocationID']):
                identity = current
        guest.require(identity is not None and identity['ActiveState'] == 'active' and
                      identity['MainPID'].isdecimal() and int(identity['MainPID']) > 1,
                      'kiosk-collateral:manager-startup')
        yield PROC / identity['MainPID']
    finally:
        if identity is not None:
            guest.require(manager(unit)['InvocationID'] == identity['InvocationID'],
                          'kiosk-collateral:manager-replaced')
            guest.run(['systemctl', 'stop', unit], timeout=75)
            guest.require(manager(unit)['ActiveState'] == 'inactive',
                          'kiosk-collateral:manager-not-stopped')


def retained_observation(account, backend):
    """Observe the original mounted sources, not merely equal marker bytes."""
    import system_kiosk_confinement as confinement
    unit = f'user@{account.pw_uid}.service'
    before = manager(unit)
    guest.require(before['ActiveState'] == 'active' and
                  valid_invocation(before['InvocationID']), 'retained-manager:not-active')
    boundary = confinement.manager_boundary(account, unit, backend, retained_view=True)
    view = confinement.bootstrap_view(confinement.PROC / str(boundary['pid']))
    # V, rather than a caller's mutation list, identifies optional ambient
    # leaves. Their retained inode may intentionally lose/recover trust between
    # visits; the gate must then omit/mask it. Keep the original inode and type
    # (and file content metadata) without freezing mode/owner. Consumers still
    # independently check the actual trust change and invocation omission/mask.
    # Required ownership/mode, complete source proofs, receipts and mounts stay
    # exact. Unlink ctime/nlink and directory-child timestamps do not replace a
    # dentry, matching the existing retained observation contract.
    ambient = set(view['ambient_paths'])
    view['objects'] = {
        path: (info[:2] + [stat.S_IFMT(info[2])] +
               (info[5:7] if stat.S_ISREG(info[2]) else [])) if path in ambient
        else info[:7] if stat.S_ISREG(info[2]) else info[:5]
        for path, info in view['objects'].items()}
    # A vendor privilege mutation followed by exact restoration necessarily
    # changes ctime. Only that timestamp is excluded from lifetime equality;
    # the independent observer still checks current trust and bytes, while
    # original inode, privilege/content metadata and link count remain exact.
    view['sources'] = {
        path: dict(source, identity=source['identity'][:7] + [None] + source['identity'][8:])
        if isinstance(source, dict) and source.get('class') == 'vendor' and 'identity' in source
        else source for path, source in view['sources'].items()}
    guest.require(manager(unit) == before and
                  confinement.manager_boundary(account, unit, backend, retained_view=True) == boundary,
                  'retained-manager:observation-changed')
    return json.loads(json.dumps(dict(unit=before, boundary=boundary, view=view)))


def login_state(account):
    """An absent logind user has neither sessions nor lingering enabled."""
    users = guest.run(['loginctl', 'list-users', '--no-legend', '--no-pager'], timeout=15)
    if not any(line.split()[0] == str(account.pw_uid) for line in users.splitlines() if line.split()):
        return {'Linger': 'no', 'Sessions': ''}
    values = dict(line.split('=', 1) for line in guest.run(
        ['loginctl', 'show-user', str(account.pw_uid), '--property=Linger', '--property=Sessions'],
        timeout=15).splitlines())
    guest.require(set(values) == {'Linger', 'Sessions'} and values['Linger'] in ('yes', 'no'),
                  'retained-manager:login-state')
    return values


class RetainedManager:
    """Append-only, attempt-bound owner spanning separate guest calls.

    prepare's handle must be retained before start is submitted. A lost start
    reply is recovered with that handle, never by submitting start again.
    Records remain evidence in the existing attempt's private allocation.
    """
    phases = ('intent', 'starting', 'owned', 'retention', 'ready', 'cleanup', 'restored', 'stopped', 'complete')

    def __init__(self, owner, handle=None):
        guest.require(isinstance(owner, str) and re.fullmatch(r'[a-f0-9]{32}', owner),
                      'retained-manager:owner')
        self.owner, self.handle = owner, handle

    def path(self, phase):
        import system_native_update as checkpoints
        return checkpoints.private() / f'retained-manager-{self.owner}-{phase}.json'

    def fingerprint(self, phase):
        path = self.path(phase)
        info = path.lstat()
        return [info.st_dev, info.st_ino, guest.sha(path)]

    def append(self, phase, **values):
        import system_native_update as checkpoints
        index = self.phases.index(phase)
        previous = self.phases[index - 1] if index else None
        checkpoints.publish(self.path(phase).name, dict(schema=1, owner=self.owner, phase=phase,
            previous=self.fingerprint(previous) if previous else None, **values))
        if self.handle is not None:
            self.handle.setdefault('checkpoints', {})[phase] = self.fingerprint(phase)

    def load(self):
        import system_native_update as checkpoints
        records = {}
        previous = None
        missing = False
        for phase in self.phases:
            if not self.path(phase).exists():
                missing = True
                continue
            guest.require(not missing, 'retained-manager:checkpoint-gap')
            value = checkpoints.read_private(self.path(phase))
            guest.require(value.get('schema') == 1 and value.get('owner') == self.owner and
                          value.get('phase') == phase and value.get('previous') == previous,
                          'retained-manager:checkpoint-changed')
            records[phase] = value
            previous = self.fingerprint(phase)
        guest.require('intent' in records and self.handle is not None and
                      self.handle.get('owner') == self.owner and
                      self.handle.get('intent') == self.fingerprint('intent'),
                      'retained-manager:ownership-changed')
        for phase, expected in self.handle.get('checkpoints', {}).items():
            guest.require(phase in records and self.fingerprint(phase) == expected,
                          'retained-manager:checkpoint-changed')
        intent = records['intent']
        marker = guest.guard()
        guest.require(intent['binding'] == self.binding(marker) and
                      intent['boot'] == self.boot(), 'retained-manager:attempt-changed')
        account = pwd.getpwnam('oh-no-parent-control')
        guest.require(intent['account'] == [account.pw_name, account.pw_uid] and
                      intent['backend'] == json.loads((PAYLOAD / 'config.json').read_text())['backend'],
                      'retained-manager:account-changed')
        return records, account

    @staticmethod
    def binding(marker):
        return {key: marker[key] for key in ('run', 'machine_id', 'domain_uuid', 'package_sha256',
            'preparation_sha256', 'baseline_sha256', 'selected_inputs_sha256')}

    @staticmethod
    def boot():
        return (PROC / 'sys/kernel/random/boot_id').read_text().strip()

    def result(self):
        self.handle = dict(owner=self.owner, intent=self.fingerprint('intent'), checkpoints={
            phase: self.fingerprint(phase) for phase in self.phases if self.path(phase).exists()})
        return json.loads(json.dumps(self.handle))

    def prepare(self):
        marker = guest.guard()
        account = pwd.getpwnam('oh-no-parent-control')
        backend = json.loads((PAYLOAD / 'config.json').read_text())['backend']
        unit = f'user@{account.pw_uid}.service'
        before = manager(unit)
        login = login_state(account)
        guest.require(before['ActiveState'] == 'inactive' and before['MainPID'] == '0' and
                      not login['Sessions'], 'retained-manager:already-active')
        guest.require(manager(unit) == before and login_state(account) == login,
                      'retained-manager:preparation-changed')
        self.append('intent', binding=self.binding(marker), boot=self.boot(),
                    account=[account.pw_name, account.pw_uid], backend=backend,
                    before=before, login=login)
        return self.result()

    def start(self):
        records, account = self.load()
        guest.require(set(records) == {'intent'}, 'retained-manager:start-not-replayable')
        intent = records['intent']
        unit = f'user@{account.pw_uid}.service'
        guest.require(manager(unit) == intent['before'] and login_state(account) == intent['login'],
                      'retained-manager:preexisting-manager')
        self.append('starting')
        # The start command is never retried. Capture an independently proved
        # new invocation even when its command reports failure or times out.
        primary = None
        try:
            guest.run(['systemctl', 'start', unit], timeout=75)
        except BaseException as error:
            primary = error
        try:
            current = manager(unit)
            if (current['ActiveState'] == 'active' and valid_invocation(current['InvocationID']) and
                    current['InvocationID'] != intent['before']['InvocationID']):
                observed = retained_observation(account, intent['backend'])
                guest.require(observed['unit'] == current, 'retained-manager:startup-changed')
                self.append('owned', observed=observed)
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note('retained-manager:startup-observation-failed:' + type(error).__name__)
        if primary is not None:
            raise primary
        guest.require(self.path('owned').exists(), 'retained-manager:startup-unproved')
        self.append('retention')  # durable intent precedes uncertain linger input
        self.check(ready=False)
        if intent['login']['Linger'] == 'no':
            self.load()
            guest.run(['loginctl', 'enable-linger', account.pw_name], timeout=30)
        guest.require(login_state(account)['Linger'] == 'yes', 'retained-manager:not-retained')
        self.check(ready=False)
        self.append('ready')
        return self.result()

    def check(self, *, ready=True):
        records, account = self.load()
        guest.require('owned' in records and (not ready or ('ready' in records and
                      not records['ready'].get('startup_incomplete'))) and
                      'cleanup' not in records, 'retained-manager:not-ready')
        guest.require(retained_observation(account, records['intent']['backend']) ==
                      records['owned']['observed'], 'retained-manager:identity-changed')
        if ready:
            guest.require(login_state(account)['Linger'] == 'yes', 'retained-manager:retention-changed')
        return records['owned']['observed']

    def cleanup(self):
        records, account = self.load()
        if 'complete' in records:
            return self.result()
        intent = records['intent']
        unit = f'user@{account.pw_uid}.service'
        current = manager(unit)
        login = login_state(account)
        guest.require(not login['Sessions'], 'retained-manager:public-session-remains')
        if 'owned' not in records:
            # No proof was saved after an interrupted start. Inactivity is safe;
            # any live manager is ambiguous and must remain untouched.
            guest.require(current == intent['before'] and login == intent['login'],
                          'retained-manager:uncertain-start')
            return self.result()
        owned = records['owned']['observed']
        if current['ActiveState'] != 'inactive':
            guest.require(retained_observation(account, intent['backend']) == owned,
                          'retained-manager:identity-changed')
        else:
            guest.require(current['MainPID'] == '0' and current['InvocationID'] in
                          ('', owned['unit']['InvocationID']), 'retained-manager:identity-changed')
        # A start failure can leave an owned manager before retention intent.
        if 'retention' not in records:
            guest.require(login == intent['login'], 'retained-manager:unowned-retention')
            self.append('retention')
        if 'ready' not in records:
            self.append('ready', startup_incomplete=True)
        if 'cleanup' not in records:
            self.append('cleanup')
        if 'restored' not in records:
            guest.require(login['Linger'] == intent['login']['Linger'] or
                          (intent['login']['Linger'] == 'no' and login['Linger'] == 'yes'),
                          'retained-manager:retention-changed')
            if login['Linger'] != intent['login']['Linger']:
                self.load()
                guest.run(['loginctl', 'disable-linger', account.pw_name], timeout=30)
            guest.require(login_state(account) == intent['login'], 'retained-manager:not-restored')
            self.append('restored')
        guest.require(login_state(account) == intent['login'], 'retained-manager:restoration-changed')
        if 'stopped' not in records:
            current = manager(unit)
            if current['ActiveState'] != 'inactive':
                guest.require(retained_observation(account, intent['backend']) == owned,
                              'retained-manager:identity-changed')
                self.load()
                guest.run(['systemctl', 'stop', unit], timeout=75)
            current = manager(unit)
            guest.require(current['ActiveState'] == 'inactive' and current['MainPID'] == '0' and
                          current['InvocationID'] in ('', owned['unit']['InvocationID']),
                          'retained-manager:not-stopped')
            self.append('stopped')
        guest.require(manager(unit)['ActiveState'] == 'inactive', 'retained-manager:replacement-active')
        self.append('complete')
        return self.result()


def retained_command(action, owner, handle=None):
    """Fixed guest transport leaf; no installation or case registration."""
    guest.require(action in ('prepare', 'start', 'check', 'cleanup'), 'retained-manager:action')
    lifetime = RetainedManager(owner, handle)
    if action == 'prepare':
        guest.require(handle is None, 'retained-manager:prepare-handle')
    return getattr(lifetime, action)()


def ordinary_process(process, account, backend, *, domain='unconfined_t'):
    guest.require(process_identity(process)[2] == (str(account.pw_uid),) * 4,
                  'kiosk-collateral:process-credentials')
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    label = (process / attribute).read_text().strip().rstrip('\0')
    parts = label.split(':')
    guest.require(label == 'unconfined' if backend == 'apparmor' else
                  len(parts) >= 4 and parts[2] == domain, 'kiosk-collateral:process-label')
    guest.require((process / 'root' / PAYLOAD.relative_to('/') / 'generation').read_text()
                  == 'unconfined\n', 'kiosk-collateral:private-generation')
    for executable in ('/usr/bin/python3', '/usr/bin/gjs', '/usr/bin/wireplumber'):
        original = Path(executable).stat()
        visible = (process / 'root' / executable.lstrip('/')).stat()
        guest.require((visible.st_dev, visible.st_ino) == (original.st_dev, original.st_ino),
                      'kiosk-collateral:private-executable')


def properties(account, service, names):
    raw = user_command(account, ['systemctl', '--user', 'show', service,
                                '--property=' + ','.join(names)]).decode()
    result = dict(line.split('=', 1) for line in raw.splitlines())
    guest.require(set(result) == set(names), 'kiosk-collateral:unit-properties')
    return result


def verify_units(account, backend):
    unit_path = user_command(account, ['systemctl', '--user', 'show',
                                     '--value', '--property=UnitPath']).decode().strip()
    guest.require(unit_path and str(PAYLOAD) not in unit_path, 'kiosk-collateral:private-unit-path')
    for service in SERVICES:
        values = properties(account, service, ('LoadState', 'FragmentPath', 'DropInPaths',
                                              'Environment', 'ExecStart', 'NoNewPrivileges'))
        guest.require(values['LoadState'] == 'loaded' and values['FragmentPath'] and
                      all(str(PAYLOAD) not in values[key] for key in
                          ('FragmentPath', 'DropInPaths', 'Environment', 'ExecStart')),
                      'kiosk-collateral:private-unit-override')
        if service in SERVICES[:3]:
            guest.require(values['NoNewPrivileges'] == 'yes', 'kiosk-collateral:vendor-nnp')
        if service == 'org.gnome.Kiosk@wayland.service':
            guest.require('GIO_USE_VFS=local' not in shlex.split(values['Environment']),
                          'kiosk-collateral:compositor-environment')
        if service == 'wireplumber.service':
            hardening = properties(account, service, ('LockPersonality', 'MemoryDenyWriteExecute',
                                                       'SystemCallFilter', 'SystemCallArchitectures'))
            guest.require(hardening['LockPersonality'] == hardening['MemoryDenyWriteExecute'] == 'yes'
                          and hardening['SystemCallArchitectures'] == 'native' and
                          hardening['SystemCallFilter'] not in ('', '~'),
                          'kiosk-collateral:vendor-audio-hardening')
        if service == 'dbus.service':
            executable = '/usr/bin/dbus-daemon' if backend == 'apparmor' else '/usr/bin/dbus-broker-launch'
            guest.require('path=' + executable + ' ;' in values['ExecStart'] and
                          (backend != 'selinux' or '--scope user ;' in values['ExecStart']),
                          'kiosk-collateral:vendor-bus-executable')
    if backend == 'apparmor':
        for name in MASKS:
            mask = PAYLOAD / 'user-units' / name
            guest.require(mask.is_symlink() and mask.readlink() == Path('/dev/null'),
                          'kiosk-collateral:private-mask-missing')
            values = properties(account, name, ('LoadState', 'FragmentPath'))
            guest.require(values['LoadState'] == 'loaded' and
                          values['FragmentPath'] not in ('', '/dev/null') and
                          str(PAYLOAD) not in values['FragmentPath'],
                          'kiosk-collateral:ordinary-service-masked')


def verify_services(account, backend):
    raw = user_command(account, ['systemctl', '--user', 'show-environment']).decode()
    inherited = dict(shlex.split(line)[0].split('=', 1) for line in raw.splitlines())
    guest.require(str(PAYLOAD) not in inherited.get('XDG_DATA_DIRS', '') and
                  'SYSTEMD_UNIT_PATH' not in inherited, 'kiosk-collateral:private-manager-environment')
    for service, names in (
        ('wireplumber.service', ('LUA_PATH', 'LUA_CPATH', 'WIREPLUMBER_CONFIG_DIR', 'WIREPLUMBER_DATA_DIR')),
        ('oh-no-parent-control-wellbeing.service', ('DCONF_PROFILE', 'GSETTINGS_BACKEND', 'XDG_CONFIG_HOME')),
        ('dbus.service', ('XDG_DATA_DIRS',)),
    ):
        user_command(account, ['systemctl', '--user', 'start', service])
        values = properties(account, service, ('MainPID', 'ActiveState'))
        guest.require(values['ActiveState'] == 'active' and values['MainPID'].isdecimal() and
                      int(values['MainPID']) > 1, 'kiosk-collateral:service-startup')
        process = PROC / values['MainPID']
        identity = process_identity(process)
        # Fedora's vendor user-bus entrypoint has its own ordinary domain.
        # Keep that measured distinction rather than accepting arbitrary labels.
        ordinary_process(process, account, backend, domain=(
            'unconfined_dbusd_t' if service == 'dbus.service' else 'unconfined_t'))
        actual = environment(process)
        guest.require(all(actual.get(name) == inherited.get(name) for name in names),
                      'kiosk-collateral:ordinary-service-environment')
        guest.require(process_identity(process) == identity and
                      properties(account, service, ('MainPID',))['MainPID'] == process.name,
                      'kiosk-collateral:service-replaced')


def verify(record):
    guest.guard()
    guest.enable_diagnostics()
    accounts = ordinary_accounts()
    backend = json.loads((PAYLOAD / 'config.json').read_text())['backend']
    verify_vendor_pam(record)
    verify_namespace_guard(record)
    for role, account in accounts.items():
        with owned_manager(account) as process:
            identity = process_identity(process)
            ordinary_process(process, account, backend)
            verify_units(account, backend)
            verify_services(account, backend)
            for index, command in enumerate((
                ['/bin/sh', '-c', 'printf onpc-ordinary-shell'],
                ['/usr/bin/python3', '-I', '-c', 'print("onpc-ordinary-python")'],
                ['/usr/bin/gjs', '-c', 'print("onpc-ordinary-gjs")'],
            )):
                result = user_command(account, ['systemd-run', '--user', '--wait', '--collect',
                    '--pipe', '--unit=onpc-collateral-' + str(index), *command])
                guest.require(result.strip() == b'onpc-ordinary-' + (b'shell', b'python', b'gjs')[index],
                              'kiosk-collateral:ordinary-execution')
            guest.require(process_identity(process) == identity,
                          'kiosk-collateral:manager-process-replaced')
            record('onpc.kiosk.collateral.' + role + '.pam-manager-and-policy-preserved', True)
        record('onpc.kiosk.collateral.' + role + '.owned-manager-stopped', True)


if __name__ == '__main__':
    guest.require(len(sys.argv) in (3, 4), 'retained-manager:arguments')
    print(json.dumps(retained_command(sys.argv[1], sys.argv[2],
        json.loads(sys.argv[3]) if len(sys.argv) == 4 else None), sort_keys=True))
