"""Publisher identity, Debian versioning and signed source integrity checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
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


def verify_signature(path: Path, root: Path) -> None:
    status = run("gpg", "--batch", "--status-fd=1", "--verify", str(path), cwd=root)
    signatures = [line.split() for line in status.splitlines()
                  if line.startswith("[GNUPG:] VALIDSIG ")]
    if not signatures or any(KEY not in (line[2], line[-1]) for line in signatures):
        raise ValueError("source signature does not belong to the configured publisher")


def inspect(root: Path) -> None:
    root = root.resolve()
    clean(root)
    version = run("dpkg-parsechangelog", "-S", "Version", cwd=root)
    if not re.fullmatch(r"[0-9]+\.[0-9]+\+ppa[1-9][0-9]*~ubuntu26\.04\.1", version):
        raise ValueError("unexpected PPA package version")
    if run("dpkg-parsechangelog", "-S", "Distribution", cwd=root) != "resolute":
        raise ValueError("release must target resolute")
    tag = source_tag(version)
    verified = subprocess.run(
        ["git", "-c", "gpg.program=/usr/bin/gpg", "verify-tag", "--raw", tag],
        cwd=root, text=True, capture_output=True, check=True)
    signatures = [line.split() for line in verified.stderr.splitlines()
                  if line.startswith("[GNUPG:] VALIDSIG ")]
    if not signatures or any(KEY not in (line[2], line[-1]) for line in signatures):
        raise ValueError("source tag signature does not belong to the publisher")
    if run("git", "rev-parse", "HEAD", cwd=root) != run("git", "rev-parse", f"{tag}^{{commit}}", cwd=root):
        raise ValueError("HEAD differs from the package source tag")
    prefix = root.parent / f"{PACKAGE}_{version}"
    changes = Path(f"{prefix}_source.changes")
    dsc = Path(f"{prefix}.dsc")
    archive = Path(f"{prefix}.tar.xz")
    for path in (changes, dsc):
        verify_signature(path, root)
    inspect_archive(root, version, tag=tag)


def inspect_archive(root: Path, version: str, *, tag: str | None = None) -> None:
    """Check upload manifests and archive bytes against a frozen local Git tree.

    Publishing authenticates signatures before calling this; local tests use an
    unsigned snapshot and need no publisher credentials or release tags.
    """
    prefix = root.parent / f"{PACKAGE}_{version}"
    changes = Path(f"{prefix}_source.changes")
    dsc = Path(f"{prefix}.dsc")
    archive = Path(f"{prefix}.tar.xz")
    # Authenticate every file in the upload, including source buildinfo.
    content = changes.read_text()
    for field, expected in (("Source", PACKAGE), ("Version", version), ("Architecture", "source")):
        matches = re.findall(r"^" + field + r": (.*)$", content, re.MULTILINE)
        if matches != [expected]:
            raise ValueError(f"unexpected source changes {field}")
    if re.findall(r"^Distribution: (.*)$", content, re.MULTILINE) != ["resolute"]:
        raise ValueError("source upload distribution must be resolute")
    block = re.search(r"^Checksums-Sha256:\n((?: .+\n)+)", content, re.MULTILINE)
    if block is None or (len(re.findall(r'^Checksums-Sha256:', content, re.MULTILINE)) != 1):
        raise ValueError("source changes lacks SHA-256 manifest")
    listed = set()
    for line in block[1].splitlines():
        digest, size, name = line.split()
        if PurePosixPath(name).name != name or name in (".", ".."):
            raise ValueError("unsafe upload filename")
        path = root.parent / name
        if path.is_symlink() or not path.is_file() or name in listed:
            raise ValueError("upload artifact must not be a symlink")
        payload = path.read_bytes()
        if len(payload) != int(size) or hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError(f"upload checksum mismatch: {name}")
        listed.add(name)
    if not {dsc.name, archive.name} <= listed:
        raise ValueError("source changes does not include expected source artifacts")
    # Compare archived bytes with the signed Git tree without extracting files.
    tracked = set(run("git", "ls-files", cwd=root).splitlines())
    modes = {}
    for entry in run("git", "ls-files", "--stage", cwd=root).splitlines():
        metadata, name = entry.split('\t', 1)
        modes[name] = metadata.split()[0]
    seen = set()
    archive_root = None
    with tarfile.open(archive) as source:
        for member in source:
            parts = PurePosixPath(member.name).parts
            if not parts or PurePosixPath(member.name).is_absolute() or '..' in parts:
                raise ValueError("unsafe source archive member path")
            if archive_root is None:
                archive_root = parts[0]
            if parts[0] != archive_root:
                raise ValueError("source archive must have a single root directory")
            if member.isdir():
                continue
            relative = str(PurePosixPath(*parts[1:]))
            if relative not in tracked or relative in seen or ".." in parts:
                raise ValueError(f"unexpected/duplicate archive member: {member.name}")
            expected = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root)
            if member.issym():
                actual = member.linkname.encode()
                if modes[relative] != '120000':
                    raise ValueError("source archive symlink type differs from Git")
            elif member.isfile():
                actual = source.extractfile(member).read()
                if (modes[relative] not in ('100644', '100755')
                               or bool(member.mode & 0o111) != (modes[relative] == '100755')):
                    raise ValueError("source archive executable mode differs from Git")
            else:
                raise ValueError(f"unsupported archive member: {member.name}")
            if actual != expected:
                raise ValueError(f"archive differs from signed source: {relative}")
            seen.add(relative)
    missing = sorted(tracked - seen)
    if any(not name.startswith(('.codex/', '.agents/')) for name in missing):
        raise ValueError("source archive excludes tracked files beyond development agent configuration")
    report = {"version": version, "source_tag": tag,
              "excluded_tracked_files_requiring_review": missing,
              "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (changes, dsc, archive)}}
    (root.parent / "source-review.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
