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


def translated_release_blocks(record, saved_language='', language_names=(), *,
                              localedir=LOCALE_DIR, links_enabled=True):
    """Translate and parse each release independently before combining blocks."""
    from .release_markdown import markdown_blocks
    releases = record.get('releases', [record])
    blocks = []
    for release in releases:
        translations = load_whats_new_translations(
            release['ProductVersion'], saved_language, language_names, localedir=localedir)
        content = translate_content(release, translations)
        if 'releases' in record:
            if blocks:
                blocks.append(('rule', ''))
            blocks.append(('heading', 'v' + release['ProductVersion']))
        blocks.extend(markdown_blocks(content, links_enabled=links_enabled))
        if 'releases' in record:
            # The current release's link remains in the dialog footer.
            if release.get('SeeMore') and release['ProductVersion'] != record['ProductVersion']:
                link = release['SeeMore'].replace('(', '%28').replace(')', '%29')
                blocks.extend(markdown_blocks(
                    f"[v{release['ProductVersion']}]({link})", links_enabled=links_enabled))
    return blocks
