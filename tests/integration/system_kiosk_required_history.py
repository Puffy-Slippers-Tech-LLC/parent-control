"""Finite retained-manager drift inputs; the runner owns visits and reboot.

Every mutation has a durable, attempt-bound intent before changing its original
inode. Cleanup accepts only the original or the finite attributable mutation,
including an interrupted append. It never replaces a path or signals a manager.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import runpy
import stat
import sys

import system_guest as guest
import system_kiosk_confinement as confinement
import system_kiosk_scope as scope
import system_native_update as native


BRANCHES = ('native', 'config', 'policy', 'privilege')
CONFIG = Path('/usr/share/oh-no-parent-control/confinement/config.json')
INTEGRATION = '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration'
PREPARATION = '/usr/libexec/oh-no-parent-control-kiosk-confinement'
PRESERVED_HELPER = Path('/usr/lib/polkit-1/polkit-agent-helper-1')
BOOT = Path('/proc/sys/kernel/random/boot_id')
SUFFIX = b'\nONPC-007a1-required-native-drift\n'
MAX_FILE = 2 * 1024 * 1024
PHASES = ('intent', 'mutated', 'refusal', 'public-refusal', 'restored', 'complete')


def checkpoint_names():
    return tuple(checkpoint_name(branch, phase) for branch in BRANCHES for phase in PHASES)


def binding():
    marker = guest.guard()
    return {key: marker[key] for key in ('run', 'package_sha256', 'selected_inputs_sha256')}


def checkpoint_name(branch, phase):
    guest.require(branch in BRANCHES and phase in PHASES,
                  'required-history:checkpoint-name')
    return 'required-history-' + branch + '-' + phase + '.json'


def saved(branch, phase):
    value = native.read_private(native.private() / checkpoint_name(branch, phase))
    guest.require(value.get('binding') == binding() and value.get('branch') == branch,
                  'required-history:checkpoint-binding')
    return value


def save(branch, phase, **values):
    native.publish(checkpoint_name(branch, phase), dict(binding=binding(), branch=branch, **values))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(fd):
    before = os.fstat(fd)
    guest.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                  before.st_size <= MAX_FILE, 'required-history:file-metadata')
    os.lseek(fd, 0, os.SEEK_SET)
    data = bytearray()
    while len(data) <= MAX_FILE:
        block = os.read(fd, min(65536, MAX_FILE + 1 - len(data)))
        if not block:
            break
        data.extend(block)
    after = os.fstat(fd)
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_size', 'st_nlink',
              'st_mtime_ns', 'st_ctime_ns')
    guest.require(len(data) <= MAX_FILE and all(getattr(before, key) == getattr(after, key)
                  for key in fields), 'required-history:file-changed')
    metadata = {key: getattr(after, key) for key in fields}
    metadata['st_atime_ns'] = before.st_atime_ns
    metadata['xattrs'] = {key: os.getxattr(fd, key).hex() for key in os.listxattr(fd)}
    return metadata, bytes(data)


def selected_path(branch, preparation, config):
    if branch == 'config':
        return CONFIG
    if branch == 'policy':
        return CONFIG.parent / ('onpc-kiosk.apparmor' if config['backend'] == 'apparmor'
                                else 'onpc-kiosk.cil')
    if branch == 'native':
        rows = [row for row in preparation['inventory'](config)
                if row.get('source', row['path']) == '/usr/bin/xdg-dbus-proxy']
        guest.require(len(rows) == 1 and rows[0]['role'] == 'service',
                      'required-history:native-not-selected')
        return Path(rows[0].get('source', rows[0]['path']))
    rows, _ = preparation['preserved_inventory'](config)
    selected = [row for row in rows if row['path'] == str(PRESERVED_HELPER)]
    guest.require(len(selected) == 1, 'required-history:privileged-helper-missing')
    return PRESERVED_HELPER


def boundary(intent):
    account = pwd.getpwnam('oh-no-parent-control')
    observed = confinement.manager_boundary(account, f'user@{account.pw_uid}.service',
                                            intent['backend'], retained_view=True)
    # JSON normalization preserves the actual PID/start/credentials/namespace,
    # marker, enforcing label and original systemd invocation across commands.
    observed = json.loads(json.dumps(observed))
    guest.require(observed == intent['original']['boundary'] and
                  scope.manager(f'user@{account.pw_uid}.service') == intent['original']['unit'],
                  'required-history:manager-replaced')
    return account


def prepare(branch, record=lambda *_: None):
    guest.require(branch in BRANCHES, 'required-history:branch')
    binding()
    for other in BRANCHES:
        if (native.private() / checkpoint_name(other, 'intent')).exists():
            guest.require((native.private() / checkpoint_name(other, 'restored')).exists(),
                          'required-history:pending-mutation')
    config = json.loads(CONFIG.read_bytes())
    preparation = runpy.run_path(PREPARATION)
    path = selected_path(branch, preparation, config)
    guest.require(preparation['trusted'](path) == path, 'required-history:fixture-alias')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata, data = snapshot(fd)
    finally:
        os.close(fd)
    guest.require(metadata['st_uid'] == metadata['st_gid'] == 0 and
                  not metadata['st_mode'] & 0o022, 'required-history:fixture-trust')
    account = pwd.getpwnam('oh-no-parent-control')
    original = scope.retained_observation(account, config['backend'])
    from system_kiosk_accounts import ordinary_state
    intent = dict(path=str(path), metadata=metadata, data=base64.b64encode(data).decode(),
                  sha256=sha(data), backend=config['backend'], original=original,
                  ordinary=ordinary_state(), pam=guest.pam_service_state(),
                  boot=BOOT.read_text().strip())
    # publish fsyncs both the exclusive checkpoint and its private directory.
    save(branch, 'intent', **intent)
    record('onpc.kiosk.required.' + branch + '.intent', str(path))


def expected(intent, branch):
    original = base64.b64decode(intent['data'], validate=True)
    guest.require(sha(original) == intent['sha256'], 'required-history:backup-digest')
    return (original if branch == 'privilege' else original +
            (SUFFIX if branch == 'native' else b'\n'))


def privilege_mode(intent):
    """Tighten the actual vendor requirement without adding any permission."""
    original = intent['metadata']['st_mode']
    if intent['backend'] == 'apparmor':
        guest.require(not original & 0o6000 and original & 0o111,
                      'required-history:vendor-privilege-mode')
        return original & ~0o111
    guest.require(intent['backend'] == 'selinux' and original & 0o6000,
                  'required-history:vendor-privilege-mode')
    return original & ~0o6000


def checked_file(intent, branch, *, recovery=False):
    path = Path(intent['path'])
    guest.require(path.resolve(strict=True) == path, 'required-history:fixture-alias')
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata, data = snapshot(fd)
        old = intent['metadata']
        guest.require(all(metadata[key] == old[key] for key in
                      ('st_dev', 'st_ino', 'st_uid', 'st_gid', 'st_nlink', 'xattrs')),
                      'required-history:fixture-replaced')
        named = path.lstat()
        guest.require((named.st_dev, named.st_ino) == (metadata['st_dev'], metadata['st_ino']),
                      'required-history:fixture-replaced')
        mode = privilege_mode(intent) if branch == 'privilege' else old['st_mode']
        original = base64.b64decode(intent['data'], validate=True)
        changed = expected(intent, branch)
        attributable = (metadata['st_mode'] in (old['st_mode'], mode) and
                        len(original) <= len(data) <= len(changed) and changed.startswith(data))
        guest.require(attributable if recovery else
                      metadata['st_mode'] == old['st_mode'] and data == original and
                      metadata['st_mtime_ns'] == old['st_mtime_ns'],
                      'required-history:unattributable-file')
        return fd, metadata, data
    except BaseException:
        os.close(fd)
        raise


def mutate(branch, record=lambda *_: None):
    intent = saved(branch, 'intent')
    boundary(intent)
    fd, _metadata, _data = checked_file(intent, branch)
    try:
        if branch == 'privilege':
            os.fchmod(fd, stat.S_IMODE(privilege_mode(intent)))
        else:
            os.lseek(fd, 0, os.SEEK_END)
            suffix = SUFFIX if branch == 'native' else b'\n'
            while suffix:
                suffix = suffix[os.write(fd, suffix):]
        os.fsync(fd)
        metadata, data = snapshot(fd)
        guest.require(data == expected(intent, branch) and
                      (sha(data) != intent['sha256'] if branch != 'privilege' else
                       metadata['st_mode'] != intent['metadata']['st_mode']),
                      'required-history:mutation-ineffective')
        save(branch, 'mutated', sha256=sha(data), mode=metadata['st_mode'])
    finally:
        os.close(fd)
    boundary(intent)
    record('onpc.kiosk.required.' + branch + '.changed', True)


def diagnostic_path(branch, phase):
    guest.require(branch in BRANCHES and phase in ('pam', 'public'),
                  'required-history:diagnostic-name')
    # The normal collector exports redacted private subdirectory .txt files,
    # including failed observations that never reached a result checkpoint.
    directory = native.private() / 'required-history-output'
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / (branch + '-' + phase + '.txt')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    return path


def capture_refusal(account, branch):
    """Use the native owner's journal transport for this one owned PAM call."""
    path = diagnostic_path(branch, 'pam')
    stage, reason = refusal_cause(branch)
    return native.pam_refusal(account, native.private(), stage=stage, reason=reason, diagnostic=path)


