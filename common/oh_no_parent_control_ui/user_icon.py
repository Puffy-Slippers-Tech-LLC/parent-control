"""Account-selector helpers for AccountsService user icons."""

from __future__ import annotations

from pathlib import Path

from gi.repository import Gtk

DEFAULT_USER_ICON_NAME = "avatar-default-symbolic"


def parse_listed_user(entry):
    if not isinstance(entry, (list, tuple)) or not 2 <= len(entry) <= 3:
        raise ValueError("broker returned an invalid account")
    uid, label, *rest = entry
    icon_file = rest[0] if rest else ""
    if type(uid) is not int or uid < 0 or not isinstance(label, str) or not label.strip():
        raise ValueError("broker returned an invalid account")
    if not isinstance(icon_file, str):
        raise ValueError("broker returned an invalid account")
    return uid, label.strip(), icon_file


def apply_gtk_user_icon(image: Gtk.Image, icon_file: str, pixel_size: int = 22) -> None:
    image.set_pixel_size(pixel_size)
    if icon_file.startswith("/") and Path(icon_file).is_file():
        image.set_from_file(icon_file)
    else:
        image.set_from_icon_name(DEFAULT_USER_ICON_NAME)
