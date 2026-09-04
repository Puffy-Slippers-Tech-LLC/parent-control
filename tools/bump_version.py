#!/usr/bin/env python3
"""Prepare one x.y product release and its Debian changelog entry."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_METADATA_PATH = ROOT / "data/app.json"
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class VersionError(ValueError):
    """The requested release violates the repository version policy."""


def parse_product_version(value: object) -> tuple[int, int]:
    if not isinstance(value, str):
        raise VersionError("product version must be a string in x.y form")
    match = VERSION_RE.fullmatch(value)
    if match is None:
        raise VersionError("product version must use x.y with no leading zeroes")
    return int(match.group(1)), int(match.group(2))


def validate_release(current: tuple[int, int], requested: tuple[int, int]) -> None:
    if requested <= current:
        raise VersionError("new product version must be greater than the current version")


def staged_metadata(version: str) -> str:
    return json.dumps({"version": version}, indent=2) + "\n"


def read_metadata() -> tuple[dict, tuple[int, int]]:
    metadata = json.loads(APP_METADATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or set(metadata) != {"version"}:
        raise VersionError("app metadata must contain only the product version")
    return metadata, parse_product_version(metadata["version"])


def debian_version() -> str:
    return subprocess.check_output(
        ["dpkg-parsechangelog", "-S", "Version"], cwd=ROOT, text=True
    ).strip()


def check_repository() -> None:
    metadata, _version = read_metadata()
    product_version = metadata["version"]
    package_version = debian_version()
    if not (package_version == product_version or
            package_version.startswith(f"{product_version}+")):
        raise VersionError(
            "Debian package version must equal the product version or add a + suffix"
        )


def replace_text_atomically(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def bump(version: str, change: str) -> None:
    requested = parse_product_version(version)
    _metadata, current = read_metadata()
    validate_release(current, requested)
    content = staged_metadata(version)

    comparison = subprocess.run(
        ["dpkg", "--compare-versions", version, "gt",
         debian_version()],
        cwd=ROOT,
        check=False,
    )
    if comparison.returncode != 0:
        raise VersionError("new product version must be newer than the Debian package version")

    subprocess.run(
        ["dch", "--newversion", version, "--distribution", "resolute", change],
        cwd=ROOT,
        check=True,
    )
    replace_text_atomically(APP_METADATA_PATH, content)
    print(f"Prepared release {version}; review data/app.json and debian/changelog.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare an increasing x.y product release."
    )
    parser.add_argument("version", nargs="?", help="new product version in x.y form")
    parser.add_argument(
        "--check", action="store_true",
        help="verify that product and Debian package versions agree",
    )
    parser.add_argument(
        "--change", default=None,
        help="Debian changelog text (defaults to a release entry)",
    )
    args = parser.parse_args()
    try:
        if args.check:
            if args.version is not None or args.change is not None:
                raise VersionError("--check does not accept a version or change message")
            check_repository()
        elif args.version is None:
            raise VersionError("a new x.y product version is required")
        else:
            bump(args.version, args.change or f"Release Oh No! Parent Control {args.version}.")
    except (VersionError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