def refusal_cause(branch):
    guest.require(branch in BRANCHES, 'required-history:branch')
    return (('manager-material', 'stale-manager-reboot-required') if branch == 'native' else
            ('measurement', 'unexpected-preserved-executable') if branch == 'privilege' else
            ('measurement', 'attestation-command-failed'))


def refusal(branch, record=lambda *_: None):
    intent = saved(branch, 'intent')
    changed = saved(branch, 'mutated')
    account = boundary(intent)
    fd, metadata, data = checked_file(intent, branch, recovery=True)
    os.close(fd)
    guest.require(sha(data) == changed['sha256'] and metadata['st_mode'] == changed['mode'],
                  'required-history:mutation-not-present')
    if branch == 'native':
        # This owner requires the actual stale manager reason from real PAM;
        # an attestation failure cannot satisfy the assertion.
        observation = native.stale_admission(account, record)
    else:
        if branch in ('config', 'policy'):
            output = guest.commands.run([INTEGRATION, 'verify'], check=False,
                                         merge_stderr=True, timeout=15)
            guest.require(guest.commands.last_returncode != 0 and
                          re.findall(rb'(?:^|\s)reason=([^;\s]+)', output) ==
                          [b'policy-load-incomplete-reconfigure-required'],
                          'required-history:attestation-drift-not-refused')
        observation = capture_refusal(account, branch)
    stage, reason = refusal_cause(branch)
    boundary(intent)
    guest.require(guest.pam_service_state() == intent['pam'], 'required-history:pam-changed')
    ordinary_controls(intent, record)
    save(branch, 'refusal', stage=stage, expected_stage=stage, observation=observation,
         expected_reason=reason, attestation_reason=('policy-load-incomplete-reconfigure-required' if branch in
                             ('config', 'policy') else None), public_window=native.refusal_window())
    record('onpc.kiosk.required.' + branch + '.refused', stage)


