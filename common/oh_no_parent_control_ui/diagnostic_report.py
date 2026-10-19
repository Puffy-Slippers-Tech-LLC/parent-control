"""Readable dated logs, rebuilt from closed diagnostic fields at every boundary."""

from datetime import date
from io import BytesIO
import json
import re
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from .diagnostic_bundle import MAX_BYTES, MAX_INPUT_BYTES, MAX_RECORDS, _manifest, validate_record
from .diagnostic_events import COMPONENTS, describe, encode
from .system_info import DIAGNOSTIC_PACKAGES, RPM_DIAGNOSTIC_PACKAGES, validate_system_info
from .languages import SUPPORTED_LANGUAGES

MAX_LANGUAGE_USERS = 256
LANGUAGE_IDS = frozenset(identity for identity, _name in SUPPORTED_LANGUAGES)


def validate_user_languages(value):
    """Accept report-local role labels and catalogue IDs, never account identity."""
    if (type(value) is not dict or set(value) != {"status", "users"}
            or value["status"] not in ("complete", "partial", "unavailable")
            or type(value["users"]) is not list or len(value["users"]) > MAX_LANGUAGE_USERS):
        raise ValueError("Invalid diagnostic user languages")
    ordinals = {"Parent": 0, "Child": 0}
    for row in value["users"]:
        if type(row) is not dict or set(row) != {"user", "language"}:
            raise ValueError("Invalid diagnostic user language")
        role = next((role for role in ordinals
                     if row["user"] == f"[{role} {ordinals[role] + 1}]"), None)
        if (role is None or type(row["language"]) is not str
                or row["language"] not in LANGUAGE_IDS | {"unset", "other", "unavailable"}):
            raise ValueError("Invalid diagnostic user language")
        ordinals[role] += 1
    if value["status"] == "unavailable" and value["users"]:
        raise ValueError("Invalid diagnostic user languages")
    if value["status"] == "complete" and any(row["language"] == "unavailable" for row in value["users"]):
        raise ValueError("Invalid diagnostic user languages")
    return value

DIRECTORIES = tuple(component + "/" for component in sorted(COMPONENTS))
HEADER = (
    "ONPC component log (schema 3)\n"
    "Offsets are elapsed time within a broker diagnostic segment, not clock times.\n"
    "Dates name retained source files; incident context can include earlier observations.\n"
    "Frontend events are observations; broker events describe broker decisions.\n"
    "Missing observations do not establish that an operation did not occur.\n\n"
)
LINE = re.compile(
    r"\[([A-Z]+)\] (?:([0-9T:.Z-]{24}) )?segment=([0-9]+) \+([0-9]+)ms #([0-9]+) op=([0-9]+) "
    r"event=([a-z0-9.-]+) fields=(.*) \| (.*)"
)


def _component(name):
    if type(name) is not str:
        raise ValueError("Invalid diagnostic log path")
    parts = name.split("/")
    if len(parts) != 2 or parts[0] not in COMPONENTS:
        raise ValueError("Invalid diagnostic log path")
    filename = parts[1]
    if filename != "undated.log":
        if (len(filename) != 14 or not filename.endswith(".log")
                or date.fromisoformat(filename[:10]).isoformat() != filename[:10]):
            raise ValueError("Invalid diagnostic log date")
    return parts[0]


def _line(record):
    timestamp = record["timestamp"] + " " if "timestamp" in record else ""
    return (f"[{record['level']}] {timestamp}segment={record['segment']} +{record['elapsed_ms']}ms "
            f"#{record['sequence']} op={record['operation']} event={record['event']} "
            f"fields={encode(record['fields'])} | {describe(record)}\n")


def compact_system_info(value):
    """Project older collectors onto the same small, named runtime list."""
    if value is None:
        return None
    validate_system_info(value)
    packages = {row["name"]: row for row in value["dependencies"]["packages"]
                if row["name"] in (*DIAGNOSTIC_PACKAGES, *RPM_DIAGNOSTIC_PACKAGES, "quill")}
    return {**value, "dependencies": {**value["dependencies"],
            "packages": [packages[name] for name in sorted(packages)]}}


