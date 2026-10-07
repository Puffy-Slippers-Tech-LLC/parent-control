"""Render release-note Markdown as safe native GTK/Pango blocks.

Headings, paragraphs, lists, quotes, rules, fenced code and inline emphasis,
code and HTTP(S) links are supported. Raw HTML remains literal text; images
remain text and never fetch remote resources.
"""

import html
import re
from urllib.parse import urlsplit


def safe_link(uri):
    try:
        parts = urlsplit(uri)
        return (parts.scheme in ('http', 'https') and bool(parts.hostname)
                and not parts.username and not parts.password
                and not any(character.isspace() or ord(character) < 32 for character in uri)
                and '\\' not in uri)
    except ValueError:
        return False


_INLINE = re.compile(
    r'\\([\\`*{}_\[\]()#+.!>-])|(`+)(.+?)\2|'
    r'(!?)\[([^\]\n]+)\]\(([^\s)]+)\)|'
    r'(\*\*|__)(.+?)\7|(\*|_)([^\n]+?)\9|~~(.+?)~~')


def inline_markup(text):
    """Escape data before emitting the small supported Pango vocabulary."""
    output = []
    position = 0
    for match in _INLINE.finditer(text):
        output.append(html.escape(text[position:match.start()]))
        escaped, ticks, code, image, label, uri, bold, strong, italic, emphasis, strike = match.groups()
        if escaped:
            output.append(html.escape(escaped))
        elif ticks:
            output.append('<tt>' + html.escape(code) + '</tt>')
        elif label:
            if not image and safe_link(uri):
                output.append('<a href="' + html.escape(uri, quote=True) + '">'
                              + inline_markup(label) + '</a>')
            else:
                output.append(html.escape(match.group()))
        elif bold:
            output.append('<b>' + inline_markup(strong) + '</b>')
        elif italic:
            output.append('<i>' + html.escape(emphasis) + '</i>')
        else:
            output.append('<s>' + html.escape(strike) + '</s>')
        position = match.end()
    output.append(html.escape(text[position:]))
    return ''.join(output)


def markdown_blocks(source):
    """Return (kind, markup) blocks without importing GTK or creating widgets."""
    result = []
    paragraph = []
    fence = None
    code = []

    def flush():
        if paragraph:
            result.append(('paragraph', inline_markup('\n'.join(paragraph))))
            paragraph.clear()

    for line in source.splitlines():
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                result.append(('code', '<tt>' + html.escape('\n'.join(code)) + '</tt>'))
                code.clear()
                fence = None
            else:
                code.append(line)
            continue
        if marker:
            flush()
            fence = marker[1]
            continue
        heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*$', line)
        bullet = re.match(r'^(\s*)(?:[-+*]|(\d+)[.)])\s+(.+)$', line)
        quote = re.match(r'^\s{0,3}>\s?(.*)$', line)
        if not line.strip():
            flush()
        elif paragraph and re.fullmatch(r'\s{0,3}(?:=+|-+)\s*', line):
            result.append(('heading', inline_markup('\n'.join(paragraph))))
            paragraph.clear()
        elif re.fullmatch(r'\s{0,3}(?:\*\s*){3,}|\s{0,3}(?:-\s*){3,}|\s{0,3}(?:_\s*){3,}', line):
            flush()
            result.append(('rule', ''))
        elif heading:
            flush()
            result.append(('heading', inline_markup(heading[2])))
        elif bullet:
            flush()
            prefix = (bullet[2] + '.' if bullet[2] else '•') + '  '
            result.append(('list', html.escape(' ' * len(bullet[1]) + prefix) + inline_markup(bullet[3])))
        elif quote:
            flush()
            result.append(('quote', inline_markup(quote[1])))
        elif line.startswith(('    ', '\t')) and result and result[-1][0] == 'list':
            kind, text = result[-1]
            result[-1] = (kind, text + '\n' + inline_markup(line.strip()))
        else:
            paragraph.append(line)
    flush()
    if fence is not None:
        result.append(('code', '<tt>' + html.escape('\n'.join(code)) + '</tt>'))
    return result