def ordinary_controls(intent, record):
    from system_kiosk_accounts import verify_ordinary
    verify_ordinary(intent['ordinary'])
    scope.verify_vendor_pam(record)
    for role, account in scope.ordinary_accounts().items():
        guest.require(confinement.user_command(account,
                      ['/bin/sh', '-c', 'printf onpc-required-ordinary']) ==
                      b'onpc-required-ordinary', 'required-history:ordinary-execution')
        record('onpc.kiosk.required.ordinary.' + role, True)


def public_refusal(branch, record=lambda *_: None):
    """Bind new journal causes and no graphical session to the later GDM visit."""
    intent = saved(branch, 'intent')
    prior = saved(branch, 'refusal')
    account = boundary(intent)
    changed = saved(branch, 'mutated')
    fd, metadata, data = checked_file(intent, branch, recovery=True)
    os.close(fd)
    guest.require(sha(data) == changed['sha256'] and metadata['st_mode'] == changed['mode'],
                  'required-history:mutation-not-present')
    stage, reason = refusal_cause(branch)
    guest.require(prior['public_window']['boot'] == intent['boot'].replace('-', ''),
                  'required-history:refusal-boot')
    markers = native.journal_refusal(prior['public_window'], stage=stage, reason=reason,
                                     timeout=75, diagnostic=diagnostic_path(branch, 'public'))
    guest.require(all(row['pid'] != prior['observation']['call']['pid'] for row in markers),
                  'required-history:reused-internal-call')
    sessions = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager'])
    for line in sessions.splitlines():
        fields = line.split()
        if not fields:
            continue
        state = dict(row.split('=', 1) for row in guest.run(['loginctl', 'show-session', fields[0],
                     '--property=User', '--property=Class', '--property=Type']).splitlines())
        guest.require(not (state.get('User') == str(account.pw_uid) and
                      state.get('Class') == 'user' and state.get('Type') in ('wayland', 'x11')),
                      'required-history:public-graphical-session-admitted')
    boundary(intent)
    ordinary_controls(intent, record)
    save(branch, 'public-refusal', markers=markers, graphical_session='absent')
    record('onpc.kiosk.required.' + branch + '.public-refusal', True)


