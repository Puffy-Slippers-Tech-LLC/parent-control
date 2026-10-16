#!/usr/bin/python3 -I
"""Install the last PAM session gate and the owned kiosk MAC policy."""
import json
import hashlib
import fcntl
import errno
from contextlib import contextmanager
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import tempfile


PAYLOAD = Path('/usr/share/oh-no-parent-control/confinement')
STATE = Path('/var/lib/oh-no-parent-control/kiosk-confinement.json')
ADMISSION_LOCK = Path('/run/oh-no-parent-control-kiosk-admission.lock')
ADMISSION_DISABLED = Path('/var/lib/oh-no-parent-control/kiosk-confinement-removing')
LEGACY_LOGIN_LOCK = Path('/run/oh-no-parent-control-kiosk-login.lock')
PREPARATION_LOCK = Path('/run/oh-no-parent-control-confinement.lock')
PROCESSES = Path('/proc')
PREVIOUS_ACTIVATION = Path('/var/lib/oh-no-parent-control/previous-package-activation.json')
_CONFINEMENT_FILESYSTEM_ROOT = Path('/')
_CONFINEMENT_OWNER_UID = 0
BEGIN = '# BEGIN Oh No Parent Control execution confinement\n'
BLOCK = BEGIN + 'session required pam_oh_no_parent_control.so kiosk-confinement\n' + '# END Oh No Parent Control execution confinement\n'
PREFIX = ('# Oh No Parent Control admission integrity\n'
          'account requisite pam_oh_no_parent_control.so kiosk-integrity\n'
          'session requisite pam_oh_no_parent_control.so kiosk-admission\n')
MANAGER_CREDENTIALS = (
    '# Oh No Parent Control manager credentials (never authentication)\n'
    'auth [success=done ignore=ignore default=die] '
    'pam_oh_no_parent_control.so kiosk-manager-credentials\n'
    'auth include other\n')
REMOVAL_PREFIX = ('# Oh No Parent Control removal admission barrier\n'
                  'account requisite pam_succeed_if.so quiet user != oh-no-parent-control\n'
                  'session requisite pam_succeed_if.so quiet user != oh-no-parent-control\n')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}
PAM_LOCAL = Path('/etc/pam.d')
PAM_VENDOR = Path('/usr/lib/pam.d')
KEYRING_GUARD = ('session [success=1 auth_err=ignore default=die] '
                 'pam_succeed_if.so quiet user = oh-no-parent-control\n')
# The same guard excludes namespace open AND close callbacks. No namespace
# configuration, init script, temporary-directory cleanup or pending SELinux
# context reset is consumed for the kiosk; ordinary users keep vendor behavior.
NAMESPACE_GUARD = KEYRING_GUARD
SESSION_MODULES = frozenset(('pam_selinux.so', 'pam_loginuid.so', 'pam_keyinit.so',
    'pam_limits.so', 'pam_env.so', 'pam_unix.so', 'pam_sss.so', 'pam_systemd.so',
    'pam_systemd_home.so', 'pam_umask.so', 'pam_succeed_if.so',
    'pam_lastlog2.so', 'pam_permit.so', 'pam_deny.so', 'pam_oh_no_parent_control.so'))


