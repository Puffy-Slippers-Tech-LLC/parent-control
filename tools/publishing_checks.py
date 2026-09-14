#!/usr/bin/python3 -IB
"""Shared local publishing checks for make test-all and make test-all-verify."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import publish, package_inputs
from tools import test_retention
from tools.publishing import build, source

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
    # Build the upcoming release metadata when history announces a new version.
    # Ordinary regression runs also work after a release, with current metadata.
    current = json.loads((checkout / 'data/app.json').read_text())['version']
    # Release notes are consumed to generate metadata, never shipped as docs.
    history = ((root / publish.HISTORY).read_text() if (root / publish.HISTORY).exists()
               else f'## v{current} ')
    draft = re.fullmatch(r'## v([0-9]+\.[0-9]+)', history.partition('\n')[0].strip())
    if draft and publish.parse_product_version(draft[1]) > publish.parse_product_version(current):
        # Local regression builds can run while the next release notes are a
        # draft. Keep the real package metadata; only actual publishing requires
        # the new entry's date and promotes it to a release.
        print(f'test-publish: undated release draft; testing current version {current}', flush=True)
    elif not history.startswith(f'## v{current} '):
        product, notes = publish.history_entry(history, current)
        old = publish.command('dpkg-parsechangelog', '-S', 'Version', cwd=checkout)
        version = source.next_version(product, [old])
        (checkout / 'data/app.json').write_text(json.dumps({'version': product}, indent=2) + '\n')
        changelog = checkout / 'debian/changelog'
        changelog.write_text(publish.changelog_entry(version, notes) + changelog.read_text())
    publish.command('git', 'add', '--all', cwd=checkout, log=log)
    publish.command('git', 'diff', '--cached', '--check', cwd=checkout, log=log)
    publish.command(*commit, 'Local publishing test snapshot', cwd=checkout, log=log)


def run(root=ROOT):
    if os.geteuid() == 0:
        raise ValueError('run publishing tests as an unprivileged user')
    build.check_prerequisites()
    for tool in ('git', 'dpkg-buildpackage', 'dpkg-checkbuilddeps', 'lintian', 'unshare', 'make'):
        if shutil.which(tool, path='/usr/sbin:/usr/bin:/sbin:/bin') is None:
            raise ValueError('missing publishing test tools; use ./setup.sh --dependencies-only')
    directory = Path(test_retention.allocate(tempfile.mkdtemp, prefix='onpc-test-publish-', dir='/tmp'))
    checkout, log = directory / 'source', directory / 'test.log'
    report = dict(status='running', directory=str(directory))
    print(f'test-publish: evidence: {directory}', flush=True)
    try:
        publish.command('unshare', '--user', '--map-root-user', 'true', cwd=root, log=log)
        publish.command('dpkg-checkbuilddeps', cwd=root, log=log)
        publish.command('make', 'check-release-version', cwd=root, log=log)
        snapshot(root, checkout, log)
        publish.command('make', 'check-release-version', cwd=checkout, log=log)
        version = publish.command('dpkg-parsechangelog', '-S', 'Version', cwd=checkout)
        report['version'] = version
        print('test-publish: building and inspecting unsigned source', flush=True)
        publish.command('dpkg-buildpackage', '--build=source', '--no-sign', '-sa',
                        cwd=checkout, log=log, timeout=3600)
        with log.open('a') as stream, redirect_stdout(stream), redirect_stderr(stream):
            source.inspect_archive(checkout, version)
        report['source'] = json.loads((directory / 'source-review.json').read_text())
        changes = directory / f'{source.PACKAGE}_{version}_source.changes'
        # Lintian normally removes its pool, but interruption can leave it
        # behind. Keep that scratch inside this run's registered evidence.
        publish.command('lintian', '--no-cfg', '--fail-on', 'error', str(changes),
                        cwd=checkout, log=log, temporary_directory=directory)
        print('test-publish: clean resolute/amd64 build and package checks', flush=True)
        result = build.check_build(checkout)
        report['local_build'] = result
        binary_changes = Path(result['directory']) / 'output' / f'{source.PACKAGE}_{version}_amd64.changes'
        publish.command('lintian', '--no-cfg', '--fail-on', 'error', str(binary_changes),
                        cwd=checkout, log=log, temporary_directory=directory)
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
    parser.parse_args(argv)
    original_env = dict(os.environ)
    try:
        safe_env = publish.environment()
        safe_env.update(test_retention.environment())
        os.environ.clear()
        os.environ.update(safe_env)
        run()
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
