#!/usr/bin/env python3
"""Build digest-identified Debian/Fedora and application-fixture test artifacts.

The output is an input to the guarded installed-system runner. This builder
never installs the product: package construction happens in a private source
copy and application fixtures are emitted as an ordinary payload directory.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tarfile
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools import package_inputs


REPOSITORY = Path(__file__).resolve().parents[1]
FIXTURE_BUILDER = REPOSITORY / "tests/fixtures/build_test_applications.py"
MANIFEST_NAME = "artifact-manifest.json"
SCHEMA_VERSION = 1
PACKAGE_INPUT_NAME = 'package-input.json'
PACKAGE_INPUT_SCHEMA = 'onpc-package-input-v1'
# Published annotated v1.2 tag and its peeled commit, independently matched to
# the public GitHub tag object. The published tag is unsigned. Qualification
# never substitutes the working tree or rewrites its version for this input.
RELEASE_TAG = 'f0520a6f36ad43f57357cdc9e8cd9fa1216e73ae'
RELEASE_COMMIT = '81ffa5c37abeefdc922825bc27b5933b3eff3ba6'
RELEASE_VERSION = '1.2+ppa1~ubuntu26.04.1'
PREVIOUS_RELEASES = {
    'deb': {'name': 'v1.2', 'tag': RELEASE_TAG, 'commit': RELEASE_COMMIT,
            'version': RELEASE_VERSION, 'architecture': 'amd64'},
    # Unsigned v1.3 annotated tag/commit independently matched to GitHub's
    # public git/tags API on 2026-10-17. It contains the Fedora 44 recipe.
    # Build those exact inputs with the maintained builder; never backport
    # today's packaging.
    'rpm': {'name': 'v1.3', 'tag': '8e2423f3308893cc8a582cb2a66f60aab5f88a77',
            'commit': '188be907c46b1cd0dabae06ac898c43e75beb05e',
            'version': '0:1.3-0.1.dev.fc44', 'architecture': 'x86_64'},
}


class ArtifactError(RuntimeError):
    """A reproducible artifact operation cannot continue safely."""


def _log(stage: str, outcome: str, **fields: str) -> None:
    suffix = " ".join(f"{name}={value}" for name, value in sorted(fields.items()))
    print(f"test-artifacts: stage={stage} outcome={outcome}" + (f" {suffix}" if suffix else ""), file=sys.stderr)


def _run(command: list[str], *, cwd: Path | None = None, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    from tools.test_storage import scratch_descriptors
    try:
        return subprocess.run(command, cwd=cwd, env=environment, check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              pass_fds=scratch_descriptors())
    except (OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            diagnostic = ((error.stdout or "") + "\n" + (error.stderr or "")).strip().splitlines()
            category = " | ".join(diagnostic[-180:]) if diagnostic else f"exit-{error.returncode}"
            _log("tool", "failed", command=command[0], category=category)
        raise ArtifactError(f"command failed: {command[0]}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_empty_output(output: Path) -> Path:
    resolved = output.resolve(strict=False)
    if ((resolved == REPOSITORY or REPOSITORY in resolved.parents)
            and not resolved.is_relative_to(REPOSITORY / 'output/test-runs')):
        raise ArtifactError("artifact output must be outside the source checkout")
    if resolved.exists():
        if not resolved.is_dir() or any(resolved.iterdir()):
            raise ArtifactError("artifact output directory must be empty")
    else:
        resolved.mkdir(parents=True, mode=0o755)
    return resolved


def _source_paths() -> list[Path]:
    result = _run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z",
                   "--", "."], cwd=REPOSITORY)
    paths = sorted({Path(name) for name in result.stdout.split("\0")
                    if name})
    if not paths or any(path.is_absolute() or ".." in path.parts for path in paths):
        raise ArtifactError("source input list is invalid")
    present = []
    for path in paths:
        try:
            # Git's index includes unstaged deletions. Hash/copy the current
            # working tree, but retain links and special files for rejection.
            (REPOSITORY / path).lstat()
        except FileNotFoundError:
            continue
        present.append(path)
    if not present:
        raise ArtifactError("source input list is empty")
    return sorted(present)


def _source_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for relative in paths:
        candidate = REPOSITORY / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise ArtifactError(f"source input is not a regular file: {relative}")
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        digest.update(f"{candidate.stat().st_mode & 0o7777:o}".encode("ascii") + b"\0")
        with candidate.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def _copy_source(paths: list[Path], destination: Path, *, root=None) -> None:
    root = REPOSITORY if root is None else root
    for relative in paths:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)


def _command_version(command: list[str]) -> str:
    result = _run(command)
    line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not line:
        line = next((line.strip() for line in result.stderr.splitlines() if line.strip()), "")
    if not line:
        raise ArtifactError(f"tool did not report a version: {command[0]}")
    return line


def _fixture_digest(payload: Path) -> str:
    manifest = payload / "SHA256SUMS.json"
    try:
        contents = json.loads(manifest.read_text(encoding="utf-8"))
        files = contents["files"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ArtifactError("fixture builder did not produce a valid digest manifest") from error
    if contents.get("algorithm") != "sha256" or not isinstance(files, dict):
        raise ArtifactError("fixture digest manifest has an unsupported format")
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _metadata(source_paths: list[Path], source_digest: str) -> dict[str, Any]:
    # Documentation-only commits must not change package timestamps or identity.
    selection = ['HEAD', '--', *(path.as_posix() for path in source_paths)]
    revision = _run(['git', 'log', '-1', '--format=%H', *selection], cwd=REPOSITORY).stdout.strip()
    epoch = _run(['git', 'log', '-1', '--format=%ct', *selection], cwd=REPOSITORY).stdout.strip()
    architecture = _run(["dpkg-architecture", "-qDEB_HOST_ARCH"], cwd=REPOSITORY).stdout.strip()
    if not revision or not epoch.isdecimal() or not architecture:
        raise ArtifactError("source revision metadata is invalid")
    return {
        "source": {"revision": revision, "digest_sha256": source_digest, "file_count": len(source_paths),
                   "scope": "package"},
        "build_inputs": {"source_date_epoch": int(epoch), "architecture": architecture,
                         "deb_build_options": "nocheck parallel=2",
                         "package_command": ["dpkg-buildpackage", "--build=binary", "--no-sign", f"-a{architecture}"]},
        "tools": {"dpkg-architecture": _command_version(["dpkg-architecture", "--version"]),
                  "dpkg-buildpackage": _command_version(["dpkg-buildpackage", "--version"]),
                  "dpkg-deb": _command_version(["dpkg-deb", "--version"]),
                  "flatpak": _command_version(["flatpak", "--version"])},
    }


def build(output: Path, *, package_format, reuse: dict[str, Path] | None = None) -> Path:
    if package_format not in ('deb', 'rpm'):
        raise ArtifactError('unsupported package format')
    source_paths = package_inputs.paths(REPOSITORY)
    source_digest = package_inputs.digest(REPOSITORY, source_paths)
    metadata = _metadata(source_paths, source_digest)
    return _build(output, REPOSITORY, source_paths, source_digest, metadata,
                  reuse=reuse, package_format=package_format)


def _build(output, source_root, source_paths, source_digest, metadata, *, package_format, reuse=None):
    if package_format not in ('deb', 'rpm'):
        raise ArtifactError('unsupported package format')
    output = _require_empty_output(output)
    reuse = reuse or {}
    if package_format == 'rpm':
        from tools.build_rpm import metadata as rpm_metadata
        metadata['build_inputs'].update(package_format='rpm', architecture='x86_64',
                                       source_date_epoch=rpm_metadata(source_root, '0.1.dev')[1],
                                       package_command=['tools/build_rpm.py'])
    _log("build", "started", revision=metadata["source"]["revision"][:12])
    from tools.test_storage import scratch_directory
    with tempfile.TemporaryDirectory(prefix="onpc-package-build-", dir=scratch_directory()) as temporary_name:
        temporary = Path(temporary_name)
        # Stable, private build settings; caller desktop/terminal/home settings
        # cannot affect either artifacts or their reuse identity.
        home = temporary / 'home'
        home.mkdir()
        environment = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8",
                       "HOME": str(home), "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                       "SOURCE_DATE_EPOCH": str(metadata["build_inputs"]["source_date_epoch"]),
                                    "DEB_BUILD_OPTIONS": metadata["build_inputs"]["deb_build_options"]}
        package_output = output / "package"
        if 'package' in reuse:
            shutil.copytree(reuse['package'], package_output)
            packages = sorted(package_output.glob('oh-no-parent-control_*.deb' if
                package_format == 'deb' else 'oh-no-parent-control-[0-9]*.x86_64.rpm'))
        else:
            source_copy = temporary / "source"
            source_copy.mkdir()
            _copy_source(source_paths, source_copy, root=source_root)
            if (package_inputs.paths(source_root) != source_paths
                    or package_inputs.digest(source_root, source_paths) != source_digest
                    or package_inputs.digest(source_copy, source_paths) != source_digest):
                raise ArtifactError('package source inputs changed while copying')
            if package_format == 'rpm':
                # Keep the caller's rootless build image/storage identity. The
                # maintained builder freezes inputs and disables networking.
                from tools.build_rpm import build as build_rpm
                build_rpm(source_copy, package_output)
                packages = sorted(package_output.glob('oh-no-parent-control-[0-9]*.x86_64.rpm'))
            else:
                _run(metadata["build_inputs"]["package_command"], cwd=source_copy, environment=environment)
                packages = sorted(temporary.glob("oh-no-parent-control_*.deb"))
                package_output.mkdir()
        if len(packages) != 1:
            raise ArtifactError("package build did not produce exactly one binary package")
        destination = package_output / packages[0].name
        if packages[0] != destination:
            shutil.copyfile(packages[0], destination)
        fixture_output = output / "fixtures"
        if 'fixtures' in reuse:
            shutil.copytree(reuse['fixtures'], fixture_output)
        else:
            # Fixture contents are independent of the product commit timestamp.
            fixture_environment = environment | {'SOURCE_DATE_EPOCH': '0'}
            _run([sys.executable, '-I', '-S', '-B', str(FIXTURE_BUILDER), "--output", str(fixture_output)],
                 cwd=REPOSITORY, environment=fixture_environment)
        manifest = {"schema_version": SCHEMA_VERSION, **metadata, "artifacts": {
            "package": {"path": f"package/{destination.name}", "sha256": _sha256(destination)},
            "fixtures": {"path": "fixtures", "digest_manifest": "fixtures/SHA256SUMS.json", "sha256": _fixture_digest(fixture_output)},
        }}
        (output / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify(output)
    _log("build", "passed", package=destination.name)
    return output / MANIFEST_NAME


@contextmanager
def released_source(*, repository=None, package_format='deb'):
    """Read a format's pinned release into shared scratch, without Git edits."""
    release = _require_previous_release(package_format)
    repository = REPOSITORY if repository is None else repository
    prefix = ['git', '-c', 'safe.directory=' + str(repository)]
    tag = _run([*prefix, 'rev-parse', 'refs/tags/' + release['name']], cwd=repository).stdout.strip()
    commit = _run([*prefix, 'rev-parse', release['tag'] + '^{commit}'], cwd=repository).stdout.strip()
    if tag != release['tag'] or commit != release['commit']:
        raise ArtifactError(f"authentic {release['name']} release source unavailable")
    from tools.test_storage import scratch_directory, scratch_descriptors
    with tempfile.TemporaryDirectory(prefix='onpc-release-source-', dir=scratch_directory()) as name:
        root = Path(name)
        raw = subprocess.run([*prefix, 'archive', '--format=tar', release['commit']],
            cwd=repository, check=True, capture_output=True, pass_fds=scratch_descriptors()).stdout
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            # Source links and special files are never accepted as build inputs.
            for entry in archive.getmembers():
                if (Path(entry.name).is_absolute() or '..' in Path(entry.name).parts
                        or not (entry.isfile() or entry.isdir())):
                    raise ArtifactError('unsafe released source archive')
            archive.extractall(root, filter='data')
        yield root


