#!/usr/bin/python3 -IB
"""Publish docs/VersionHistory.md end to end; run `make publish` without arguments."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import date, datetime, timezone
from email.utils import format_datetime
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen

# Direct execution uses isolated Python; import only this maintained checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.publishing import build as ppa_build, source as release
from tools.bump_version import parse_product_version

ROOT = Path(__file__).resolve().parents[1]
HISTORY = 'docs/VersionHistory.md'
API = release.API
SERIES = 'https://api.launchpad.net/1.0/ubuntu/resolute'
PPA_FILES = f'https://ppa.launchpadcontent.net/{release.OWNER}/{release.PACKAGE}/ubuntu/'
PUBLIC_GIT = 'https://github.com/Puffy-Slippers-Tech-LLC/parent-control.git'
PHASES = ('prepared', 'signed', 'built', 'push-started', 'pushed', 'upload-started', 'published', 'complete')
POLL_SECONDS = 30
WAIT_SECONDS = 24 * 60 * 60


def say(message, *, error=False, success=False):
    color = '\033[31m' if error else '\033[32m' if success else ''
    print(f'{color}publish: {message}' + ('\033[0m' if color else ''),
          file=sys.stderr if error else sys.stdout, flush=True)


def environment():
    env = {key: os.environ[key] for key in ('HOME', 'USER', 'LOGNAME', 'SSH_AUTH_SOCK')
           if key in os.environ}
    env.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8',
               GIT_TERMINAL_PROMPT='0', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
               GIT_SSH_COMMAND='ssh -oBatchMode=yes -oStrictHostKeyChecking=yes -oConnectTimeout=20',
               SSH_ASKPASS_REQUIRE='never', DEBIAN_FRONTEND='noninteractive',
               DEB_BUILD_OPTIONS='parallel=2', DEB_BUILD_PROFILES='')
    return env


def command(*args, cwd=ROOT, log=None, timeout=300):
    """No shell or stdin, sanitized environment, and redacted command failures."""
    try:
        result = subprocess.run(args, cwd=cwd, env=environment(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        if log is not None and error.output:
            output = error.output.decode('utf-8', errors='replace') if isinstance(error.output, bytes) else error.output
            with log.open('a', encoding='utf-8') as stream:
                stream.write(output)
        raise ValueError(f'{Path(args[0]).name} timed out; check the retained release log') from None
    if log is not None:
        with log.open('a', encoding='utf-8') as stream:
            stream.write(result.stdout)
    if result.returncode:
        suffix = f'; see {log}' if log else ''
        raise ValueError(f'{Path(args[0]).name} failed (exit {result.returncode}){suffix}')
    return result.stdout.rstrip('\n')


def history_entry(text, current):
    """Strict top-level version records; preserve section headings and bullets."""
    headings = list(re.finditer(r'^## (.+)$', text, re.M))
    if len(headings) < 2:
        raise ValueError('VersionHistory.md needs at least two ## vX.Y — YYYY-MM-DD entries')
    versions = []
    for heading in headings:
        match = re.fullmatch(r'v([0-9]+\.[0-9]+) (?:—|-) ([0-9]{4}-[0-9]{2}-[0-9]{2})', heading[1])
        if not match:
            raise ValueError('invalid VersionHistory.md heading; expected ## vX.Y — YYYY-MM-DD')
        versions.append((match[1], parse_product_version(match[1])))
        date.fromisoformat(match[2])
    if any(a[1] <= b[1] for a, b in zip(versions, versions[1:])):
        raise ValueError('VersionHistory.md versions must be unique and newest first')
    if versions[0][1] <= parse_product_version(current):
        raise ValueError('top VersionHistory.md version must be higher than the current app version')
    if versions[1][0] != current:
        raise ValueError('second VersionHistory.md version must equal the current app version')
    body = text[headings[0].end():headings[1].start()].strip()
    if not re.search(r'^[-*] \S', body, re.M):
        raise ValueError('new version entry needs at least one change bullet')
    if any(ord(char) < 32 and char not in '\n\t' for char in body) or '\x7f' in body:
        raise ValueError('version notes contain control characters')
    return versions[0][0], body


def changelog_entry(version, body):
    lines = []
    for line in body.splitlines():
        line = re.sub(r'^#{3,6}\s+', '', line.strip())
        line = line.replace('**', '').replace('`', '')
        if not line:
            lines.append('')
            continue
        bullet = bool(re.match(r'^[-*]\s+', line))
        line = re.sub(r'^[-*]\s+', '', line)
        lines.extend(textwrap.wrap(line, width=78, initial_indent='  * ' if bullet else '  ',
                                   subsequent_indent='    ', break_long_words=False,
                                   break_on_hyphens=False))
    stamp = format_datetime(datetime.now(timezone.utc))
    return (f'{release.PACKAGE} ({version}) resolute; urgency=medium\n\n'
            + '\n'.join(lines) + f'\n\n -- {release.NAME} <{release.EMAIL}>  {stamp}\n\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    """Persist transitions before external writes, including directory metadata."""
    fd, temporary = tempfile.mkstemp(prefix='.publish-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def locked(root):
    common = Path(command('git', 'rev-parse', '--git-common-dir', cwd=root))
    if not common.is_absolute():
        common = root / common
    directory = common / 'onpc-publish'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise ValueError('unsafe publishing journal directory')
    fd = os.open(directory / 'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another publisher is already running for this checkout') from None
        yield directory / 'state.json'


def read_url(url):
    """Public HTTPS only. Never load credentials from the caller's environment."""
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.hostname not in ('api.launchpad.net', 'ppa.launchpadcontent.net')):
        raise ValueError('unexpected publication service URL')
    with urlopen(url, timeout=30) as response:
        return response.read()


