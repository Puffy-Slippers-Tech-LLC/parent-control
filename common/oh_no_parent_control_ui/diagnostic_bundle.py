"""Validate current readable reports and previous structured broker snapshots."""

from io import BytesIO
from datetime import datetime, timezone
import json
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from .diagnostic_events import COMPONENTS, LEVELS, decode, encode, describe
from .system_info import validate_system_info

MAX_BYTES = 2 * 1024 * 1024
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 12000
HEALTH_KEYS = ("accounts", "timer", "polkit", "systemd", "migration", "storage")
HEALTH_STATES = ("available", "inactive", "unavailable", "incomplete", "unknown")
COUNTERS = ("suppressed", "rotations", "incidents", "invalid", "truncated", "missing", "write_failures")
MEMBERS = ("manifest.json", "events.jsonl", "report.txt")
SYSTEM_MEMBERS = (*MEMBERS, "system-info.json")


def validate_record(value):
    extras = {"component", "level", "sequence", "segment", "elapsed_ms"}
    if type(value) is dict and "timestamp" in value:
        timestamp = value["timestamp"]
        if type(timestamp) is not str or len(timestamp) != 24 or not timestamp.endswith("Z"):
            raise ValueError("Invalid diagnostic timestamp")
        parsed = datetime.fromisoformat(timestamp[:-1] + "+00:00")
        if parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z") != timestamp:
            raise ValueError("Invalid diagnostic timestamp")
        extras.add("timestamp")
    if type(value) is not dict or set(value) != extras | {"v", "event", "fields", "operation"}:
        raise ValueError("Invalid diagnostic record")
    if value["component"] not in COMPONENTS or value["level"] not in LEVELS:
        raise ValueError("Invalid diagnostic record")
    for key in ("sequence", "segment", "elapsed_ms"):
        if type(value[key]) is not int or not 0 <= value[key] <= 2**53 - 1:
            raise ValueError("Invalid diagnostic record")
    safe = decode(encode({key: value[key] for key in ("v", "event", "fields", "operation")}),
                  component=value["component"])
    return {**safe, **{key: value[key] for key in extras}}


def _manifest(health, summary):
    health = {} if health is None else health
    summary = {} if summary is None else summary
    if type(health) is not dict or type(summary) is not dict:
        raise ValueError("Invalid diagnostic summary")
    if set(health) - set(HEALTH_KEYS) or set(summary) - set(COUNTERS):
        raise ValueError("Invalid diagnostic summary")
    health = {key: health.get(key, "unknown") for key in HEALTH_KEYS}
    if any(type(value) is not str or value not in HEALTH_STATES for value in health.values()):
        raise ValueError("Invalid diagnostic health")
    counts = {key: summary.get(key, 0) for key in COUNTERS}
    if any(type(value) is not int or not 0 <= value <= 2**53 - 1 for value in counts.values()):
        raise ValueError("Invalid diagnostic counts")
    return {"schema": 1, "health": health, "counts": counts}


def contents(records, health=None, summary=None, system_info=None):
    if len(records) > MAX_RECORDS:
        raise ValueError("Diagnostic record limit")
    safe = [validate_record(record) for record in records]
    manifest = _manifest(health, summary)
    if system_info is not None:
        validate_system_info(system_info)
        manifest["schema"] = 2
    text = [f"ONPC diagnostic report (schema {manifest['schema']})",
            "Offsets are elapsed time within a diagnostic segment, not clock times.",
            "Frontend events are observations; broker events describe broker decisions.",
            "Missing observations do not establish that an operation did not occur.", "",
            "Health: " + encode(manifest["health"]),
            "Collection: " + encode(manifest["counts"]), ""]
    if system_info is not None:
        text.extend([
            "System information: see system-info.json.",
            "Versions retain numeric upstream components only; packaging/custom suffixes are discarded.",
            "Unapproved dependency names share [Dependency]; no identity mapping is retained.",
            "Account counts cover local interactive human accounts, excluding the product kiosk.",
            "Partial/unavailable collection must not be interpreted as a complete inventory.", "",
        ])
    for record in safe:
        text.append(f"segment={record['segment']} +{record['elapsed_ms']}ms "
                    f"#{record['sequence']} {record['component']} {record['level']} "
                    f"op={record['operation']} {describe(record)}")
    payload = {"manifest.json": encode(manifest).encode("ascii"),
            "events.jsonl": "".join(encode(record) + "\n" for record in safe).encode("ascii"),
            "report.txt": ("\n".join(text) + "\n").encode("ascii")}
    if system_info is not None:
        payload["system-info.json"] = encode(system_info).encode("ascii")
    return payload


def build_bundle(records, health=None, summary=None, system_info=None):
    payload = contents(records, health, summary, system_info)
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name in payload:
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, payload[name])
    if output.tell() > MAX_BYTES:
        raise ValueError("Diagnostic attachment limit")
    return output.getvalue()


def validate_bundle(data):
    """Reject raw logs, extra files, arbitrary report prose and ZIP bombs."""
    if type(data) is not bytes or not data or len(data) > MAX_BYTES:
        raise ValueError("Invalid diagnostic archive")
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            members = tuple(entry.filename for entry in entries)
            if sum(entry.file_size for entry in entries) > MAX_INPUT_BYTES:
                raise ValueError("Diagnostic archive limit")
            if members and members[0] == "system-info.json":
                from .diagnostic_report import read_report, build_report
                logs, info = read_report(archive)
                return build_report(logs, info["health"], info["counts"], info["system"])
            if members not in (MEMBERS, SYSTEM_MEMBERS):
                raise ValueError("Invalid diagnostic archive members")
            manifest = json.loads(archive.read("manifest.json"))
            schema = 2 if members == SYSTEM_MEMBERS else 1
            if (type(manifest) is not dict or set(manifest) != {"schema", "health", "counts"}
                    or type(manifest["schema"]) is not int or manifest["schema"] != schema):
                raise ValueError("Invalid diagnostic manifest")
            raw_records = archive.read("events.jsonl").splitlines()
            if len(raw_records) > MAX_RECORDS:
                raise ValueError("Diagnostic record limit")
            records = [json.loads(line) for line in raw_records]
            system_info = json.loads(archive.read("system-info.json")) if schema == 2 else None
            if schema == 2:
                validate_system_info(system_info)
            expected = contents(records, manifest["health"], manifest["counts"], system_info)
            if any(archive.read(name) != expected[name] for name in members):
                raise ValueError("Invalid diagnostic content")
    except Exception:
        # Malformed compression, encryption, JSON and metadata share one safe
        # failure contract. Never let library exception text reach the report.
        raise ValueError("Invalid diagnostic archive") from None
    # ZIP comments, extra headers and trailing bytes are not record content.
    # Rebuild instead of forwarding an otherwise valid, privately annotated ZIP.
    return build_bundle(records, manifest["health"], manifest["counts"], system_info)


def with_system_info(data, system_info):
    """Enrich a validated broker snapshot without trusting its ZIP metadata."""
    clean = validate_bundle(data)
    with ZipFile(BytesIO(clean)) as archive:
        from .diagnostic_report import read_report, build_report
        if archive.namelist()[0] == "system-info.json":
            logs, manifest = read_report(archive)
        else:
            manifest = json.loads(archive.read("manifest.json"))
            logs = {}
            for line in archive.read("events.jsonl").splitlines():
                record = json.loads(line)
                # Older brokers discarded source dates. Never invent them.
                logs.setdefault(record["component"] + "/undated.log", []).append(record)
    return build_report(logs, manifest["health"], manifest["counts"],
                        validate_system_info(system_info))
