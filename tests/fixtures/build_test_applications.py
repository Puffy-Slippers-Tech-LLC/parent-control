#!/usr/bin/env python3
"""Build and safely exercise deterministic native and Flatpak test targets.

The output is an *image payload*, never an installation.  Its layout is copied
only into a marked disposable VM by later installed-system tests.  The local
smoke uses a private Flatpak user installation rooted below its supplied
temporary directory, never the developer's real user or system installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import select
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("onpc_test_application.c")
APP_ID = "com.puffyslippers.ONPCTestApplication"
PLATFORM_ID = "com.puffyslippers.ONPCTestPlatform"
SDK_ID = "com.puffyslippers.ONPCTestSdk"
BRANCH = "stable"
INSTALL_PREFIX = Path("opt/onpc-test-fixtures")
READY_MARKER = "ONPC_TEST_APPLICATION_READY"
NATIVE_NAMES = (
    "Exact Fixture.AppImage",
    "Path With Spaces.AppImage",
    "Lunar Client-3.7.17.AppImage",
    "Lunar Client-3.8.0.AppImage",
    "PrismLauncher.AppImage",
)


class FixtureError(RuntimeError):
    """A fixture command cannot safely continue."""


def _log(stage: str, outcome: str) -> None:
    print(f"test-fixtures: stage={stage} outcome={outcome}", file=sys.stderr)


def _run(command: list[str], *, environment: Mapping[str, str] | None = None) -> None:
    try:
        subprocess.run(command, check=True, env=environment)
    except (OSError, subprocess.CalledProcessError) as error:
        raise FixtureError(f"fixture command failed during {command[0]!r}") from error


def _require_empty_output(output: Path) -> Path:
    resolved = output.resolve(strict=False)
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if resolved == ROOT or ROOT in resolved.parents or temporary_root not in resolved.parents:
        raise FixtureError("fixture output must be below the system temporary directory")
    if resolved.exists():
        if not resolved.is_dir() or any(resolved.iterdir()):
            raise FixtureError("fixture output directory must be empty")
    else:
        resolved.mkdir(parents=True, mode=0o700)
    return resolved


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _set_reproducible_times(root: Path) -> None:
    for item in sorted(root.rglob("*"), reverse=True):
        if not item.is_symlink():
            os.utime(item, (0, 0), follow_symlinks=False)
    os.utime(root, (0, 0), follow_symlinks=False)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_manifest(output: Path) -> None:
    files = {}
    for item in sorted(output.rglob("*")):
        relative = item.relative_to(output).as_posix()
        # Flatpak's public export API writes a wall-clock timestamp into these
        # delivery indexes. They do not alter the application/runtime commits.
        # The bundle is made from that index, so it has the same container-only
        # variation. Verify its presence, while hashing the stable payload.
        volatile = relative in {
            "flatpak-repository/summary",
            "flatpak-repository/summary.idx",
            "onpc-test-application.flatpak",
        }
        if item.is_file() and item.name != "SHA256SUMS.json" and not volatile:
            files[item.relative_to(output).as_posix()] = _digest(item)
    _write_text(
        output / "SHA256SUMS.json",
        json.dumps({"algorithm": "sha256", "files": files}, indent=2, sort_keys=True) + "\n",
    )


def verify(output: Path) -> None:
    manifest_path = output / "SHA256SUMS.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise FixtureError("fixture digest manifest is invalid") from error
    if manifest.get("algorithm") != "sha256" or not isinstance(files, dict):
        raise FixtureError("fixture digest manifest has an unsupported format")
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise FixtureError("fixture digest manifest has invalid entries")
        candidate = (output / relative).resolve(strict=False)
        if output not in candidate.parents or not candidate.is_file():
            raise FixtureError("fixture digest manifest escapes its output directory")
        if _digest(candidate) != expected:
            raise FixtureError("fixture digest verification failed")
    _log("verify-digests", "passed")


def _compile_native(output: Path) -> Path:
    compiler = os.environ.get("CC", "cc")
    native = output / "native" / "onpc-test-application"
    native.parent.mkdir(parents=True)
    _run([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-static", "-o", str(native), str(SOURCE)])
    native.chmod(0o755)
    return native


def _desktop_entry(name: str, executable: Path) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        "Icon=applications-system\n"
        f"Exec=/{executable.as_posix()} --stay-alive\n"
        "Terminal=false\n"
    )


def _build_native_layout(output: Path, native: Path) -> None:
    image = output / "image-root"
    applications = image / INSTALL_PREFIX / "Applications"
    for name in NATIVE_NAMES:
        target = applications / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(native, target)
        target.chmod(0o755)
    exact = INSTALL_PREFIX / "Applications" / NATIVE_NAMES[0]
    versioned = INSTALL_PREFIX / "Applications" / NATIVE_NAMES[2]
    _write_text(
        image / "usr/share/applications/com.puffyslippers.ONPCTest.System.desktop",
        _desktop_entry("ONPC System Test Application", exact),
    )
    _write_text(
        image / "home/onpc-child/.local/share/applications/com.puffyslippers.ONPCTest.Child.desktop",
        _desktop_entry("ONPC Child Test Application", versioned),
    )
    _write_text(
        output / "fixture-targets.json",
        json.dumps(
            {
                "native": {
                    "exact": f"/{exact.as_posix()}",
                    "spaces": f"/{(INSTALL_PREFIX / 'Applications' / NATIVE_NAMES[1]).as_posix()}",
                    "version_pattern": f"/{(INSTALL_PREFIX / 'Applications' / 'Lunar Client-*.AppImage').as_posix()}",
                    "nonmatching": f"/{(INSTALL_PREFIX / 'Applications' / NATIVE_NAMES[-1]).as_posix()}",
                },
                "flatpak": {"app_id": APP_ID, "branch": BRANCH},
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
    )


def _flatpak_environment(output: Path) -> dict[str, str]:
    isolated_home = output / "flatpak-home"
    isolated_home.mkdir(mode=0o700, exist_ok=True)
    environment = {
        "HOME": str(isolated_home),
        "LANG": "C.UTF-8",
        "PATH": os.defpath,
        "SOURCE_DATE_EPOCH": "0",
        "XDG_CACHE_HOME": str(isolated_home / ".cache"),
        "XDG_CONFIG_HOME": str(isolated_home / ".config"),
        "XDG_DATA_HOME": str(isolated_home / ".local/share"),
        "XDG_RUNTIME_DIR": str(isolated_home / ".runtime"),
    }
    for name in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
        Path(environment[name]).mkdir(mode=0o700, parents=True, exist_ok=True)
    return environment


def _build_flatpak(output: Path, native: Path) -> None:
    if shutil.which("flatpak") is None:
        raise FixtureError("flatpak is required to build the deterministic test fixture")
    repository = output / "flatpak-repository"
    runtime = output / "flatpak-runtime-build"
    app = output / "flatpak-app-build"
    environment = _flatpak_environment(output)
    architecture = os.uname().machine
    # Do not use ``flatpak build-init`` here: it insists that an SDK is already
    # installed, which would make a clean offline fixture build depend on the
    # developer's Flatpak state.  build-export's public artifact contract is a
    # finalized metadata file plus files/export trees, so make the minimal
    # platform and app artifacts directly from that documented format.
    # build-export requires the standard ``files`` marker for every initialized
    # build tree; runtime payloads themselves are exported from ``usr``.
    (runtime / "files").mkdir(parents=True)
    (runtime / "usr").mkdir(parents=True)
    _write_text(
        runtime / "metadata",
        "# This file is autogenerated by flatpak build-init\n"
        "[Runtime]\n"
        f"name={PLATFORM_ID}\n"
        f"sdk={SDK_ID}/{architecture}/{BRANCH}\n",
    )
    _set_reproducible_times(runtime)
    _run(["flatpak", "build-export", "--runtime", f"--arch={architecture}", "--timestamp=0", str(repository), str(runtime), BRANCH], environment=environment)
    app_binary = app / "files/bin/onpc-test-application"
    app_binary.parent.mkdir(parents=True)
    shutil.copyfile(native, app_binary)
    app_binary.chmod(0o755)
    _write_text(
        app / "metadata",
        "# This file is autogenerated by flatpak build-init\n"
        "[Application]\n"
        f"name={APP_ID}\n"
        f"runtime={PLATFORM_ID}/{architecture}/{BRANCH}\n"
        f"sdk={SDK_ID}/{architecture}/{BRANCH}\n"
        "command=onpc-test-application\n"
        "\n[Context]\n"
        "shared=ipc;\n",
    )
    _write_text(
        app / f"export/share/applications/{APP_ID}.desktop",
        f"[Desktop Entry]\nType=Application\nName=ONPC Flatpak Test Application\nIcon={APP_ID}\nExec=onpc-test-application --stay-alive\n",
    )
    # The fixture exercises Flatpak application identity and launch behavior;
    # it deliberately has no icon payload, avoiding an unrelated host decoder
    # dependency during hermetic repository construction.
    _set_reproducible_times(app)
    # Icon validation's sandbox needs unprivileged user namespaces, which are
    # intentionally unavailable in some test runners.  The checked-in SVG is
    # deterministic and the eventual Flatpak launch remains sandboxed.
    _run(["flatpak", "build-export", "--disable-sandbox", f"--arch={architecture}", "--timestamp=0", str(repository), str(app), BRANCH], environment=environment)
    _run(["flatpak", "build-bundle", f"--arch={architecture}", str(repository), str(output / "onpc-test-application.flatpak"), APP_ID, BRANCH], environment=environment)


def build(output: Path) -> None:
    output = _require_empty_output(output)
    _log("build", "started")
    native = _compile_native(output)
    _build_native_layout(output, native)
    _build_flatpak(output, native)
    _set_reproducible_times(output)
    _write_manifest(output)
    verify(output)
    _log("build", "passed")


def _preexec_for_uid(uid: int):
    if uid == os.geteuid():
        return None
    if os.geteuid() != 0:
        raise FixtureError("launching a different UID requires an explicitly privileged disposable environment")
    account = pwd.getpwuid(uid)

    def apply_uid() -> None:
        os.setgroups(())
        os.setgid(account.pw_gid)
        os.setuid(uid)

    return apply_uid


def launch_native(binary: Path, uid: int) -> subprocess.Popen[str]:
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise FixtureError("native fixture executable is unavailable")
    process = subprocess.Popen(
        [str(binary), "--stay-alive"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=_preexec_for_uid(uid),
    )
    marker = _read_readiness(process)
    if marker.strip() != READY_MARKER:
        process.terminate()
        process.wait(timeout=5)
        raise FixtureError("native fixture did not report readiness")
    _log("launch-native", "ready")
    return process


def _read_readiness(process: subprocess.Popen[str]) -> str:
    if process.stdout is None:
        raise FixtureError("fixture process has no readiness stream")
    ready, _, _ = select.select([process.stdout], [], [], 5)
    if not ready:
        terminate(process)
        raise FixtureError("fixture did not report readiness before its deadline")
    return process.stdout.readline()


def launch_flatpak(output: Path, uid: int) -> subprocess.Popen[str]:
    """Launch the bundled Flatpak only through an isolated temporary user root."""

    if uid != os.geteuid():
        raise FixtureError("Flatpak smoke launch requires the fixture owner UID")
    environment = _flatpak_environment(output)
    repository = output / "flatpak-repository"
    if not repository.is_dir():
        raise FixtureError("Flatpak fixture repository is unavailable")
    remote = "onpc-test-fixture"
    _run(
        ["flatpak", "--user", "remote-add", "--no-gpg-verify", "--no-enumerate",
         "--no-use-for-deps", remote, repository.as_uri()],
        environment=environment,
    )
    _run(
        ["flatpak", "--user", "install", "--noninteractive", "--assumeyes", "--runtime", remote, PLATFORM_ID],
        environment=environment,
    )
    _run(
        ["flatpak", "--user", "install", "--no-deps", "--noninteractive", "--assumeyes", remote, APP_ID],
        environment=environment,
    )
    process = subprocess.Popen(
        ["flatpak", "--user", "run", "--die-with-parent", "--no-documents-portal", APP_ID, "--stay-alive"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        preexec_fn=_preexec_for_uid(uid),
    )
    marker = _read_readiness(process)
    if marker.strip() != READY_MARKER:
        diagnostic = process.stderr.read().strip() if process.stderr is not None else ""
        terminate(process)
        category = diagnostic.splitlines()[-1] if diagnostic else "no readiness marker"
        raise FixtureError(f"Flatpak fixture did not report readiness: {category}")
    _log("launch-flatpak", "ready")
    return process


def report_process_identity(process: subprocess.Popen[str]) -> dict[str, int]:
    if process.poll() is not None:
        raise FixtureError("fixture process exited before identity inspection")
    try:
        uid = os.stat(f"/proc/{process.pid}").st_uid
    except OSError as error:
        raise FixtureError("fixture process identity is unavailable") from error
    return {"pid": process.pid, "uid": uid}


def terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as error:
        raise FixtureError("identity-recorded fixture process did not terminate") from error
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    _log("terminate", "passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="empty directory for the disposable fixture payload")
    parser.add_argument("--verify", action="store_true", help="verify an existing fixture payload instead of building")
    arguments = parser.parse_args()
    try:
        if arguments.verify:
            verify(arguments.output.resolve(strict=True))
        else:
            build(arguments.output)
    except FixtureError as error:
        print(f"test-fixtures: outcome=failed category={error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
