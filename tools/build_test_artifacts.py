#!/usr/bin/env python3
"""Build digest-identified Debian and application-fixture test artifacts.

The output is an input to the guarded installed-system runner. This builder
never installs the product: package construction happens in a private source
copy and Task 11 fixtures are emitted as an ordinary payload directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


REPOSITORY = Path(__file__).resolve().parents[1]
FIXTURE_BUILDER = REPOSITORY / "tests/fixtures/build_test_applications.py"
MANIFEST_NAME = "artifact-manifest.json"
SCHEMA_VERSION = 1


class ArtifactError(RuntimeError):
    """A reproducible artifact operation cannot continue safely."""


def _log(stage: str, outcome: str, **fields: str) -> None:
    suffix = " ".join(f"{name}={value}" for name, value in sorted(fields.items()))
    print(f"test-artifacts: stage={stage} outcome={outcome}" + (f" {suffix}" if suffix else ""), file=sys.stderr)


def _run(command: list[str], *, cwd: Path | None = None, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, env=environment, check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    if resolved == REPOSITORY or REPOSITORY in resolved.parents:
        raise ArtifactError("artifact output must be outside the source checkout")
    if resolved.exists():
        if not resolved.is_dir() or any(resolved.iterdir()):
            raise ArtifactError("artifact output directory must be empty")
    else:
        resolved.mkdir(parents=True, mode=0o755)
    return resolved


def _source_paths() -> list[Path]:
    result = _run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPOSITORY)
    paths = [Path(line) for line in result.stdout.splitlines() if line]
    if not paths or any(path.is_absolute() or ".." in path.parts for path in paths):
        raise ArtifactError("source input list is invalid")
    return sorted(paths)


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


def _copy_source(paths: list[Path], destination: Path) -> None:
    for relative in paths:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY / relative, target)


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
    revision = _run(["git", "rev-parse", "HEAD"], cwd=REPOSITORY).stdout.strip()
    epoch = _run(["git", "log", "-1", "--format=%ct", "HEAD"], cwd=REPOSITORY).stdout.strip()
    architecture = _run(["dpkg-architecture", "-qDEB_HOST_ARCH"], cwd=REPOSITORY).stdout.strip()
    if not revision or not epoch.isdecimal() or not architecture:
        raise ArtifactError("source revision metadata is invalid")
    return {
        "source": {"revision": revision, "digest_sha256": source_digest, "file_count": len(source_paths)},
        "build_inputs": {"source_date_epoch": int(epoch), "architecture": architecture,
                         "deb_build_options": "nocheck",
                         "package_command": ["dpkg-buildpackage", "--build=binary", "--no-sign", f"-a{architecture}"]},
        "tools": {"dpkg-architecture": _command_version(["dpkg-architecture", "--version"]),
                  "dpkg-buildpackage": _command_version(["dpkg-buildpackage", "--version"]),
                  "dpkg-deb": _command_version(["dpkg-deb", "--version"]),
                  "flatpak": _command_version(["flatpak", "--version"])},
    }


def build(output: Path) -> Path:
    output = _require_empty_output(output)
    source_paths = _source_paths()
    source_digest = _source_digest(source_paths)
    metadata = _metadata(source_paths, source_digest)
    _log("build", "started", revision=metadata["source"]["revision"][:12])
    with tempfile.TemporaryDirectory(prefix="onpc-package-build-") as temporary_name:
        temporary = Path(temporary_name)
        source_copy = temporary / "source"
        source_copy.mkdir()
        _copy_source(source_paths, source_copy)
        # Task 12's preparation guard verifies that a checkout has a Git
        # directory. The isolated package tree has recorded source files rather
        # than repository history, so provide only that structural marker.
        (source_copy / ".git").mkdir()
        # The copied source tree is intentionally not the fixed development
        # checkout accepted by Task 12's host-controller tests. Run make check
        # from the real checkout as this task's separate required validation;
        # use Debian's standard nocheck option only for this test artifact.
        environment = os.environ | {"SOURCE_DATE_EPOCH": str(metadata["build_inputs"]["source_date_epoch"]),
                                    "DEB_BUILD_OPTIONS": metadata["build_inputs"]["deb_build_options"]}
        command = metadata["build_inputs"]["package_command"]
        _run(command, cwd=source_copy, environment=environment)
        packages = sorted(temporary.glob("oh-no-parent-control_*.deb"))
        if len(packages) != 1:
            raise ArtifactError("package build did not produce exactly one binary package")
        package_output = output / "package"
        package_output.mkdir()
        package = packages[0]
        destination = package_output / package.name
        shutil.copyfile(package, destination)
        fixture_output = output / "fixtures"
        _run([sys.executable, str(FIXTURE_BUILDER), "--output", str(fixture_output)], cwd=REPOSITORY, environment=environment)
        manifest = {"schema_version": SCHEMA_VERSION, **metadata, "artifacts": {
            "package": {"path": f"package/{destination.name}", "sha256": _sha256(destination)},
            "fixtures": {"path": "fixtures", "digest_manifest": "fixtures/SHA256SUMS.json", "sha256": _fixture_digest(fixture_output)},
        }}
        (output / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify(output)
    _log("build", "passed", package=destination.name)
    return output / MANIFEST_NAME


def verify(output: Path) -> dict[str, Any]:
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
        raise ArtifactError("repeated build changed the Debian package")
    for path in (first / first_package["path"], second / second_package["path"]):
        _run(["dpkg-deb", "--info", str(path)])
        _run(["dpkg-deb", "--contents", str(path)])
    if first_manifest["artifacts"]["fixtures"] != second_manifest["artifacts"]["fixtures"]:
        raise ArtifactError("repeated build changed the fixture payload")
    _log("reproducibility", "passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="an empty output directory outside the checkout")
    parser.add_argument("--verify", action="store_true", help="verify an existing artifact manifest")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("FIRST", "SECOND"), help="compare two built artifact directories")
    arguments = parser.parse_args()
    try:
        if arguments.compare:
            compare(arguments.compare[0].resolve(strict=True), arguments.compare[1].resolve(strict=True))
        elif arguments.verify:
            if arguments.output is None:
                raise ArtifactError("--verify requires --output")
            verify(arguments.output.resolve(strict=True))
        elif arguments.output is not None:
            build(arguments.output)
        else:
            raise ArtifactError("--output is required when building")
    except ArtifactError as error:
        _log("command", "failed", category=str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