def release_identity(root, *, package_format='deb'):
    release = _require_previous_release(package_format)
    selected = package_inputs.paths(root)
    return {'revision': release['commit'], 'release_tag': release['tag'], 'scope': 'package',
            'digest_sha256': package_inputs.digest(root, selected), 'file_count': len(selected)}


def _require_previous_release(package_format):
    if package_format not in PREVIOUS_RELEASES:
        raise ArtifactError('unsupported upgrade package format')
    return PREVIOUS_RELEASES[package_format]


def build_upgrade(output, *, package_format):
    """Finite genuine release/current preparation; no fabricated predecessor."""
    release = _require_previous_release(package_format)
    output = _require_empty_output(output)
    build(output / 'current', package_format=package_format)
    with released_source(package_format=package_format) as root:
        selected = package_inputs.paths(root)
        source = release_identity(root, package_format=package_format)
        metadata = _metadata(package_inputs.paths(REPOSITORY), source['digest_sha256'])
        metadata['source'] = source
        metadata['build_inputs']['source_date_epoch'] = int(_run(
            ['git', 'show', '-s', '--format=%ct', release['commit']], cwd=REPOSITORY).stdout.strip())
        _build(output / 'previous', root, selected, source['digest_sha256'], metadata,
               package_format=package_format)
    verify_upgrade(output)


