#!/usr/bin/env python3
"""Validate the requirement-to-test manifest without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIREMENT_ID = re.compile(r"ONPC-[A-Z0-9]+(?:-[A-Z0-9]+)+")
REQUIREMENT_MARKER = re.compile(
    r"^\s*-\s+\[(ONPC-[A-Z0-9]+(?:-[A-Z0-9]+)+)\]\s+"
)
REQUIRED_KEYS = {
    "id",
    "section",
    "component",
    "required_test_layer",
    "test_references",
    "supporting_contract_references",
    "evidence_type",
    "coverage_state",
}
VALID_LAYERS = {"unit", "contract", "component", "system", "e2e"}
VALID_EVIDENCE_TYPES = {"runtime", "three-sided-runtime"}
VALID_COVERAGE_STATES = {"planned", "covered"}


def specification_ids(specification: Path) -> tuple[list[str], list[str]]:
    """Return requirement IDs and untagged normative bullets from the specification."""
    ids: list[str] = []
    untagged: list[str] = []
    normative = False
    for line_number, line in enumerate(
        specification.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if line.startswith("## 1. Core end-to-end release acceptance"):
            normative = True
            continue
        if not normative or not re.match(r"^\s*-\s+", line):
            continue
        match = REQUIREMENT_MARKER.match(line)
        if match:
            ids.append(match.group(1))
        else:
            untagged.append(f"{specification}:{line_number}")
    return ids, untagged


def _load_manifest(manifest_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"cannot read manifest {manifest_path}: {error}"]
    if not isinstance(manifest, dict):
        return None, ["manifest must be a JSON object"]
    return manifest, []


def _known_test_reference(reference: str, repository_root: Path) -> bool:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts or not reference.startswith("tests/"):
        return False
    return (repository_root / path).is_file()


def validate(
    specification: Path,
    manifest_path: Path,
    mode: str = "stage",
    repository_root: Path | None = None,
) -> list[str]:
    """Return all structural and traceability errors for a manifest."""
    errors: list[str] = []
    repository_root = repository_root or manifest_path.resolve().parents[1]
    specification_ids_in_file, untagged = specification_ids(specification)
    errors.extend(f"normative bullet has no requirement ID: {item}" for item in untagged)

    duplicate_specification_ids = {
        item for item in specification_ids_in_file if specification_ids_in_file.count(item) > 1
    }
    errors.extend(
        f"duplicate specification requirement ID: {item}"
        for item in sorted(duplicate_specification_ids)
    )

    manifest, load_errors = _load_manifest(manifest_path)
    errors.extend(load_errors)
    if manifest is None:
        return errors
    if manifest.get("schema_version") != 1:
        errors.append("manifest schema_version must be 1")
    records = manifest.get("requirements")
    if not isinstance(records, list):
        return errors + ["manifest requirements must be a list"]

    manifest_ids: list[str] = []
    for index, record in enumerate(records):
        location = f"requirements[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{location} must be an object")
            continue
        missing_keys = REQUIRED_KEYS - record.keys()
        extra_keys = record.keys() - REQUIRED_KEYS
        if missing_keys:
            errors.append(f"{location} missing keys: {', '.join(sorted(missing_keys))}")
        if extra_keys:
            errors.append(f"{location} has unknown keys: {', '.join(sorted(extra_keys))}")
        requirement_id = record.get("id")
        if not isinstance(requirement_id, str) or not REQUIREMENT_ID.fullmatch(requirement_id):
            errors.append(f"{location} has an invalid requirement ID")
        else:
            manifest_ids.append(requirement_id)
        for key in ("section", "component"):
            if not isinstance(record.get(key), str) or not record[key].strip():
                errors.append(f"{location}.{key} must be a non-empty string")
        layer = record.get("required_test_layer")
        if layer not in VALID_LAYERS:
            errors.append(f"{location} has invalid test layer: {layer!r}")
        evidence_type = record.get("evidence_type")
        if evidence_type not in VALID_EVIDENCE_TYPES:
            errors.append(f"{location} has invalid evidence type: {evidence_type!r}")
        coverage_state = record.get("coverage_state")
        if coverage_state not in VALID_COVERAGE_STATES:
            errors.append(f"{location} has invalid coverage state: {coverage_state!r}")
        for key in ("test_references", "supporting_contract_references"):
            references = record.get(key)
            if not isinstance(references, list) or not all(
                isinstance(reference, str) for reference in references
            ):
                errors.append(f"{location}.{key} must be a list of strings")
                continue
            for reference in references:
                if not _known_test_reference(reference, repository_root):
                    errors.append(f"{location} has unknown test reference: {reference}")
        if coverage_state == "covered" and not record.get("test_references"):
            errors.append(f"{location} is covered but has no executable test reference")
        if mode == "final":
            if coverage_state != "covered":
                errors.append(f"{location} is not covered in final mode")
            if not record.get("test_references"):
                errors.append(f"{location} has no executable test reference in final mode")

    duplicate_manifest_ids = {item for item in manifest_ids if manifest_ids.count(item) > 1}
    errors.extend(
        f"duplicate manifest requirement ID: {item}"
        for item in sorted(duplicate_manifest_ids)
    )
    specification_id_set = set(specification_ids_in_file)
    manifest_id_set = set(manifest_ids)
    errors.extend(
        f"missing manifest record for specification ID: {item}"
        for item in sorted(specification_id_set - manifest_id_set)
    )
    errors.extend(
        f"manifest references unknown specification ID: {item}"
        for item in sorted(manifest_id_set - specification_id_set)
    )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specification", type=Path, default=Path("docs/Specification.md"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/requirements.json"))
    parser.add_argument("--mode", choices=("stage", "final"), default="stage")
    arguments = parser.parse_args(argv)
    errors = validate(arguments.specification, arguments.manifest, arguments.mode)
    if errors:
        print("Traceability validation failed:", file=sys.stderr)
        print(*[f"- {error}" for error in errors], sep="\n", file=sys.stderr)
        return 1
    print(f"Traceability validation passed ({arguments.mode} mode).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
