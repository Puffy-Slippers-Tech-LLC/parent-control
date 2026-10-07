"""Private gettext lookup for release-note Markdown; no UI or broker state."""

import gettext
import re

from .languages import selected_language
from .localization import LOCALE_DIR


DOMAIN = 'oh-no-parent-control-whats-new'


def release_domain(version):
    """Use only canonical numeric release identities as catalogue components."""
    if not isinstance(version, str) or not re.fullmatch(
            r'(?:0|[1-9][0-9]{0,8})(?:\.(?:0|[1-9][0-9]{0,8})){1,3}', version):
        raise ValueError('invalid release version')
    parts = version.split('.')
    while len(parts) > 2 and parts[-1] == '0':
        parts.pop()
    return DOMAIN + '-' + '.'.join(parts)


def content_context(record):
    return 'whats-new:' + record['record_id']


def load_whats_new_translations(version, saved_language='', language_names=(), *, localedir=LOCALE_DIR):
    """Resolve the same personal/session language as the owning frontend."""
    language = selected_language(saved_language, language_names).replace('-', '_')
    return gettext.translation(release_domain(version), localedir=str(localedir),
                               languages=[language], fallback=True)


def translate_content(record, translations):
    """Translate before Markdown rendering; exact source edits invalidate lookup."""
    return translations.pgettext(content_context(record), record['Content'])