def package_identity(path):
    if path.suffix == '.rpm':
        values = _run(['rpm', '-qp', '--queryformat',
            '%{NAME}\n%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n%{ARCH}\n', str(path)]).stdout.splitlines()
        if len(values) != 3 or any(not value or '\t' in value for value in values):
            raise ArtifactError('package identity unavailable')
        return {'name': values[0], 'version': values[1], 'architecture': values[2],
                'sha256': _sha256(path)}
    values = _run(['dpkg-deb', '-f', str(path), 'Package', 'Version', 'Architecture']).stdout.splitlines()
    # dpkg prints field prefixes for a multi-field query.
    fields = dict(row.split(': ', 1) for row in values)
    if set(fields) != {'Package', 'Version', 'Architecture'}:
        raise ArtifactError('package identity unavailable')
    return {'name': fields['Package'], 'version': fields['Version'],
            'architecture': fields['Architecture'], 'sha256': _sha256(path)}


def _require_newer_version(new, old, *, package_format):
    if package_format == 'deb':
        _run(['dpkg', '--compare-versions', new, 'gt', old])
        return
    # Compare epoch, version and release separately with RPM's own comparator.
    # Strict EVR parsing also keeps package header values out of Lua syntax.
    pattern = r'([0-9]+):([A-Za-z0-9][A-Za-z0-9._+~^]*)-([A-Za-z0-9][A-Za-z0-9._+~^]*)'
    values = [re.fullmatch(pattern, value) for value in (new, old)]
    if any(value is None for value in values):
        raise ArtifactError('invalid RPM upgrade version')
    for current, previous in zip(values[0].groups(), values[1].groups()):
        result = _run(['rpm', '--eval',
            '%{lua:print(rpm.vercmp("' + current + '","' + previous + '"))}']).stdout.strip()
        if result == '1':
            return
        if result != '0':
            raise ArtifactError('RPM upgrade version is not newer')
    raise ArtifactError('RPM upgrade version is not newer')


