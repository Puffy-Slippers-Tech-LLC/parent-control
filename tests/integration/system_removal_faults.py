"""Finite installed removal faults; all mounts have exact, serial ownership.

Fixtures live inside the controller's already allocated guest private payload.
No policy, package script, shared executable bytes or host state is rewritten.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import tempfile

import system_guest as guest


OWNER_UID = 0
TOOLS = {'usermod': Path('/usr/sbin/usermod'),
         'deluser': Path('/usr/sbin/deluser'),
         'userdel': Path('/usr/sbin/userdel'),
         'distro-pam': Path('/usr/libexec/oh-no-parent-control-distro-pam')}
SBIN = Path('/usr/sbin')
BIN = Path('/usr/bin')
WITNESS = b'onpc-removal-fault:exact-native-invocation-refused\n'
RELEASE_WITNESS = b'onpc-release-gate:exact-native-invocation-paused\n'
INTERRUPTION_VARIANTS = ('denial-publication', 'pam-restoration', 'account-finalization')
# The removed private MAC unload has no fresh-install action to intercept.
# Its installed case ID remains reserved in the controller inventory.
RETIRED_VARIANTS = ('mac-unload',)


def require(condition, reason):
    guest.require(condition, 'removal-fault:' + reason)


def parents(path):
    for parent in path.parents:
        info = parent.lstat()
        # The guarded controller places its private guest allocation beneath
        # this fixed distro scratch ancestor. Its sticky bit protects child
        # names; every allocation/fixture ancestor below it remains private.
        if (parent == Path('/var/tmp') and stat.S_ISDIR(info.st_mode) and
                info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o1777):
            continue
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == OWNER_UID and
                not info.st_mode & 0o022, 'unsafe-parent')


def metadata(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_gid,
            info.st_mode, info.st_nlink)


def alias_identity(path):
    """Fedora's distribution-owned merged sbin alias is the only exception."""
    parents(path)
    info = path.lstat()
    target = os.readlink(path) if stat.S_ISLNK(info.st_mode) else None
    require(path == SBIN and stat.S_ISLNK(info.st_mode) and
            info.st_uid == info.st_gid == OWNER_UID and target == 'bin',
            'unsafe-native-tool-alias')
    return metadata(info) + (target,)


def native_tool(name):
    tool = TOOLS[name]
    if tool.parent == SBIN and SBIN.is_symlink():
        return BIN / tool.name, ((SBIN, alias_identity(SBIN)),)
    return tool, ()


def identity(path, *, directory=False, owner=None, links=1):
    # Writable fixture files still require one link. A native read-only mount
    # target may explicitly pin its observed count; never mutate that inode.
    parents(path)
    info = path.lstat()
    require((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) and
            info.st_uid == (OWNER_UID if owner is None else owner) and
            not info.st_mode & 0o022 and (directory or info.st_nlink == links),
            'unsafe-target')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC |
                 (os.O_DIRECTORY if directory else 0))
    try:
        value = pinned_identity(fd, directory=directory)
        require(metadata(os.fstat(fd)) == metadata(info) == metadata(path.lstat()) and
                value[:6] == metadata(info), 'target-changed-during-read')
        return value
    finally:
        os.close(fd)


def pinned_identity(fd, *, directory=False):
    info = os.fstat(fd)
    attrs = tuple((name, os.getxattr(fd, name)) for name in sorted(os.listxattr(fd)))
    contents = () if directory else (os.pread(fd, info.st_size + 1, 0),)
    return metadata(info) + (attrs,) + contents


def fault_command(variant):
    """Match the complete current lifecycle command, never a removed helper."""
    require(variant in INTERRUPTION_VARIANTS, 'unknown-variant')
    fedora = guest.package_path().suffix == '.rpm'
    distribution = 'fedora' if fedora else 'ubuntu'
    if variant == 'denial-publication':
        name, arguments = 'usermod', [('--expiredate', '1', 'oh-no-parent-control')]
    elif variant == 'account-finalization':
        name, arguments = ('userdel' if fedora else 'deluser'), [('oh-no-parent-control',)]
    else:
        name = 'distro-pam'
        arguments = [('--distribution', distribution, action) for action in ('remove', 'restore')]
    tool, aliases = native_tool(name)
    return tool, aliases, arguments


