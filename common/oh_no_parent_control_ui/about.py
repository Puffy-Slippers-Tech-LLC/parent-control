"""Brand-backed About dialog shared by the GTK front ends."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk


_INSTALLED_DATA_DIR = Path("/usr/share/oh-no-parent-control")
_SOURCE_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _data_dir() -> Path:
    return _INSTALLED_DATA_DIR if _INSTALLED_DATA_DIR.is_dir() else _SOURCE_DATA_DIR


def _load_json(name: str) -> dict:
    value = json.loads((_data_dir() / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return value


def branding() -> dict:
    """Return the product's shared, package-installed branding data."""
    values = _load_json("brand.json")
    for name in ("app_name", "vendor_name", "app_url", "contact"):
        if not isinstance(values.get(name), str) or not values[name]:
            raise ValueError(f"brand.json {name} must be a non-empty string")
    return values


def app_name() -> str:
    """Return the product name from the shared branding record."""
    return branding()["app_name"]


def app_version() -> str:
    """Return the release version declared by this installed application."""
    version = _load_json("app.json").get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("app.json version must be a non-empty string")
    return version


def _launch_uri(uri: str) -> None:
    Gio.AppInfo.launch_default_for_uri(uri, None)


def _detail_row(icon_name: str | None, label: str, value: str, uri: str | None, *,
                links_enabled: bool, icon_filename: str | None = None) -> Gtk.Box:
    row = Gtk.Box(spacing=16, margin_top=8, margin_bottom=8)
    icon = (Gtk.Image.new_from_file(str(_data_dir() / icon_filename))
            if icon_filename else Gtk.Image(icon_name=icon_name))
    icon.set_pixel_size(32)
    icon.set_valign(Gtk.Align.CENTER)
    row.append(icon)
    copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
    copy.append(Gtk.Label(label=label, xalign=0, css_classes=["about-detail-label"]))
    if uri and links_enabled:
        # LinkButton delegates activation to GTK's URI launcher.  Besides
        # handling pointer clicks, this makes the links reachable by keyboard
        # and exposes their target to assistive technology.
        value_widget = Gtk.LinkButton.new_with_label(uri, value)
        value_widget.set_halign(Gtk.Align.START)
        value_widget.add_css_class("about-link")
        value_widget.add_css_class("about-detail-value")
    else:
        value_widget = Gtk.Label(label=value, xalign=0,
                                 css_classes=["about-detail-value"])
    copy.append(value_widget)
    row.append(copy)
    return row


class AboutDialog(Gtk.Window):
    """A modal product About dialog.

    ``links_enabled=False`` keeps kiosk information visible without offering
    browser, mail-client, or local-file launches.
    """

    def __init__(self, parent: Gtk.Window, *, links_enabled: bool = True):
        values = branding()
        super().__init__(title="About", transient_for=parent, modal=True)
        self.set_default_size(460, 680)
        self.set_resizable(False)
        self.add_css_class("about-dialog")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                          margin_top=18, margin_bottom=18,
                          margin_start=24, margin_end=24)

        logo = Gtk.Picture.new_for_filename(str(_data_dir() / "app_logo.png"))
        logo.set_size_request(150, 150)
        logo.set_content_fit(Gtk.ContentFit.CONTAIN)
        logo.set_halign(Gtk.Align.CENTER)
        logo.set_margin_top(16)
        content.append(logo)
        content.append(Gtk.Label(label=values["app_name"], css_classes=["title-1"],
                                 halign=Gtk.Align.CENTER, margin_top=10))
        content.append(Gtk.Label(label=f"Version {app_version()}",
                                 css_classes=["dim-label"], halign=Gtk.Align.CENTER))
        content.append(Gtk.Label(label="Helping families build healthy digital habits.",
                                 css_classes=["dim-label"], halign=Gtk.Align.CENTER,
                                 margin_bottom=16))
        content.append(Gtk.Separator())
        content.append(_detail_row(None, "Website", values["app_url"],
                                   values["app_url"],
                                   links_enabled=links_enabled,
                                   icon_filename="company_logo.png"))
        subject = f"{values['app_name']}: Feedbacks"
        # Some mail clients display '+' from form-style query encoding
        # literally. Percent encoding is unambiguous for a mailto URI.
        email_uri = f"mailto:{values['contact']}?subject={quote(subject, safe='')}"
        content.append(_detail_row("mail-unread-symbolic", "Support", values["contact"],
                                   email_uri, links_enabled=links_enabled))
        license_path = _data_dir() / "LICENSE"
        content.append(_detail_row("text-x-generic-symbolic", "License",
                                   "GNU General Public License v3.0",
                                   license_path.as_uri(), links_enabled=links_enabled))
        content.append(Gtk.Box(vexpand=True))
        content.append(Gtk.Label(
            label=f"© 2026 {values['vendor_name']}\nAll rights reserved.",
            justify=Gtk.Justification.CENTER, css_classes=["dim-label"],
            halign=Gtk.Align.CENTER,
        ))
        self.set_child(content)


def open_help() -> None:
    """Open the product website in the registered browser."""
    _launch_uri(branding()["app_url"])