def verify_upgrade(output, *, staged=False, repository=None, package_only=False):
    """Independently bind both manifests, source identities and exact package bytes."""
    output = Path(output)
    if output.resolve() != output or not output.is_dir():
        raise ArtifactError('unsafe upgrade asset directory')
    owner = output.stat().st_uid
    if owner not in (os.geteuid(), REPOSITORY.stat().st_uid):
        raise ArtifactError('unsafe upgrade asset owner')
    for path in (output, *output.rglob('*')):
        info = path.lstat()
        if (path.resolve() != path or info.st_uid != owner or info.st_mode & 0o022
                or not (stat.S_ISDIR(info.st_mode) or
                        (stat.S_ISREG(info.st_mode) and info.st_nlink == 1))):
            raise ArtifactError('unsafe upgrade asset file')
    if not staged:
        if set(path.name for path in output.iterdir()) != {'current', 'previous'}:
            raise ArtifactError('upgrade input layout mismatch')
        for root in (output / 'current', output / 'previous'):
            if any(os.path.lexists(root / name) for name in (
                    'package.deb', 'package.rpm', 'installed-files.json', 'transfer-sha256.json', 'previous')):
                raise ArtifactError('upgrade staging name collision')
    current_root = output if staged else output / 'current'
    options = {'package_only': True} if package_only else {}
    current, previous = verify(current_root, **options), verify(output / 'previous', **options)
    formats = {Path(manifest['artifacts']['package']['path']).suffix
               for manifest in (current, previous)}
    if len(formats) != 1:
        raise ArtifactError('upgrade package format mismatch')
    package_format = formats.pop().removeprefix('.')
    release = _require_previous_release(package_format)
    with released_source(repository=repository, package_format=package_format) as root:
        if previous['source'] != release_identity(root, package_format=package_format):
            raise ArtifactError(f"{release['name']} source identity mismatch")
    repository = REPOSITORY if repository is None else repository
    selected = package_inputs.paths(repository)
    if (set(current['source']) != {'revision', 'scope', 'digest_sha256', 'file_count'}
            or type(current['source']['revision']) is not str
            or re.fullmatch(r'[0-9a-f]{40}', current['source']['revision']) is None
            or current['source'].get('scope') != 'package'
            or current['source'].get('digest_sha256') != package_inputs.digest(repository, selected)
            or current['source'].get('file_count') != len(selected)):
        raise ArtifactError('current package source identity mismatch')
    identities = {}
    for label, directory, manifest in (('current', current_root, current),
                                       ('previous', output / 'previous', previous)):
        item = package_identity(directory / manifest['artifacts']['package']['path'])
        if item['name'] != 'oh-no-parent-control' or item['architecture'] != release['architecture']:
            raise ArtifactError('upgrade package product or architecture mismatch')
        identities[label] = item
    old, new = identities['previous'], identities['current']
    if package_format == 'rpm':
        from tools.build_rpm import metadata as rpm_metadata
        expected = f"0:{rpm_metadata(repository, '0.1.dev')[0]}-0.1.dev.fc44"
    else:
        expected = _run(['dpkg-parsechangelog', '-l' + str(repository / 'debian/changelog'),
                         '-S', 'Version']).stdout.strip()
    if (old['version'] != release['version'] or new['version'] != expected
            or old['sha256'] == new['sha256']
            or current['source']['digest_sha256'] == previous['source']['digest_sha256']):
        raise ArtifactError('upgrade package release identity mismatch')
    _require_newer_version(new['version'], old['version'], package_format=package_format)
    return {'packages': identities, 'sources': {'current': current['source'], 'previous': previous['source']}}