def fetch(url):
    if not url.startswith(('https://api.launchpad.net/1.0/', 'https://api.launchpad.net/devel/')):
        raise ValueError('unexpected Launchpad API URL')
    return json.loads(read_url(url))


def collection(url):
    entries, seen = [], set()
    while url:
        if url in seen:
            raise ValueError('Launchpad pagination loop')
        seen.add(url)
        page = fetch(url)
        entries.extend(page['entries'])
        url = page.get('next_collection_link')
    return entries


def sources(version=None):
    result = []
    for status in ('Pending', 'Published', 'Superseded', 'Deleted', 'Obsolete'):
        query = dict(**{'ws.op': 'getPublishedSources'}, source_name=release.PACKAGE,
                     exact_match='true', status=status)
        if version is not None:
            query['version'] = version
        result.extend(collection(API + '?' + urlencode(query)))
    return result


def archive_preflight():
    archive = fetch(API)
    if archive['private'] or not archive['publish']:
        raise ValueError('configured PPA must be public and publishing enabled')
    # Processor configuration is exposed only by the documented devel API.
    current = fetch(API.replace('/1.0/', '/devel/'))
    if current['status'] != 'Active':
        raise ValueError('PPA is not active')
    processors = collection(current['processors_collection_link'])
    if {item['name'] for item in processors} != {'amd64'}:
        raise ValueError('PPA must enable only amd64; local validation covers resolute/amd64')
    keys = collection(f'https://api.launchpad.net/1.0/~{release.OWNER}/gpg_keys')
    if release.KEY not in {item['fingerprint'] for item in keys}:
        raise ValueError('publisher signing key is not registered with Launchpad')


def source_state(root):
    if command('git', 'symbolic-ref', '--short', 'HEAD', cwd=root) != 'main':
        raise ValueError('run the publisher from the main branch')
    # Release notes are the sole automatically included working-tree input.
    # No filenames are printed: an unrelated working tree can contain PII.
    status = command('git', 'status', '--porcelain=v1', '-z', '--untracked-files=all', cwd=root)
    if any(record and record[3:] != HISTORY for record in status.split('\0')):
        raise ValueError('commit application changes first; only VersionHistory.md may be uncommitted')
    if (root / HISTORY).is_symlink():
        raise ValueError('VersionHistory.md must be a regular file')
    history = (root / HISTORY).read_text(encoding='utf-8')
    current = json.loads((root / 'data/app.json').read_text())['version']
    return command('git', 'rev-parse', 'HEAD', cwd=root), history, current


