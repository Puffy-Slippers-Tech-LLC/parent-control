"""Select test package inputs from the pinned VM's verified baseline."""

import argparse
from pathlib import Path
import sys
import tempfile

from dev_privileges import check
from regression_process import Control
import test_launcher
import test_retention
from vm_selection import arguments, extract


def prepare(root, control, environment, *, candidate=None, output=None, upgrade_inputs=False):
    helper = '/usr/local/libexec/onpc-test-runner'
    check(helper)
    # This existing probe only reads provenance under the VM lock. Overwrite
    # selects the required format even when an app snapshot already exists;
    # it does not replace that snapshot or start/restore the guest.
    status = control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
        helper, 'appsnapshot', '--probe', '--mode', 'online', '--overwrite', 'true',
        *arguments()], cwd=root, env=environment)
    if status not in (3, 5):
        return status or 2
    package_format = 'rpm' if status == 5 else 'deb'
    if upgrade_inputs and package_format != 'deb':
        print('run-tests: genuine v1.2 upgrade inputs support DEB only; '
              'RPM upgrade qualification is unavailable', file=sys.stderr)
        return 2
    if candidate is not None:
        if upgrade_inputs:
            from build_test_artifacts import verify_upgrade
            verify_upgrade(Path(candidate))
            print('run-tests: output=' + str(candidate), flush=True)
            return 0
        from build_test_artifacts import verify
        manifest = verify(Path(candidate))
        if Path(manifest['artifacts']['package']['path']).suffix == '.' + package_format:
            print('run-tests: output=' + str(candidate), flush=True)
            return 0
        if output is not None:
            print('run-tests: qualification input package format does not match '
                  'the verified VM baseline; existing inputs preserved', file=sys.stderr)
            return 2
    if output is None:
        output = test_retention.allocate(tempfile.mkdtemp, prefix='onpc-test-artifacts-')
        print('run-tests: output=' + str(output), flush=True)
    # The existing reuse cache is DEB-specific. RPM uses its maintained builder.
    return control.run(['/usr/bin/python3', '-B', str(root / 'tools/build_test_artifacts.py'),
        *(['--upgrade-inputs'] if upgrade_inputs else ['--reuse'] if package_format == 'deb' else []),
        '--package-format', package_format, '--output', str(output)],
        cwd=root, env=environment)


def main(argv=None):
    argv, _ = extract(list(sys.argv[1:] if argv is None else argv), required=True)
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--candidate')
    parser.add_argument('--output')
    parser.add_argument('--upgrade-inputs', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    with Control().installed(pipe=False) as control:
        return prepare(root, control, test_launcher.environment(root),
                       candidate=args.candidate, output=args.output, upgrade_inputs=args.upgrade_inputs)


if __name__ == '__main__':
    sys.exit(main())
