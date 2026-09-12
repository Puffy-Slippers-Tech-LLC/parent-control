"""Regression checks for shipped license and Malcontent disclosures."""

from __future__ import annotations

import unittest


from tests.support.paths import ROOT


class LicensingTests(unittest.TestCase):
    def test_notice_describes_the_separate_malcontent_dependency(self):
        notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
        self.assertIn("LGPL-2.1-or-later", notice)
        self.assertIn("does not include, modify, or redistribute Malcontent", notice)
        self.assertIn("not affiliated with, endorsed by, or sponsored", notice)

    def test_debian_metadata_covers_product_and_bundled_font(self):
        copyright_file = (ROOT / "debian/copyright").read_text(encoding="utf-8")
        self.assertIn("License: GPL-3.0-only", copyright_file)
        self.assertIn("License: OFL-1.1", copyright_file)

    def test_about_dialog_exposes_local_legal_notices(self):
        source = (ROOT / "common/oh_no_parent_control_ui/about.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('notices_path = _data_dir() / "NOTICE"', source)
        self.assertIn('"Legal notices"', source)
        self.assertNotIn("All rights reserved.", source)

    def test_installation_ships_legal_notices_without_developer_documentation(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("LICENSE COPYRIGHT NOTICE", makefile)
        product_files = makefile.split("_install-product-files:\n", 1)[1].split(
            "\n_generate-package-activation-manifest:", 1
        )[0]
        self.assertNotIn("docs/", product_files)
        self.assertNotIn("README.md", product_files)
