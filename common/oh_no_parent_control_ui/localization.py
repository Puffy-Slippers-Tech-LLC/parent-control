"""GTK-independent GNU gettext support for the product's per-user language.

Keep the returned object with the requesting surface/user. Never install it in
builtins or change process locale: the broker can serve several users at once.
"""

import gettext
from collections.abc import Iterable
from pathlib import Path

from .languages import selected_language


DOMAIN = "oh-no-parent-control"
LOCALE_DIR = Path(__file__).with_name("locale")


def load_translations(
    saved_language: str = "",
    language_names: Iterable[str] = (),
    *,
    localedir: str | Path = LOCALE_DIR,
) -> gettext.NullTranslations:
    """Return standard gettext/gettext-plural/context methods for one user.

    Pass GetOwnLanguage's value and the frontend's GLib.get_language_names().
    Empty/unsupported selections follow the existing catalogue resolver. With
    no frontend locale supplied, English is the default, never the root service's
    environment. Canonical product IDs become gettext directory names (pt_BR,
    zh_Hans). Missing catalogues/messages use the original English source text.

    Malformed/unreadable catalogues raise: shipped catalogues are trusted build
    artifacts checked by msgfmt, not downloaded or user-supplied content.
    """
    language = selected_language(saved_language, language_names).replace("-", "_")
    return gettext.translation(
        DOMAIN, localedir=str(localedir), languages=[language], fallback=True,
    )