@contextmanager
def admission_barrier(*, exclusive=True, preparation=False):
    """Refuse in-flight PAM handles before any scan or policy/PAM mutation.

    A UID scan cannot see a root GDM/systemd executor waiting to setuid/exec.
    PAM holds a shared lease until pam_end/exec; inherited helper descriptors
    also keep the lease while a worker aborts. Keep this inode across retries.
    """
    descriptors = []
    try:
        paths = ((ADMISSION_LOCK, LEGACY_LOGIN_LOCK, PREPARATION_LOCK) if exclusive else
                 (ADMISSION_LOCK, PREPARATION_LOCK) if preparation else (ADMISSION_LOCK,))
        for path in paths:
            # Legacy callers create these in their native SELinux domains.
            # A current caller cannot start while our admission lock is held;
            # pre-lease generations require a completed reboot below. Do not
            # manufacture missing legacy inodes with a different runtime type.
            if path != ADMISSION_LOCK and not os.path.lexists(path):
                if preparation and path == PREPARATION_LOCK:
                    raise ValueError('missing-preparation-lock')
                continue
            safe(path, absent=True)
            fd = os.open(path, os.O_RDWR | (os.O_CREAT if path == ADMISSION_LOCK else 0) | os.O_NOFOLLOW |
                         os.O_CLOEXEC | os.O_NONBLOCK, 0o600)
            descriptors.append(fd)
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != _CONFINEMENT_OWNER_UID or
                    stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise ValueError('unsafe-admission-lock')
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX if exclusive or path != ADMISSION_LOCK else fcntl.LOCK_SH) |
                            fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('kiosk-admissions-active') from None
            path_info = path.stat(follow_symlinks=False)
            if (path_info.st_dev, path_info.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError('replaced-admission-lock')
        yield
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def removal_pam(record):
    source = record['before'] if record['before'] is not None else record['vendor']
    return REMOVAL_PREFIX + source


def boot_id():
    value = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
        raise ValueError('invalid-boot-identity')
    return value


def safe(path, *, absent=False, symlinks=False):
    if not path.is_relative_to(_CONFINEMENT_FILESYSTEM_ROOT):
        raise ValueError('outside-confinement-root')
    for ancestor in (path, *path.parents):
        if ancestor == path and absent and not os.path.lexists(ancestor):
            continue
        info = ancestor.lstat()
        if symlinks and stat.S_ISLNK(info.st_mode) and info.st_uid == _CONFINEMENT_OWNER_UID:
            continue
        if stat.S_ISLNK(info.st_mode) or info.st_uid != _CONFINEMENT_OWNER_UID or info.st_mode & 0o022:
            raise ValueError('unsafe-confinement-path')
        if ancestor == path:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('unsafe-confinement-file')
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError('unsafe-confinement-ancestor')
        if ancestor == _CONFINEMENT_FILESYSTEM_ROOT:
            break
    if symlinks:
        safe(path.resolve(strict=True))


def run(args):
    result = subprocess.run(args, env=ENV, text=True, capture_output=True, timeout=60)
    if result.returncode:
        # These fixed policy-tool arguments contain no account or UI data.
        # Compiler diagnostics are essential to repair an installation failure.
        if args[0] in ('/usr/sbin/semodule', '/usr/sbin/apparmor_parser'):
            print(result.stderr[-4000:], file=sys.stderr)
        result.check_returncode()
    return result


def atomic(path, contents, mode):
    safe(path, absent=True)
    fd, name = tempfile.mkstemp(prefix='.onpc-confinement-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def unlink_synced(path):
    path.unlink(missing_ok=True)
    sync_directory(path.parent)


def state():
    # A later standalone purge can follow a complete remove which already
    # deleted this empty product directory. No ownership record remains.
    if not os.path.lexists(STATE.parent):
        return None
    safe(STATE, absent=True)
    if not STATE.exists():
        return None
    if stat.S_IMODE(STATE.stat().st_mode) != 0o600:
        raise ValueError('unsafe-confinement-record')
    value = json.loads(STATE.read_text())
    if value.get('schema') != 1 or set(value.get('pam', {})) != {'gdm-password', 'systemd-user'}:
        raise ValueError('invalid-confinement-record')
    return value


def pam_lines(source):
    """Parse logical rules while retaining exact vendor bytes for rendering.

    Linux-PAM joins backslash continuations before tokenizing and accepts tabs
    in @include directives. All audits must see the same rules as the loader.
    Noncanonical group/control spelling and incomplete rules fail closed.
    """
    if any(ord(char) < 32 and char not in '\t\n' for char in source):
        raise ValueError('unsupported-pam-syntax')
    raw_parts, parts = [], []
    for raw in source.splitlines(keepends=True):
        raw_parts.append(raw)
        trimmed = raw.rstrip(' \t\n')
        continued = trimmed.endswith('\\') and '#' not in raw
        parts.append((trimmed[:-1] + ' ' if continued else raw.split('#', 1)[0]).lstrip(' \t'))
        if continued:
            continue
        line = ''.join(parts).strip()
        original = ''.join(raw_parts)
        raw_parts, parts = [], []
        if not line:
            yield original, None, None, None
            continue
        group = line.split()[0]
        if group.lower().lstrip('-') == '@include':
            if group != '@include':
                raise ValueError('unsupported-pam-spelling')
            fields = line.split()
            if len(fields) != 2:
                raise ValueError('invalid-pam-include')
            yield original, '@include', 'include', fields[1]
            continue
        if group.lower().lstrip('-') not in ('auth', 'account', 'password', 'session'):
            raise ValueError('unsupported-pam-syntax')
        match = re.fullmatch(r'(-?\w+)\s+(\[[^]]+\]|\S+)\s+(\S+)(?:\s+.*)?', line)
        if match is None:
            raise ValueError('unsupported-pam-session')
        group, control, module = match.groups()
        if group != group.lower() or control != control.lower():
            raise ValueError('unsupported-pam-spelling')
        yield original, group.lstrip('-'), control, module
    if raw_parts:
        raise ValueError('incomplete-pam-continuation')


def included_source(name, seen):
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name) or name in seen or len(seen) >= 16:
        raise ValueError('invalid-pam-include')
    path = PAM_LOCAL / name
    # A dangling or unsafe local override must never fall back to vendor data.
    if not os.path.lexists(path):
        path = PAM_VENDOR / name
    safe(path, symlinks=True)
    return path.read_text(), (*seen, name)


def session_rules(source, seen=()):
    """Expand include controls; a substack cannot jump beyond its caller slot."""
    rules = []
    for _, group, control, module in pam_lines(source):
        if group == '@include' or (group == 'session' and control == 'include'):
            nested, ancestry = included_source(module, seen)
            rules.extend(session_rules(nested, ancestry))
        elif group == 'session':
            rules.append(control)
    return rules


def validate_stack(source):
    rules = session_rules(source)
    for index, control in enumerate(rules):
        if control in ('required', 'requisite', 'optional', 'substack'):
            continue
        if not control.startswith('['):
            raise ValueError('pam-can-skip-confinement')
        for item in control[1:-1].split():
            if '=' not in item:
                raise ValueError('unsupported-pam-control')
            action = item.split('=', 1)[1]
            if action in ('ignore', 'bad', 'die', 'ok', 'reset'):
                continue
            # A jump may land on the appended gate, but never beyond it.
            if action.isdecimal() and index + 1 + int(action) <= len(rules):
                continue
            raise ValueError('pam-can-skip-confinement')


def guarded_sessions(source, seen=(), *, verify=False):
    """Keep vendor callbacks except the kiosk's pre-boundary keyring daemon.

    Audit includes and substacks too: a final gate cannot retroactively confine
    an earlier module's children. Unknown session modules require review.
    """
    output = []
    original_rules = session_rules(source)
    position = 0
    for raw, group, control, module in pam_lines(source):
        name = module if group == '@include' else None
        if group == 'session':
            if control in ('include', 'substack'):
                name = module
            elif module in ('pam_gnome_keyring.so', 'pam_namespace.so'):
                kind = 'keyring' if module == 'pam_gnome_keyring.so' else 'namespace'
                controls = ('optional',) if kind == 'keyring' else ('optional', 'required', 'requisite')
                if seen or control not in controls:
                    raise ValueError('unsupported-pam-' + kind + '-placement')
                if verify:
                    if not output or output[-1] != KEYRING_GUARD:
                        raise ValueError('unguarded-pam-' + kind)
                else:
                    for index, previous in enumerate(original_rules[:position]):
                        if previous.startswith('['):
                            for item in previous[1:-1].split():
                                action = item.split('=', 1)[-1]
                                if action.isdecimal() and index + 1 + int(action) > position:
                                    raise ValueError('pam-jump-crosses-' + kind + '-guard')
                    output.append(KEYRING_GUARD)
            elif module not in SESSION_MODULES:
                raise ValueError('unsupported-pam-session-module:' + module)
        if name is not None:
            nested, ancestry = included_source(name, seen)
            guarded_sessions(nested, ancestry, verify=verify)
        output.append(raw)
        position += len(session_rules(raw, seen))
    return ''.join(output)


def audit_manager_credentials(source, seen=()):
    """systemd calls setcred even without authenticate, including at teardown.

    Supported vendor systemd-user stacks have no auth rules. The owned native
    credential route bypasses the implicit "other" fallback for the kiosk;
    ordinary accounts retain it. Refuse added vendor credential callbacks.
    """
    for _, group, _, module in pam_lines(source):
        if group == 'auth':
            raise ValueError('unsupported-manager-pam-credentials')
        if group == '@include':
            nested, ancestry = included_source(module, seen)
            audit_manager_credentials(nested, ancestry)


def rendered(source, *, service=None):
    credentials = ''
    if service == 'systemd-user':
        audit_manager_credentials(source)
        credentials = MANAGER_CREDENTIALS
    validate_stack(source)
    result = credentials + PREFIX + guarded_sessions(source).rstrip('\n') + '\n' + BLOCK
    validate_stack(result.removesuffix(BLOCK))
    return result


def verify_pam(saved, *, recovery=False):
    for name, record in saved['pam'].items():
        path = PAM_LOCAL / name
        safe(path, absent=True)
        actual = path.read_text() if path.exists() else None
        accepted = (record['before'], record['after']) if recovery else (record['after'],)
        if recovery and saved.get('removing'):
            accepted += (removal_pam(record),)
        if recovery and name in saved.get('previous_pam', {}):
            accepted += (saved['previous_pam'][name]['after'],)
        if actual not in accepted:
            raise ValueError('modified-pam-confinement')
        if not recovery:
            if record['before'] is None:
                vendor = PAM_VENDOR / name
                safe(vendor)
                if vendor.read_text() != record['vendor']:
                    raise ValueError('vendor-pam-changed-reconfigure-required')
            else:
                pending_pam_update(path, record['before'])
            source = record['before'] if record['before'] is not None else record['vendor']
            if rendered(source, service=name) != record['after']:
                raise ValueError('pam-generation-reconfigure-required')
            validate_stack(record['after'].removesuffix(BLOCK))
            guarded_sessions(record['after'], verify=True)


def pending_pam_update(path, source):
    # These package-manager conffile candidates must be reconciled explicitly;
    # never silently keep replaying an obsolete source or adopt a local merge.
    for suffix in ('.dpkg-dist', '.rpmnew'):
        pending = path.with_name(path.name + suffix)
        if os.path.lexists(pending):
            safe(pending)
            if pending.read_text() != source:
                raise ValueError('pending-distribution-pam-update')


def install():
    # Configuration also serializes with removals, and recovery keeps the
    # durable admission denial until policy plus both PAM stacks are restored.
    saved = state()
    # Keep live sessions, but exclude native preparation through the complete
    # policy/PAM/attestation transaction. If no preparation inode exists, EX
    # admission prevents a native caller creating it while we configure; never
    # manufacture that inode outside its Fedora named runtime transition.
    exclusive = bool(saved and saved.get('removing')) or not os.path.lexists(PREPARATION_LOCK)
    with admission_barrier(exclusive=exclusive, preparation=not exclusive):
        install_locked()


def install_locked():
    safe(PAYLOAD / 'config.json')
    config = json.loads((PAYLOAD / 'config.json').read_text())
    saved = state()
    if saved is None:
        # A reserved loaded policy without our ownership record is foreign.
        if config['backend'] == 'selinux':
            if any(line.split()[0] == 'onpc-kiosk' for line in run(['/usr/sbin/semodule', '-l']).stdout.splitlines() if line.split()):
                raise ValueError('foreign-selinux-module')
        else:
            profiles = Path('/sys/kernel/security/apparmor/profiles').read_text()
            if any(line.startswith('onpc-kiosk-') for line in profiles.splitlines()):
                raise ValueError('foreign-apparmor-profile')
        saved = {'schema': 1, 'backend': config['backend'], 'pam': {}, 'admission_protocol': 1}
        safe(PREVIOUS_ACTIVATION, absent=True)
        if PREVIOUS_ACTIVATION.exists():
            # First deployment over an older installed package has no prior
            # confinement record, but can still have pre-lease PAM workers.
            saved['prelease_upgrade_boot_id'] = boot_id()
        for name in ('gdm-password', 'systemd-user'):
            target = PAM_LOCAL / name
            safe(target, absent=True)
            before = target.read_text() if target.exists() else None
            vendor = PAM_VENDOR / name
            if before is None:
                safe(vendor)
            source = before if before is not None else vendor.read_text()
            if before is not None:
                pending_pam_update(target, before)
            if BEGIN in source:
                raise ValueError('foreign-pam-confinement')
            validate_stack(source)
            saved['pam'][name] = {'before': before, 'after': rendered(source, service=name),
                                  'vendor': source if before is None else None,
                                  'mode': stat.S_IMODE((target if before is not None else vendor).stat().st_mode)}
        # Record before any system mutation. Interrupted installation can only
        # accept these exact original or generated bytes on its next attempt.
        atomic(STATE, json.dumps(saved, sort_keys=True) + '\n', 0o600)
    if saved['backend'] != config['backend']:
        raise ValueError('changed-confinement-backend')
    verify_pam(saved, recovery=True)
    try:
        account_uid = pwd.getpwnam('oh-no-parent-control').pw_uid
    except KeyError:
        pass
    else:
        if saved.get('kiosk_uid', account_uid) != account_uid:
            raise ValueError('changed-kiosk-identity')
        saved['kiosk_uid'] = account_uid
    if saved.get('admission_protocol') != 1:
        # The previous native generation did not hold lifetime leases. A
        # process census cannot prove that its root workers will never fork
        # between observations. Preserve that generation's boot identity and
        # require its natural retirement at reboot before unloading policy.
        saved['prelease_upgrade_boot_id'] = boot_id()
        saved['admission_protocol'] = 1
    # Retain exactly the owned generation still on disk, including across
    # repeated interruptions with intervening vendor updates. Replacing it
    # with a newer, never-published generation would make recovery impossible.
    published = {}
    for name, record in saved['pam'].items():
        path = PAM_LOCAL / name
        actual = path.read_text() if path.exists() else None
        for candidate in (record, saved.get('previous_pam', {}).get(name)):
            if candidate is not None and actual == candidate['after']:
                published[name] = candidate.copy()
                break
    # Refresh a vendor-derived override only after matching the exact owned
    # previous output. A distro security update must never remain hidden.
    for name, record in saved['pam'].items():
        if record['before'] is None:
            vendor = PAM_VENDOR / name
            safe(vendor)
            source = vendor.read_text()
            validate_stack(source)
            record['vendor'] = source
            record['after'] = rendered(source, service=name)
        else:
            pending_pam_update(PAM_LOCAL / name, record['before'])
            validate_stack(record['before'])
            record['after'] = rendered(record['before'], service=name)
    # Preserve both generations until all PAM writes complete, so interrupted
    # vendor refresh can be resumed without adopting unrelated edits.
    saved['previous_pam'] = published
    atomic(STATE, json.dumps(saved, sort_keys=True) + '\n', 0o600)
    load_policy(saved)
    if saved['backend'] == 'selinux':
        run(['/usr/sbin/restorecon', str(ADMISSION_LOCK)])
    for name, record in saved['pam'].items():
        atomic(PAM_LOCAL / name, record['after'], record['mode'])
    if config['backend'] == 'selinux':
        run(['/usr/sbin/restorecon', '/etc/pam.d/gdm-password', '/etc/pam.d/systemd-user'])
    saved.pop('previous_pam', None)
    saved.pop('removing', None)
    atomic(STATE, json.dumps(saved, sort_keys=True) + '\n', 0o600)
    safe(ADMISSION_DISABLED, absent=True)
    unlink_synced(ADMISSION_DISABLED)


def load():
    # Boot/startup loading writes the same attestation as configuration. Take
    # the existing exclusive barrier before reading it: otherwise removal can
    # publish its durable denial while this writer restores an older record
    # or reloads the policy which removal just unloaded. Ordinary install holds
    # SH admission, so this also excludes an interrupted-generation refresh.
    with admission_barrier():
        saved = state()
        if saved is None:
            raise ValueError('missing-confinement-record')
        verify_pam(saved)
        # Boot renews only an already configured payload. Interrupted unpack
        # must not become a new accepted generation merely by rebooting.
        digests = verify_policy(saved)
        load_policy(saved, expected=digests)
        if saved['backend'] == 'selinux':
            # /run expires at reboot. The startup loader may now create this
            # inode before a native PAM caller can apply its named transition.
            run(['/usr/sbin/restorecon', str(ADMISSION_LOCK)])
        atomic(STATE, json.dumps(saved, sort_keys=True) + '\n', 0o600)


def policy_payload(saved):
    config = PAYLOAD / 'config.json'
    safe(config)
    config_bytes = config.read_bytes()
    if json.loads(config_bytes).get('backend') != saved['backend']:
        raise ValueError('changed-confinement-backend')
    policy = PAYLOAD / ('onpc-kiosk.cil' if saved['backend'] == 'selinux' else 'onpc-kiosk.apparmor')
    safe(policy)
    return policy, (hashlib.sha256(config_bytes).hexdigest(),
                    hashlib.sha256(policy.read_bytes()).hexdigest())


def load_policy(saved, *, expected=None):
    policy, digests = policy_payload(saved)
    if expected is not None and digests != expected:
        raise ValueError('policy-load-incomplete-reconfigure-required')
    if saved['backend'] == 'selinux':
        run(['/usr/sbin/semodule', '-i', str(policy)])
    else:
        run(['/usr/sbin/apparmor_parser', '-r', str(policy)])
    if policy_payload(saved) != (policy, digests):
        raise ValueError('policy-changed-during-load')
    saved['loaded_config_sha256'], saved['loaded_policy_sha256'] = digests


def verify_policy(saved):
    _, digests = policy_payload(saved)
    if (saved.get('loaded_config_sha256'), saved.get('loaded_policy_sha256')) != digests:
        raise ValueError('policy-load-incomplete-reconfigure-required')
    return digests


def check_remove(saved):
    verify_pam(saved, recovery=True)
    if (saved.get('admission_protocol') != 1 or
            saved.get('prelease_upgrade_boot_id') == boot_id()):
        raise ValueError('legacy-pam-reboot-required')
    try:
        uid = pwd.getpwnam('oh-no-parent-control').pw_uid
    except KeyError:
        # Cached root workers can outlive an administrator deleting the NSS
        # account. Retain its recorded numeric identity for the final census.
        uid = saved.get('kiosk_uid')
    if saved.get('kiosk_uid', uid) != uid:
        raise ValueError('changed-kiosk-identity')
    for path in PROCESSES.iterdir():
        if path.name.isdecimal():
            try:
                # Credentials are per-thread on Linux. A changed thread must
                # not disappear behind a root thread-group leader's status.
                for thread in (path / 'task').iterdir():
                    try:
                        identities = [line.split()[1:] for line in (thread / 'status').read_text().splitlines()
                                      if line.startswith('Uid:')]
                        if len(identities) != 1 or len(identities[0]) != 4 or not all(value.isdecimal() for value in identities[0]):
                            raise ValueError('invalid-process-identity')
                        if str(uid) in identities[0]:
                            raise ValueError('kiosk-processes-active')
                        if '0' in identities[0]:
                            check_root_pam_generation(thread)
                            # Exec can drop UID and replace mappings between
                            # these reads. Recheck credentials after maps.
                            refreshed = [line.split()[1:] for line in (thread / 'status').read_text().splitlines()
                                         if line.startswith('Uid:')]
                            if refreshed and str(uid) in refreshed[0]:
                                raise ValueError('kiosk-processes-active')
                        # pam_loginuid identifies GDM's trusted root worker
                        # before setuid. Legacy module generations did not yet
                        # hold admission leases, but may still execute later.
                        loginuid = (thread / 'loginuid').read_text().strip()
                        if not loginuid.isdecimal():
                            raise ValueError('invalid-process-identity')
                        if int(loginuid) == uid:
                            raise ValueError('kiosk-processes-active')
                        for attribute in ('current', 'exec'):
                            try:
                                label = (thread / 'attr' / attribute).read_text()
                            except OSError as error:
                                # AppArmor exposes no readable exec attr. An
                                # absent task is the only other benign loss.
                                if (attribute == 'exec' and saved['backend'] == 'apparmor' and
                                        error.errno == errno.EINVAL):
                                    continue
                                raise
                            if re.search(r'(^|[:/&])onpc(?:-kiosk-|_kiosk_)', label):
                                raise ValueError('kiosk-executors-active')
                    except FileNotFoundError:
                        pass
            except FileNotFoundError:
                pass


def check_root_pam_generation(thread):
    """Reject old/deleted native generations; current ordinary PAM is inert."""
    for line in (thread / 'maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6:
            continue
        path = fields[5]
        if Path(path.removesuffix(' (deleted)')).name != 'pam_oh_no_parent_control.so':
            continue
        if path.endswith(' (deleted)'):
            raise ValueError('legacy-pam-reboot-required')
        try:
            safe(Path(path), symlinks=True)
            info = Path(path).stat()
            # /proc/maps uses the superblock device, while Btrfs stat() uses
            # the subvolume device. Compare the actual mapped object instead
            # of those differently scoped device numbers. map_files resolves
            # the pinned mapping, including a replaced pathname's old inode.
            if not re.fullmatch(r'[0-9a-f]+-[0-9a-f]+', fields[0]):
                raise ValueError('invalid-process-mapping')
            # Linux exposes map_files at the /proc/TID alias, including for
            # non-leader threads, but not beneath /proc/PID/task/TID. Retain
            # each thread's own maps/credentials and resolve its exact alias.
            mapped = (PROCESSES / thread.name / 'map_files' / fields[0]).stat()
        except FileNotFoundError:
            raise ValueError('legacy-pam-reboot-required') from None
        if (mapped.st_dev, mapped.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('legacy-pam-reboot-required')


def remove(*, check=False):
    new_lock = not os.path.lexists(ADMISSION_LOCK)
    with admission_barrier():
        saved = state()
        if saved is None:
            return
        if new_lock and saved['backend'] == 'selinux':
            # /run expires at reboot. Label a freshly recreated admission
            # inode even if this removal is subsequently refused or aborted.
            run(['/usr/sbin/restorecon', str(ADMISSION_LOCK)])
        check_remove(saved)
        if check:
            return
        # Persist intent before publishing either deny stack. Interrupted
        # removals can only accept the exact owned enforcement/denial bytes.
        saved['removing'] = True
        atomic(STATE, json.dumps(saved, sort_keys=True) + '\n', 0o600)
        atomic(ADMISSION_DISABLED, 'removing\n', 0o600)
        for name, record in saved['pam'].items():
            atomic(PAM_LOCAL / name, removal_pam(record), record['mode'])
        if saved['backend'] == 'selinux':
            if any(line.split()[0] == 'onpc-kiosk' for line in run(['/usr/sbin/semodule', '-l']).stdout.splitlines() if line.split()):
                run(['/usr/sbin/semodule', '-r', 'onpc-kiosk'])
            # Retain the exact leased inode, but remove its now-invalid custom
            # type before postrm reopens it. Denials are durable and EX remains
            # held; relabel failure preserves them and the recovery record.
            run(['/usr/sbin/restorecon', '-F', str(ADMISSION_LOCK)])
        else:
            if any(line.startswith('onpc-kiosk-') for line in Path('/sys/kernel/security/apparmor/profiles').read_text().splitlines()):
                run(['/usr/sbin/apparmor_parser', '-R', str(PAYLOAD / 'onpc-kiosk.apparmor')])
        # Keep standalone, vendor-module-only PAM denials through payload
        # erasure. postrm restores the original files after account deletion.


def finish_remove():
    """Embedded in postrm: no erased helper or product module is required."""
    with admission_barrier():
        saved = state()
        if saved is None:
            return
        if not saved.get('removing'):
            raise ValueError('confinement-removal-not-prepared')
        try:
            pwd.getpwnam('oh-no-parent-control')
        except KeyError:
            pass
        else:
            raise ValueError('kiosk-account-still-present')
        verify_pam(saved, recovery=True)
        for name, record in saved['pam'].items():
            target = PAM_LOCAL / name
            if record['before'] is None:
                unlink_synced(target)
            else:
                atomic(target, record['before'], record['mode'])
        # Keep the denial marker until both original stacks are restored. An
        # interrupted finalization accepts only exact original/owned bytes.
        safe(ADMISSION_DISABLED, absent=True)
        unlink_synced(ADMISSION_DISABLED)
        unlink_synced(STATE)


if __name__ == '__main__':
    try:
        if os.geteuid() != 0 or len(sys.argv) != 2:
            raise ValueError('invalid-caller')
        if sys.argv[1] == 'install':
            install()
        elif sys.argv[1] == 'load':
            load()
        elif sys.argv[1] == 'verify':
            saved = state()
            if saved is None:
                raise ValueError('missing-confinement-record')
            verify_pam(saved)
            print(' '.join(verify_policy(saved)))
        elif sys.argv[1] == 'check-remove':
            remove(check=True)
        elif sys.argv[1] == 'remove':
            remove()
        elif sys.argv[1] == 'finish-remove':
            finish_remove()
        else:
            raise ValueError('invalid-operation')
    except Exception as error:
        reason = 'unavailable'
        if isinstance(error, ValueError) and error.args and re.fullmatch(r'[a-z-]{1,80}', str(error.args[0])):
            reason = str(error.args[0])
        print(f'oh-no-parent-control: kiosk confinement configuration failed reason={reason}; preserving ownership records', file=sys.stderr)
        sys.exit(1)
