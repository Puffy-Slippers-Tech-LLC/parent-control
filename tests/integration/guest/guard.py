#!/usr/bin/python3
"""Fail closed unless a mutating command is inside the marked Ubuntu VM."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


MARKER = Path("/etc/oh-no-parent-control-integration-vm")
NAME_RE = re.compile(r"onpc-h50-[a-z0-9](?:[a-z0-9-]{0,45}[a-z0-9])?")


class GuardError(RuntimeError):
    pass


def validate_marker_document(document: object, expected_name: str) -> dict:
    if NAME_RE.fullmatch(expected_name) is None:
        raise GuardError("expected VM name is invalid")
    if not isinstance(document, dict):
        raise GuardError("disposable-VM marker must be an object")
    if set(document) != {"purpose", "name", "token", "ubuntu_version"}:
        raise GuardError("disposable-VM marker has unexpected fields")
    if document["purpose"] != "oh-no-parent-control-integration":
        raise GuardError("disposable-VM marker has the wrong purpose")
    if document["name"] != expected_name:
        raise GuardError("disposable-VM marker does not match the selected VM")
    if document["ubuntu_version"] != "26.04":
        raise GuardError("disposable-VM marker has the wrong Ubuntu version")
    if not isinstance(document["token"], str) or re.fullmatch(
            r"[0-9a-f]{32}", document["token"]) is None:
        raise GuardError("disposable-VM marker token is invalid")
    return document


def validate_marker_file(path: Path, expected_name: str) -> dict:
    try:
        status = path.stat(follow_symlinks=False)
    except OSError as error:
        raise GuardError(f"disposable-VM marker is unavailable: {error}") from error
    if not stat.S_ISREG(status.st_mode) or status.st_uid != 0:
        raise GuardError("disposable-VM marker must be a root-owned regular file")
    if stat.S_IMODE(status.st_mode) != 0o600:
        raise GuardError("disposable-VM marker must have mode 0600")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GuardError(f"disposable-VM marker is invalid: {error}") from error
    return validate_marker_document(document, expected_name)


def validate_runtime(expected_name: str) -> dict:
    if os.geteuid() != 0:
        raise GuardError("host-altering integration steps must run as root inside the VM")
    marker = validate_marker_file(MARKER, expected_name)
    virtual = subprocess.run(
        ["systemd-detect-virt", "--vm"], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if virtual.returncode != 0:
        raise GuardError("refusing to alter a machine that is not a virtual machine")
    values = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
    except OSError as error:
        raise GuardError(f"could not identify the guest OS: {error}") from error
    if values.get("ID") != "ubuntu" or values.get("VERSION_ID") != "26.04":
        raise GuardError("host-altering tests require Ubuntu 26.04")
    if os.uname().nodename != expected_name:
        raise GuardError("guest hostname does not match the selected disposable VM")
    return marker


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: guard.py VM_NAME", file=sys.stderr)
        return 2
    try:
        validate_runtime(argv[1])
    except GuardError as error:
        print(f"integration guard: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
