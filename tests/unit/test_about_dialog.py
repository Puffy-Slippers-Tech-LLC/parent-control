"""Tests for intrinsic-size About dialog branding."""

import unittest


from tests.support.paths import ROOT


class AboutDialogTests(unittest.TestCase):
    def test_help_uses_the_desktop_default_uri_launcher(self):
        source = (ROOT / "common/oh_no_parent_control_ui/about.py").read_text(
            encoding="utf-8")
        self.assertIn('_launch_uri(portal_url(branding()["help_url"], context_for(owner).language))', source)
        self.assertIn('Gio.AppInfo.launch_default_for_uri(uri, None)', source)

    def test_portal_pages_use_canonical_surface_locale(self):
        from common.oh_no_parent_control_ui.localization import portal_url
        from common.oh_no_parent_control_ui.languages import SUPPORTED_LANGUAGES
        base = 'https://tech.puffyslippers.com'
        languages = [(identity, '' if identity == 'en' else '/' + identity)
                     for identity, _name in SUPPORTED_LANGUAGES]
        languages.extend([('pt_BR.UTF-8', '/pt-BR'),
                          ('zh_TW.UTF-8', '/zh-Hant'), ('zz', '')])
        for language, prefix in languages:
            for page in ('', 'help', 'privacy', 'version-history',
                         'compare-gnome', 'coming-next'):
                path = '/oh-no-parent-control' + ('/' + page if page else '')
                with self.subTest(language=language, path=path):
                    expected = base + prefix + path + '/?source=app#notice'
                    for suffix in ('', '/'):
                        self.assertEqual(portal_url(base + path + suffix + '?source=app#notice',
                                                    language), expected)
        for uri in ('mailto:contact@tech.puffyslippers.com', 'file:///usr/share/LICENSE',
                    'https://example.com/help',
                    base + '/api/oh-no-parent-control/feedback'):
            self.assertEqual(portal_url(uri, 'de'), uri)

    def test_website_row_uses_the_small_company_icon(self):
        source = (ROOT / "common/oh_no_parent_control_ui/about.py").read_text(
            encoding="utf-8")

        self.assertIn('_detail_row(None, m.WEBSITE', source)
        messages = (ROOT / "common/oh_no_parent_control_ui/messages.py").read_text(
            encoding="utf-8")
        self.assertIn("WEBSITE = gettext('Website')", messages)
        self.assertIn('icon_filename="company_icon_32.png"', source)

        with (ROOT / "data/company_icon_32.png").open("rb") as logo:
            logo.read(16)
            self.assertEqual(logo.read(8), b"\x00\x00\x00 \x00\x00\x00 ")

    def test_information_rows_expose_clickable_links(self):
        source = (ROOT / "common/oh_no_parent_control_ui/about.py").read_text(
            encoding="utf-8")

        self.assertIn('Gtk.LinkButton.new_with_label(uri, value)', source)
        self.assertIn('"security-high-symbolic", m.PRIVACY', source)
        messages = (ROOT / "common/oh_no_parent_control_ui/messages.py").read_text(
            encoding="utf-8")
        self.assertIn("PRIVACY = gettext('Privacy')", messages)

    def test_gtk_about_logo_uses_launcher_art_at_the_original_display_size(self):
        source = (ROOT / "common/oh_no_parent_control_ui/about.py").read_text(
            encoding="utf-8")

        self.assertIn('branding_asset_path("app_logo_gnome_launcher.png")', source)
        self.assertIn("_ABOUT_LOGO_WIDTH = 126", source)
        self.assertIn("_ABOUT_LOGO_HEIGHT = 128", source)
        self.assertIn("Gsk.ScalingFilter.TRILINEAR", source)
        self.assertIn("logo = _AboutLogo()", source)

    def test_child_session_uses_the_shared_gtk_about_dialog(self):
        stylesheet = (ROOT / "child/stylesheet.css").read_text(encoding="utf-8")
        kiosk = (ROOT / "kiosk/oh_no_parent_control_kiosk/main.py").read_text(
            encoding="utf-8")

        self.assertNotIn(".oh-no-parent-control-about-logo", stylesheet)
        self.assertIn("AboutDialog(self, links_enabled=self._child_overlay)", kiosk)
