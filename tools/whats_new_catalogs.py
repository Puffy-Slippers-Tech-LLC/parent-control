"""Deterministic latest-release preparation, validation and gettext compilation.

Release-note catalogs are singular whole-document messages in a separate domain.
Only the latest numeric VersionHistory release is prepared/checked, with any
matching child TOML entry. Historical PO sources
are read solely by packaging, never merged or translated by synchronization.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'broker'))
from oh_no_parent_control.whats_new import read_history, read_metadata, validate_metadata, version_key
from common.oh_no_parent_control_ui.whats_new import content_context, release_domain


@dataclass(frozen=True)
class Release:
    version: str
    records: tuple[dict, ...]
    languages: tuple[str, ...]
    source_digest: str


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def latest(root=ROOT):
    history = root / 'docs/VersionHistory.md'
    source = root / 'data/whats-new-child.toml'
    parent = read_history(history)
    records = parent + validate_metadata(read_metadata(source))
    version = max((record['ProductVersion'] for record in parent), key=version_key)
    entries = json.loads((root / 'common/oh_no_parent_control_ui/languages.json').read_text())
    languages = tuple(entry['id'].replace('-', '_') for entry in entries if entry['id'] != 'en')
    if not languages or len(languages) != len(set(languages)) or any(
            not re.fullmatch(r'[A-Za-z]{2,8}(?:_[A-Za-z0-9]{1,8})*', language)
            for language in languages):
        raise ValueError('invalid supported language catalogue')
    return Release(version, tuple(record for record in records if record['ProductVersion'] == version),
                   languages, hashlib.sha256(json.dumps(
                       [fingerprint(history), fingerprint(source)]).encode()).hexdigest())


def catalog_path(root, release, language):
    return root / 'po/whats-new' / release.version / (language + '.po')


def regular_path(path):
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError(f'catalogue path contains a symlink: {path}')
    if path.exists() and not path.is_file():
        raise ValueError(f'catalogue is not a regular file: {path}')


def write_changed(path, content):
    """Replace only a changed caller-owned source/build asset, atomically."""
    regular_path(path)
    if path.exists() and path.read_text(encoding='utf-8') == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.' + path.name, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            temporary.chmod(0o644)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def po_entries(text):
    """Read the singular PO dialect emitted here (including GNU multiline strings).

    Comments and previous-source references are accepted; plurals, duplicate keys,
    unsupported syntax and duplicate contexts are refused. GNU msgfmt independently
    checks the resulting catalogues. Application PO files are read for headers only.
    """
    entries = []
    for block in re.split(r'\n\s*\n', text.strip()):
        fields, active, fuzzy, previous = {}, None, False, None
        for line in block.splitlines():
            if line.startswith('#,'):
                fuzzy |= 'fuzzy' in [flag.strip() for flag in line[2:].split(',')]
            elif line.startswith('#| msgid '):
                previous = ast.literal_eval(line[9:])
            elif line.startswith('#'):
                continue
            elif match := re.fullmatch(r'(msgctxt|msgid|msgstr) (".*")', line):
                active = match[1]
                if active in fields:
                    raise ValueError('duplicate PO field')
                fields[active] = ast.literal_eval(match[2])
            elif line.startswith('"') and active:
                fields[active] += ast.literal_eval(line)
            elif line.strip():
                raise ValueError(f'unsupported release-note PO syntax: {line[:80]}')
        if not fields:
            continue
        if not {'msgid', 'msgstr'} <= fields.keys() or any(
                not isinstance(value, str) for value in fields.values()):
            raise ValueError('invalid PO entry')
        fields.update(fuzzy=fuzzy, previous=previous)
        entries.append(fields)
    keys = [(entry.get('msgctxt'), entry['msgid']) for entry in entries]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate PO entry')
    return entries


def read_catalog(path):
    regular_path(path)
    if not path.exists():
        return []
    entries = po_entries(path.read_text(encoding='utf-8'))
    contexts = [entry.get('msgctxt') for entry in entries if entry['msgid']]
    if len(set(contexts)) != len(contexts) or any(
            not context or not context.startswith('whats-new:') for context in contexts):
        raise ValueError(f'invalid release-note contexts: {path}')
    return entries


def header(root, language):
    # Reuse the established language-specific headers/plural metadata; no model
    # authors infrastructure or plural rules during a translation session.
    source = (root / 'po' / (language + '.po')).read_text(encoding='utf-8')
    for block in re.split(r'\n\s*\n', source):
        if re.search(r'^msgid ""$', block, re.MULTILINE):
            entries = po_entries(block)
            if len(entries) == 1 and entries[0]['msgid'] == '':
                return entries[0]['msgstr']
    raise ValueError(f'missing application PO header: {language}')


def serialize(header_text, records, translations):
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    blocks = ['# Release-note Markdown; maintained by tools/sync-whatsnew.\n'
              'msgid ""\nmsgstr ' + quote(header_text)]
    for record in records:
        context = content_context(record)
        entry = translations.get(context, {})
        lines = ['#. Translate the complete Markdown; preserve structure, URLs, code and branding.']
        if entry.get('fuzzy'):
            lines.append('#, fuzzy')
        if entry.get('previous') is not None:
            lines.append('#| msgid ' + quote(entry['previous']))
        lines += ['msgctxt ' + quote(context), 'msgid ' + quote(record['Content']),
                  'msgstr ' + quote(entry.get('msgstr', ''))]
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks) + '\n'


def prepare(root=ROOT, release=None):
    release = release or latest(root)
    directory = root / 'po/whats-new' / release.version
    template_header = 'Project-Id-Version: ' + release_domain(release.version) + '\nContent-Type: text/plain; charset=UTF-8\n'
    write_changed(directory / 'whats-new.pot', serialize(template_header, release.records, {}))
    for language in release.languages:
        path = catalog_path(root, release, language)
        existing = {entry['msgctxt']: entry for entry in read_catalog(path) if entry.get('msgctxt')}
        translations = {}
        for record in release.records:
            context = content_context(record)
            entry = dict(existing.get(context, {}))
            if entry and entry['msgid'] != record['Content']:
                entry.update(previous=entry['msgid'], fuzzy=True)
            translations[context] = entry
        write_changed(path, serialize(header(root, language), release.records, translations))
    return release


def markdown_signature(text):
    """Conservative checks for structure and non-translatable Markdown operands.

    This is not a Markdown renderer or a semantic quality score. Agents also
    review grammar, meaning, formatting and regional terminology themselves.
    """
    structure, fence, code, fenced = [], None, [], []
    for line in text.splitlines():
        delimiter = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if delimiter and fence is None:
            fence = delimiter[1][0]
            structure.append(('fence', delimiter[2].strip()))
            code = []
        elif delimiter and fence == delimiter[1][0]:
            fenced.append('\n'.join(code))
            fence = None
        elif fence:
            code.append(line)
        elif match := re.match(r'^(\s*)(#{1,6})\s+', line):
            structure.append(('heading', len(match[2])))
        elif match := re.match(r'^(\s*)(?:[-+*]|[0-9]+[.)])\s+', line):
            structure.append(('list', len(match[1])))
        elif re.match(r'^\s*>', line):
            structure.append(('quote',))
        elif re.match(r'^\s*\|', line):
            structure.append(('table', line.count('|')))
    if fence:
        raise ValueError('unclosed Markdown code fence')
    protected = Counter(re.findall(r'https?://[^\s<>\)\]"\']+', text))
    protected.update(re.findall(r'`+[^`\n]+`+', text))
    protected.update(re.findall(r'%\([^)]+\)[a-zA-Z]|\{[A-Za-z_][A-Za-z0-9_]*\}', text))
    protected.update(re.findall(r'(?<![\w.])v?[0-9]+\.[0-9]+(?:\.[0-9]+){0,2}\b', text))
    protected.update(re.findall(r'<[^>]+>', text))
    protected['Oh No! Parent Control'] = text.count('Oh No! Parent Control')
    return structure, fenced, protected, text.count('**')


def validate_content(source, translated):
    if (not isinstance(translated, str) or not translated.strip() or len(translated) > 65536
            or '\x00' in translated or any(0xD800 <= ord(char) <= 0xDFFF for char in translated)):
        raise ValueError('invalid translated Markdown')
    if markdown_signature(source) != markdown_signature(translated):
        raise ValueError('translation changed Markdown structure or protected literals')


def pending(root=ROOT, release=None):
    release = release or latest(root)
    result = {}
    for language in release.languages:
        path = catalog_path(root, release, language)
        entries = {entry.get('msgctxt'): entry for entry in read_catalog(path)}
        work = []
        for record in release.records:
            entry = entries.get(content_context(record), {})
            reason = 'missing'
            if entry:
                reason = 'changed' if entry['msgid'] != record['Content'] else 'unreviewed'
                if entry['msgid'] == record['Content'] and entry['msgstr'] and not entry['fuzzy']:
                    try:
                        validate_content(record['Content'], entry['msgstr'])
                    except ValueError:
                        reason = 'invalid'
                    else:
                        continue
            work.append(dict(record, reason=reason, previous_source=entry.get('previous') or entry.get('msgid'),
                             previous_translation=entry.get('msgstr', '')))
        if work:
            result[language] = work
    return result


def check(root=ROOT):
    release = latest(root)
    work = pending(root, release)
    if work:
        raise ValueError(f'latest release {release.version}: pending translations for ' + ', '.join(work))
    for language in release.languages:
        subprocess.run(['msgfmt', '--check', '--check-format', '-o', '/dev/null',
                        str(catalog_path(root, release, language))], check=True, timeout=30)
    return release


def compile_catalogs(root, output):
    directory = root / 'po/whats-new'
    if not directory.exists():
        return
    for source in sorted(directory.glob('*/*.po')):
        regular_path(source)
        domain = release_domain(source.parent.name)
        locale = source.stem
        if not re.fullmatch(r'[A-Za-z]{2,8}(?:_[A-Za-z0-9]{1,8})*', locale):
            raise ValueError('invalid release-note locale')
        destination = output / locale / 'LC_MESSAGES' / (domain + '.mo')
        regular_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.' + domain, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            subprocess.run(['msgfmt', '--check', '--check-format', '-o', str(temporary), str(source)],
                           check=True, timeout=30)
            temporary.chmod(0o644)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('compile', 'check'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.action == 'compile':
        if args.output is None:
            parser.error('compile requires --output')
        compile_catalogs(ROOT, args.output)
    else:
        release = check()
        print(f'What’s New v{release.version}: all {len(release.languages)} non-English languages complete')
    return 0


if __name__ == '__main__':
    sys.exit(main())