def wrapper_source(original, witness, arguments, *, hold_seconds=0, resume=None):
    """One exclusive witness per exact command; all other arguments delegate."""
    require(arguments and all(isinstance(value, str) for value in arguments),
            'invalid-native-arguments')
    require(type(hold_seconds) is int and 0 <= hold_seconds <= 1, 'invalid-hold')
    quote = shlex.quote
    receipt = RELEASE_WITNESS if resume is not None else WITNESS
    if resume is None:
        action = (f'    sleep {hold_seconds}\n' if hold_seconds else '') + '    exit 79\n'
    else:
        # Pause only this exact native release, then execute the unchanged
        # command. A lost observer fails finitely instead of hanging installation.
        # Publish readiness only after the witness writer has closed its file.
        action = ('    (set -C; umask 077; '
                  f': > {quote(str(witness) + ".ready")})\n'
                  '    remaining=300\n'
                  f'    while [ ! -f {quote(str(resume))} ] && [ "$remaining" -gt 0 ]; do\n'
                  '        sleep 0.1\n'
                  '        remaining=$((remaining - 1))\n'
                  '    done\n'
                  f'    [ -f {quote(str(resume))} ] || exit 79\n')
    return ('#!/bin/sh\nset -eu\n'
            f'if [ "$#" -eq {len(arguments)} ] && ' +
            ' && '.join(f'[ "${{{index}}}" = {quote(value)} ]'
                        for index, value in enumerate(arguments, 1)) + '; then\n' +
            '    (set -C; umask 077; '
            f'printf %s {quote(receipt.decode())} > {quote(str(witness))})\n'
            f'    printf %s {quote(receipt.decode())} >&2\n'
            + action + 'fi\n'
            f'exec {quote(str(original))} "$@"\n')


