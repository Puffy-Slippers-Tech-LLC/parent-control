#!/usr/bin/python3 -I
"""Owned kiosk account lifecycle and finite legacy confinement migration.

Pre-unpack capture retains the legacy policy payload until commit. Configuration
runs visibility() at AccountsService start-pre and composes prepare(),
restore_original_pam(), commit_migration(real_verifier), release_account().
The verifier performs side-effect-free native/distro PAM readiness checks,
returning None or raising. Post-unpack rollback preserves account quarantine.
Removal uses prepare() then finish_remove() after verified account/home deletion;
keep the numeric ownership marker until this finalizer succeeds. Never delete
runtime locks or private /run generations: their retirement belongs to reboot.
"""

from contextlib import contextmanager
import errno
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile


USER = 'oh-no-parent-control'
STATE_DIRECTORY = Path('/var/lib/oh-no-parent-control')
STATE = STATE_DIRECTORY / 'kiosk-confinement.json'
OWNERSHIP = STATE_DIRECTORY / 'package-created-kiosk-uid'
EXPIRY = STATE_DIRECTORY / 'kiosk-configuration-account.json'
DISABLED = STATE_DIRECTORY / 'kiosk-confinement-removing'
PAYLOAD = Path('/usr/share/oh-no-parent-control/confinement')
RETAINED = STATE_DIRECTORY / 'legacy-kiosk-policy'
CAPTURE = STATE_DIRECTORY / 'legacy-kiosk-policy.json'
PAM = Path('/etc/pam.d')
PROCESSES = Path('/proc')
BOOT = Path('/proc/sys/kernel/random/boot_id')
PROFILES = Path('/sys/kernel/security/apparmor/profiles')
LOCKS = tuple(Path('/run') / name for name in (
    'oh-no-parent-control-kiosk-admission.lock',
    'oh-no-parent-control-kiosk-login.lock', 'oh-no-parent-control-confinement.lock'))
CACHE = Path('/var/lib/AccountsService/users')
SLOT = '.onpc-kiosk-visibility-v1'
ATTRIBUTE = 'user.oh-no-parent-control.visibility-v1'
ROOT = Path('/')
OWNER = 0
GROUP = 0
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}
SERVICES = frozenset(('gdm-password', 'systemd-user'))
DENIAL = ('# Oh No Parent Control removal admission barrier\n'
          'account requisite pam_succeed_if.so quiet user != oh-no-parent-control\n'
          'session requisite pam_succeed_if.so quiet user != oh-no-parent-control\n')
DIGEST = re.compile(r'[0-9a-f]{64}')


def run(arguments):
    return subprocess.run(arguments, check=True, capture_output=True, text=True,
                          timeout=60, env=ENV)


@contextmanager
def directory(path):
    """Pin the source-defined directory chain; reject foreign writable state."""
    descriptor = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for component in (None, *path.relative_to(ROOT).parts):
            if component is not None:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                                os.O_CLOEXEC, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            info = os.fstat(descriptor)
            if (info.st_uid != OWNER or info.st_mode & 0o002 or
                    (info.st_mode & 0o020 and info.st_gid != GROUP)):
                raise ValueError('unsafe-migration-directory')
        yield descriptor
    finally:
        os.close(descriptor)


def read(path, *, private=False, optional=False):
    try:
        with directory(path.parent) as parent:
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                                 os.O_CLOEXEC, dir_fd=parent)
            try:
                info = os.fstat(descriptor)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != OWNER or
                        info.st_nlink != 1 or info.st_mode & 0o022 or
                        (private and stat.S_IMODE(info.st_mode) != 0o600) or
                        info.st_size > 4 * 1024 * 1024):
                    raise ValueError('unsafe-migration-file')
                with os.fdopen(descriptor, 'rb', closefd=False) as stream:
                    contents = stream.read(4 * 1024 * 1024 + 1)
                if len(contents) > 4 * 1024 * 1024:
                    raise ValueError('oversized-migration-file')
                attributes = {name: os.getxattr(descriptor, name) for name in os.listxattr(descriptor)}
                return info, contents, attributes
            finally:
                os.close(descriptor)
    except FileNotFoundError:
        if optional and not os.path.lexists(path):
            return None
        raise


