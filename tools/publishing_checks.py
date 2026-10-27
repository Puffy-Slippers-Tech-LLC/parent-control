#!/usr/bin/python3 -IB
"""One independent local publishing job; the runner schedules DEB and RPM jobs."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import publish, package_inputs
from tools.bump_version import update_from_history
from tools import test_retention
from tools.publishing import build, rpm, source

ROOT = Path(__file__).resolve().parents[1]


def snapshot(root, checkout, log):
    """Freeze only declared product/build files, including uncommitted edits."""
    checkout.mkdir()
    package_inputs.copy(root, checkout)
    publish.command('git', 'init', '-q', cwd=checkout, log=log)
    publish.command('git', 'add', '--all', cwd=checkout, log=log)
    commit = ('git', '-c', 'user.name=Publishing tests', '-c',
              'user.email=publishing-tests@invalid', '-c', 'commit.gpgsign=false',
              'commit', '-q', '--allow-empty', '-m')
    publish.command(*commit, 'Local publishing test inputs', cwd=checkout, log=log)
    # Use the same private version preparation as updateversion, even for drafts.
    # Notes are consumed from the checkout and never shipped in the package.
    if (root / publish.HISTORY).exists():
        update_from_history(checkout, (root / publish.HISTORY).read_text(encoding='utf-8'))
    publish.command('git', 'add', '--all', cwd=checkout, log=log)
    publish.command('git', 'diff', '--cached', '--check', cwd=checkout, log=log)
    publish.command(*commit, 'Local publishing test snapshot', cwd=checkout, log=log)


def check_deb(root, checkout, directory, log, report):
    publish.command('unshare', '--user', '--map-root-user', 'true', cwd=root, log=log)
    publish.command('dpkg-checkbuilddeps', cwd=root, log=log)
    version = publish.command('dpkg-parsechangelog', '-S', 'Version', cwd=checkout)
    report['version'] = version
    print('test-publish: building and inspecting unsigned source', flush=True)
    publish.command('dpkg-buildpackage', '--build=source', '--no-sign', '-sa',
                    cwd=checkout, log=log, timeout=3600)
    with log.open('a') as stream, redirect_stdout(stream), redirect_stderr(stream):
        source.inspect_archive(checkout, version)
    report['source'] = json.loads((directory / 'source-review.json').read_text())
    changes = directory / f'{source.PACKAGE}_{version}_source.changes'
    # Keep Lintian scratch inside this attempt, including interrupted output.
    publish.command('lintian', '--no-cfg', '--fail-on', 'error', str(changes),
                    cwd=checkout, log=log, temporary_directory=directory)
    print('test-publish: clean resolute/amd64 build and package checks', flush=True)
    result = build.check_build(checkout)
    report['local_build'] = result
    binary_changes = Path(result['directory']) / 'output' / f'{source.PACKAGE}_{version}_amd64.changes'
    publish.command('lintian', '--no-cfg', '--fail-on', 'error', str(binary_changes),
                    cwd=checkout, log=log, temporary_directory=directory)


def run(root=ROOT, *, package_format):
    if package_format not in ('deb', 'rpm'):
        raise ValueError('select one publishing package format: deb or rpm')
    if os.geteuid() == 0:
        raise ValueError('run publishing tests as an unprivileged user')
    tools = ('git', 'make')
    if package_format == 'deb':
        build.check_prerequisites()
        tools += ('dpkg-buildpackage', 'dpkg-checkbuilddeps', 'dpkg-parsechangelog', 'lintian', 'unshare')
    else:
        rpm.prerequisites()
    for tool in tools:
        if shutil.which(tool, path='/usr/sbin:/usr/bin:/sbin:/bin') is None:
            raise ValueError('missing publishing test tools; use ./setup.sh --dependencies-only')
    directory = Path(test_retention.allocate(tempfile.mkdtemp, prefix=f'onpc-test-publish-{package_format}-'))
    checkout, log = directory / 'source', directory / 'test.log'
    report = dict(status='running', directory=str(directory), package_format=package_format)
    print(f'test-publish: evidence: {directory}', flush=True)
    try:
        publish.command('make', 'check-release-version', cwd=root, log=log)
        snapshot(root, checkout, log)
        publish.command('make', 'check-release-version', cwd=checkout, log=log)
        if package_format == 'rpm':
            report['rpm'] = rpm.check_build(root, checkout, directory)
        else:
            check_deb(root, checkout, directory, log, report)
        report['status'] = 'passed'
    except BaseException:
        report['status'] = 'failed'
        raise
    finally:
        (directory / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'test-publish: {report["status"]}; evidence: {directory}', flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--package-format', choices=('deb', 'rpm'), required=True)
    args = parser.parse_args(argv)
    original_env = dict(os.environ)
    try:
        safe_env = publish.environment()
        safe_env.update(test_retention.environment())
        os.environ.clear()
        os.environ.update(safe_env)
        run(package_format=args.package_format)
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError, subprocess.SubprocessError) as error:
        detail = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(f'test-publish: failed ({detail}); see retained evidence', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        os.environ.clear()
        os.environ.update(original_env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