class Fault:
    def __init__(self, variant, path, expected, *, directory=False, owner=None,
                 witness=None, wrapper=None, artifacts=(), aliases=(), witnesses=(),
                 resume=None):
        self.variant, self.path, self.expected = variant, path, expected
        self.directory, self.owner = directory, owner
        self.witness, self.wrapper = witness, wrapper
        self.artifacts = artifacts
        self.aliases = aliases
        self.witnesses = witnesses or ((witness,) if witness is not None else ())
        self.resume_path = resume
        self.ready_path = Path(str(witness) + '.ready') if resume is not None else None
        self.triggered = {}

    def resume(self):
        """Release our private gate before joining its owned installer."""
        require(self.resume_path is not None, 'missing-resume-path')
        self.verify_artifacts()
        fd = os.open(self.resume_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        os.close(fd)
        self.triggered[self.resume_path] = identity(self.resume_path)

    def verify_artifacts(self):
        for path, expected in self.aliases:
            require(alias_identity(path) == expected, 'native-tool-alias-changed')
        for path, expected in self.artifacts:
            require(identity(path) == expected, 'fixture-identity-changed')
        for path, expected in self.triggered.items():
            require(identity(path) == expected, 'trigger-witness-changed')

    def verify_triggered(self):
        self.verify_artifacts()
        require(self.witnesses and self.wrapper is not None, 'missing-witness-identity')
        require(identity(self.path) == self.wrapper, 'wrapper-changed')
        if self.ready_path is not None:
            ready = identity(self.ready_path)
            require(stat.S_IMODE(ready[4]) == 0o600 and ready[-1] == b'', 'unsafe-ready-witness')
            self.triggered[self.ready_path] = ready
        for witness in self.witnesses:
            value = identity(witness)
            receipt = RELEASE_WITNESS if self.resume_path is not None else WITNESS
            require(stat.S_IMODE(value[4]) == 0o600 and value[-1] == receipt,
                    'exact-native-invocation-not-observed')
            self.triggered[witness] = value


@contextmanager
def mounted_fault(fault, source, record, *, readonly=False):
    """Hold the original inode and refuse cleanup after any ownership change."""
    from system_removal import mount_inventory
    namespace, before = mount_inventory()
    require(not any(row[0][4] == str(fault.path) for row in before.values()),
            'preexisting-mount')
    fd = os.open(fault.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC |
                 (os.O_DIRECTORY if fault.directory else 0))
    owned = None
    visible = fault.wrapper if fault.wrapper is not None else fault.expected
    try:
        require(pinned_identity(fd, directory=fault.directory) == fault.expected,
                'target-changed-before-mount')
        try:
            try:
                guest.run(['mount', '--bind', str(source), str(fault.path)], timeout=30)
            finally:
                # Even a failing mount command can have completed its syscall.
                # Adopt only a new row in the original namespace whose visible
                # inode and pinned original are still exactly ours.
                current, rows = mount_inventory()
                candidates = {key: row for key, row in rows.items()
                              if key not in before and row[0][4] == str(fault.path)}
                if candidates:
                    require(current == namespace and len(candidates) == 1 and
                            identity(fault.path, directory=fault.directory, owner=fault.owner) == visible and
                            pinned_identity(fd, directory=fault.directory) == fault.expected,
                            'mount-not-attributable')
                    owned = candidates
            require(owned is not None, 'mount-not-attributable')
            if readonly:
                try:
                    guest.run(['mount', '-o', 'remount,bind,ro', str(fault.path)], timeout=30)
                finally:
                    # A failed remount may still have changed its options.
                    # Keep only the same recorded mount identity, including
                    # its source and namespace, before attempting cleanup.
                    current, rows = mount_inventory()
                    updated = {key: rows[key] for key in owned if key in rows}
                    require(current == namespace and len(updated) == 1 and
                            all(updated[key][0][:5] == row[0][:5] and
                                updated[key][1] == row[1] for key, row in owned.items()),
                            'readonly-mount-changed')
                    owned = updated
                require(all('ro' in row[0][5].split(',') for row in owned.values()),
                        'mount-not-readonly')
            record('onpc.interruption.fault', json.dumps({
                'variant': fault.variant, 'namespace': namespace, 'mounts': owned,
                'device': fault.expected[0], 'inode': fault.expected[1]}, sort_keys=True))
            yield fault
        finally:
            # No attributable mount means no authority over an unknown row.
            if owned is not None:
                fault.verify_artifacts()
                current, rows = mount_inventory()
                matches = {key: row for key, row in rows.items() if row[0][4] == str(fault.path)}
                require(current == namespace and matches == owned and
                        identity(fault.path, directory=fault.directory, owner=fault.owner) == visible and
                        pinned_identity(fd, directory=fault.directory) == fault.expected,
                        'cleanup-ownership-changed')
                guest.run(['umount', '--', str(fault.path)], timeout=30)
                current, rows = mount_inventory()
                require(current == namespace and
                        not any(row[0][4] == str(fault.path) for row in rows.values()) and
                        identity(fault.path, directory=fault.directory, owner=fault.owner,
                                 links=fault.expected[5]) == fault.expected,
                        'cleanup-not-verified')
    finally:
        os.close(fd)


@contextmanager
def interruption_fault(variant, record):
    """Yield an owned finite mount; caller verifies product protection before exit."""
    guest.guard()
    tool, aliases, commands = fault_command(variant)
    with native_fixture(variant, tool, aliases, commands, record) as fault:
        yield fault


@contextmanager
def expiry_release_gate(expires, record):
    """Keep real native expiry closed until its independent observer finishes."""
    guest.guard()
    require(expires is None or (type(expires) is int and expires >= 0 and expires != 1),
            'invalid-release-expiry')
    tool, aliases = native_tool('usermod')
    commands = [('--expiredate', '-1' if expires is None else str(expires),
                 'oh-no-parent-control')]
    with native_fixture('expiry-release', tool, aliases, commands, record, pause=True) as fault:
        yield fault


def record_reinstall_access(fault, record):
    """Distinguish MAC, native admission and mount refusal without changing them."""
    observation = {}
    try:
        observation['selinux_audit'] = guest.access_audit()
    except Exception as error:
        observation['selinux_audit'] = {'error': type(error).__name__}
    # Match audit inode/context coordinates to the copied tool and its
    # ancestors. Retain no account names, audit command lines or PROCTITLE.
    entries = []
    for path in (fault.original, *fault.original.parents):
        entry = {'depth': len(entries)}
        try:
            info = path.lstat()
            entry.update(device=info.st_dev, inode=info.st_ino, uid=info.st_uid,
                         gid=info.st_gid, mode=stat.S_IMODE(info.st_mode),
                         noexec=bool(os.statvfs(path).f_flag & os.ST_NOEXEC))
            label = os.getxattr(path, 'security.selinux', follow_symlinks=False)
            label = label.rstrip(b'\0').decode('ascii')
            entry['selinux'] = label if re.fullmatch(r'[a-zA-Z0-9_:.,-]{1,256}', label) else 'invalid'
        except OSError as error:
            entry['errno'] = error.errno
        except UnicodeError:
            entry['selinux'] = 'invalid'
        entries.append(entry)
    observation['original_and_ancestors'] = entries
    reader = shutil.which('ausearch')
    native = {'status': 'reader-unavailable'}
    if reader is not None:
        try:
            commands = guest.Commands()
            raw = commands.run([reader, '--input-logs', '--start', 'boot',
                                '--file', str(fault.original), '--message', 'FANOTIFY', '--raw'],
                               timeout=30, check=False, merge_stderr=False)
            rows = []
            for line in raw.decode(errors='replace').splitlines():
                header = re.match(r'(?:node=\S+ )?type=FANOTIFY '
                                  r'msg=audit\(([0-9.]+):([0-9]+)\):', line)
                if header is None:
                    continue
                row = {'epoch': header[1], 'serial': header[2]}
                for field in ('pid', 'uid', 'resp', 'fan_type', 'fan_info',
                              'subj_trust', 'obj_trust'):
                    match = re.search(r'\b' + field + r'=([0-9a-fA-Fx]+)\b', line)
                    if match:
                        row[field] = match[1]
                rows.append(row)
            native = {'returncode': commands.last_returncode, 'events': rows[-20:],
                      'truncated': len(rows) > 20}
        except Exception as error:
            native = {'error': type(error).__name__}
    observation['original_native_admission_audit'] = native
    record('onpc.rpm-posterase.reinstall-access', json.dumps(observation, sort_keys=True))


@contextmanager
def native_fixture(variant, tool, aliases, commands, record, *, pause=False):
    """Reuse the same pinned native-tool mount and serial cleanup for both fixtures."""
    expected = identity(tool)
    private = guest.PAYLOAD / 'private'
    info = private.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == OWNER_UID and
            stat.S_IMODE(info.st_mode) == 0o700, 'unsafe-private-root')
    parents(private)
    # This is a child of the already retained guest allocation, not another
    # storage root. Keep its evidence for the controller's owned final cleanup.
    fixture = Path(tempfile.mkdtemp(prefix='removal-' + variant + '-', dir=private))
    original, wrapper = (fixture / name for name in ('original', 'wrapper'))
    resume = fixture / 'resume' if pause else None
    witnesses = tuple(fixture / ('triggered-' + str(index) + '.txt') for index in range(len(commands)))
    shutil.copy2(tool, original, follow_symlinks=False)
    require(identity(tool) == expected and original.read_bytes() == expected[-1],
            'native-tool-changed-during-copy')
    # Compose bounded exact matches; a nonmatching command delegates through
    # the next match and eventually to the untouched original native tool.
    source = f'exec {shlex.quote(str(original))} "$@"\n'
    for witness, arguments in reversed(tuple(zip(witnesses, commands))):
        source = wrapper_source(original, witness, arguments, hold_seconds=1,
                                resume=resume).replace(
            f'exec {shlex.quote(str(original))} "$@"\n', source)
    wrapper.write_text(source)
    shutil.copystat(tool, wrapper, follow_symlinks=False)
    native_attrs = dict(expected[6])
    wrapper_attrs = native_attrs.copy()
    if 'security.selinux' in native_attrs:
        # This fixture is a shell, not the native account tool. Giving it
        # useradd_exec_t enters useradd_t too early; that domain cannot then
        # exec the copied useradd_exec_t binary (execute_no_trans is denied).
        # Use the installed interpreter's label for the wrapper, retaining the
        # native label on the delegate so its normal transition happens once.
        shell_attrs = dict(identity(Path('/bin/sh').resolve(strict=True))[6])
        require('security.selinux' in shell_attrs, 'shell-label-missing')
        wrapper_attrs['security.selinux'] = shell_attrs['security.selinux']
        os.setxattr(wrapper, 'security.selinux', wrapper_attrs['security.selinux'],
                    follow_symlinks=False)
    # Compare the complete xattr sets, including the wrapper's selected label.
    # An unrelated exec denial still cannot stand in for an exact fault hit.
    require(identity(tool) == expected and dict(identity(original)[6]) == native_attrs and
            dict(identity(wrapper)[6]) == wrapper_attrs, 'native-tool-xattr-not-preserved')
    require(stat.S_IMODE(wrapper.stat().st_mode) == stat.S_IMODE(expected[4]),
            'native-tool-mode-not-preserved')
    wrapper_identity = identity(wrapper)
    fault = Fault(variant, tool, expected, witness=witnesses[0], witnesses=witnesses,
                  wrapper=wrapper_identity,
                  artifacts=((original, identity(original)), (wrapper, wrapper_identity)),
                  aliases=aliases, resume=resume)
    fault.original = original
    record('onpc.interruption.native-fixture', json.dumps({
        'tool': str(tool), 'commands': commands,
        'wrapper_sha256': hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest()}, sort_keys=True))
    with mounted_fault(fault, wrapper, record):
        yield fault
