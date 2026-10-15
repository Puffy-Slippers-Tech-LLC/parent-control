"""Finite installed removal faults; all mounts have exact, serial ownership.

Fixtures live inside the controller's already allocated guest private payload.
No policy, package script, shared executable bytes or host state is rewritten.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import stat
import tempfile

import system_guest as guest


OWNER_UID = 0
PAM = Path('/etc/pam.d/systemd-user')
HOME = Path('/home/oh-no-parent-control')
STATE = Path('/var/lib/oh-no-parent-control/kiosk-confinement.json')
MARKER = Path('/var/lib/oh-no-parent-control/kiosk-confinement-removing')
TOOLS = {'selinux': Path('/usr/sbin/semodule'),
         'apparmor': Path('/usr/sbin/apparmor_parser')}
SBIN = Path('/usr/sbin')
BIN = Path('/usr/bin')
POLICY = Path('/usr/share/oh-no-parent-control/confinement/onpc-kiosk.apparmor')
WITNESS = b'onpc-removal-fault:exact-native-unload-refused\n'


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


def native_tool(backend):
    tool = TOOLS[backend]
    if tool.parent == SBIN and SBIN.is_symlink():
        return BIN / tool.name, ((SBIN, alias_identity(SBIN)),)
    return tool, ()


def identity(path, *, directory=False, owner=None):
    parents(path)
    info = path.lstat()
    require((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) and
            info.st_uid == (OWNER_UID if owner is None else owner) and
            not info.st_mode & 0o022 and (directory or info.st_nlink == 1),
            'unsafe-target')
    return metadata(info) + (() if directory else (path.read_bytes(),))


def pinned_identity(fd, *, directory=False):
    info = os.fstat(fd)
    contents = () if directory else (os.pread(fd, info.st_size, 0),)
    return metadata(info) + contents


def unload_arguments(backend):
    require(backend in TOOLS, 'unknown-backend')
    return ['-r', 'onpc-kiosk'] if backend == 'selinux' else ['-R', str(POLICY)]


def wrapper_source(original, witness, arguments):
    """Only the exact two native unload arguments select the deliberate fault."""
    require(len(arguments) == 2, 'invalid-unload-arguments')
    quote = shlex.quote
    return ('#!/bin/sh\nset -eu\n'
            f'if [ "$#" -eq 2 ] && [ "$1" = {quote(arguments[0])} ] && '
            f'[ "$2" = {quote(arguments[1])} ]; then\n'
            '    (set -C; umask 077; '
            f'printf %s {quote(WITNESS.decode())} > {quote(str(witness))})\n'
            '    exit 79\nfi\n'
            f'exec {quote(str(original))} "$@"\n')


class Fault:
    def __init__(self, variant, path, expected, *, directory=False, owner=None,
                 witness=None, wrapper=None, artifacts=(), aliases=()):
        self.variant, self.path, self.expected = variant, path, expected
        self.directory, self.owner = directory, owner
        self.witness, self.wrapper = witness, wrapper
        self.artifacts = artifacts
        self.aliases = aliases

    def verify_artifacts(self):
        for path, expected in self.aliases:
            require(alias_identity(path) == expected, 'native-tool-alias-changed')
        for path, expected in self.artifacts:
            require(identity(path) == expected, 'fixture-identity-changed')

    def verify_triggered(self):
        self.verify_artifacts()
        if self.variant == 'mac-unload':
            require(self.witness is not None and self.wrapper is not None,
                    'missing-witness-identity')
            require(identity(self.path) == self.wrapper, 'wrapper-changed')
            value = identity(self.witness)
            require(stat.S_IMODE(value[4]) == 0o600 and value[-1] == WITNESS,
                    'exact-unload-not-observed')
        else:
            require(identity(self.path, directory=self.directory, owner=self.owner) == self.expected,
                    'protected-target-changed')
            saved, marker = identity(STATE), identity(MARKER)
            require(stat.S_IMODE(saved[4]) == stat.S_IMODE(marker[4]) == 0o600 and
                    json.loads(saved[-1]).get('removing') is True and
                    marker[-1] == b'removing\n', 'removal-transition-not-observed')


@contextmanager
def mounted_fault(fault, source, record):
    """Hold the original inode and refuse cleanup after any ownership change."""
    from system_removal import mount_inventory
    namespace, before = mount_inventory()
    require(not any(row[0][4] == str(fault.path) for row in before.values()),
            'preexisting-mount')
    fd = os.open(fault.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC |
                 (os.O_DIRECTORY if fault.directory else 0))
    try:
        require(pinned_identity(fd, directory=fault.directory) == fault.expected,
                'target-changed-before-mount')
        guest.run(['mount', '--bind', str(source), str(fault.path)], timeout=30)
        current, rows = mount_inventory()
        owned = {key: row for key, row in rows.items()
                 if key not in before and row[0][4] == str(fault.path)}
        require(current == namespace and len(owned) == 1, 'mount-not-attributable')
        visible = identity(fault.path, directory=fault.directory, owner=fault.owner)
        require(visible == (fault.wrapper if fault.wrapper is not None else fault.expected),
                'mounted-target-changed')
        try:
            record('onpc.interruption.fault', json.dumps({
                'variant': fault.variant, 'namespace': namespace, 'mounts': owned,
                'device': fault.expected[0], 'inode': fault.expected[1]}, sort_keys=True))
            yield fault
        finally:
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
                    identity(fault.path, directory=fault.directory, owner=fault.owner) == fault.expected,
                    'cleanup-not-verified')
    finally:
        os.close(fd)


@contextmanager
def interruption_fault(variant, record):
    """Yield an owned finite mount; caller verifies product protection before exit."""
    guest.guard()
    require(variant in ('denial-publication', 'mac-unload', 'account-finalization'),
            'unknown-variant')
    if variant != 'mac-unload':
        directory = variant == 'account-finalization'
        path = HOME if directory else PAM
        owner = pwd.getpwnam('oh-no-parent-control').pw_uid if directory else OWNER_UID
        expected = identity(path, directory=directory, owner=owner)
        fault = Fault(variant, path, expected, directory=directory, owner=owner)
        with mounted_fault(fault, path, record):
            yield fault
        return
    saved = identity(STATE)
    require(stat.S_IMODE(saved[4]) == 0o600, 'unsafe-removal-state')
    backend = json.loads(saved[-1])['backend']
    arguments = unload_arguments(backend)
    tool, aliases = native_tool(backend)
    expected = identity(tool)
    private = guest.PAYLOAD / 'private'
    info = private.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == OWNER_UID and
            stat.S_IMODE(info.st_mode) == 0o700, 'unsafe-private-root')
    parents(private)
    # This is a child of the already retained guest allocation, not another
    # storage root. Keep its evidence for the controller's owned final cleanup.
    fixture = Path(tempfile.mkdtemp(prefix='removal-unload-', dir=private))
    original, wrapper, witness = (fixture / name for name in ('original', 'wrapper', 'triggered.txt'))
    shutil.copy2(tool, original, follow_symlinks=False)
    require(identity(tool) == expected and original.read_bytes() == expected[-1],
            'native-tool-changed-during-copy')
    wrapper.write_text(wrapper_source(original, witness, arguments))
    shutil.copystat(tool, wrapper, follow_symlinks=False)
    # copystat includes Linux extended attributes, notably security.selinux.
    # Explicitly compare them: an unrelated exec denial is never a fault hit.
    for name in os.listxattr(tool):
        require(os.getxattr(tool, name) == os.getxattr(original, name) == os.getxattr(wrapper, name),
                'native-tool-xattr-not-preserved')
    require(stat.S_IMODE(wrapper.stat().st_mode) == stat.S_IMODE(expected[4]),
            'native-tool-mode-not-preserved')
    wrapper_identity = identity(wrapper)
    fault = Fault(variant, tool, expected, witness=witness, wrapper=wrapper_identity,
                  artifacts=((original, identity(original)), (wrapper, wrapper_identity)),
                  aliases=aliases)
    record('onpc.interruption.unload-fixture', json.dumps({
        'tool': str(tool), 'arguments': arguments,
        'wrapper_sha256': hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest()}, sort_keys=True))
    with mounted_fault(fault, wrapper, record):
        yield fault
