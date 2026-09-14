"""Guarded qualification inside the packaged broker's ExecStartPost sandbox."""

import errno
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import sys

import system_guest as guest
from system_enforcement import native_probe_lifecycle


INPUT = Path('/run/oh-no-parent-control/probes/sandbox-input')
DROPIN = Path('/run/systemd/system/oh-no-parent-control-broker.service.d')
PROPERTIES = (
    'User', 'Group', 'CapabilityBoundingSet', 'AmbientCapabilities',
    'NoNewPrivileges', 'PrivateDevices', 'PrivateTmp', 'ProtectHome',
    'ProtectSystem', 'StateDirectory', 'StateDirectoryMode', 'RuntimeDirectory',
    'RuntimeDirectoryMode', 'RuntimeDirectoryPreserve', 'LogsDirectory',
    'LogsDirectoryMode', 'ReadWritePaths', 'ProtectKernelTunables',
    'ProtectKernelModules', 'ProtectControlGroups', 'RestrictAddressFamilies',
    'RestrictNamespaces', 'LockPersonality', 'MemoryDenyWriteExecute',
    'SystemCallArchitectures',
)


def restrictions():
    raw = guest.run(['systemctl', 'show', guest.BROKER,
                     '--property=' + ','.join(PROPERTIES)], timeout=10)
    fields = dict(line.split('=', 1) for line in raw.splitlines())
    guest.require(set(fields) == set(PROPERTIES), 'sandbox:properties-missing')
    guest.require(fields['ProtectSystem'] == 'strict' and
                  fields['NoNewPrivileges'] == 'yes' and
                  fields['RestrictAddressFamilies'] == 'AF_UNIX',
                  'sandbox:restrictions-missing')
    return fields


def stage_inputs():
    """Copy only guarded transferred inputs; never copy private guest artifacts.

    PrivateTmp hides the ordinary /var/tmp input directory. This copy uses the
    already writable broker runtime root; no bind mount or sandbox exemption.
    The normal guest guard revalidates the entire closure inside the worker.
    The outer baseline owns this fixture directory, including failure evidence.
    """
    guest.guard()
    inventory = json.loads((guest.PAYLOAD / 'transfer-sha256.json').read_text())
    INPUT.mkdir(mode=0o700)  # Refuse every preexisting directory/symlink.
    for relative in [*inventory, 'transfer-sha256.json']:
        path = Path(relative)
        guest.require(not path.is_absolute() and '..' not in path.parts,
                      'sandbox:input-path')
        source = guest.PAYLOAD / path
        guest.require(stat.S_ISREG(source.lstat().st_mode), 'sandbox:input-type')
        target = INPUT / path
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with source.open('rb') as reader, target.open('xb') as writer:
            shutil.copyfileobj(reader, writer)
        target.chmod(0o600)
        guest.require(guest.sha(target) == guest.sha(source), 'sandbox:copy-changed')


def _file_identity(path):
    info = path.lstat()
    return info.st_dev, info.st_ino