def preflight(root, log):
    if os.geteuid() == 0:
        raise ValueError('run as the publishing user, without sudo or pkexec')
    required = ('git', 'gpg', 'dpkg-buildpackage', 'dpkg-parsechangelog', 'dpkg-checkbuilddeps',
                'dpkg', 'make', 'lintian', 'debsign', 'dput', 'sbuild', 'mmdebstrap',
                'newuidmap', 'newgidmap', 'unshare')
    if any(shutil.which(tool, path='/usr/sbin:/usr/bin:/sbin:/bin') is None for tool in required):
        raise ValueError('missing prerequisites; use ./setup.sh --dependencies-only')
    if command('dpkg', '--print-architecture', cwd=root) != 'amd64':
        raise ValueError('publishing requires an amd64 development host')
    ppa_build.check_prerequisites()
    command('unshare', '--user', '--map-root-user', 'true', cwd=root, log=log)
    command('dpkg-checkbuilddeps', cwd=root, log=log)
    command('make', 'check-release-version', cwd=root, log=log)
    archive_preflight()
    signer = root / 'tools/publishing/signing.py'
    if not os.access(signer, os.X_OK):
        raise ValueError('restore the executable mode of tools/publishing/signing.py')
    # Sign harmless fixed bytes immediately; fail on unavailable credentials
    # before a long build. The secret is read only by the signer subprocess.
    probe = log.parent / 'signing-probe.txt'
    probe.write_text('Oh No! Parent Control publishing credential preflight.\n')
    command(str(signer), '--local-user', release.KEY, '--armor', '--detach-sign',
            '--output', str(probe.with_suffix('.asc')), str(probe), cwd=root, log=log)
    # Dry-run validates SSH/push permission without publishing any refs.
    command('git', 'push', '--dry-run', release.ORIGIN, 'HEAD:refs/heads/main', cwd=root, log=log)


def prepare(root, base, history, current, product, notes, directory):
    checkout = directory / 'source'
    log = directory / 'release.log'
    preflight(root, log)
    command('git', 'clone', '--no-hardlinks', str(root), str(checkout), log=log)
    command('git', 'checkout', '--detach', base, cwd=checkout, log=log)
    command('git', 'remote', 'set-url', 'origin', release.ORIGIN, cwd=checkout)
    command('git', 'fetch', '--tags', 'origin', 'main', cwd=checkout, log=log)
    command('git', 'merge-base', '--is-ancestor', 'FETCH_HEAD', base, cwd=checkout, log=log)
    known = [item['source_package_version'] for item in sources()]
    known += [tag[1:].replace('_', '~') for tag in command('git', 'tag', '--list', cwd=checkout).splitlines()
              if re.fullmatch(r'v[0-9]+\.[0-9]+(?:\+ppa[0-9]+_ubuntu26\.04\.1)?', tag)]
    known.append(command('dpkg-parsechangelog', '-S', 'Version', cwd=checkout))
    version = release.next_version(product, known)
    for old in known:
        command('dpkg', '--compare-versions', version, 'gt', old, cwd=checkout)
    tags = (release.source_tag(version), 'v' + product)
    existing_tags = command('git', 'tag', '--list', cwd=checkout).splitlines()
    if any(tag in existing_tags for tag in tags):
        raise ValueError('release tag already exists; published tags cannot be reused')
    for key, value in {'user.name': release.NAME, 'user.email': release.EMAIL,
                       'user.signingkey': release.KEY, 'gpg.format': 'openpgp',
                       'gpg.program': str(root / 'tools/publishing/signing.py'),
                       'commit.gpgsign': 'true', 'tag.gpgsign': 'true'}.items():
        command('git', 'config', '--local', key, value, cwd=checkout)
    (checkout / HISTORY).write_text(history, encoding='utf-8')
    (checkout / 'data/app.json').write_text(json.dumps({'version': product}, indent=2) + '\n')
    changelog = checkout / 'debian/changelog'
    changelog.write_text(changelog_entry(version, notes) + changelog.read_text(), encoding='utf-8')
    command('make', 'check-release-version', cwd=checkout, log=log)
    command('git', 'diff', '--check', cwd=checkout, log=log)
    command('git', 'add', '--', HISTORY, 'data/app.json', 'debian/changelog', cwd=checkout)
    command('git', 'commit', '-m', f'Release {product} ({version})', cwd=checkout, log=log)
    for tag in tags:
        command('git', 'tag', '-s', tag, '-m', f'Oh No! Parent Control {version}', cwd=checkout, log=log)
    revision = command('git', 'rev-parse', 'HEAD', cwd=checkout)
    return dict(phase='prepared', base=base, current=current, product=product, version=version,
                revision=revision, source_tag=tags[0], product_tag=tags[1],
                history_sha256=hashlib.sha256(history.encode()).hexdigest(), directory=str(directory),
                checkout=str(root), created=datetime.now(timezone.utc).isoformat())


