"""Packaged release notes and upgrade eligibility, independent of any UI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from urllib.parse import urlsplit

PRODUCT_PATH = Path("/usr/share/oh-no-parent-control/app.json")
METADATA_PATH = Path("/usr/share/oh-no-parent-control/whats-new.toml")
INSTALLATION_PATH = Path("/var/lib/oh-no-parent-control/whats-new-installation.json")
INSTALLATION_FORMAT_VERSION = 1
MAX_RECORDS = 64
MAX_DOCUMENT_BYTES = 512 * 1024
VERSION_RE = re.compile(r"(?:0|[1-9][0-9]{0,8})(?:\.(?:0|[1-9][0-9]{0,8})){1,3}")


class WhatsNewError(ValueError):
    """Invalid release metadata or installation history."""


def product_version(value: object) -> str:
    """Canonical numeric product version; distribution revisions are separate."""
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        raise WhatsNewError("invalid product version")
    parts = value.split(".")
    while len(parts) > 2 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)


def version_key(value: str) -> tuple[int, ...]:
    parts = tuple(int(part) for part in product_version(value).split("."))
    return parts + (0,) * (4 - len(parts))


def validate_seen(raw: object) -> list[str]:
    if not isinstance(raw, list) or len(raw) > 256:
        raise WhatsNewError("invalid release acknowledgements")
    identifiers = []
    for value in raw:
        if not isinstance(value, str) or value.count(":") != 1:
            raise WhatsNewError("invalid release record identity")
        version, components = value.split(":")
        if components not in {"Parent", "Child", "Child,Parent"}:
            raise WhatsNewError("invalid release record identity")
        identifiers.append(f"{product_version(version)}:{components}")
    if len(identifiers) != len(set(identifiers)):
        raise WhatsNewError("duplicate release acknowledgement")
    return sorted(identifiers, key=lambda value: (version_key(value.split(":")[0]), value))


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WhatsNewError("duplicate metadata key")
        result[key] = value
    return result


def _read_text(path: Path) -> str:
    with path.open("rb") as stream:
        encoded = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(encoded) > MAX_DOCUMENT_BYTES:
        raise WhatsNewError("release metadata is too large")
    try:
        return encoded.decode("utf-8")
    except UnicodeError as error:
        raise WhatsNewError("invalid release metadata encoding") from error


def read_document(path: Path) -> object:
    text = _read_text(path)
    try:
        return json.loads(text, object_pairs_hook=_unique_keys)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise WhatsNewError("invalid release metadata JSON") from error


def read_metadata(path: Path) -> object:
    """Read author-edited TOML, preserving literal multiline Markdown."""
    text = _read_text(path)
    try:
        return tomllib.loads(text)
    except (ValueError, RecursionError) as error:
        raise WhatsNewError("invalid release metadata TOML") from error


def validate_metadata(raw: object) -> tuple[dict, ...]:
    if (not isinstance(raw, dict) or set(raw) != {"version", "records"} or
            type(raw["version"]) is not int or raw["version"] != 1 or
            not isinstance(raw["records"], list) or len(raw["records"]) > MAX_RECORDS):
        raise WhatsNewError("invalid release metadata document")
    records, version_components = [], {}
    for raw_record in raw["records"]:
        if (not isinstance(raw_record, dict) or
                not {"ProductVersion", "ShowIn", "Content"} <= set(raw_record) or
                not set(raw_record) <= {"ProductVersion", "ShowIn", "Content", "SeeMore"}):
            raise WhatsNewError("invalid release record keys")
        version = product_version(raw_record["ProductVersion"])
        show_in = raw_record["ShowIn"]
        if not isinstance(show_in, str):
            raise WhatsNewError("invalid release components")
        components = [part.strip() for part in show_in.split(",")]
        if (not components or len(components) != len(set(components)) or
                not set(components) <= {"Parent", "Child"}):
            raise WhatsNewError("invalid release components")
        occupied = version_components.setdefault(version, set())
        if occupied & set(components):
            raise WhatsNewError("overlapping release components for the same version")
        occupied.update(components)
        content = raw_record["Content"]
        if (not isinstance(content, str) or not content.strip() or len(content) > 65536 or
                "\x00" in content or any(0xD800 <= ord(char) <= 0xDFFF for char in content)):
            raise WhatsNewError("invalid Markdown content")
        show_in = ",".join(sorted(components))
        record = {"ProductVersion": version, "ShowIn": show_in, "Content": content,
                  "record_id": f"{version}:{show_in}"}
        if "SeeMore" in raw_record:
            link = raw_record["SeeMore"]
            if (not isinstance(link, str) or not link or len(link) > 2048 or "\\" in link or
                    any(char.isspace() or ord(char) < 32 or ord(char) >= 127 for char in link)):
                raise WhatsNewError("invalid SeeMore link")
            try:
                parsed = urlsplit(link)
                if (parsed.scheme not in {"http", "https"} or not parsed.hostname or
                        parsed.username is not None or parsed.password is not None):
                    raise ValueError("invalid URL")
                # urlsplit decomposes URLs but accepts malformed authorities,
                # including text outside IPv6 brackets and encoded delimiters.
                if ("%" in parsed.netloc or
                        ("[" in parsed.netloc and not re.fullmatch(
                            r"\[[^\[\]]+\](?::[0-9]+)?", parsed.netloc))):
                    raise ValueError("invalid URL authority")
                parsed.port  # Reject malformed/out-of-range ports too.
            except ValueError as error:
                raise WhatsNewError("invalid SeeMore link") from error
            record["SeeMore"] = link
        records.append(record)
    return tuple(sorted(records, key=lambda record: version_key(record["ProductVersion"])))


def validate_installation(raw: object) -> dict:
    if (not isinstance(raw, dict) or set(raw) != {"version", "first_version", "current_version"} or
            type(raw["version"]) is not int or raw["version"] != INSTALLATION_FORMAT_VERSION):
        raise WhatsNewError("invalid installation history")
    first = product_version(raw["first_version"])
    current = product_version(raw["current_version"])
    if version_key(first) > version_key(current):
        raise WhatsNewError("installation history moves backwards")
    return {"version": INSTALLATION_FORMAT_VERSION, "first_version": first, "current_version": current}


@dataclass(frozen=True)
class WhatsNewCatalog:
    current_version: str
    first_version: str
    records: tuple[dict, ...]

    @classmethod
    def load(cls, metadata_path: Path = METADATA_PATH, product_path: Path = PRODUCT_PATH,
             installation_path: Path = INSTALLATION_PATH) -> WhatsNewCatalog:
        product = read_document(product_path)
        if not isinstance(product, dict) or set(product) != {"version"}:
            raise WhatsNewError("invalid product metadata")
        current = product_version(product["version"])
        installation = validate_installation(read_document(installation_path))
        if current != installation["current_version"]:
            raise WhatsNewError("installation history is not configured for this release")
        return cls(current, installation["first_version"],
                   validate_metadata(read_metadata(metadata_path)))

    @property
    def retained_records(self) -> set[str]:
        # Keep acknowledgement for every component, including future records.
        return {record["record_id"] for record in self.records}

    def available(self, component: str, seen: list[str]) -> dict:
        records = []
        for record in self.records:
            version = record["ProductVersion"]
            if (component in record["ShowIn"].split(",") and
                    version_key(version) == version_key(self.current_version)):
                records.append({**record, "auto_show": record["record_id"] not in seen and
                                version_key(self.first_version) < version_key(version)})
        return {"product_version": self.current_version, "records": records}

    def acknowledgement(self, component: str, version: object) -> str:
        version = product_version(version)
        for record in self.available(component, [])["records"]:
            if record["ProductVersion"] == version:
                return record["record_id"]
        raise WhatsNewError("release is unavailable for this component")
