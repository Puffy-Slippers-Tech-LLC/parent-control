"""Standalone controller for the same snapshot module used by E2E suites."""
import argparse
import fcntl
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))

import system_runner as system
from app_snapshot import mode_mismatch, preparation, snapshot_name
from execution import open_source
from owned_commands import Commands
from suite_lease import Suite
from vm_control import check_identity


def current_version(commands, root=ROOT):
    return commands.run(['dpkg-parsechangelog', '-l' + str(root / 'debian/changelog'),
                         '-SVersion']).decode().strip()


def current_name(commands, root=ROOT):
    return snapshot_name(current_version(commands, root))


def preparation_format(source, commands):
    base = system.baseline
    capture = base.Capture(source, commands, None)
    capture.directory_identity = capture.private_directory()
    capture.state = capture.read_state()
    system.require(capture.state['phase'] == 'finalized' and
                   capture.state['source']['layout']['uuid'] == source.uuid and
                   capture.state['script_digest'] == capture.script_digest,
                   'baseline:preparation-outdated')
    proof = base.snapshot_proof(capture.proven_snapshot_xml(source.baseline()),
        capture.state['source']['layout'], capture.description())
    system.require(all(capture.state['proof'].get(key) == value for key, value in proof.items()),
                   'baseline:changed')
    return system.package_format(capture.state['guest'])


def probe(expected_uuid, *, mode='online', overwrite=False):
    """Read only, under the shared VM lock; no journal writes or cleanup."""
    commands = Commands()
    name = current_name(commands)
    base = system.baseline
    base.canonical(base.BASELINES)
    lock_path = base.baseline_lock_path(base.BASELINES)
    base.identity(lock_path, private=True, mode=0o600)
    fd = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
    source = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source, _ = open_source()
        check_identity(source, expected_uuid)
        package_format = preparation_format(source, commands)
        required = 5 if package_format == 'rpm' else 3
        if overwrite:
            return required
        if name in source.domain.snapshotListNames(0):
            xml = source.domain.snapshotLookupByName(name, 0).getXMLDesc(0)
            reason = mode_mismatch(xml, mode)
            if reason is not None:
                preparation('Refreshing snapshot ' + name + ': ' + reason +
                            '; forcing overwrite=true')
                return required
            if mode == 'online':
                from online_snapshot import load
                if load(source, name, xml) is None:
                    preparation('Online snapshot credentials missing; preparation required')
                    return required
                return 4
            preparation('Keeping existing snapshot ' + name + ' (overwrite=false); no changes')
            return 0
        preparation('No existing snapshot ' + name + '; preparation required')
        return required
    finally:
        try:
            if source is not None:
                source.close()
        finally:
            os.close(fd)


def prepare(artifacts, expected_uuid, *, overwrite=True, mode='online'):
    from provenance import preflight_source
    from tools.test_retention import allocate
    directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-graphical-smoke-', dir='/tmp'))
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite = Suite(open_source)
    suite.commands.directory = private
    complete = False
    try:
        assets = directory / 'assets'
        system.stage_assets(system.artifact_source(artifacts), assets, suite.commands)
        source_inputs = preflight_source(assets)
        expected_version = current_version(suite.commands)
        name = snapshot_name(expected_version)
        package = assets / ('package.rpm' if (assets / 'package.rpm').is_file() else 'package.deb')
        version = system.package_version(suite.commands, package)
        system.require(snapshot_name(version) == name, 'suite:package-version-changed')
        if package.suffix == '.deb':
            system.require(version == expected_version, 'suite:package-version-changed')
        source, _, lease = suite.acquire(system.RunLedger())
        check_identity(source, expected_uuid)
        with lease:
            suite.prepare_installed(directory, assets,
                {'schema_version': 1, 'scope': 'standalone-appsnapshot',
                 'source_sha256': source_inputs['source_sha256']},
                root=ROOT, overwrite=overwrite, mode=mode)
        complete = True
    except Exception:
        # Keep the underlying host/guestfs failure in this existing private
        # allocation; the public output contains fixed categories only.
        (private / 'controller-error.txt').write_text(traceback.format_exc())
        raise
    finally:
        # Online snapshots retain their memory image; cleanup restores the
        # outer baseline without reviving an unowned preparation guest.
        suite.close(retain_installed=complete and mode == 'offline')
    preparation('Snapshot ready: ' + name)
    return 0