def native_probe_broker_sandbox(record):
    """Append one unprefixed start-post command; restore only our exact drop-in."""
    marker = guest.guard()
    guest.enable_diagnostics()
    expected = restrictions()
    stage_inputs()
    config = DROPIN / '90-onpc-probe-qualification.conf'
    DROPIN.mkdir(mode=0o700)  # Existing overrides require investigation, not overwrite.
    directory_identity = _file_identity(DROPIN)
    descriptor = None
    config_identity = None
    values = {}
    written = b''
    body = ('[Service]\nExecStartPost=/usr/bin/env ONPC_EXPECTED_RUN=' + marker['run'] +
            ' /usr/bin/python3 -B ' + str(INPUT / 'system_probe_sandbox.py') +
            ' --worker\n').encode()
    try:
        descriptor = os.open(config, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        info = os.fstat(descriptor)
        config_identity = (info.st_dev, info.st_ino)
        # Keep the descriptor pinned through restoration, including partial writes.
        count = os.write(descriptor, body)
        written = body[:count]
        guest.require(count == len(body), 'sandbox:short-dropin-write')
        guest.run(['systemctl', 'daemon-reload'])
        guest.require(restrictions() == expected, 'sandbox:restrictions-changed')
        try:
            guest.run(['systemctl', 'restart', guest.BROKER], timeout=120)
        finally:
            result = INPUT / 'sandbox-result.json'
            if result.is_file() and not result.is_symlink():
                values = json.loads(result.read_text())
                for key, value in values.items():
                    record(key, value)
            diagnostics = INPUT / 'private'
            if diagnostics.is_dir() and not diagnostics.is_symlink():
                shutil.copytree(diagnostics, guest.PAYLOAD / 'private/sandbox-worker')
        guest.require(values.get('onpc.probe.sandbox.passed') is True,
                      'sandbox:worker-incomplete')
    finally:
        # Observed foreign replacement is left intact for outer guarded recovery.
        # Never daemon-reload/restart through configuration we cannot restore.
        try:
            guest.require(_file_identity(DROPIN) == directory_identity,
                          'sandbox:dropin-directory-replaced')
            if config_identity is not None:
                guest.require(_file_identity(config) == config_identity,
                              'sandbox:dropin-replaced')
                current = os.pread(descriptor, len(body) + 1, 0)
                guest.require(current == written, 'sandbox:dropin-mutated')
                config.unlink()
            DROPIN.rmdir()
            guest.run(['systemctl', 'daemon-reload'])
            guest.run(['systemctl', 'restart', guest.BROKER], timeout=60)
            guest.require(restrictions() == expected, 'sandbox:restoration-changed')
            guest.require(guest.run(['systemctl', 'is-active', guest.BROKER]) == 'active',
                          'sandbox:restoration-inactive')
            record('onpc.probe.sandbox.restored', True)
        finally:
            if descriptor is not None:
                os.close(descriptor)


def observe_process(record):
    """Compare effective process restrictions, not a copied unit declaration."""
    pid = guest.run(['systemctl', 'show', guest.BROKER, '--property=MainPID', '--value'])
    guest.require(re.fullmatch(r'[1-9][0-9]*', pid) is not None, 'sandbox:broker-pid')
    status = lambda path: dict(line.split(':', 1) for line in path.read_text().splitlines())
    own = status(Path('/proc/self/status'))
    broker = status(Path('/proc') / pid / 'status')
    for key in ('CapBnd', 'CapEff', 'CapAmb', 'NoNewPrivs', 'Seccomp'):
        guest.require(own[key].strip() == broker[key].strip(), 'sandbox:process-restrictions')
        record('onpc.probe.sandbox.' + key, own[key].strip())
    guest.require(own['NoNewPrivs'].strip() == '1' and own['Seccomp'].strip() == '2',
                  'sandbox:process-unrestricted')
    guest.require(Path('/proc/self/cgroup').read_bytes() ==
                  (Path('/proc') / pid / 'cgroup').read_bytes(), 'sandbox:foreign-cgroup')
    guest.require(os.statvfs('/usr').f_flag & os.ST_RDONLY, 'sandbox:usr-writable')
    try:
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError as error:
        guest.require(error.errno in {errno.EPERM, errno.EAFNOSUPPORT}, 'sandbox:socket-error')
    else:
        connection.close()
        raise guest.GuestError('sandbox:inet-permitted')
    record('onpc.probe.sandbox.inet-refused', True)


def worker():
    guest.PAYLOAD = INPUT
    guest.guard()
    records = {}
    try:
        observe_process(records.__setitem__)
        for stage, refuse in (('success', False), ('refusal', True), ('fresh', False)):
            def record(key, value):
                records[f'{key}.{stage}'] = value
            native_probe_lifecycle(record, refuse_admission=refuse)
        records['onpc.probe.sandbox.passed'] = True
    finally:
        # Preserve bounded evidence even when native recovery fails. No raw errors.
        with (INPUT / 'sandbox-result.json').open('x') as stream:
            json.dump(records, stream, sort_keys=True)
        (INPUT / 'sandbox-result.json').chmod(0o600)


if __name__ == '__main__':
    guest.require(sys.argv[1:] == ['--worker'], 'sandbox:arguments')
    worker()