def contents(logs, health=None, summary=None, system_info=None, user_languages=None):
    if type(logs) is not dict or len(logs) > 3 * len(COMPONENTS):
        raise ValueError("Invalid diagnostic logs")
    payload, inventory = {}, {}
    component_counts = {component: 0 for component in COMPONENTS}
    total = 0
    for name in sorted(logs):
        component = _component(name)
        component_counts[component] += 1
        if component_counts[component] > 3 or type(logs[name]) is not list:
            raise ValueError("Invalid diagnostic history")
        total += len(logs[name])
        if total > MAX_RECORDS:
            raise ValueError("Diagnostic record limit")
        records = [validate_record(record) for record in logs[name]]
        if any(record["component"] != component for record in records):
            raise ValueError("Invalid diagnostic component")
        payload[name] = (HEADER + "".join(_line(record) for record in records)).encode("ascii")
        inventory[name] = len(records)
    manifest = _manifest(health, summary)
    info = {"schema": 3, "system": compact_system_info(system_info),
            "health": manifest["health"], "counts": manifest["counts"], "logs": inventory}
    if user_languages is not None:
        info["user_languages"] = validate_user_languages(user_languages)
    # Indentation makes the small summary usable without a JSON formatter.
    return {"system-info.json": (json.dumps(info, ensure_ascii=True, indent=2, sort_keys=True)
                                 + "\n").encode("ascii"),
            **{name: b"" for name in DIRECTORIES}, **payload}


def build_report(logs, health=None, summary=None, system_info=None, user_languages=None):
    payload = contents(logs, health, summary, system_info, user_languages)
    if sum(map(len, payload.values())) > MAX_INPUT_BYTES:
        raise ValueError("Diagnostic attachment limit")
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, data)
    if output.tell() > MAX_BYTES:
        raise ValueError("Diagnostic attachment limit")
    return output.getvalue()


def read_report(archive):
    """Parse only our canonical log grammar; arbitrary prose fails closed."""
    info = json.loads(archive.read("system-info.json"))
    keys = {"schema", "system", "health", "counts", "logs"}
    if (type(info) is not dict or set(info) not in (keys, keys | {"user_languages"})
            or type(info["schema"]) is not int or info["schema"] != 3
            or type(info["logs"]) is not dict or len(info["logs"]) > 12):
        raise ValueError("Invalid diagnostic system information")
    members = ["system-info.json", *DIRECTORIES, *sorted(info["logs"])]
    if archive.namelist() != members:
        raise ValueError("Invalid diagnostic archive members")
    logs, total = {}, 0
    for name, count in info["logs"].items():
        component = _component(name)
        if type(count) is not int or not 0 <= count <= MAX_RECORDS:
            raise ValueError("Invalid diagnostic record count")
        total += count
        if total > MAX_RECORDS:
            raise ValueError("Diagnostic record limit")
        content = archive.read(name).decode("ascii")
        if not content.startswith(HEADER):
            raise ValueError("Invalid diagnostic log header")
        lines = content[len(HEADER):].splitlines()
        if len(lines) != count:
            raise ValueError("Invalid diagnostic record count")
        records = []
        for line in lines:
            match = LINE.fullmatch(line) if len(line) <= 8192 else None
            if match is None:
                raise ValueError("Invalid diagnostic log record")
            level, timestamp, segment, elapsed, sequence, operation, event, fields, _ = match.groups()
            record = validate_record({"v": 1, "component": component, "level": level,
                **({"timestamp": timestamp} if timestamp is not None else {}),
                "segment": int(segment), "elapsed_ms": int(elapsed), "sequence": int(sequence),
                "operation": int(operation), "event": event, "fields": json.loads(fields)})
            if _line(record) != line + "\n":
                raise ValueError("Invalid diagnostic log text")
            records.append(record)
        logs[name] = records
    if "user_languages" in info:
        validate_user_languages(info["user_languages"])
    expected = contents(logs, info["health"], info["counts"], info["system"], info.get("user_languages"))
    if any(archive.read(name) != expected[name] for name in members):
        raise ValueError("Invalid diagnostic content")
    return logs, info
