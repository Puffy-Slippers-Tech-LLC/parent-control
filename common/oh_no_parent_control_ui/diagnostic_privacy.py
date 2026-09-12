"""Lossy, shared diagnostic projection. Never retain identity mappings or hashes.

Do not pass arbitrary prose to this module. Producers select individual fields
with reviewed provenance; validators reject anything outside the shipped schema.
"""

import re


def category(value, allowed, fallback="unknown"):
    return value if type(value) is str and value in allowed else fallback


def version(value):
    """Keep a bounded numeric upstream version; discard ALL custom suffixes.

Epochs are packaging metadata, not the upstream version. Never scan arbitrary
text for numbers: the source must be a version field, starting with a version.
"""
    if type(value) is not str or len(value) > 256:
        return "unknown"
    match = re.match(r"^(?:[0-9]{1,4}:)?([0-9]{1,6}(?:\.[0-9]{1,6}){0,3})(?![0-9.])", value)
    return match.group(1) if match else "unknown"


def account_counts(roles, *, complete):
    """Aggregate role categories only. Never accept or return account objects."""
    counts = {"administrators": 0, "non_administrators": 0}
    for role in roles:
        if role not in ("administrator", "non-administrator", "excluded"):
            complete = False
        elif role != "excluded":
            key = "administrators" if role == "administrator" else "non_administrators"
            counts[key] += 1
    return {**counts, "status": "complete" if complete else "partial"}
