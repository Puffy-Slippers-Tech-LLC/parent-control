"""Host-safe verification for deterministic application-test fixtures."""

from tests.support.modules import load_module
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


if __name__ == "__main__":
    unittest.main()