def inspect_source(checkout, log):
    with log.open('a') as stream, redirect_stdout(stream), redirect_stderr(stream):
        # Existing verifier compares the entire signed source archive with Git.
        release.inspect(checkout)


def verify_frozen(state):
    directory = Path(state['directory'])
    checkout = directory / 'source'
    if command('git', 'rev-parse', 'HEAD', cwd=checkout) != state['revision']:
        raise ValueError('release checkout HEAD changed; retained artifacts cannot be published')
    if command('git', 'status', '--porcelain', '--untracked-files=all', cwd=checkout):
        raise ValueError('release checkout changed; restore the frozen release inputs')
    for name, expected in state.get('source_sha256', {}).items():
        if PurePosixPath(name).name != name or digest(directory / name) != expected:
            raise ValueError('frozen upload artifact changed')


def dput_config(directory):
    path = directory / 'dput.cf'
    path.write_text(f'''[onpc]
fqdn = ppa.launchpad.net
method = ftp
incoming = ~{release.OWNER}/ubuntu/{release.PACKAGE}/
login = anonymous
allow_unsigned_uploads = 0
allow_dcut = 0
run_lintian = 0
run_dinstall = 0
check_version = 0
passive_ftp = 1
allowed_distributions = ^resolute$
pre_upload_command =
post_upload_command =
''')
    return path


def published_binary(version):
    """Return only when the exact source/build/binary and apt index agree."""
    entries = [item for item in sources(version) if item['source_package_version'] == version
               and item['distro_series_link'] == SERIES]
    if any(item['status'] in ('Deleted', 'Obsolete', 'Superseded') for item in entries):
        raise ValueError('release source was removed or superseded; inspect the PPA')
    for source in entries:
        builds = collection(source['self_link'] + '?ws.op=getBuilds')
        for build in builds:
            if build['arch_tag'] != 'amd64':
                raise ValueError('Launchpad started an architecture not validated locally')
            status = build['buildstate']
            if status in ('Failed to build', 'Dependency wait', 'Chroot problem', 'Build for superseded Source',
                          'Failed to upload', 'Cancelled', 'Cannot be built'):
                raise ValueError(f'Launchpad build {status}; {build["web_link"]}')
        if (source['status'] != 'Published' or not builds
                or any(build['buildstate'] != 'Successfully built' for build in builds)):
            continue
        query = urlencode({'ws.op': 'getPublishedBinaries', 'binary_name': release.PACKAGE,
                           'exact_match': 'true', 'version': version, 'status': 'Published'})
        binaries = collection(API + '?' + query)
        if not any(item['binary_package_version'] == version
                   and item['source_package_version'] == version
                   and item['distro_arch_series_link'] == SERIES + '/amd64'
                   and item['build_link'] in {build['self_link'] for build in builds}
                   for item in binaries):
            continue
        try:
            index = gzip.decompress(read_url(PPA_FILES + 'dists/resolute/main/binary-amd64/Packages.gz')).decode()
        except HTTPError as error:
            if error.code == 404:
                return None
            raise
        for paragraph in index.split('\n\n'):
            fields = dict(line.split(': ', 1) for line in paragraph.splitlines()
                          if ': ' in line and not line.startswith(' '))
            if (fields.get('Package'), fields.get('Version'), fields.get('Architecture')) != (
                    release.PACKAGE, version, 'amd64'):
                continue
            name = fields['Filename']
            if not name.startswith('pool/') or '..' in PurePosixPath(name).parts or '?' in name or '#' in name:
                raise ValueError('unsafe PPA binary filename')
            binary = read_url(PPA_FILES + name)
            if len(binary) != int(fields['Size']) or hashlib.sha256(binary).hexdigest() != fields['SHA256']:
                raise ValueError('published binary does not match the PPA package index')
            return dict(version=version, architecture='amd64', filename=name,
                        size=len(binary), sha256=fields['SHA256'], builds=[b['web_link'] for b in builds])
    return None


