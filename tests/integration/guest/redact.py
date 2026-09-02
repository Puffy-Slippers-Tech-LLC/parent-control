#!/usr/bin/python3
"""Redact credentials and bearer material from collected text artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


VALUE = re.compile(
    r"(?im)\b(password|passwd|secret|token|authorization[_-]?id)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
BEARER = re.compile(r"(?im)(authorization\s*:\s*bearer\s+)[^\s]+")
SSH_KEY = re.compile(r"(?m)ssh-(?:rsa|ed25519)\s+[A-Za-z0-9+/=]+(?:\s+[^\n]+)?")
PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?-----END [^-\n]*PRIVATE KEY-----",
    re.DOTALL,
)


def redact_text(contents: str, marker_token: str) -> str:
    if marker_token:
        contents = contents.replace(marker_token, "<redacted-token>")
    contents = VALUE.sub(lambda match: match.group(1) + match.group(2) + "<redacted>", contents)
    contents = BEARER.sub(r"\1<redacted>", contents)
    contents = SSH_KEY.sub("<redacted-ssh-public-key>", contents)
    return PRIVATE_KEY.sub("<redacted-private-key>", contents)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: redact.py ARTIFACT_DIRECTORY MARKER", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    marker = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    token = marker.get("token", "")
    if not isinstance(token, str):
        raise SystemExit("invalid marker token")
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        encoded = path.read_bytes()
        if b"\0" in encoded:
            raise SystemExit(f"unexpected binary artifact: {path.relative_to(root)}")
        contents = encoded.decode("utf-8", errors="replace")
        path.write_text(redact_text(contents, token), encoding="utf-8")

    manifest = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest.append(f"{digest}  {path.relative_to(root)}")
    (root / "SHA256SUMS").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
