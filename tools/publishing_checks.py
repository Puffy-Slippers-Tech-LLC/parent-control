#!/usr/bin/python3 -IB
"""Shared local publishing checks for make test-publish and make test-all."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import publish
from tools.publishing import build, source

ROOT = Path(__file__).resolve().parents[1]


def snapshot(root, checkout, log):
    """Freeze current tracked and unignored files, including uncommitted edits."""
    names = publish.command('git', 'ls-files', '-z', '--cached', '--others',
                            '--exclude-standard', cwd=root).split('\0')
    publish.command('git', 'diff', '--check', cwd=root, log=log)
    publish.command('git', 'diff', '--cached', '--check', cwd=root, log=log)
    checkout.mkdir()
    for name in sorted(set(names) - {''}):
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
            raise ValueError('invalid publishing test source path')
        original = root / name
        if not original.exists() and not original.is_symlink():
            continue  # Unstaged deletion of an indexed file.
        if any(parent.is_symlink() for parent in original.parents if parent != root):
            raise ValueError('publishing test source has a symlink parent')
        target = checkout / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if original.is_symlink():
            target.symlink_to(os.readlink(original))
        elif original.is_file():
            shutil.copy2(original, target)
        else:
            raise ValueError('publishing test source must be a regular file or symlink')
    publish.command('git', 'init', '-q', cwd=checkout, log=log)
    publish.command('git', 'add', '--all', cwd=checkout, log=log)
    commit = ('git', '-c', 'user.name=Publishing tests', '-c',
              'user.email=publishing-tests@invalid', '-c', 'commit.gpgsign=false',
              'commit', '-q', '--allow-empty', '-m')
    publish.command(*commit, 'Local publishing test inputs', cwd=checkout, log=log)
    # Build the upcoming release metadata when history announces a new version.
    # Ordinary regression runs also work after a release, with current metadata.
    current = json.loads((checkout / 'data/app.json').read_text())['version']
    history = (checkout / publish.HISTORY).read_text()
    if not history.startswith(f'## v{current} '):
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
    directory = Path(tempfile.mkdtemp(prefix='onpc-test-publish-', dir='/tmp'))
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
        publish.command('lintian', '--no-cfg', '--fail-on', 'error', str(changes), cwd=checkout, log=log)
        print('test-publish: clean resolute/amd64 build and declared tests', flush=True)
        result = build.check_build(checkout)
        report['local_build'] = result
        binary_changes = Path(result['directory']) / 'output' / f'{source.PACKAGE}_{version}_amd64.changes'
        publish.command('lintian', '--no-cfg', '--fail-on', 'error', str(binary_changes), cwd=checkout, log=log)
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
