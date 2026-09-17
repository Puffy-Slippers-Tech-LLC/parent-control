"""Standalone controller for the same snapshot module used by E2E suites."""
import argparse
import fcntl
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))

import system_runner as system
from app_snapshot import preparation, snapshot_name
from execution import open_source
from owned_commands import Commands
from suite_lease import Suite
from vm_control import check_identity


def current_version(commands, root=ROOT):
    return commands.run(['dpkg-parsechangelog', '-l' + str(root / 'debian/changelog'),
                         '-SVersion']).decode().strip()


def current_name(commands, root=ROOT):
    return snapshot_name(current_version(commands, root))


def probe(expected_uuid):
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
        if name in source.domain.snapshotListNames(0):
            preparation('Keeping existing snapshot ' + name + ' (overwrite=false); no changes')
            return 0
        preparation('No existing snapshot ' + name + '; preparation required')
        return 3
    finally:
        try:
            if source is not None:
                source.close()
        finally:
            os.close(fd)


def prepare(artifacts, expected_uuid, *, overwrite=True):
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
        version = suite.commands.run(['dpkg-deb', '-f', str(assets / 'package.deb'),
                                     'Version']).decode().strip()
        system.require(version == expected_version, 'suite:package-version-changed')
        source, _, lease = suite.acquire(system.RunLedger())
        check_identity(source, expected_uuid)
        with lease:
            suite.prepare_installed(directory, assets,
                {'schema_version': 1, 'scope': 'standalone-appsnapshot',
                 'source_sha256': source_inputs['source_sha256']},
                root=ROOT, overwrite=overwrite)
        complete = True
    finally:
        suite.close(retain_installed=complete)
    preparation('Snapshot ready: ' + name)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--expected-uuid', required=True)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--overwrite', choices=('true', 'false'), default='true',
                        nargs='?', const='true')
    args = parser.parse_args(argv)
    try:
        system.require(os.geteuid() == 0, 'appsnapshot:root-required')
        os.umask(0o077)
        if args.probe:
            system.require(args.artifacts is None, 'appsnapshot:invalid-arguments')
            return probe(args.expected_uuid)
        from runner import validate_artifact_path
        validate_artifact_path(args.artifacts)
        return prepare(args.artifacts, args.expected_uuid, overwrite=args.overwrite == 'true')
    except (ValueError, RuntimeError, OSError) as error:
        print('prepare-appsnapshot: ' + system.error_category(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