def restore(branch, record=lambda *_: None):
    intent = saved(branch, 'intent')
    fd, _metadata, _data = checked_file(intent, branch, recovery=True)
    try:
        original = base64.b64decode(intent['data'], validate=True)
        # Appends preserve the entire original prefix, so truncate suffices even
        # after an interrupted write. Privilege drift changes no file bytes.
        os.ftruncate(fd, len(original))
        os.fchmod(fd, stat.S_IMODE(intent['metadata']['st_mode']))
        os.utime(fd, ns=(intent['metadata']['st_atime_ns'], intent['metadata']['st_mtime_ns']))
        os.fsync(fd)
        metadata, data = snapshot(fd)
        guest.require(data == original and all(metadata[key] == intent['metadata'][key]
                      for key in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
                                  'st_mtime_ns', 'xattrs')), 'required-history:restoration')
        named = Path(intent['path']).lstat()
        guest.require((named.st_dev, named.st_ino) ==
                      (intent['metadata']['st_dev'], intent['metadata']['st_ino']),
                      'required-history:fixture-replaced')
        # Verification reads may advance atime; restore it after the final read.
        os.utime(fd, ns=(intent['metadata']['st_atime_ns'], intent['metadata']['st_mtime_ns']))
        os.fsync(fd)
    finally:
        os.close(fd)
    if not (native.private() / checkpoint_name(branch, 'restored')).exists():
        save(branch, 'restored', sha256=sha(original), inode=metadata['st_ino'])
    record('onpc.kiosk.required.' + branch + '.restored', True)


def cleanup(record=lambda *_: None):
    binding()
    for branch in BRANCHES:
        if (native.private() / checkpoint_name(branch, 'intent')).exists():
            restore(branch, record)


def complete(branch, record=lambda *_: None):
    intent = saved(branch, 'intent')
    saved(branch, 'refusal')
    saved(branch, 'public-refusal')
    saved(branch, 'restored')
    guest.require(BOOT.read_text().strip() != intent['boot'], 'required-history:reboot-required')
    fd, _metadata, _data = checked_file(intent, branch)
    os.close(fd)
    config = json.loads(CONFIG.read_bytes())
    account = pwd.getpwnam('oh-no-parent-control')
    observed = scope.retained_observation(account, config['backend'])
    guest.require(guest.pam_service_state() == intent['pam'], 'required-history:pam-changed')
    ordinary_controls(intent, record)
    save(branch, 'complete', boot=BOOT.read_text().strip(), observation=observed)
    record('onpc.kiosk.required.' + branch + '.recovered', True)


def verify_history(record):
    for branch in BRANCHES:
        intent = saved(branch, 'intent')
        value = saved(branch, 'complete')
        guest.require(value['boot'] != intent['boot'], 'required-history:reboot-required')
        saved(branch, 'refusal')
        saved(branch, 'public-refusal')
        saved(branch, 'restored')
        record('onpc.kiosk.required.' + branch + '.history', True)
    record('onpc.kiosk.required.recovered', True)


def command(action, branch=None, record=lambda *_: None):
    binding()
    if action == 'idle' and branch is None:
        guest.enable_diagnostics()
        return confinement.wait_kiosk_inactive(pwd.getpwnam('oh-no-parent-control'))
    if action in ('prepare', 'mutate', 'refusal', 'public-refusal', 'restore', 'complete'):
        guest.require(branch in BRANCHES, 'required-history:branch')
        guest.enable_diagnostics()
        return globals()[action.replace('-', '_')](branch, record)
    guest.require(action == 'cleanup' and branch is None,
                  'required-history:command')
    guest.enable_diagnostics()
    return globals()[action](record)


if __name__ == '__main__':
    guest.require(len(sys.argv) in (2, 3), 'required-history:arguments')
    command(*sys.argv[1:])
