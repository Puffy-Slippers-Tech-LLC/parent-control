#!/usr/bin/env python3
"""Package installation helper: generate and compare package activation manifests.

The manifest describes *installed* files, not source files, so distribution lifecycle
scripts can make an upgrade decision from the package that is actually being
unpacked.  Keep the classifications here deliberately small and auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


LEVELS = ("none", "process-restart", "session-renewal", "reboot")
MANIFEST_VERSION = 1
EXTENSION_PATH = Path('usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com')
EXTENSION_TRUST_PATH = Path('usr/share/oh-no-parent-control/child-extension.trust')


def activation_for(path: str) -> str:
    """Return the activation required when an installed path changes."""
    # These lifecycle commands and notices take effect on invocation;
    # changing them needs no running-service or session activation.
    if path in {
        "usr/libexec/oh-no-parent-control-migrate-state",
        "usr/libexec/oh-no-parent-control-uninstall",
        "usr/libexec/oh-no-parent-control-package-notice",
        "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice",
        "etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice",
        "usr/lib/oh-no-parent-control/broker/oh_no_parent_control/uninstall.py",
    }:
        return "none"
    # The PAM helper is executed afresh for each authentication. The readiness
    # helper exits after checking fapolicyd at service startup; no copy remains
    # resident once the gate has passed. Replacing either executable (including
    # its diagnostics) needs no machine restart. Boot ordering and the canary
    # contract remain classified separately below.
    if path in {
        "usr/libexec/oh-no-parent-control-session-limit-check",
        "usr/libexec/oh-no-parent-control-execution-policy-ready",
    }:
        return "none"
    # Existing PAM transactions may retain the loaded library. New login
    # sessions use its replacement without restarting the machine.
    if path.endswith("/security/pam_oh_no_parent_control.so"):
        return "session-renewal"
    if path.startswith((
        "etc/gdm3/",
        "etc/gdm/",
        "usr/share/oh-no-parent-control/pam/",
        "usr/share/pam-configs/",
        "etc/pam.d/",
        "usr/lib/systemd/system/display-manager.service.d/",
        "usr/lib/systemd/system/fapolicyd.service.d/",
        "usr/lib/systemd/system/onpc-execution-probe-.service.d/",
    )) or path in {
        "usr/lib/systemd/system/oh-no-parent-control-execution-policy-ready.service",
        "usr/share/oh-no-parent-control/00-oh-no-parent-control-canary.rules",
        "usr/libexec/oh-no-parent-control-execution-policy-probe",
        "usr/libexec/oh-no-parent-control-login-check",
        "usr/share/oh-no-parent-control/gdm-presession",
    }:
        return "reboot"
    # polkitd monitors its action and rule directories and evaluates them for
    # each authorization request, so no service or session restart is required.
    if path.startswith((
        "etc/polkit-1/rules.d/",
        "usr/share/polkit-1/rules.d/",
        "usr/share/polkit-1/actions/",
    )):
        return "none"
    # The broker regenerates and reloads the aggregate execution rules during
    # startup, so a changed packaged fallback activates with a broker restart.
    if path.startswith("etc/fapolicyd/rules.d/") or path == (
            "usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules"):
        return "process-restart"
    if path.startswith((
        "usr/lib/oh-no-parent-control/kiosk/",
        "usr/lib/systemd/user/",
        "usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/",
        "usr/share/gnome-session/",
        "usr/share/wayland-sessions/",
    )):
        return "session-renewal"
    # GNOME Shell may retain an icon texture for the running session.  The next
    # login reliably picks up a replacement without requiring a reboot.
    if path.startswith("usr/share/icons/"):
        return "session-renewal"
    if path in {
        "usr/libexec/oh-no-parent-control-broker",
        "usr/libexec/oh-no-parent-control-execution-probe-gate",
        "usr/libexec/oh-no-parent-control-execution-probe-witness",
        "usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/app_policy.py",
        "usr/lib/systemd/system/oh-no-parent-control-broker.service",
    } or path.startswith((
        "usr/lib/oh-no-parent-control/broker/",
        "usr/share/dbus-1/system-services/",
        "usr/share/dbus-1/interfaces/",
        "usr/share/dbus-1/system.d/",
    )):
        return "process-restart"
    return "none"


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def included_files(root: Path, includes: list[Path]) -> list[Path]:
    """Return regular files beneath the requested paths, without duplicates."""
    candidates = set()
    for include in includes:
        if include.is_absolute() or ".." in include.parts:
            raise ValueError(f"include path must be relative to root: {include}")
        candidate = root / include
        if candidate.is_file():
            candidates.add(candidate)
        elif candidate.is_dir():
            candidates.update(path for path in candidate.rglob("*") if path.is_file())
    return sorted(candidates)


def generate(root: Path, output: Path, includes: list[Path] | None = None) -> None:
    # Freeze trust from the staged package bytes, never from mutable installed
    # files during configuration. The package filter can omit .mjs even though
    # the daemon classifies them as JavaScript. Only packaged ES modules need
    # supplemental trust; do not trust a directory or change language rules.
    modules = sorted((root / EXTENSION_PATH).glob('*.mjs'))
    if modules:
        records = ['# Packaged child ES modules; generated from shipped bytes.\n']
        for module in modules:
            if module.is_symlink() or not module.is_file():
                raise ValueError('invalid packaged child ES module')
            records.append(f'/{module.relative_to(root).as_posix()} '
                           f'{module.stat().st_size} {file_digest(module)}\n')
        trust = root / EXTENSION_TRUST_PATH
        trust.parent.mkdir(parents=True, exist_ok=True)
        trust.write_text(''.join(records), encoding='utf-8')
    output_relative = output.relative_to(root).as_posix()
    files = []
    if includes is None:
        candidates = sorted(path for path in root.rglob("*") if path.is_file())
    else:
        candidates = included_files(root, includes)
    for candidate in candidates:
        relative = candidate.relative_to(root).as_posix()
        if relative == output_relative or relative.startswith("DEBIAN/"):
            continue
        files.append({
            "path": relative,
            "sha256": file_digest(candidate),
            "activation": activation_for(relative),
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"version": MANIFEST_VERSION, "files": files}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def read_manifest(path: Path) -> dict[str, tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != MANIFEST_VERSION:
        raise ValueError(f"unsupported manifest version in {path}")
    entries = data.get("files")
    if not isinstance(entries, list):
        raise ValueError(f"invalid manifest files in {path}")
    result = {}
    for entry in entries:
        file_path = entry.get("path")
        digest = entry.get("sha256")
        activation = entry.get("activation")
        if (not isinstance(file_path, str) or not isinstance(digest, str)
                or activation not in LEVELS):
            raise ValueError(f"invalid manifest entry in {path}")
        result[file_path] = (digest, activation)
    return result


def changed_impacts(old_path: Path, new_path: Path) -> list[str]:
    # An installation from an older package has no reliable baseline.  Treat it
    # like the initial integration deployment rather than risk a partial login
    # stack activation.
    if not old_path.is_file():
        return ["reboot"]
    old = read_manifest(old_path)
    new = read_manifest(new_path)
    impacts = set()
    for path in old.keys() | new.keys():
        old_entry = old.get(path)
        new_entry = new.get(path)
        if old_entry != new_entry:
            impacts.add((new_entry or old_entry)[1])
    # `none` records changes for auditability but never requires a maintainer
    # script action, so callers receive only actionable levels.
    return [level for level in LEVELS[1:] if level in impacts]


def prepare_child_trust_backend(
        config=Path('/etc/fapolicyd/fapolicyd.conf'),
        record=Path('/var/lib/oh-no-parent-control/child-trust-backend')):
    """Enable file trust for Ubuntu's debdb-only default, with exact rollback.

    debdb omits a package during its own postinst. Do not change an already
    file-enabled configuration or accept an unrecognised backend selection.
    Commit both ownership records before replacing the live configuration.
    """
    def regular(path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('unsafe child trust backend path')

    def enabled(contents):
        matches = list(re.finditer(rb'(?m)^([ \t]*trust[ \t]*=[ \t]*)([^\r\n#]*)(.*)$', contents))
        if len(matches) != 1:
            raise ValueError('ambiguous child trust backend configuration')
        match = matches[0]
        sources = [value.strip() for value in match[2].split(b',')]
        if b'file' in sources:
            return contents
        if sources != [b'debdb']:
            raise ValueError('unsupported child trust backend configuration')
        return (contents[:match.start(2)] + match[2].replace(b'debdb', b'debdb,file', 1)
                + contents[match.end(2):])

    if config.parent.is_symlink() or record.parent.is_symlink() or record.is_symlink():
        raise ValueError('unsafe child trust backend directory')
    regular(config)
    current = config.read_bytes()
    if record.exists():
        regular(record / 'before')
        regular(record / 'after')
        before, after = (record / 'before').read_bytes(), (record / 'after').read_bytes()
        if before == after or enabled(before) != after or current not in (before, after):
            raise ValueError('modified child trust backend configuration')
    else:
        before, after = current, enabled(current)
        if before == after:
            return 'none'
        # A previously disabled file source may contain administrator records.
        # Never activate those as a side effect of trusting our two modules.
        trust_paths = [config.parent / 'fapolicyd.trust']
        trust_dir = config.parent / 'trust.d'
        if trust_dir.is_symlink():
            raise ValueError('unsafe child trust directory')
        if trust_dir.exists():
            trust_paths.extend(trust_dir.iterdir())
        for path in trust_paths:
            if path == trust_dir / 'oh-no-parent-control.trust':
                continue  # postinst has independently verified this owned file
            if not path.exists() and not path.is_symlink():
                continue
            regular(path)
            if any(line.strip() and not line.lstrip().startswith(b'#')
                   for line in path.read_bytes().splitlines()):
                raise ValueError('inactive administrator file trust must be reviewed')
        temporary = Path(tempfile.mkdtemp(prefix='.child-trust-backend-', dir=record.parent))
        try:
            shutil.copy2(config, temporary / 'before')
            (temporary / 'after').write_bytes(after)
            temporary.rename(record)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    if current != after:
        descriptor, temporary = tempfile.mkstemp(prefix='.onpc-trust-', dir=config.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(after)
                stream.flush()
                os.fsync(stream.fileno())
            metadata = config.stat()
            os.chmod(temporary, metadata.st_mode & 0o777)
            os.chown(temporary, metadata.st_uid, metadata.st_gid)
            os.replace(temporary, config)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    # The caller must not restart a live daemon: its display-manager dependency
    # could log out unrelated desktops. Live exact-record readiness also guards
    # retries made before a required reboot has loaded the new backend.
    return 'changed' if current != after else 'none'


def wait_child_trust(path: Path = Path('/') / EXTENSION_TRUST_PATH) -> None:
    """Wait for the asynchronous trust update to publish our exact records.

    Read the packaged manifest, not mutable module bytes. The CLI's update
    command only queues a request; dump-db reads the committed live database.
    This is database readiness, not proof of a fresh Shell import.
    """
    expected = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        fields = line.split()
        if (len(fields) != 3 or Path(fields[0]).parent != Path('/') / EXTENSION_PATH
                or not re.fullmatch(r'[A-Za-z0-9_-]+\.mjs', Path(fields[0]).name)
                or not fields[1].isdecimal() or not re.fullmatch(r'[0-9a-f]{64}', fields[2])):
            raise ValueError('invalid packaged child trust record')
        expected.add(tuple(fields))
    if not expected:
        raise ValueError('missing packaged child trust records')
    deadline = time.monotonic() + 120
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('packaged child trust update did not complete')
        result = subprocess.run(['/usr/sbin/fapolicyd-cli', '--dump-db'],
                                stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, check=True, timeout=remaining,
                                env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
        present = set()
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) == 4 and fields[0] in ('file', 'filedb'):
                present.add(tuple(fields[1:]))
        if expected <= present:
            return
        time.sleep(min(.25, max(0, deadline - time.monotonic())))


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser('prepare-child-trust-backend')
    generate_parser = commands.add_parser("generate")
    generate_parser.add_argument("--root", type=Path, required=True)
    generate_parser.add_argument("--output", type=Path, required=True)
    generate_parser.add_argument(
        "--include", action="append", type=Path,
        help="relative file or directory to include; may be specified repeatedly",
    )
    compare_parser = commands.add_parser("changed-impacts")
    compare_parser.add_argument("--old", type=Path, required=True)
    compare_parser.add_argument("--new", type=Path, required=True)
    commands.add_parser("wait-child-trust")
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.root.resolve(), args.output.resolve(), args.include)
    elif args.command == "changed-impacts":
        print("\n".join(changed_impacts(args.old, args.new)))
    elif args.command == 'prepare-child-trust-backend':
        try:
            print(prepare_child_trust_backend())
        except (OSError, ValueError):
            raise SystemExit('oh-no-parent-control: child file trust backend cannot be configured safely') from None
    else:
        try:
            wait_child_trust()
        except (OSError, ValueError, subprocess.SubprocessError):
            raise SystemExit('oh-no-parent-control: child trust database is not ready') from None


if __name__ == "__main__":
    main()