def write(path, contents, mode=0o600):
    before = read(path, optional=True)
    with directory(path.parent) as parent:
        descriptor, temporary = tempfile.mkstemp(prefix='.onpc-migration-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                os.fchmod(stream.fileno(), mode)
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            current = read(path, optional=True)
            if (current is None) != (before is None) or (current is not None and
                    (current[0].st_dev, current[0].st_ino, current[1]) !=
                    (before[0].st_dev, before[0].st_ino, before[1])):
                raise ValueError('replaced-migration-file')
            os.replace(temporary, path)
            os.fsync(parent)
        finally:
            if os.path.lexists(temporary):
                os.unlink(temporary)


def erase(path):
    before = read(path, optional=True)
    if before is None:
        return
    with directory(path.parent) as parent:
        current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (before[0].st_dev, before[0].st_ino):
            raise ValueError('replaced-migration-file')
        os.unlink(path.name, dir_fd=parent)
        os.fsync(parent)


def save(path, value):
    write(path, (json.dumps(value, sort_keys=True) + '\n').encode())


def uid():
    value = read(OWNERSHIP, private=True)
    if not re.fullmatch(rb'[1-9][0-9]*\n', value[1]):
        raise ValueError('invalid-owned-kiosk-uid')
    return int(value[1])


def account(identity, *, absent=False):
    try:
        user = pwd.getpwnam(USER)
    except KeyError:
        user = None
    if absent:
        if user is not None:
            raise ValueError('kiosk-account-still-present')
        try:
            pwd.getpwuid(identity)
        except KeyError:
            return None
        raise ValueError('reassigned-kiosk-uid')
    if user is None or user.pw_uid != identity or user.pw_name != USER or user.pw_dir != '/home/' + USER:
        raise ValueError('changed-kiosk-identity')
    memberships = {group.gr_name for group in grp.getgrall()
                   if user.pw_name in group.gr_mem or group.gr_gid == user.pw_gid}
    if identity <= 0 or memberships & {'sudo', 'adm', 'wheel'}:
        raise ValueError('administrative-kiosk-identity')
    home = ROOT / user.pw_dir.lstrip('/')
    info = home.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != identity:
        raise ValueError('changed-kiosk-home')
    return user


def expiry_record(identity):
    value = read(EXPIRY, private=True, optional=True)
    if value is None:
        return None
    record = json.loads(value[1])
    if (not isinstance(record, dict) or set(record) != {'version', 'uid', 'expires', 'phase'} or
            type(record['version']) is not int or record['version'] != 1 or
            type(record['uid']) is not int or record['uid'] != identity or
            (record['expires'] is not None and
             (type(record['expires']) is not int or record['expires'] < 0)) or
            record['phase'] not in ('quarantined', 'releasing')):
        raise ValueError('changed-kiosk-expiry-record')
    return record


def current_expiry():
    fields = run(['getent', 'shadow', USER]).stdout.rstrip('\n').split(':')
    if len(fields) != 9 or fields[0] != USER or (fields[7] and not re.fullmatch(r'[0-9]+', fields[7])):
        raise ValueError('invalid-kiosk-expiry')
    return int(fields[7]) if fields[7] else None


def set_expiry(value):
    run(['usermod', '--expiredate', '-1' if value is None else str(value), USER])
    if current_expiry() != value:
        raise ValueError('kiosk-expiry-readback-failed')


def quarantine(identity):
    account(identity)
    record = expiry_record(identity)
    actual = current_expiry()
    if record is None:
        record = {'version': 1, 'uid': identity, 'expires': actual, 'phase': 'quarantined'}
    elif actual not in (1, record['expires']):
        raise ValueError('changed-kiosk-expiry')
    record['phase'] = 'quarantined'
    save(EXPIRY, record)
    if actual != 1:
        set_expiry(1)


def quarantined(identity):
    account(identity)
    record = expiry_record(identity)
    if record is None or record['phase'] != 'quarantined' or current_expiry() != 1:
        raise ValueError('kiosk-quarantine-required')


def release_account():
    """C02 calls only after its real replacement verifier and successful commit."""
    with barriers():
        identity = uid()
        account(identity)
        if read(STATE, optional=True) is not None or read(DISABLED, optional=True) is not None:
            raise ValueError('legacy-migration-not-committed')
        record = expiry_record(identity)
        if record is None:
            return
        actual = current_expiry()
        if actual != 1 and not (record['phase'] == 'releasing' and actual == record['expires']):
            raise ValueError('changed-kiosk-expiry')
        record['phase'] = 'releasing'
        save(EXPIRY, record)
        if actual != record['expires']:
            set_expiry(record['expires'])
        erase(EXPIRY)


def pam_record(record):
    if (not isinstance(record, dict) or set(record) != {'before', 'after', 'vendor', 'mode'} or
            not isinstance(record['after'], str) or
            type(record['mode']) is not int or record['mode'] < 0 or record['mode'] > 0o777 or
            record['mode'] & 0o022 or
            (record['before'] is None and not isinstance(record['vendor'], str)) or
            (record['before'] is not None and
             (not isinstance(record['before'], str) or record['vendor'] is not None))):
        raise ValueError('invalid-legacy-pam-record')


def state():
    value = read(STATE, private=True, optional=True)
    if value is None:
        return None
    saved = json.loads(value[1])
    allowed = {'schema', 'backend', 'pam', 'admission_protocol', 'kiosk_uid', 'previous_pam',
               'prelease_upgrade_boot_id', 'loaded_config_sha256', 'loaded_policy_sha256', 'removing'}
    if (not isinstance(saved, dict) or set(saved) - allowed or
            type(saved.get('schema')) is not int or saved['schema'] != 1 or
            saved.get('backend') not in ('apparmor', 'selinux') or
            not isinstance(saved.get('pam'), dict) or set(saved['pam']) != SERVICES or
            ('kiosk_uid' in saved and
             (type(saved['kiosk_uid']) is not int or saved['kiosk_uid'] <= 0)) or
            ('admission_protocol' in saved and
             (type(saved['admission_protocol']) is not int or saved['admission_protocol'] != 1)) or
            ('removing' in saved and type(saved['removing']) is not bool)):
        raise ValueError('invalid-legacy-confinement-record')
    if ('prelease_upgrade_boot_id' in saved and
            (not isinstance(saved['prelease_upgrade_boot_id'], str) or
             not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', saved['prelease_upgrade_boot_id']))):
        raise ValueError('invalid-legacy-boot')
    for key in ('loaded_config_sha256', 'loaded_policy_sha256'):
        if key in saved and (not isinstance(saved[key], str) or not DIGEST.fullmatch(saved[key])):
            raise ValueError('invalid-legacy-attestation')
    previous = saved.get('previous_pam', {})
    if not isinstance(previous, dict) or set(previous) - SERVICES:
        raise ValueError('invalid-legacy-previous-pam')
    for record in (*saved['pam'].values(), *previous.values()):
        pam_record(record)
    return saved


def original(record):
    return record['before'] if record['before'] is not None else record['vendor']


def verify_pam(saved, *, originals=False):
    for name, record in saved['pam'].items():
        value = read(PAM / name, optional=True)
        actual = value[1].decode() if value else None
        accepted = (record['before'],) if originals else (record['before'], record['after'])
        if not originals and saved.get('removing'):
            accepted += (DENIAL + original(record),)
        if not originals and name in saved.get('previous_pam', {}):
            accepted += (saved['previous_pam'][name]['after'],)
        if actual not in accepted:
            raise ValueError('modified-legacy-pam')


@contextmanager
def barriers():
    """Keep exact legacy lease inodes and current-policy labels across retries."""
    descriptors = []
    try:
        # Serialize expiry and visibility owner records with the old provisioner.
        with directory(STATE_DIRECTORY) as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Classify owned state before creating an inode: invalid state
            # must not leave a new stock-labelled lease under live SELinux.
            saved = state()
            for path in LOCKS:
                if not os.path.lexists(path):
                    if path != LOCKS[0]:
                        continue
                    # This is the same source-defined admission lease inode
                    # used by native PAM, never a new private lock protocol.
                    with directory(path.parent) as parent:
                        descriptor = os.open(path.name, os.O_RDWR | os.O_CREAT | os.O_EXCL |
                                             os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
                        os.close(descriptor)
                before = read(path, private=True)[0]
                with directory(path.parent) as parent:
                    descriptor = os.open(path.name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK |
                                         os.O_CLOEXEC, dir_fd=parent)
                descriptors.append(descriptor)
                info = os.fstat(descriptor)
                if (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino):
                    raise ValueError('replaced-legacy-lock')
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                current = path.stat(follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                    raise ValueError('replaced-legacy-lock')
                if path == LOCKS[0] and saved is not None and saved['backend'] == 'selinux':
                    # /run can lack this inode after reboot. Repair its label
                    # before any later lock or account/PAM/policy/live preflight
                    # can refuse, while the old policy still governs admission.
                    # Reassert on existing inodes too: a failed first relabel
                    # must retry without replacing the lease or adding a journal.
                    # Post-erase this uses only the distro tool and fixed path;
                    # unloaded policy naturally selects the stock label.
                    run(['/usr/sbin/restorecon', str(path)])
                    current = path.stat(follow_symlinks=False)
                    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                        raise ValueError('replaced-legacy-lock')
                elif path == LOCKS[0] and saved is None and (ROOT / 'sys/fs/selinux/enforce').exists():
                    # The package can create this lease before GDM does. Its
                    # generic var_run_t label denies xdm_t even read access.
                    # Use the stock label GDM creates here, also readable by
                    # systemd-user. Relabel only our validated, exclusively
                    # locked inode; retain legacy policy labels until commit.
                    label = b'system_u:object_r:xdm_var_run_t:s0'
                    if os.getxattr(descriptor, 'security.selinux').rstrip(b'\0') != label:
                        os.setxattr(descriptor, 'security.selinux', label)
            yield
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def mapped_generation(thread):
    for line in (thread / 'maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or Path(fields[5].removesuffix(' (deleted)')).name != 'pam_oh_no_parent_control.so':
            continue
        if fields[5].endswith(' (deleted)') or not re.fullmatch(r'[0-9a-f]+-[0-9a-f]+', fields[0]):
            raise ValueError('legacy-pam-reboot-required')
        path = Path(fields[5])
        # Native /usr/lib64 may be a root-owned distro symlink. Follow only
        # that resolved system payload, retaining exact mapped-object identity.
        read(path.resolve(strict=True))
        info = path.stat()
        try:
            mapped = (PROCESSES / thread.name / 'map_files' / fields[0]).stat()
        except FileNotFoundError:
            raise ValueError('legacy-pam-reboot-required') from None
        if (mapped.st_dev, mapped.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('legacy-pam-reboot-required')


def idle(saved, identity, *, post_erase=False):
    """Observe legacy executors without signalling them or deleting runtime state.

    After erasure, an ordinary PAM worker can retain the removed native module.
    Its mapping no longer identifies a kiosk executor. Account absence, lifetime
    leases, the pre-lease boot and UID/audit/MAC checks still protect retirement.
    """
    boot = BOOT.read_text().strip()
    if saved and (saved.get('admission_protocol') != 1 or saved.get('prelease_upgrade_boot_id') == boot):
        raise ValueError('legacy-pam-reboot-required')
    for process in PROCESSES.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            for thread in (process / 'task').iterdir():
                try:
                    status = (thread / 'status').read_text()
                    identities = [line.split()[1:] for line in status.splitlines() if line.startswith('Uid:')]
                    if len(identities) != 1 or len(identities[0]) != 4 or not all(x.isdecimal() for x in identities[0]):
                        raise ValueError('invalid-process-identity')
                    if str(identity) in identities[0] or (thread / 'loginuid').read_text().strip() == str(identity):
                        raise ValueError('kiosk-processes-active')
                    if saved and '0' in identities[0]:
                        # First preparation proves old mappings before unpack.
                        # Once its durable removal intent exists, the exact
                        # admission lease plus UID/audit/MAC checks distinguish
                        # kiosk executors from ordinary workers retaining the
                        # replaced module. Never make those workers a reboot
                        # requirement during interrupted configure retries.
                        if not post_erase and not saved.get('removing'):
                            mapped_generation(thread)
                        refreshed = [line.split()[1:] for line in (thread / 'status').read_text().splitlines()
                                     if line.startswith('Uid:')]
                        if refreshed and str(identity) in refreshed[0]:
                            raise ValueError('kiosk-processes-active')
                    if saved:
                        for attribute in ('current', 'exec'):
                            try:
                                label = (thread / 'attr' / attribute).read_text()
                            except OSError as error:
                                if attribute == 'exec' and saved['backend'] == 'apparmor' and error.errno == errno.EINVAL:
                                    continue
                                raise
                            if re.search(r'(^|[:/&])onpc(?:-kiosk-|_kiosk_)', label):
                                raise ValueError('kiosk-executors-active')
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass


def marker():
    value = read(DISABLED, private=True, optional=True)
    if value is not None and value[1] != b'removing\n':
        raise ValueError('changed-legacy-removal-marker')


def policy_material(saved, *, source=False):
    base = RETAINED if not source and (os.path.lexists(RETAINED) or os.path.lexists(CAPTURE)) else PAYLOAD
    if base == RETAINED:
        receipt = capture_record()
        capture_authority(receipt, uid(), saved)
        if receipt['phase'] != 'ready':
            raise ValueError('legacy-policy-capture-not-ready')
        verify_capture(receipt)
    path = base / ('onpc-kiosk.cil' if saved['backend'] == 'selinux' else 'onpc-kiosk.apparmor')
    contents = read(path)[1]
    config = read(base / 'config.json')[1]
    if (json.loads(config).get('backend') != saved['backend'] or
            ('loaded_config_sha256' in saved and hashlib.sha256(config).hexdigest() != saved['loaded_config_sha256']) or
            ('loaded_policy_sha256' in saved and hashlib.sha256(contents).hexdigest() != saved['loaded_policy_sha256'])):
        raise ValueError('changed-legacy-policy-payload')
    return path, contents


def capture_names(backend):
    return {'config.json', 'onpc-kiosk.cil' if backend == 'selinux' else 'onpc-kiosk.apparmor'}


def capture_record():
    value = read(CAPTURE, private=True, optional=True)
    if value is None:
        return None
    record = json.loads(value[1])
    if (not isinstance(record, dict) or
            set(record) != {'version', 'uid', 'backend', 'directory', 'phase', 'files'} or
            type(record['version']) is not int or record['version'] != 1 or
            type(record['uid']) is not int or record['uid'] <= 0 or
            record['backend'] not in ('apparmor', 'selinux') or
            record['phase'] not in ('capture', 'ready', 'retiring') or
            not isinstance(record['directory'], dict) or
            set(record['directory']) != {'device', 'inode'} or
            any(type(record['directory'][key]) is not int or record['directory'][key] < 0
                for key in ('device', 'inode')) or
            not isinstance(record['files'], dict) or
            set(record['files']) != capture_names(record['backend'])):
        raise ValueError('invalid-legacy-policy-capture')
    for member in record['files'].values():
        if (not isinstance(member, dict) or set(member) != {'sha256', 'device', 'inode'} or
                not isinstance(member['sha256'], str) or not DIGEST.fullmatch(member['sha256']) or
                not ((member['device'] is None and member['inode'] is None and record['phase'] == 'capture') or
                     all(type(member[key]) is int and member[key] >= 0 for key in ('device', 'inode')))):
            raise ValueError('invalid-legacy-policy-capture')
    return record


def capture_authority(receipt, identity, saved=None):
    if receipt is None or receipt['uid'] != identity:
        raise ValueError('changed-legacy-capture-identity')
    if saved is not None:
        if saved.get('kiosk_uid', identity) != identity or saved['backend'] != receipt['backend']:
            raise ValueError('changed-legacy-capture-identity')
        policy_name = next(name for name in receipt['files'] if name != 'config.json')
        for key, name in (('loaded_config_sha256', 'config.json'), ('loaded_policy_sha256', policy_name)):
            if key in saved and saved[key] != receipt['files'][name]['sha256']:
                raise ValueError('changed-legacy-policy-capture')


def captured_member(path, expected, *, optional=False):
    value = read(path, private=True, optional=optional)
    if value is not None and ((value[0].st_dev, value[0].st_ino) !=
                              (expected['device'], expected['inode']) or
                              hashlib.sha256(value[1]).hexdigest() != expected['sha256']):
        raise ValueError('changed-retained-policy')
    return value


def verify_capture(receipt, *, missing=False):
    with directory(RETAINED) as descriptor:
        info = os.fstat(descriptor)
        if (stat.S_IMODE(info.st_mode) != 0o700 or
                (info.st_dev, info.st_ino) !=
                (receipt['directory']['device'], receipt['directory']['inode'])):
            raise ValueError('changed-retained-policy-directory')
        if set(os.listdir(descriptor)) - set(receipt['files']):
            raise ValueError('foreign-retained-policy-content')
        for name, expected in receipt['files'].items():
            captured_member(RETAINED / name, expected, optional=missing)


def capture_policy():
    """Retain only exact rollback inputs before package unpack replaces them."""
    if not os.path.lexists(STATE_DIRECTORY):
        return
    with barriers():
        saved = state()
        if saved is None:
            return
        identity = uid()
        account(identity)
        if saved.get('kiosk_uid', identity) != identity:
            raise ValueError('changed-kiosk-identity')
        receipt = capture_record()
        if receipt is not None:
            capture_authority(receipt, identity, saved)
            if receipt['phase'] == 'ready':
                verify_capture(receipt)
                return
            if receipt['phase'] != 'capture':
                raise ValueError('legacy-policy-capture-retiring')
            verify_capture(receipt, missing=True)
        path, contents = policy_material(saved, source=True)
        config = read(PAYLOAD / 'config.json')[1]
        inputs = {'config.json': config, path.name: contents}
        with directory(STATE_DIRECTORY):
            try:
                RETAINED.mkdir(mode=0o700)
            except FileExistsError:
                pass
            with directory(RETAINED) as descriptor:
                info = os.fstat(descriptor)
                if stat.S_IMODE(info.st_mode) != 0o700:
                    raise ValueError('unsafe-retained-policy-directory')
                if receipt is None:
                    if os.listdir(descriptor):
                        raise ValueError('unowned-retained-policy-content')
                    receipt = {'version': 1, 'uid': identity, 'backend': saved['backend'],
                               'directory': {'device': info.st_dev, 'inode': info.st_ino},
                               'phase': 'capture', 'files': {
                                   name: {'sha256': hashlib.sha256(value).hexdigest(),
                                          'device': None, 'inode': None}
                                   for name, value in inputs.items()}}
                    capture_authority(receipt, identity, saved)
                    save(CAPTURE, receipt)
                for name, value in inputs.items():
                    expected = receipt['files'][name]
                    if hashlib.sha256(value).hexdigest() != expected['sha256']:
                        raise ValueError('changed-legacy-policy-capture')
                    if captured_member(RETAINED / name, expected, optional=True) is not None:
                        continue
                    # Record the independent inode before publishing its name.
                    # If interrupted before linking, the unnamed inode expires;
                    # a retry may renew it only from still-attested old inputs.
                    member = os.open('.', os.O_RDWR | os.O_TMPFILE | os.O_CLOEXEC,
                                     0o600, dir_fd=descriptor)
                    try:
                        with os.fdopen(member, 'wb', closefd=False) as stream:
                            stream.write(value)
                            stream.flush()
                            os.fsync(member)
                        member_info = os.fstat(member)
                        expected.update(device=member_info.st_dev, inode=member_info.st_ino)
                        save(CAPTURE, receipt)
                        os.link(f'/proc/self/fd/{member}', name,
                                dst_dir_fd=descriptor, follow_symlinks=True)
                        os.fsync(descriptor)
                    finally:
                        os.close(member)
                verify_capture(receipt)
                receipt['phase'] = 'ready'
                save(CAPTURE, receipt)


def retire_policy():
    """Delete only the finite captured members after legacy state is retired."""
    # Repeated remove/purge may already have retired the entire state directory.
    # Check through its pinned, validated parent so an absent path behind a
    # substituted ancestor is not mistaken for completed owned cleanup.
    with directory(STATE_DIRECTORY.parent) as parent:
        try:
            os.stat(STATE_DIRECTORY.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
    with barriers():
        receipt = capture_record()
        if receipt is None:
            if os.path.lexists(RETAINED):
                raise ValueError('unowned-retained-policy-content')
            return
        if read(STATE, optional=True) is not None:
            raise ValueError('legacy-state-still-present')
        capture_authority(receipt, uid())
        if receipt['phase'] == 'capture':
            raise ValueError('legacy-policy-capture-not-ready')
        if os.path.lexists(RETAINED):
            # Validate every remaining member before deleting any of them.
            # Only a durable retirement phase permits a previously deleted
            # member to be absent on retry after the old state is gone.
            verify_capture(receipt, missing=receipt['phase'] == 'retiring')
            receipt['phase'] = 'retiring'
            save(CAPTURE, receipt)
            for name, expected in sorted(receipt['files'].items()):
                if captured_member(RETAINED / name, expected, optional=True) is not None:
                    erase(RETAINED / name)
            with directory(STATE_DIRECTORY) as descriptor:
                info = RETAINED.stat(follow_symlinks=False)
                if (info.st_dev, info.st_ino) != (receipt['directory']['device'], receipt['directory']['inode']):
                    raise ValueError('changed-retained-policy-directory')
                RETAINED.rmdir()
                os.fsync(descriptor)
        elif receipt['phase'] != 'retiring':
            raise ValueError('missing-retained-policy-directory')
        erase(CAPTURE)


def policy(saved, *, load):
    path, contents = policy_material(saved)
    if saved['backend'] == 'selinux':
        if not load:
            modules = run(['/usr/sbin/semodule', '-l']).stdout.splitlines()
            if any(line.split() and line.split()[0] == 'onpc-kiosk' for line in modules):
                run(['/usr/sbin/semodule', '-r', 'onpc-kiosk'])
            return
    else:
        if not load and not any(line.startswith('onpc-kiosk-') for line in PROFILES.read_text().splitlines()):
            return
    run((['/usr/sbin/semodule', '-i', str(path)] if saved['backend'] == 'selinux' else
         ['/usr/sbin/apparmor_parser', '-r' if load else '-R', str(path)]))
    if read(path)[1] != contents:
        raise ValueError('legacy-policy-changed-during-operation')


def prepare():
    """Quarantine the owned identity and prepare resumable legacy retirement."""
    with barriers():
        identity = uid()
        account(identity)
        saved = state()
        marker()
        if saved is None and read(DISABLED, optional=True) is not None:
            raise ValueError('unowned-legacy-removal-marker')
        if saved is not None:
            if saved.get('kiosk_uid', identity) != identity:
                raise ValueError('changed-kiosk-identity')
            verify_pam(saved)
            # Refuse before mutation when unpack failed to retain the exact
            # source-defined rollback inputs, including for SELinux's named
            # module removal which itself needs no policy filename.
            policy_material(saved)
            if saved.get('admission_protocol') != 1:
                # First encounter records the pre-lease boot. A finite retry
                # after its natural retirement can then prove old workers gone.
                saved['admission_protocol'] = 1
                saved['prelease_upgrade_boot_id'] = BOOT.read_text().strip()
                save(STATE, saved)
        idle(saved, identity)
        quarantine(identity)
        if saved is None:
            return
        saved['kiosk_uid'] = identity
        saved['removing'] = True
        save(STATE, saved)
        write(DISABLED, b'removing\n')
        for name, record in saved['pam'].items():
            write(PAM / name, (DENIAL + original(record)).encode(), record['mode'])
        policy(saved, load=False)
        if saved['backend'] == 'selinux' and os.path.lexists(LOCKS[0]):
            run(['/usr/sbin/restorecon', '-F', str(LOCKS[0])])


def prepare_remove():
    """Failed first configuration and interrupted post-erase remain removable."""
    ownership = read(OWNERSHIP, private=True, optional=True)
    if ownership is None:
        if any(read(path, optional=True) is not None for path in (STATE, EXPIRY, DISABLED)):
            raise ValueError('unowned-kiosk-recovery-state')
        return
    try:
        pwd.getpwnam(USER)
    except KeyError:
        finish_remove()
        return
    prepare()


def restore_locked(saved):
    verify_pam(saved)
    if not saved.get('removing'):
        raise ValueError('legacy-removal-not-prepared')
    for name, record in saved['pam'].items():
        if record['before'] is None:
            erase(PAM / name)
        else:
            write(PAM / name, record['before'].encode(), record['mode'])


def restore_original_pam():
    """Restore owned originals under quarantine; retain rollback records."""
    with barriers():
        identity = uid()
        quarantined(identity)
        saved = state()
        marker()
        if saved is None and read(DISABLED, optional=True) is not None:
            raise ValueError('unowned-legacy-removal-marker')
        if saved is not None:
            if saved.get('kiosk_uid') != identity:
                raise ValueError('changed-kiosk-identity')
            idle(saved, identity)
            restore_locked(saved)


def commit_migration(replacement_ready):
    """The caller owns real C02c readiness, not fixture callback acceptance."""
    if not callable(replacement_ready):
        raise TypeError('replacement-readiness-verifier-required')
    with barriers():
        identity = uid()
        quarantined(identity)
        saved = state()
        marker()
        if saved is not None:
            if saved.get('kiosk_uid') != identity or not saved.get('removing'):
                raise ValueError('legacy-removal-not-prepared')
            verify_pam(saved, originals=True)
            idle(saved, identity)
        if replacement_ready() is not None:
            raise ValueError('replacement-verifier-must-return-none')
        verify_visibility()
        quarantined(identity)
        if state() != saved:
            raise ValueError('legacy-state-changed-during-readiness')
        if saved is not None:
            verify_pam(saved, originals=True)
        # Both deletions are retryable: an interrupted marker deletion retains
        # the authoritative record, and account expiry remains closed.
        erase(DISABLED)
        erase(STATE)


def rollback(*, release=True):
    """Reload retained policy before restoring gates; expiry stays journaled."""
    with barriers():
        identity = uid()
        account(identity)
        saved = state()
        marker()
        if saved is None and read(DISABLED, optional=True) is not None:
            raise ValueError('unowned-legacy-removal-marker')
        if saved is not None:
            if saved.get('kiosk_uid', identity) != identity:
                raise ValueError('changed-kiosk-identity')
            verify_pam(saved)
            idle(saved, identity)
            quarantine(identity)
            if not release:
                # Unpack has replaced the native module. Its old options are
                # invalid even for ordinary users, so retain vendor callbacks
                # with kiosk-only vendor-module denials, never old native gates.
                saved['removing'] = True
                save(STATE, saved)
                write(DISABLED, b'removing\n')
                for name, record in saved['pam'].items():
                    write(PAM / name, (DENIAL + original(record)).encode(), record['mode'])
                policy(saved, load=False)
                if saved['backend'] == 'selinux':
                    run(['/usr/sbin/restorecon', '-F', str(LOCKS[0]),
                         str(PAM / 'gdm-password'), str(PAM / 'systemd-user')])
                return
            policy(saved, load=True)
            if saved['backend'] == 'selinux':
                run(['/usr/sbin/restorecon', str(LOCKS[0])])
            for name, record in saved['pam'].items():
                write(PAM / name, record['after'].encode(), record['mode'])
            if saved['backend'] == 'selinux':
                run(['/usr/sbin/restorecon', str(PAM / 'gdm-password'), str(PAM / 'systemd-user')])
            saved.pop('previous_pam', None)
            if release:
                saved.pop('removing', None)
            save(STATE, saved)
            if release:
                erase(DISABLED)
        if not release:
            # Package unpack may already have replaced the old native gate
            # and launchers. Retain quarantine until configure verifies the
            # selected replacement; old PAM/policy is recovery state only.
            quarantine(identity)
            return
        record = expiry_record(identity)
        if record is not None:
            actual = current_expiry()
            if actual not in (1, record['expires']):
                raise ValueError('changed-kiosk-expiry')
            record['phase'] = 'releasing'
            save(EXPIRY, record)
            if actual != record['expires']:
                set_expiry(record['expires'])
            erase(EXPIRY)


def finish_remove():
    """Post-erase finalizer: no erased policy payload or helper is consumed."""
    if not os.path.lexists(STATE_DIRECTORY):
        return
    with barriers():
        saved = state()
        marker()
        if saved is None and read(EXPIRY, optional=True) is None and read(DISABLED, optional=True) is None:
            return
        identity = uid()
        account(identity, absent=True)
        expiry_record(identity)
        if saved is not None:
            if saved.get('kiosk_uid', identity) != identity:
                raise ValueError('changed-kiosk-identity')
            idle(saved, identity, post_erase=True)
            restore_locked(saved)
        elif read(DISABLED, optional=True) is not None:
            raise ValueError('unowned-legacy-removal-marker')
        erase(DISABLED)
        erase(STATE)
        erase(EXPIRY)


def main(arguments=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', choices=('ubuntu', 'fedora'), required=True)
    parser.add_argument('action', choices=('capture', 'prepare', 'prepare-remove', 'original-pam',
                                          'commit', 'release', 'rollback', 'configure-failed',
                                          'visibility', 'visibility-needed', 'remove'))
    args = parser.parse_args(arguments)
    if os.geteuid() != 0:
        parser.exit(1, 'kiosk-lifecycle: must run as root\n')
    try:
        if args.action == 'commit':
            import distro_pam
            commit_migration(lambda: distro_pam.runtime_ready(args.distribution))
            retire_policy()
        elif args.action == 'capture':
            capture_policy()
        elif args.action == 'remove':
            finish_remove()
            retire_policy()
        elif args.action == 'configure-failed':
            if state() is not None:
                rollback(release=False)
        elif args.action == 'rollback':
            if state() is not None:
                rollback(release=False)
            else:
                import distro_pam
                distro_pam.runtime_ready(args.distribution)
                rollback()
        elif args.action == 'visibility-needed':
            identity = uid()
            account(identity)
            cached = read(CACHE / USER, optional=True)
            needed = read(CACHE / SLOT, optional=True) is not None or (cached is not None and
                     (ATTRIBUTE in cached[2] or not visibility_position(cached[1])[2]))
            print('yes' if needed else 'no')
        else:
            {'prepare': prepare, 'prepare-remove': prepare_remove, 'original-pam': restore_original_pam, 'release': release_account,
             'visibility': visibility}[args.action]()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'kiosk-lifecycle: {error}', file=sys.stderr)
        return 1
    return 0


def visibility_position(contents):
    """Edit only the old source-defined boolean, preserving every other byte."""
    text = contents.decode('utf-8')
    if '\0' in text:
        raise ValueError('invalid-legacy-cache-encoding')
    section, groups, matches, offset, insertion = None, 0, [], 0, None
    for line in contents.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped or stripped.startswith(b'#'):
            offset += len(line)
            continue
        group = re.fullmatch(rb'\[([^\]\r\n]+)\]', stripped)
        if group:
            if section == b'User' and insertion is None:
                insertion = offset
            section = group[1]
            groups += section == b'User'
        elif section == b'User':
            key, separator, value = line.partition(b'=')
            if separator and key.strip() == b'SystemAccount':
                boolean = value.strip()
                if boolean not in (b'true', b'false'):
                    raise ValueError('invalid-legacy-cache-classification')
                start = offset + len(key) + 1 + len(value) - len(value.lstrip())
                matches.append((start, start + len(boolean), boolean == b'false'))
        offset += len(line)
    if groups != 1 or len(matches) > 1:
        raise ValueError('ambiguous-legacy-cache')
    return matches[0] if matches else (insertion if insertion is not None else len(contents), None, False)


def verify_visibility():
    """Public visibility cannot forgive an unfinished private cache recovery."""
    if read(CACHE / SLOT, optional=True) is not None:
        raise ValueError('visibility-recovery-not-settled')
    cached = read(CACHE / USER, optional=True)
    if cached is not None and (ATTRIBUTE in cached[2] or not visibility_position(cached[1])[2]):
        raise ValueError('visibility-recovery-not-settled')


def metadata(info, attributes):
    fields = [info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode),
              {key: value.hex() for key, value in attributes.items() if key != ATTRIBUTE}]
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def transaction(value):
    record = json.loads(value)
    if (not isinstance(record, dict) or set(record) != {'version', 'uid', 'device', 'inode', 'before', 'after', 'metadata'} or
            type(record['version']) is not int or record['version'] != 1 or
            any(type(record[key]) is not int or record[key] < 0 for key in ('uid', 'device', 'inode')) or
            any(not isinstance(record[key], str) or not DIGEST.fullmatch(record[key])
                for key in ('before', 'after', 'metadata'))):
        raise ValueError('invalid-legacy-visibility-transaction')
    return record


def recover_visibility(parent, identity):
    info, contents, attributes = read(CACHE / USER)
    if ATTRIBUTE in attributes:
        record = transaction(attributes[ATTRIBUTE])
        if (record['uid'] != identity or record['after'] != hashlib.sha256(contents).hexdigest() or
                record['metadata'] != metadata(info, attributes)):
            raise ValueError('changed-committed-visibility-transaction')
        descriptor = os.open(USER, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
        try:
            current = os.fstat(descriptor)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError('replaced-committed-visibility-transaction')
            os.removexattr(descriptor, ATTRIBUTE)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    pending = read(CACHE / SLOT, optional=True)
    if pending is None:
        return
    other, data, attrs = pending
    if ATTRIBUTE not in attrs:
        raise ValueError('unowned-visibility-slot')
    record = transaction(attrs[ATTRIBUTE])
    if (record['uid'] != identity or (record['device'], record['inode']) != (info.st_dev, info.st_ino) or
            record['before'] != hashlib.sha256(contents).hexdigest() or
            record['after'] != hashlib.sha256(data).hexdigest() or
            record['metadata'] != metadata(info, attributes) or record['metadata'] != metadata(other, attrs)):
        raise ValueError('changed-visibility-slot')
    erase(CACHE / SLOT)


def visibility():
    """Run once at the daemon's actual start-pre boundary, never live cache IO."""
    if read(OWNERSHIP, private=True, optional=True) is None:
        return
    identity = uid()
    account(identity)
    cached = read(CACHE / USER, optional=True)
    if cached is None:
        if read(CACHE / SLOT, optional=True) is not None:
            raise ValueError('orphaned-visibility-slot')
        return
    info, before, attributes = cached
    start, end, visible = visibility_position(before)
    if visible and ATTRIBUTE not in attributes and read(CACHE / SLOT, optional=True) is None:
        return
    status = run(['systemctl', 'show', '--property=ActiveState,SubState,MainPID', 'accounts-daemon.service'])
    observed = dict(line.split('=', 1) for line in status.stdout.splitlines() if '=' in line)
    if observed != {'ActiveState': 'activating', 'SubState': 'start-pre', 'MainPID': '0'}:
        raise ValueError('visibility-requires-accountsservice-start-pre')
    with directory(CACHE) as parent:
        recover_visibility(parent, identity)
        info, before, attributes = read(CACHE / USER)
        start, end, visible = visibility_position(before)
        if visible:
            return
        separator = b'' if start == 0 or before[start - 1:start] == b'\n' else b'\n'
        after = (before[:start] + separator + b'SystemAccount=false\n' + before[start:] if end is None else
                 before[:start] + b'false' + before[end:])
        record = {'version': 1, 'uid': identity, 'device': info.st_dev, 'inode': info.st_ino,
                  'before': hashlib.sha256(before).hexdigest(), 'after': hashlib.sha256(after).hexdigest(),
                  'metadata': metadata(info, attributes)}
        descriptor = os.open('.', os.O_RDWR | os.O_TMPFILE | os.O_CLOEXEC, 0o600, dir_fd=parent)
        try:
            os.fchown(descriptor, info.st_uid, info.st_gid)
            os.fchmod(descriptor, stat.S_IMODE(info.st_mode))
            for name, value in attributes.items():
                os.setxattr(descriptor, name, value)
            os.setxattr(descriptor, ATTRIBUTE, json.dumps(record, sort_keys=True).encode())
            with os.fdopen(descriptor, 'wb', closefd=False) as stream:
                stream.write(after)
                stream.flush()
                os.fsync(descriptor)
            current = read(CACHE / USER)
            if ((current[0].st_dev, current[0].st_ino, current[1], current[2], metadata(current[0], current[2])) !=
                    (info.st_dev, info.st_ino, before, attributes, metadata(info, attributes))):
                raise ValueError('visibility-source-changed')
            os.link(f'/proc/self/fd/{descriptor}', SLOT, dst_dir_fd=parent, follow_symlinks=True)
            os.fsync(parent)
            os.replace(SLOT, USER, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
            os.removexattr(descriptor, ATTRIBUTE)
            os.fsync(descriptor)
            saved = read(CACHE / USER)
            if saved[1] != after or saved[2] != attributes or metadata(saved[0], saved[2]) != metadata(info, attributes):
                raise ValueError('visibility-readback-failed')
        finally:
            # A published slot/committed xattr is intentionally retained on
            # interruption. Its exact inode/UID/digests authorize the retry.
            os.close(descriptor)
