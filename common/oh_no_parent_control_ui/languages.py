"""Product language catalogue, shared by broker and presentation consumers.

The JSON source is also shipped with the Shell extension for JavaScript readers.
Availability is separate from the broker's forward-compatible storage syntax.
"""

import json
from pathlib import Path


SUPPORTED_LANGUAGES = tuple(
    (entry["id"], entry["name"])
    for entry in json.loads(Path(__file__).with_name("languages.json").read_text(encoding="utf-8"))
)
_BY_LANGUAGE = {identity.split("-")[0]: identity for identity, _name in SUPPORTED_LANGUAGES}


def supported_language(locale_name: str) -> str:
    """Map every regional/script variant to its one product language choice."""
    language = locale_name.split(".", 1)[0].split("@", 1)[0].replace("_", "-").split("-", 1)[0]
    return _BY_LANGUAGE.get(language.lower(), "en")


def session_language(language_names) -> str:
    """Use the session's primary message locale, falling back to English.

    Callers supply GLib.get_language_names(), which observes LANGUAGE,
    LC_ALL, LC_MESSAGES and LANG without consulting the broker's root locale.
    An unsupported primary language falls back to English, not another locale.
    """
    return supported_language(next(iter(language_names), "en"))
