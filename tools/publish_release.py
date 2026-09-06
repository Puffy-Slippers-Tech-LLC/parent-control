#!/usr/bin/env python3
"""Prepare PPA releases and inspect source uploads; never push or upload."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
NAME = "Puffy Slippers Tech LLC"
EMAIL = "dev@tech.puffyslippers.com"
KEY = "4449F02C3E57F8215261A57958109B593907EFDE"
OWNER = "puffyslipperstechllc"
PACKAGE = "oh-no-parent-control"
API = f"https://api.launchpad.net/1.0/~{OWNER}/+archive/ubuntu/{PACKAGE}"
ORIGIN = "git@github.com:Puffy-Slippers-Tech-LLC/parent-control.git"


def source_tag(version: str) -> str:
    # Git forbids tilde in refs; Debian uses it for pre-release ordering.
    return "v" + version.replace("~", "_")


def run(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def fetch(url: str) -> dict:
    if not url.startswith("https://api.launchpad.net/1.0/"):
        raise ValueError("unexpected Launchpad API URL")
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def publications() -> list[dict]:
    archive = fetch(API)
    if archive["private"] or not archive["publish"]:
        raise ValueError("PPA must be public and publishing enabled")
    entries = []
    # Include deleted/superseded publications: their versions cannot be reused.
    for status in ("Pending", "Published", "Superseded", "Deleted", "Obsolete"):
        url = API + "?" + urlencode({"ws.op": "getPublishedSources",
            "source_name": PACKAGE, "exact_match": "true", "status": status})
        while url:
            page = fetch(url)
            entries.extend(page["entries"])
            url = page.get("next_collection_link")
    return entries


def next_version(product: str, versions: list[str]) -> str:
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", product):
        raise ValueError("product version must be x.y")
    pattern = re.compile(re.escape(product) + r"\+ppa([0-9]+)~ubuntu26\.04\.1")
    revisions = [int(match[1]) for value in versions
                 if (match := pattern.fullmatch(value))]
    return f"{product}+ppa{max(revisions, default=0) + 1}~ubuntu26.04.1"


def clean(root: Path) -> None:
    if run("git", "status", "--porcelain", "--untracked-files=all", cwd=root):
        raise ValueError("checkout has uncommitted/untracked files; review and commit intended release inputs first")


def plan(root: Path) -> dict:
    product = json.loads((root / "data/app.json").read_text())["version"]
    entries = publications()
    versions = [entry["source_package_version"] for entry in entries]
    tags = run("git", "tag", "--list", cwd=root).splitlines()
    versions += [tag[1:].replace("_", "~") for tag in tags if re.fullmatch(
        r"v[0-9]+\.[0-9]+(?:\+ppa[0-9]+_ubuntu26\.04\.1)?", tag)]
    versions.append(run("dpkg-parsechangelog", "-S", "Version", cwd=root))
    version = next_version(product, versions)
    for old in versions:
        # Product tags and versions from another product release also matter.
        if subprocess.run(["dpkg", "--compare-versions", version, "gt", old],
                          capture_output=True).returncode != 0:
            raise ValueError("candidate is not newer than known releases; review product version/history")
    return {"publisher": NAME, "email": EMAIL, "signing_key": KEY,
            "ppa": f"ppa:{OWNER}/{PACKAGE}", "product": product,
            "version": version, "source_tag": source_tag(version),
            "product_tag": f"v{product}",
            "revision": run("git", "rev-parse", "HEAD", cwd=root)}


def prepare(destination: Path) -> None:
    clean(ROOT)
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError("release directory must be outside the development checkout")
    if destination.exists():
        raise ValueError("release directory must not exist; choose a new path")
    info = plan(ROOT)  # Network failure stops preparation, never guesses ppa1.
    destination.mkdir(parents=True)
    checkout = destination / "source"
    subprocess.run(["git", "clone", "--no-hardlinks", str(ROOT), str(checkout)], check=True)
    run("git", "checkout", "-b", f"release/{source_tag(info['version'])}", info["revision"], cwd=checkout)
    for key, value in {"user.name": NAME, "user.email": EMAIL,
                       "user.signingkey": KEY, "gpg.format": "openpgp",
                       "commit.gpgsign": "true", "tag.gpgsign": "true"}.items():
        run("git", "config", "--local", key, value, cwd=checkout)
    run("git", "remote", "set-url", "origin", ORIGIN, cwd=checkout)
    env = dict(os.environ, DEBFULLNAME=NAME, DEBEMAIL=EMAIL)
    subprocess.run(["dch", "--newversion", info["version"], "--distribution", "resolute",
                    f"Build Oh No! Parent Control {info['product']} for the PPA."],
                   cwd=checkout, env=env, check=True)
    run("make", "check-release-version", cwd=checkout)
    (destination / "release.json").write_text(json.dumps(info, indent=2) + "\n")
    print(f"Prepared {info['version']}. Review {checkout / 'debian/changelog'}.")
    print("No commit, tag, push, or upload performed. Follow docs/Publishing.md.")


def verify_signature(path: Path, root: Path) -> None:
    status = run("gpg", "--batch", "--status-fd=1", "--verify", str(path), cwd=root)
    signatures = [line.split() for line in status.splitlines()
                  if line.startswith("[GNUPG:] VALIDSIG ")]
    if not signatures or any(KEY not in (line[2], line[-1]) for line in signatures):
        raise ValueError("source signature does not belong to the configured publisher")


def inspect(root: Path) -> None:
    root = root.resolve()
    clean(root)
    run("make", "check-release-version", cwd=root)
    version = run("dpkg-parsechangelog", "-S", "Version", cwd=root)
    if not re.fullmatch(r"[0-9]+\.[0-9]+\+ppa[1-9][0-9]*~ubuntu26\.04\.1", version):
        raise ValueError("unexpected PPA package version")
    if run("dpkg-parsechangelog", "-S", "Distribution", cwd=root) != "resolute":
        raise ValueError("release must target resolute")
    tag = source_tag(version)
    run("git", "verify-tag", tag, cwd=root)
    if run("git", "rev-parse", "HEAD", cwd=root) != run("git", "rev-parse", f"{tag}^{{commit}}", cwd=root):
        raise ValueError("HEAD differs from the package source tag")
    prefix = root.parent / f"{PACKAGE}_{version}"
    changes = Path(f"{prefix}_source.changes")
    dsc = Path(f"{prefix}.dsc")
    archive = Path(f"{prefix}.tar.xz")
    for path in (changes, dsc):
        verify_signature(path, root)
    # Authenticate every file in the upload, including source buildinfo.
    content = changes.read_text()
    for field, expected in (("Source", PACKAGE), ("Version", version), ("Architecture", "source")):
        if not re.search(r"^" + field + ": " + re.escape(expected) + r"$", content, re.MULTILINE):
            raise ValueError(f"unexpected source changes {field}")
    block = re.search(r"^Checksums-Sha256:\n((?: .+\n)+)", content, re.MULTILINE)
    if block is None:
        raise ValueError("source changes lacks SHA-256 manifest")
    listed = set()
    for line in block[1].splitlines():
        digest, size, name = line.split()
        if PurePosixPath(name).name != name or name in (".", ".."):
            raise ValueError("unsafe upload filename")
        path = root.parent / name
        if path.is_symlink():
            raise ValueError("upload artifact must not be a symlink")
        payload = path.read_bytes()
        if len(payload) != int(size) or hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError(f"upload checksum mismatch: {name}")
        listed.add(name)
    if not {dsc.name, archive.name} <= listed:
        raise ValueError("source changes does not include expected source artifacts")
    # Compare archived bytes with the signed Git tree without extracting files.
    tracked = set(run("git", "ls-files", cwd=root).splitlines())
    seen = set()
    with tarfile.open(archive) as source:
        for member in source:
            parts = PurePosixPath(member.name).parts
            if member.isdir():
                continue
            relative = str(PurePosixPath(*parts[1:]))
            if relative not in tracked or relative in seen or ".." in parts:
                raise ValueError(f"unexpected/duplicate archive member: {member.name}")
            expected = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root)
            if member.issym():
                actual = member.linkname.encode()
            elif member.isfile():
                actual = source.extractfile(member).read()
            else:
                raise ValueError(f"unsupported archive member: {member.name}")
            if actual != expected:
                raise ValueError(f"archive differs from signed source: {relative}")
            seen.add(relative)
    missing = sorted(tracked - seen)
    report = {"version": version, "source_tag": tag,
              "excluded_tracked_files_requiring_review": missing,
              "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (changes, dsc, archive)}}
    (root.parent / "source-review.json").write_text(json.dumps(report, indent=2) + "\n")
    subprocess.run(["lintian", str(changes)], cwd=root, check=True)
    print(json.dumps(report, indent=2))
    print("Review exclusions and Lintian warnings; this is not regression acceptance or upload approval.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="read PPA history and print proposed release identity")
    commands.add_parser("status", help="read all PPA source publication states")
    commands.add_parser("prepare", help="clone clean HEAD and add PPA changelog entry").add_argument("destination", type=Path)
    commands.add_parser("inspect", help="verify signed source upload against Git").add_argument("checkout", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            print(json.dumps(plan(ROOT), indent=2))
        elif args.command == "status":
            print(json.dumps(publications(), indent=2))
        elif args.command == "prepare":
            prepare(args.destination)
        else:
            inspect(args.checkout)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"publish: stopped: {error}\n")


if __name__ == "__main__":
    main()