def verify_package_input(output: Path) -> dict[str, Any]:
    """Verify a controller-staged package without claiming a fixture collection.

    This distinct schema carries the original verified source identity, exact
    package alias and installation metadata. It is never a full artifact input.
    """
    try:
        manifest = json.loads((output / PACKAGE_INPUT_NAME).read_text(encoding='utf-8'))
        if (type(manifest) is not dict or set(manifest) != {
                'schema', 'source', 'artifacts', 'installed_files_sha256'}
                or manifest['schema'] != PACKAGE_INPUT_SCHEMA
                or type(manifest['source']) is not dict
                or type(manifest['artifacts']) is not dict
                or set(manifest['artifacts']) != {'package'}):
            raise ValueError('fields')
        package = manifest['artifacts']['package']
        if (type(package) is not dict or set(package) != {'path', 'sha256'}
                or package['path'] not in ('package.deb', 'package.rpm')
                or any(type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None
                       for value in (package['sha256'], manifest['installed_files_sha256']))):
            raise ValueError('package')
        for name, expected in ((package['path'], package['sha256']),
                               ('installed-files.json', manifest['installed_files_sha256'])):
            path = output / name
            info = path.lstat()
            if (path.resolve() != path or not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1 or _sha256(path) != expected):
                raise ValueError('bytes')
        alternate = 'package.rpm' if package['path'] == 'package.deb' else 'package.deb'
        if os.path.lexists(output / alternate) or os.path.lexists(output / MANIFEST_NAME):
            raise ValueError('ambiguous input')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ArtifactError('package input verification failed') from error
    return manifest


