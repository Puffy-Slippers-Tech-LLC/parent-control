#!/usr/bin/python3 -I
"""Owned Ubuntu/Fedora PAM transaction for the release-based kiosk runtime.

Uses pam-auth-update's local-edit handling and the existing Fedora authselect
owner. Does not inspect unrelated modules, included stacks or vendor callbacks.
The lifecycle keeps its own account quarantine/removal lease while calling us.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

PAM = Path('/etc/pam.d')
BASELINE = Path('/var/lib/oh-no-parent-control/malcontent-pam-before-install')
LOGIN_CHECK = Path('/usr/libexec/oh-no-parent-control-login-check')
TIME_CHECK = Path('/usr/libexec/oh-no-parent-control-session-limit-check')
FEDORA_HELPER = Path('/usr/libexec/oh-no-parent-control-fedora-pam')
SELINUX_ENFORCE = Path('/sys/fs/selinux/enforce')
SSH_POLICY = Path('/usr/share/oh-no-parent-control/pam/onpc-ssh-accounts.cil')
SSH_POLICY_RECEIPT = Path('/var/lib/oh-no-parent-control/selinux-ssh-accounts')
# Receipt store names refer to the default root fixed by the Fedora adapter.
SSH_POLICY_STORE = 'targeted'
SSH_POLICY_PRIORITY = 200
POLICY_CHECKSUM = re.compile(r'sha256:[a-f0-9]{64}')
MODULES = {
    'ubuntu': Path('/usr/lib/x86_64-linux-gnu/security/pam_oh_no_parent_control.so'),
    'fedora': Path('/usr/lib64/security/pam_oh_no_parent_control.so'),
}
FILES = {
    'ubuntu': ('common-auth', 'common-account', 'common-password',
               'common-session', 'common-session-noninteractive'),
    'fedora': ('system-auth', 'password-auth', 'fingerprint-auth', 'smartcard-auth'),
}
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}
PROFILES = ('oh-no-parent-control-session-limits', 'oh-no-parent-control-kiosk-only')


def run(arguments, *, input=None):
    # Keep helper refusal reasons visible in the native package transaction.
    return subprocess.run(arguments, input=input, check=True, stdout=subprocess.PIPE,
                          text=True, timeout=60, env=ENV)


def secure_ssh_policy_path(path, *, directory=False):
    info = path.lstat()
    if directory:
        valid = stat.S_ISDIR(info.st_mode) and not info.st_mode & 0o022
    else:
        valid = stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    if info.st_uid != 0 or not valid:
        raise ValueError('unsafe SSH SELinux policy receipt path')


def read_ssh_policy_receipt():
    try:
        secure_ssh_policy_path(SSH_POLICY_RECEIPT)
    except FileNotFoundError:
        return None
    fields = SSH_POLICY_RECEIPT.read_text(encoding='ascii').split()
    if (len(fields) == 3 and fields[:2] == [SSH_POLICY_STORE, 'ready']
            and POLICY_CHECKSUM.fullmatch(fields[2])):
        return 'ready', (fields[2],)
    if len(fields) == 4 and fields[:2] == [SSH_POLICY_STORE, 'pending'] and all(
            value == '-' or POLICY_CHECKSUM.fullmatch(value) for value in fields[2:]):
        return 'pending', tuple(value for value in fields[2:] if value != '-')
    raise ValueError('invalid SSH SELinux policy receipt')


def write_ssh_policy_receipt(directory_fd, phase, *checksums):
    # Publish both possible store contents before changing policy. Keep the
    # receipt pending until the native commit has returned after policy reload.
    fd, temporary = tempfile.mkstemp(dir=SSH_POLICY_RECEIPT.parent, prefix='.ssh-policy-')
    pending = Path(temporary)
    try:
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            fields = [SSH_POLICY_STORE, phase, *(value or '-' for value in checksums)]
            stream.write(' '.join(fields) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        pending.replace(SSH_POLICY_RECEIPT)
        os.fsync(directory_fd)
    finally:
        pending.unlink(missing_ok=True)


def ssh_policy_store_active():
    if not SELINUX_ENFORCE.exists():
        return False
    from fedora_selinux import configured_store

    return configured_store() == SSH_POLICY_STORE


def ssh_policy_transaction(*, writable, reload):
    from fedora_selinux import module_store

    return module_store(SSH_POLICY_STORE, SSH_POLICY.stem, SSH_POLICY_PRIORITY,
                        writable=writable, reload=reload)


@contextmanager
def ssh_policy_action(action, *, state_locked=False):
    directory = SSH_POLICY_RECEIPT.parent
    try:
        secure_ssh_policy_path(directory, directory=True)
    except FileNotFoundError:
        if action != 'remove' and ssh_policy_store_active():
            raise
        yield
        return
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        # The native lock covers policy writers. This lock also covers our own
        # receipt after libsemanage releases the transaction on commit.
        if not state_locked:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        receipt = read_ssh_policy_receipt()
        if action == 'remove' and receipt is None:
            yield
            return
        active = ssh_policy_store_active()
        if receipt is None and not active:
            yield
            return
        phase, checksums = receipt or (None, ())
        with ssh_policy_transaction(writable=action != 'verify', reload=active) as store:
            installed, conflict = store.inventory()
            if installed is not None and installed not in checksums:
                raise ValueError('SSH SELinux policy at the package priority has unknown ownership')
            if action == 'remove':
                # Keep the native lock while authselect restores original PAM.
                yield
                write_ssh_policy_receipt(descriptor, 'pending', installed, None)
                if installed is not None:
                    store.remove()
                store.commit()
                SSH_POLICY_RECEIPT.unlink()
                os.fsync(descriptor)
                return

            if conflict:
                raise ValueError('SSH SELinux policy was disabled or has a local same-name module')
            data = SSH_POLICY.read_bytes()
            expected = 'sha256:' + hashlib.sha256(data).hexdigest()
            if phase != 'ready' or installed != expected:
                if action == 'verify':
                    raise ValueError('SSH SELinux policy is not active')
                write_ssh_policy_receipt(descriptor, 'pending', installed, expected)
                if installed != expected:
                    store.install(data)
                store.commit()
                write_ssh_policy_receipt(descriptor, 'ready', expected)
            yield
    finally:
        os.close(descriptor)


def private_baseline(*, optional=False):
    """Read only the existing one-line Debian selection authority."""
    try:
        info = BASELINE.lstat()
    except FileNotFoundError:
        if optional:
            return None
        raise
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or (info.st_mode & 0o7777) != 0o600:
        raise ValueError('unsafe original PAM selection')
    value = BASELINE.read_text()
    if value not in ('enabled\n', 'disabled\n'):
        raise ValueError('invalid original PAM selection')
    return value.strip()


def capture_baseline():
    if private_baseline(optional=True) is not None:
        return
    info = BASELINE.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('unsafe original PAM selection directory')
    output = run(['/usr/bin/debconf-communicate', 'libpam-runtime'],
                 input='GET libpam-runtime/profiles\n').stdout
    if not output.startswith('0 '):
        raise ValueError('cannot capture original PAM selection')
    selected = {value.strip() for value in output[2:].strip().split(',')}
    choice = 'enabled\n' if 'malcontent' in selected else 'disabled\n'
    # Publish complete bytes without replacing an existing selection authority.
    # A failed write leaves no partial baseline for a later retry to misread.
    descriptor, temporary = tempfile.mkstemp(prefix='.pam-choice-', dir=BASELINE.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(choice)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, BASELINE, follow_symlinks=False)
    finally:
        os.unlink(temporary)
    descriptor = os.open(BASELINE.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def time_policy(distribution):
    """The two finite owned sequences whose relative jumps we must preserve."""
    group = 'sudo' if distribution == 'ubuntu' else 'wheel'
    return {
        'auth': [
            'auth [success=2 default=ignore] pam_succeed_if.so quiet user = oh-no-parent-control',
            f'auth [success=1 default=ignore] pam_succeed_if.so quiet user ingroup {group}',
            'auth required pam_oh_no_parent_control.so',
        ],
        'account': [
            'account [success=5 default=ignore] pam_succeed_if.so quiet service = systemd-user',
            'account [success=4 default=ignore] pam_succeed_if.so quiet user = oh-no-parent-control',
            f'account [success=3 default=ignore] pam_succeed_if.so quiet user ingroup {group}',
            'account [success=2 default=ignore] pam_exec.so quiet quiet_log /usr/libexec/oh-no-parent-control-session-limit-check',
            'account required pam_malcontent.so',
            'account required pam_oh_no_parent_control.so',
        ],
    }


def logical_lines(text):
    """Normalize PAM physical lines without interpreting modules or includes.

    Linux-PAM's pam_line.c replaces a trailing backslash with a space (also
    allowing trailing spaces/tabs), then trims at the first '#'. A comment
    ends that logical line even when its physical line ended in a backslash.
    Keep the prefix before '#': a wrong module prefix cannot become our module.
    """
    result, pending = [], ''
    for physical in text.splitlines(keepends=True):
        tail = physical.rstrip(' \t\n')
        continued = tail.endswith('\\')
        if continued:
            physical = tail[:-1] + ' '
        pending += physical.split('#', 1)[0].lstrip(' \t')
        if continued and '#' not in physical:
            continue
        normalized = ' '.join(pending.split())
        if normalized:
            result.append(normalized)
        pending = ''
    if pending:
        raise ValueError('unterminated PAM continuation')
    return result


def verify_time_policy(distribution, files):
    """Check only owned jumps/targets at configuration time, never at login.

    Integer jumps count entries of the same PAM type. Use normalized logical
    lines, ignore other types, then require our small block to stay contiguous.
    Quiet '-type' entries count too; '@include' is an
    opaque barrier because it can add entries of any type. Unrelated native
    callbacks before/after it remain opaque: this is not an interpreter or
    inventory of the vendor stack.
    """
    for kind, expected in time_policy(distribution).items():
        stacks = [files[f'common-{kind}']] if distribution == 'ubuntu' else files.values()
        for stack in stacks:
            entries = [line for line in stack
                       if line.partition(' ')[0] in (kind, '-' + kind, '@include')]
            if not any(entries[index:index + len(expected)] == expected for index in range(len(entries))):
                raise ValueError('PAM time policy was not activated; preserving local configuration')


def verify(distribution, *, installed):
    """Verify our direct required entries, accepting unrelated native content.

    This checks effective distro output, not the staged input profiles. It is
    deliberately not an interpreter of every administrator/vendor PAM branch.
    Those branches keep their original ordering and denial authority.
    """
    files = {name: logical_lines((PAM / name).read_text()) for name in FILES[distribution]}
    active = '\n'.join(line for stack in files.values() for line in stack)
    if not installed:
        if re.search(r'pam_oh_no_parent_control(?:\.so)?|/usr/libexec/oh-no-parent-control-', active):
            raise ValueError('PAM references remain; preserving the module')
        return
    groups = ([files['common-auth']], [files['common-account']],
              [files['common-session'], files['common-session-noninteractive']]) if distribution == 'ubuntu' else (
                  list(files.values()), list(files.values()), list(files.values()))
    for kind, stacks, argument in zip(('auth', 'account', 'session'), groups, ('', 'kiosk', 'kiosk')):
        # Account/session require exactly the kiosk option; no fallback mode.
        required = f'{kind} required pam_oh_no_parent_control.so' + (f' {argument}' if argument else '')
        if any(required not in stack for stack in stacks):
            raise ValueError('PAM integration was not activated; preserving local configuration')
    if '/usr/libexec/oh-no-parent-control-login-check' in active:
        raise ValueError('legacy external PAM login dispatch remains')
    verify_time_policy(distribution, files)


def runtime_ready(distribution, *, state_locked=False):
    """Side-effect-free migration callback for the active installed integration.

    C02 installs the prepared module/helper/account/session assets, restores the
    original gdm-password/systemd-user, and activates shared profiles first.
    The migration callback already holds the state-directory lock. Standalone
    verification acquires it here before reading the Fedora policy receipt.
    This checks installed payload, effective shared PAM output and Fedora policy;
    it supplies no real GDM login, next-exec or administrator-policy proof.
    """
    verify(distribution, installed=True)
    if distribution == 'fedora':
        with ssh_policy_action('verify', state_locked=state_locked):
            pass
    for path, executable in ((MODULES[distribution], False), (LOGIN_CHECK, True), (TIME_CHECK, True)):
        info = path.stat()
        # Distro-owned lib directories may be canonical aliases. Trust their
        # installed regular payload; do not inventory unrelated directories.
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or (
                executable and not info.st_mode & 0o111):
            raise ValueError('required PAM payload unavailable')


def configure(distribution, action):
    if distribution not in FILES or action not in ('install', 'restore', 'remove'):
        raise ValueError('unsupported PAM transaction')
    if distribution == 'fedora':
        # Preserve the maintained owner: original profile/features, without-nullok
        # policy, file digests, modified-profile refusal and owned removal/retry.
        with ssh_policy_action('remove' if action == 'remove' else 'install'):
            run([str(FEDORA_HELPER), 'remove' if action == 'remove' else 'install'])
            verify(distribution, installed=action != 'remove')
        return
    if action == 'install':
        capture_baseline()
    baseline = private_baseline(optional=action == 'remove')
    arguments = ['/usr/sbin/pam-auth-update', '--package']
    if action == 'remove':
        for profile in PROFILES:
            arguments.extend(('--remove', profile))
        if baseline is not None:
            arguments.extend(('--enable' if baseline == 'enabled' else '--disable', 'malcontent'))
    else:
        arguments.extend(('--disable', 'malcontent'))
        for profile in PROFILES:
            arguments.extend(('--enable', profile))
    # Never --force: an administrator's local edit is not ours to replace.
    run(arguments, input='')
    verify(distribution, installed=action != 'remove')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', choices=tuple(FILES), required=True)
    parser.add_argument('action', choices=('install', 'restore', 'remove', 'verify'))
    arguments = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, 'distro-pam: must run as root\n')
    if arguments.distribution == 'fedora':
        sys.path.insert(0, '/usr/lib/oh-no-parent-control/lifecycle')
    try:
        if arguments.action == 'verify':
            runtime_ready(arguments.distribution)
        else:
            configure(arguments.distribution, arguments.action)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'distro-pam: {error}\n')
