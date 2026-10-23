"""Host-safe verification for deterministic application-test fixtures."""

from tests.support.modules import load_module
import json
from pathlib import Path
import tempfile
import unittest


from tests.support.paths import ROOT
FIXTURES = ROOT / "tests/fixtures/build_test_applications.py"
fixtures = load_module('onpc_test_applications', FIXTURES)


class TestApplicationFixtures(unittest.TestCase):
    def test_builder_refuses_nonempty_or_broad_output_locations(self):
        with tempfile.TemporaryDirectory(prefix="onpc-test-fixtures-") as temporary:
            output = Path(temporary)
            (output / "existing").write_text("fixture", encoding="utf-8")
            with self.assertRaises(fixtures.FixtureError):
                fixtures._require_empty_output(output)
        with self.assertRaises(fixtures.FixtureError):
            fixtures._require_empty_output(Path("/"))
        with self.assertRaises(fixtures.FixtureError):
            fixtures._require_empty_output(ROOT / "artifacts/test-fixtures")

    def test_verify_requires_the_complete_payload_inventory(self):
        with tempfile.TemporaryDirectory(prefix="onpc-test-fixtures-") as temporary:
            output = Path(temporary)
            stable = output / "mechanical/onpc-test-application"
            stable.parent.mkdir()
            stable.write_bytes(b"fixture")
            for relative in fixtures.VOLATILE_FILES:
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"container")
            fixtures._write_manifest(output)
            fixtures.verify(output)

            (output / "unlisted").write_bytes(b"not attested")
            with self.assertRaisesRegex(fixtures.FixtureError, "complete payload"):
                fixtures.verify(output)
            (output / "unlisted").unlink()

            manifest_path = output / "SHA256SUMS.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["files"]["mechanical/onpc-test-application"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(fixtures.FixtureError, "complete payload"):
                fixtures.verify(output)


if __name__ == "__main__":
    unittest.main()