def resume(expected_uuid):
    """Fast, identity-checked online restore, handed to shared VM maintenance."""
    from online_snapshot import load, restore, saved_transport
    import vm_control
    from tools.test_retention import allocate
    directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-appsnapshot-resume-'))
    source, guestfs = open_source()
    lease = None
    try:
        check_identity(source, expected_uuid)
        commands = Commands()
        commands.directory = directory
        lease = system.Lease(source, commands,
            lambda disk, digest: system.baseline.inspect_guest(guestfs, disk, digest),
            graphics_type='vnc')
        if source.domain.ID() >= 0:
            vm_control.resume(lease)
        else:
            lease.__enter__()
        name = current_name(commands)
        xml = source.domain.snapshotLookupByName(name, 0).getXMLDesc(0)
        system.require(mode_mismatch(xml, 'online') is None,
                       'online-snapshot:expired-or-invalid')
        record = load(source, name, xml)
        system.require(record is not None, 'online-snapshot:credentials-missing')
        lease.installed_name, lease.installed_xml = name, xml
        lease.snapshot_xml = source.baseline()
        lease.view.original_shares = lease.capture.state['source']['layout']['source_shares']
        lease.mutated = True
        # Select the maintenance keeper before restore attaches its observer.
        lease.watch_detached = True
        started = time.monotonic()
        hostname = restore(lease, record, maintenance=True)
        saved_transport(lease, directory, record, hostname)
        preparation(f'Running guest SSH and clock ready in {time.monotonic() - started:.2f}s')
        system.require(lease.capture.verify_snapshot(boundary='restoration') ==
                       lease.capture.state['proof'], 'cleanup:baseline-changed')
        # Keep live and persistent isolation aligned while maintenance owns the
        # guest. Stop restores the original XML from the ownership journal.
        lease.guard()
        preparation('Running VM ready from snapshot ' + name)
        return 0
    finally:
        try:
            if lease is not None:
                try:
                    # Restore durably records start-requested before touching
                    # the VM. A refusal while still validated has no cleanup
                    # obligation and must not strand an otherwise idle VM.
                    if lease.state is not None and lease.state.get('phase') == 'validated':
                        lease.save('complete')
                finally:
                    lease.release()
        finally:
            source.close()


def main(argv=None):
    argv, _ = system.baseline.guest_contract.vm_config.extract(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--expected-uuid', required=True)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--mode', choices=('online', 'offline'), default='online')
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--overwrite', choices=('true', 'false'), default='true',
                        nargs='?', const='true')
    args = parser.parse_args(argv)
    try:
        system.require(os.geteuid() == 0, 'appsnapshot:root-required')
        os.umask(0o077)
        system.require(not (args.probe and args.resume), 'appsnapshot:invalid-arguments')
        if args.resume:
            system.require(args.artifacts is None and args.mode == 'online',
                           'appsnapshot:invalid-arguments')
            return resume(args.expected_uuid)
        if args.probe:
            system.require(args.artifacts is None, 'appsnapshot:invalid-arguments')
            return probe(args.expected_uuid, mode=args.mode, overwrite=args.overwrite == 'true')
        from runner import validate_artifact_path
        validate_artifact_path(args.artifacts)
        return prepare(args.artifacts, args.expected_uuid,
                       overwrite=args.overwrite == 'true', mode=args.mode)
    except (ValueError, RuntimeError, OSError) as error:
        if system.error_category(error) == 'unexpected-failure-or-interruption':
            system.log('exception-type=' + type(error).__name__)
        print('prepare-appsnapshot: ' + system.error_category(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
