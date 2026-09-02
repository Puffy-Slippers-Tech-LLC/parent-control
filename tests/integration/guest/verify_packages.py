#!/usr/bin/python3
"""Verify that the VM matches the reviewed Ubuntu package matrix exactly."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def expected_versions(path: Path) -> dict[str, str]:
    result = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 2 or not all(fields):
            raise ValueError(f"invalid package matrix line {number}")
        package, version = fields
        if package in result:
            raise ValueError(f"duplicate package in matrix: {package}")
        result[package] = version
    return result


def installed_version(package: str) -> str | None:
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${Version}", package],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    if result.returncode != 0:
        return None
    fields = result.stdout.split("\t", 1)
    if len(fields) != 2 or fields[0] != "ii ":
        return None
    return fields[1]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: verify_packages.py EXPECTED_PACKAGES", file=sys.stderr)
        return 2
    try:
        expected = expected_versions(Path(argv[1]))
    except (OSError, ValueError) as error:
        print(f"package matrix: {error}", file=sys.stderr)
        return 1
    failures = []
    for package, version in expected.items():
        actual = installed_version(package)
        print(f"{package}\t{actual or 'not-installed'}\texpected={version}")
        if actual != version:
            failures.append(package)
    if failures:
        print(
            "supported package drift: " + ", ".join(failures) +
            "; review updates and recapture the matrix before changing it",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
