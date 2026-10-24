"""Finite installed removal faults; all mounts have exact, serial ownership.

Fixtures live inside the controller's already allocated guest private payload.
No policy, package script, shared executable bytes or host state is rewritten.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
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


def wrapper_source(original, witness, arguments, *, hold_seconds=0):
    """One exclusive witness per exact command; all other arguments delegate."""
    require(arguments and all(isinstance(value, str) for value in arguments),
            'invalid-native-arguments')
    require(type(hold_seconds) is int and 0 <= hold_seconds <= 1, 'invalid-hold')
    quote = shlex.quote
    return ('#!/bin/sh\nset -eu\n'
            f'if [ "$#" -eq {len(arguments)} ] && ' +
            ' && '.join(f'[ "${{{index}}}" = {quote(value)} ]'
                        for index, value in enumerate(arguments, 1)) + '; then\n' +
            '    (set -C; umask 077; '
            f'printf %s {quote(WITNESS.decode())} > {quote(str(witness))})\n'
            + (f'    sleep {hold_seconds}\n' if hold_seconds else '') +
            '    exit 79\nfi\n'
            f'exec {quote(str(original))} "$@"\n')


class Fault:
    def __init__(self, variant, path, expected, *, directory=False, owner=None,
                 witness=None, wrapper=None, artifacts=(), aliases=(), witnesses=()):
        self.variant, self.path, self.expected = variant, path, expected
        self.directory, self.owner = directory, owner
        self.witness, self.wrapper = witness, wrapper
        self.artifacts = artifacts
        self.aliases = aliases
        self.witnesses = witnesses or ((witness,) if witness is not None else ())
        self.triggered = {}

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
        for witness in self.witnesses:
            value = identity(witness)
            require(stat.S_IMODE(value[4]) == 0o600 and value[-1] == WITNESS,
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
    witnesses = tuple(fixture / ('triggered-' + str(index) + '.txt') for index in range(len(commands)))
    shutil.copy2(tool, original, follow_symlinks=False)
    require(identity(tool) == expected and original.read_bytes() == expected[-1],
            'native-tool-changed-during-copy')
    # Compose bounded exact matches; a nonmatching command delegates through
    # the next match and eventually to the untouched original native tool.
    source = f'exec {shlex.quote(str(original))} "$@"\n'
    for witness, arguments in reversed(tuple(zip(witnesses, commands))):
        source = wrapper_source(original, witness, arguments, hold_seconds=1).replace(
            f'exec {shlex.quote(str(original))} "$@"\n', source)
    wrapper.write_text(source)
    shutil.copystat(tool, wrapper, follow_symlinks=False)
    # copystat includes Linux extended attributes, notably security.selinux.
    # Explicitly compare them: an unrelated exec denial is never a fault hit.
    for name in os.listxattr(tool):
        require(os.getxattr(tool, name) == os.getxattr(original, name) == os.getxattr(wrapper, name),
                'native-tool-xattr-not-preserved')
    require(stat.S_IMODE(wrapper.stat().st_mode) == stat.S_IMODE(expected[4]),
            'native-tool-mode-not-preserved')
    wrapper_identity = identity(wrapper)
    fault = Fault(variant, tool, expected, witness=witnesses[0], witnesses=witnesses,
                  wrapper=wrapper_identity,
                  artifacts=((original, identity(original)), (wrapper, wrapper_identity)),
                  aliases=aliases)
    fault.original = original
    record('onpc.interruption.native-fixture', json.dumps({
        'tool': str(tool), 'commands': commands,
        'wrapper_sha256': hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest()}, sort_keys=True))
    with mounted_fault(fault, wrapper, record):
        yield fault