def verify(output: Path, *, package_only=False) -> dict[str, Any]:
    if package_only:
        return verify_package_input(output)
    try:
        manifest = json.loads((output / MANIFEST_NAME).read_text(encoding="utf-8"))
        package = manifest["artifacts"]["package"]
        fixtures = manifest["artifacts"]["fixtures"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ArtifactError("artifact manifest is invalid") from error
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ArtifactError("artifact manifest schema is unsupported")
    package_path = (output / package.get("path", "")).resolve(strict=False)
    if output not in package_path.parents or not package_path.is_file() or package.get("sha256") != _sha256(package_path):
        raise ArtifactError("package artifact digest verification failed")
    fixture_path = (output / fixtures.get("path", "")).resolve(strict=False)
    if output not in fixture_path.parents or not fixture_path.is_dir() or fixtures.get("sha256") != _fixture_digest(fixture_path):
        raise ArtifactError("fixture artifact digest verification failed")
    _log("verify", "passed")
    return manifest


def compare(first: Path, second: Path) -> None:
    first_manifest = verify(first)
    second_manifest = verify(second)
    for key in ("source", "build_inputs"):
        if first_manifest[key] != second_manifest[key]:
            raise ArtifactError(f"repeated build changed {key}")
    first_package = first_manifest["artifacts"]["package"]
    second_package = second_manifest["artifacts"]["package"]
    if first_package["path"] != second_package["path"] or first_package["sha256"] != second_package["sha256"]:
        raise ArtifactError("repeated build changed the package")
    for path in (first / first_package["path"], second / second_package["path"]):
        if path.suffix == '.rpm':
            _run(['rpm', '-qpi', str(path)])
            _run(['rpm', '-qpl', str(path)])
        else:
            _run(["dpkg-deb", "--info", str(path)])
            _run(["dpkg-deb", "--contents", str(path)])
    if first_manifest["artifacts"]["fixtures"] != second_manifest["artifacts"]["fixtures"]:
        raise ArtifactError("repeated build changed the fixture payload")
    _log("reproducibility", "passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="an empty output directory outside the checkout")
    parser.add_argument("--verify", action="store_true", help="verify an existing artifact manifest")
    parser.add_argument("--reuse", action="store_true", help="prepare verified matching inputs, building on a cache miss")
    parser.add_argument('--package-format', choices=('deb', 'rpm'),
                        help='required for every build; no default package format')
    parser.add_argument('--upgrade-inputs', action='store_true',
                        help='build pinned genuine prior-release/current inputs for the selected format')
    parser.add_argument('--native-inputs', action='store_true',
                        help='prepare the reviewed finite native dependency pair, not product packages')
    parser.add_argument('--verify-native-inputs', action='store_true',
                        help='reverify a native dependency bundle without changing it')
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("FIRST", "SECOND"), help="compare two built artifact directories")
    arguments = parser.parse_args()
    if not (arguments.verify or arguments.compare or arguments.verify_native_inputs) and arguments.package_format is None:
        parser.error('--package-format deb|rpm is required when building')
    try:
        if arguments.native_inputs or arguments.verify_native_inputs:
            from tools.native_transaction_inputs import prepare, verify as verify_native
            if (arguments.output is None or arguments.verify or arguments.compare or
                    arguments.reuse or arguments.upgrade_inputs or
                    arguments.native_inputs and arguments.verify_native_inputs):
                raise ArtifactError('native inputs require only --output and an explicit build format')
            if arguments.verify_native_inputs:
                verify_native(arguments.output, package_format=arguments.package_format)
            else:
                prepare(arguments.output, package_format=arguments.package_format)
        elif arguments.upgrade_inputs:
            if arguments.output is None or arguments.verify or arguments.compare or arguments.reuse:
                raise ArtifactError('--upgrade-inputs requires --output and --package-format')
            build_upgrade(arguments.output, package_format=arguments.package_format)
        elif arguments.reuse:
            if arguments.package_format != 'deb':
                raise ArtifactError('--reuse currently requires Debian artifacts')
            if arguments.output is None or arguments.verify or arguments.compare:
                raise ArtifactError('--reuse requires only --output')
            # Import by the same tools path used by the maintained launchers.
            from e2e_startup_cache import prepare_artifacts
            prepare_artifacts(sys.modules[__name__], arguments.output.resolve(strict=True))
        elif arguments.compare:
            compare(arguments.compare[0].resolve(strict=True), arguments.compare[1].resolve(strict=True))
        elif arguments.verify:
            if arguments.output is None:
                raise ArtifactError("--verify requires --output")
            verify(arguments.output.resolve(strict=True))
        elif arguments.output is not None:
            build(arguments.output, package_format=arguments.package_format)
        else:
            raise ArtifactError("--output is required when building")
    except (ArtifactError, ValueError, OSError, subprocess.SubprocessError) as error:
        _log("command", "failed", category=str(error))
        return 1
    return 0


if __name__ == "__main__":
    if not sys.flags.isolated or not sys.flags.no_site:
        os.execv(sys.executable, [sys.executable, '-I', '-S', '-B', __file__, *sys.argv[1:]])
    os.umask(0o022)
    raise SystemExit(main())
