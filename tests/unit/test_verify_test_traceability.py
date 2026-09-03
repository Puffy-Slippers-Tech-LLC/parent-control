import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_SPEC = importlib.util.spec_from_file_location(
    "verify_test_traceability", ROOT / "tools/verify_test_traceability.py"
)
traceability = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(traceability)


class TraceabilityValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "tests/unit").mkdir(parents=True)
        (self.root / "tests/unit/test_example.py").write_text("", encoding="utf-8")
        self.specification = self.root / "Specification.md"
        self.manifest = self.root / "requirements.json"
        self._write_specification("- [ONPC-CORE-EXAMPLE-001] An executable requirement.\n")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _write_specification(self, bullet):
        self.specification.write_text(
            "# Specification\n\n## 1. Core end-to-end release acceptance\n\n" + bullet,
            encoding="utf-8",
        )

    def _record(self, **changes):
        record = {
            "id": "ONPC-CORE-EXAMPLE-001",
            "section": "1 / Example",
            "component": "broker",
            "required_test_layer": "unit",
            "test_references": [],
            "supporting_contract_references": [],
            "evidence_type": "runtime",
            "coverage_state": "planned",
        }
        record.update(changes)
        return record

    def _write_manifest(self, records):
        self.manifest.write_text(
            json.dumps({"schema_version": 1, "requirements": records}),
            encoding="utf-8",
        )

    def _validate(self, mode="stage"):
        return traceability.validate(
            self.specification, self.manifest, mode, repository_root=self.root
        )

    def test_accepts_a_planned_record_in_stage_mode(self):
        self._write_manifest([self._record()])
        self.assertEqual(self._validate(), [])

    def test_rejects_untagged_normative_bullet_and_missing_record(self):
        self._write_specification("- An untagged executable requirement.\n")
        self._write_manifest([])
        errors = self._validate()
        self.assertTrue(any("normative bullet has no requirement ID" in error for error in errors))

    def test_rejects_a_specification_id_without_a_manifest_record(self):
        self._write_manifest([])
        errors = self._validate()
        self.assertTrue(
            any("missing manifest record for specification ID" in error for error in errors)
        )

    def test_rejects_duplicate_and_unknown_requirement_ids(self):
        self._write_manifest(
            [self._record(), self._record(id="ONPC-CORE-EXAMPLE-999")]
        )
        errors = self._validate()
        self.assertTrue(any("unknown specification ID" in error for error in errors))
        self._write_manifest([self._record(), self._record()])
        errors = self._validate()
        self.assertTrue(any("duplicate manifest requirement ID" in error for error in errors))

    def test_rejects_invalid_layers_and_unknown_test_references(self):
        self._write_manifest(
            [
                self._record(
                    required_test_layer="release",
                    test_references=["tests/unit/missing.py"],
                )
            ]
        )
        errors = self._validate()
        self.assertTrue(any("invalid test layer" in error for error in errors))
        self.assertTrue(any("unknown test reference" in error for error in errors))

    def test_final_mode_requires_executable_covered_evidence(self):
        self._write_manifest([self._record()])
        errors = self._validate(mode="final")
        self.assertTrue(any("not covered in final mode" in error for error in errors))
        self.assertTrue(any("no executable test reference in final mode" in error for error in errors))

    def test_rejects_malformed_records(self):
        malformed = self._record()
        del malformed["component"]
        self._write_manifest([malformed])
        errors = self._validate()
        self.assertTrue(any("missing keys" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
