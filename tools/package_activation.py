#!/usr/bin/env python3
"""Generate and compare package activation manifests.

The manifest describes *installed* files, not source files, so Debian maintainer
scripts can make an upgrade decision from the package that is actually being
unpacked.  Keep the classifications here deliberately small and auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LEVELS = ("none", "process-restart", "session-renewal", "reboot")
MANIFEST_VERSION = 1


def activation_for(path: str) -> str:
    """Return the activation required when an installed path changes."""
    # This command is run unconditionally by postinst before activation is
    # calculated; changing the command itself needs no later activation.
    if path == "usr/libexec/oh-no-parent-control-migrate-state":
        return "none"
    if path.startswith((
        "etc/gdm3/",
        "usr/share/pam-configs/",
        "etc/pam.d/",
    )):
        return "reboot"
    # polkitd monitors its action and rule directories and evaluates them for
    # each authorization request, so no service or session restart is required.
    if path.startswith((
        "etc/polkit-1/rules.d/",
        "usr/share/polkit-1/actions/",
    )):
        return "none"
    # The broker regenerates and reloads the aggregate execution rules during
    # startup, so a changed packaged fallback activates with a broker restart.
    if path.startswith("etc/fapolicyd/rules.d/"):
        return "process-restart"
    if path.startswith((
        "usr/lib/oh-no-parent-control/child/extension/",
        "usr/lib/oh-no-parent-control/kiosk/",
        "usr/lib/systemd/user/",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
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
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.root.resolve(), args.output.resolve(), args.include)
    else:
        print("\n".join(changed_impacts(args.old, args.new)))


if __name__ == "__main__":
    main()