def wait_for_publication(state, state_path):
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            binary = published_binary(state['version'])
        except (URLError, TimeoutError, ConnectionError) as error:
            if isinstance(error, HTTPError) and error.code not in (404, 408, 429, 500, 502, 503, 504):
                raise
            say('publication status temporarily unavailable; retrying', error=True)
        else:
            if binary is not None:
                state['binary'] = binary
                state['phase'] = 'published'
                save(state_path, state)
                return
            say('waiting for Launchpad acceptance, amd64 build, and PPA package index')
        time.sleep(POLL_SECONDS)
    raise ValueError('publication not confirmed within 24 hours; rerun to resume monitoring without re-uploading; '
                     'check Launchpad and the publisher rejection email if no source was accepted')


def finish_checkout(root, state, log):
    base, history, _ = source_state(root)
    if base == state['revision']:
        return
    if base != state['base'] or hashlib.sha256(history.encode()).hexdigest() != state['history_sha256']:
        raise ValueError('PPA published, but development checkout changed; rerun after preserving/reconciling local work')
    checkout = Path(state['directory']) / 'source'
    command('git', 'fetch', str(checkout), state['revision'], cwd=root, log=log)
    # Staging exactly the already-frozen history permits the fast-forward even
    # when the manually written history was initially untracked/uncommitted.
    command('git', 'add', '--', HISTORY, cwd=root)
    command('git', 'merge', '--ff-only', '--no-edit', state['revision'], cwd=root, log=log)
    command('git', 'fetch', '--tags', 'origin', cwd=root, log=log)


def execute(root, state, state_path):
    directory = Path(state['directory'])
    checkout = directory / 'source'
    log = directory / 'release.log'
    changes = directory / f'{release.PACKAGE}_{state["version"]}_source.changes'

    def advance(phase):
        state['phase'] = phase
        save(state_path, state)
        save(directory / 'release.json', state)

    verify_frozen(state)
    if state['phase'] == 'prepared':
        say(f'building and signing source {state["version"]}; evidence: {directory}')
        command('dpkg-buildpackage', '--build=source', '--no-sign', '-sa', cwd=checkout, log=log, timeout=3600)
        command('debsign', '--no-conf', '--re-sign', '-k' + release.KEY,
                '-p' + str(root / 'tools/publishing/signing.py'), str(changes), cwd=checkout, log=log)
        inspect_source(checkout, log)
        state['source_sha256'] = json.loads((directory / 'source-review.json').read_text())['sha256']
        advance('signed')
    if state['phase'] == 'signed':
        say('running clean resolute/amd64 sbuild, declared tests, and binary Lintian checks')
        result = ppa_build.check_build(checkout)
        build_directory = Path(result['directory'])
        command('lintian', '--no-cfg', '--fail-on', 'error', str(build_directory / 'output' /
                f'{release.PACKAGE}_{state["version"]}_amd64.changes'), cwd=checkout, log=log)
        state['local_build'] = result
        advance('built')
    if state['phase'] == 'built':
        verify_frozen(state)
        inspect_source(checkout, log)
        archive_preflight()
        if any(item['source_package_version'] == state['version'] for item in sources(state['version'])):
            raise ValueError('candidate version appeared in the PPA before this upload; refusing to reuse it')
        config = dput_config(directory)
        command('dput', '-c', str(config), '--check-only', 'onpc', str(changes), cwd=checkout, log=log)
        advance('push-started')
    if state['phase'] == 'push-started':
        verify_frozen(state)
        say('local checks passed; publishing signed source and tags')
        command('git', 'push', '--atomic', 'origin', 'HEAD:refs/heads/main',
                'refs/tags/' + state['source_tag'], 'refs/tags/' + state['product_tag'], cwd=checkout, log=log)
        advance('pushed')
    if state['phase'] == 'pushed':
        verify_frozen(state)
        inspect_source(checkout, log)
        # Anonymous public Git read proves both annotated tags refer to the
        # release commit before the package is made available to subscribers.
        refs = command('git', 'ls-remote', PUBLIC_GIT,
                       'refs/tags/' + state['source_tag'] + '^{}',
                       'refs/tags/' + state['product_tag'] + '^{}', cwd=checkout, log=log)
        found = dict(line.split()[::-1] for line in refs.splitlines())
        if any(found.get('refs/tags/' + state[name] + '^{}') != state['revision']
               for name in ('source_tag', 'product_tag')):
            raise ValueError('signed release source is not yet publicly retrievable; rerun to retry')
        config = dput_config(directory)
        # A crash or network error from here on has an uncertain remote result.
        # Write the journal first and NEVER automatically repeat this upload.
        advance('upload-started')
        say('uploading signed source to Launchpad')
        try:
            command('dput', '-c', str(config), 'onpc', str(changes), cwd=checkout, log=log, timeout=1800)
        except (ValueError, subprocess.TimeoutExpired):
            say('upload result uncertain; checking Launchpad without repeating the upload', error=True)
    if state['phase'] == 'upload-started':
        wait_for_publication(state, state_path)
    if state['phase'] == 'published':
        finish_checkout(root, state, log)
        advance('complete')
    say(f'published {state["version"]} for resolute/amd64; report: {directory / "release.json"}', success=True)


