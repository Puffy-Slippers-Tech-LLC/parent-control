"""Product language catalogue, shared by broker and presentation consumers.

The JSON source is also shipped with the Shell extension for JavaScript readers.
Availability is separate from the broker's forward-compatible storage syntax.
JSON order is product priority, never alphabetical or a runtime-derived ranking.
"""

from fnmatch import fnmatchcase
import json
from pathlib import Path


_ENTRIES = json.loads(Path(__file__).with_name("languages.json").read_text(encoding="utf-8"))
SUPPORTED_LANGUAGES = tuple((entry["id"], entry["name"]) for entry in _ENTRIES)
_BY_ID = {identity.lower(): identity for identity, _name in SUPPORTED_LANGUAGES}
_BY_LANGUAGE = {}
for identity, _name in SUPPORTED_LANGUAGES:
    base = identity.split("-")[0]
    _BY_LANGUAGE.setdefault(base, identity)
    if identity == base:
        _BY_LANGUAGE[base] = identity
_DIRECTIONS = {entry["id"]: entry.get("direction", "ltr") for entry in _ENTRIES}
_ENGLISH_NAMES = {entry["id"]: entry["english_name"] for entry in _ENTRIES}


def language_matches(query: str, identity: str, name: str) -> bool:
    """Case-insensitive partial/wildcard search of native/English names or IDs."""
    pattern = f"*{query.strip().casefold()}*"
    return any(fnmatchcase(value.casefold(), pattern)
               for value in (name, identity, _ENGLISH_NAMES.get(identity, "")))


def supported_language(locale_name: str) -> str:
    """Resolve a locale to a trusted catalogue ID, retaining supported variants.

    Exact product IDs win. Chinese script precedes region; unspecified Chinese
    uses Simplified. Portuguese defaults to pt, with Brazil selecting pt-BR.
    Serbian defaults to Cyrillic; sr@latin and sr-Latn select Latin.
    Other regional variants collapse to their base-language choice.
    """
    locale, _, modifier = locale_name.partition("@")
    normalized = locale.split(".", 1)[0].replace("_", "-").lower()
    if normalized in _BY_ID:
        # POSIX modifiers can still select a script for a bare base language.
        if not (normalized == "sr" and modifier.lower() == "latin"):
            return _BY_ID[normalized]
    parts = normalized.split("-")
    base = {"no": "nb", "iw": "he", "in": "id", "sh": "sr"}.get(parts[0], parts[0])
    if base == "zh":
        if "hans" in parts:
            return "zh-Hans"
        if "hant" in parts or any(region in parts for region in ("tw", "hk", "mo")):
            return "zh-Hant"
        return "zh-Hans"
    if base == "pt":
        return "pt-BR" if "br" in parts else "pt"
    if base == "sr":
        return "sr-Latn" if "latn" in parts or modifier.lower() == "latin" or parts[0] == "sh" else "sr"
    return _BY_LANGUAGE.get(base, "en")


def language_direction(locale_name: str) -> str:
    """Native-name direction; absent catalogue metadata means left-to-right."""
    return _DIRECTIONS[supported_language(locale_name)]


def session_language(language_names) -> str:
    """Use the session's primary message locale, falling back to English.

    Callers supply GLib.get_language_names(), which observes LANGUAGE,
    LC_ALL, LC_MESSAGES and LANG without consulting the broker's root locale.
    An unsupported primary language falls back to English, not another locale.
    """
    return supported_language(next(iter(language_names), "en"))


def selected_language(saved_language: str, language_names) -> str:
    """Resolve a chooser's saved value or session default for every frontend."""
    return (supported_language(saved_language) if saved_language
            else session_language(language_names))


def desktop_language_candidates(saved_language: str) -> tuple[str, ...]:
    """Desktop-entry locale keys for an explicit product language selection."""
    if not saved_language:
        return ()
    language = supported_language(saved_language)
    locale = {"zh-Hans": "zh_CN", "zh-Hant": "zh_TW",
              "sr-Latn": "sr@latin"}.get(language, language.replace("-", "_"))
    base = locale.split("_", 1)[0].split("@", 1)[0]
    # Also accept script spellings supplied by some desktop entries.
    return tuple(dict.fromkeys((locale.casefold(), language.replace("-", "_").casefold(), base)))
