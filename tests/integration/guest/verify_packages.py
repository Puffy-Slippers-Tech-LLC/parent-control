#!/usr/bin/python3
"""Verify the installed prerequisites and report their native versions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def required_packages(path: Path) -> list[str]:
    result = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        if len(line.split()) != 1 or line.strip() != line or line.startswith("-"):
            raise ValueError(f"invalid package matrix line {number}")
        if line in result:
            raise ValueError(f"duplicate package in matrix: {line}")
        result.append(line)
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
        expected = required_packages(Path(argv[1]))
    except (OSError, ValueError) as error:
        print(f"package matrix: {error}", file=sys.stderr)
        return 1
    failures = []
    for package in expected:
        actual = installed_version(package)
        print(f"{package}\t{actual or 'not-installed'}")
        if not actual:
            failures.append(package)
    if failures:
        print("required packages missing: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