def publish(root=ROOT):
    with locked(root) as state_path:
        base, history, current = source_state(root)
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        if state is not None and state['phase'] != 'complete':
            if state['checkout'] != str(root) or state['phase'] not in PHASES:
                raise ValueError('unfinished release belongs to a different checkout or has an invalid journal')
            changed = (base not in (state['base'], state['revision'])
                       or hashlib.sha256(history.encode()).hexdigest() != state['history_sha256'])
            if changed and state['phase'] in ('prepared', 'signed', 'built'):
                # Neither push nor upload was ever attempted. Retain the old
                # evidence and let a corrected committed source start fresh.
                history_entry(history, current)
                save(Path(state['directory']) / 'release.json',
                     dict(state, outcome='replaced-before-publication'))
                say('source changed before publication; retaining old evidence and preparing a fresh attempt')
            elif changed:
                raise ValueError('unfinished release inputs differ; preserve its journal and reconcile the checkout before retrying')
            else:
                say(f'resuming {state["version"]} at {state["phase"]}')
                execute(root, state, state_path)
                return
        product, notes = history_entry(history, current)
        directory = Path(tempfile.mkdtemp(prefix='onpc-release-', dir='/tmp'))
        say(f'preparing {current} → {product}; evidence: {directory}')
        state = prepare(root, base, history, current, product, notes, directory)
        save(state_path, state)
        save(directory / 'release.json', state)
        execute(root, state, state_path)


class PublisherParser(argparse.ArgumentParser):
    def error(self, message):
        say('this publisher accepts no parameters; use --help for usage', error=True)
        self.exit(2)


def main(argv=None):
    parser = PublisherParser(description=__doc__, allow_abbrev=False)
    parser.parse_args(argv)  # No parameters, overrides, hooks, or interactive fallback.
    original_env = dict(os.environ)
    safe_env = environment()
    try:
        os.environ.clear()
        os.environ.update(safe_env)
        publish()
    except ValueError as error:
        say(str(error), error=True)
        return 1
    except (OSError, KeyError, TypeError, tarfile.TarError, subprocess.SubprocessError) as error:
        say(f'stopped ({type(error).__name__}); check prerequisites and the retained release log', error=True)
        return 1
    except KeyboardInterrupt:
        say('interrupted; rerun the same command to resume the recorded release', error=True)
        return 130
    finally:
        os.environ.clear()
        os.environ.update(original_env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
