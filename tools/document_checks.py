"""Read-only document checks with guarded metadata access for test evidence."""
import argparse
import json
from bisect import bisect_right
from dataclasses import dataclass
from html import unescape
import os
from pathlib import Path
import re
import stat
import subprocess
import string
import sys
import unicodedata
from urllib.parse import unquote


MAX_BYTES = 8 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
MAX_DESTINATION_CHARS = 8192
MAX_NESTING = 32
MAX_LABEL_CHARS = 999


@dataclass(frozen=True)
class Link:
    """Character offsets address the original source, excluding destination wrappers.

    Reference links point at their definition's destination; their start/end and
    line still identify the use. Percent escapes remain encoded until URL parts
    have been separated by local_destination.
    """
    start: int
    end: int
    destination_start: int
    destination_end: int
    destination: str
    line: int
    kind: str
    label_start: int
    label_end: int


@dataclass(frozen=True)
class LocalDestination:
    path: str
    fragment: str | None


def _bounded(text):
    if len(text) > MAX_BYTES or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('expected a regular UTF-8 document of at most 8 MiB')


def _mask(text):
    return re.sub(r'[^\n]', ' ', text)


def _escaped(text, position):
    start = position
    while start and text[start - 1] == '\\':
        start -= 1
    return (position - start) % 2 == 1


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('invalid document check; use tools/read-only --help')


def read_text(path):
    # Opening a FIFO/device must not block, and a final symlink is not adopted.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError('expected a regular UTF-8 document of at most 8 MiB')
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('document exceeded 8 MiB while reading')
    return data.decode('utf-8')


def checkout_document(root, value):
    """Validate an explicit Markdown mutation scope, including existing .MD files."""
    root, relative = Path(root).resolve(), Path(value)
    candidate = root / relative
    if (relative.is_absolute() or '..' in relative.parts
            or relative.suffix.lower() not in ('.md', '.markdown')
            or any(part.is_symlink() for part in (candidate, *candidate.parents))
            or not candidate.resolve().is_relative_to(root)):
        raise ValueError('document check: expected an explicit checkout Markdown file')
    return candidate


def without_examples(text, *, legacy=False):
    """Mask fenced/indented examples and HTML comments, preserving offsets."""
    _bounded(text)
    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r'^ {0,3}(`{3,}|~{3,})([^\n]*)', line)
        if fence:
            lines.append(_mask(line))
            if (match and match[1][0] == fence[0] and len(match[1]) >= len(fence)
                    and not match[2].strip()):
                fence = None
        elif match and (legacy or not (match[1][0] == '`' and '`' in match[2])):
            fence = match[1]
            lines.append(_mask(line))
        elif not legacy and line.startswith(('    ', '\t')):
            lines.append(_mask(line))
        else:
            lines.append(line)
    text = ''.join(lines)
    return (text if legacy else
            re.sub(r'<!--[\s\S]*?(?:-->|\Z)', lambda match: _mask(match[0]), text))


def without_code(text, *, legacy=False):
    """Mask examples and inline code spans without changing source offsets."""
    text = without_examples(text, legacy=legacy)
    runs = list(re.finditer(r'`+', text))
    # Resolve equal-length closing runs once, rather than rescanning the suffix
    # for every unmatched opening in adversarial input.
    next_run = {}
    closings = {}
    for index in range(len(runs) - 1, -1, -1):
        size = len(runs[index][0])
        closings[index] = next_run.get(size)
        next_run[size] = index
    parts = []
    position = 0
    index = 0
    while index < len(runs):
        opening = runs[index]
        if not legacy and _escaped(text, opening.start()):
            index += 1
            continue
        closing = closings[index]
        if closing is None:
            index += 1
            continue
        end = runs[closing].end()
        parts.extend([text[position:opening.start()], _mask(text[opening.start():end])])
        position = end
        index = closing + 1
    masked = ''.join([*parts, text[position:]])
    # Apply newer exclusions only after the old mask, so removing a comment's
    # code delimiter can never expose text that the old grammar protected.
    return without_examples(masked) if legacy else masked


def _decode(value):
    return unescape(re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\\\]^_`{|}~])', r'\1', value))


def _destination(text, position, limit):
    """Return raw destination bounds and following offset, or no recognized syntax."""
    angle = text[position:position + 1] == '<'
    start = index = position + int(angle)
    depth = 0
    end_limit = min(limit, start + MAX_DESTINATION_CHARS + 1)
    while index < end_limit:
        char = text[index]
        if (char == '\\' and index + 1 < end_limit
                and text[index + 1] in string.punctuation):
            index += 2
            continue
        if angle:
            if char == '>':
                return (start, index, index + 1) if index > start else None
            if char in '<\n\r':
                return None
        else:
            if char.isspace() or (char == ')' and not depth):
                break
            if char == '<':
                return None
            if char == '(':
                depth += 1
                if depth > MAX_NESTING:
                    return None
            elif char == ')':
                depth -= 1
        index += 1
    if angle or depth or index == start or index - start > MAX_DESTINATION_CHARS:
        return None
    return start, index, index


def _ending(text, position, limit, *, inline):
    index = position
    while index < limit and text[index].isspace():
        index += 1
    if index > position and index < limit and text[index] in '\"\'(':
        close = ')' if text[index] == '(' else text[index]
        index += 1
        while index < limit:
            if text[index] == '\\' and index + 1 < limit:
                index += 2
            elif text[index] == close:
                index += 1
                break
            elif text[index] in '\n\r':
                return None
            else:
                index += 1
        else:
            return None
        while index < limit and text[index].isspace():
            index += 1
    if inline:
        return index + 1 if index < limit and text[index] == ')' else None
    return index if index == limit else None


def _label(value):
    return ' '.join(_decode(value).split()).casefold()


def _definitions(masked):
    definitions = {}
    spans = []
    offset = 0
    for line in masked.splitlines(keepends=True):
        match = re.match(r'^ {0,3}\[((?:\\.|[^\[\]\\\n]){1,999})\]:[ \t]*', line)
        if match and len(match[1]) <= MAX_LABEL_CHARS:
            limit = len(line.rstrip('\r\n'))
            destination = _destination(line, match.end(), limit)
            if destination and _ending(line, destination[2], limit, inline=False) is not None:
                start, end, _ = destination
                key = _label(match[1])
                if key:
                    definitions.setdefault(key, (offset + start, offset + end))
                    spans.append((offset, offset + len(line)))
        offset += len(line)
    return definitions, spans


def reference_definition_spans(text):
    """Include unused valid definitions so consumers cannot mistake them for prose."""
    return tuple(_definitions(without_code(text))[1])


def _parsed(text):
    masked = without_code(text)
    definitions, spans = _definitions(masked)
    characters = list(masked)
    for start, end in spans:
        characters[start:end] = _mask(masked[start:end])
    masked = ''.join(characters)
    newlines = [match.start() for match in re.finditer('\n', text)]
    # Pair brackets once. Destinations and labels use finite depth/length bounds.
    pairs = {}
    stack = []
    overflow = 0
    index = 0
    while index < len(masked):
        char = masked[index]
        if char == '\\':
            index += 2
            continue
        if char == '[':
            if overflow:
                overflow += 1
            elif len(stack) == MAX_NESTING:
                overflow = len(stack) + 1
                stack.clear()
            else:
                stack.append(index)
        elif char == ']':
            if overflow:
                overflow -= 1
            elif stack:
                pairs[stack.pop()] = index
        index += 1
    links = []
    index = 0
    while index < len(masked):
        close = pairs.get(index)
        if close is None or close - index > MAX_LABEL_CHARS + 1:
            index += 1
            continue
        start = index - 1 if (index and masked[index - 1] == '!'
                              and not _escaped(masked, index - 1)) else index
        image = start < index
        following = close + 1
        destination = None
        end = None
        kind = 'image' if image else 'inline'
        if masked[following:following + 1] == '(':
            position = following + 1
            while position < len(masked) and masked[position].isspace():
                position += 1
            destination = _destination(masked, position, len(masked))
            if destination:
                end = _ending(masked, destination[2],
                              min(len(masked), destination[2] + MAX_DESTINATION_CHARS), inline=True)
        else:
            key = _label(masked[index + 1:close])
            if following in pairs:
                ref_close = pairs[following]
                if ref_close - following > MAX_LABEL_CHARS + 1:
                    index = ref_close + 1
                    continue
                explicit = masked[following + 1:ref_close]
                key = _label(explicit) if explicit else key
                end = ref_close + 1
            else:
                end = following
            bounds = definitions.get(key)
            if bounds:
                destination = (*bounds, bounds[1])
                kind = 'reference'
            else:
                end = None
        if destination and end is not None:
            destination_start, destination_end, _ = destination
            links.append(Link(start, end, destination_start, destination_end,
                              _decode(text[destination_start:destination_end]),
                              bisect_right(newlines, start) + 1, kind, index + 1, close))
            index = end
        else:
            index = close + 1
    return links, spans


def references(text):
    """Yield bounded inline, image, full/collapsed/shortcut reference links.

    This deliberately recognizes a documented Markdown subset, not HTML links
    or an entire renderer. Unknown or malformed forms remain literal source.
    """
    yield from _parsed(text)[0]


def simple_inline_references(text):
    """Frozen legacy queue-repair grammar: broader Markdown grants no repair rights."""
    masked = without_code(text, legacy=True)
    newlines = [match.start() for match in re.finditer('\n', text)]
    for match in re.finditer(r'(?<![!\\])\[[^\[\]\\\n]+\]\(([^()\s<>\\|]+)\)', masked):
        yield Link(match.start(), match.end(), match.start(1), match.end(1), match[1],
                   bisect_right(newlines, match.start()) + 1, 'inline',
                   match.start() + 1, match.start(1) - 2)


def evidence_prose(text):
    """Exclude Markdown links/definitions/examples, retaining legacy code paths."""
    links, definitions = _parsed(text)
    masked = without_examples(text)
    parts = []
    position = 0
    for start, end in sorted([(link.start, link.end) for link in links] + definitions):
        if start < position:
            continue
        parts.extend((masked[position:start], _mask(masked[start:end])))
        position = end
    return ''.join((*parts, masked[position:]))


def inline_destinations(text):
    """Compatibility view for callers needing only inline/image destinations."""
    for link in references(text):
        if link.kind != 'reference':
            yield link.line, link.destination


def local_destination(destination):
    """Separate URL parts before decoding; retain literal punctuation in filenames."""
    if re.match(r'^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)', destination):
        return None
    path_query, separator, fragment = destination.partition('#')
    path = path_query.partition('?')[0]
    return LocalDestination(unquote(path), unquote(fragment) if separator else None)


def _heading_text(text):
    """Project shared link labels and visible code text before making heading IDs."""
    links, definitions = _parsed(text)
    examples = without_examples(text)
    parts = []
    position = 0
    for start, end in definitions:
        parts.extend((examples[position:start], _mask(examples[start:end])))
        position = end
    examples = ''.join((*parts, examples[position:]))
    parts = []
    position = 0
    for link in links:
        parts.extend((examples[position:link.start], examples[link.label_start:link.label_end]))
        position = link.end
    projected = ''.join((*parts, examples[position:]))
    # Match tags only outside code spans, so `<foo>` retains its visible text.
    parts = []
    position = 0
    for match in re.finditer(r'<[^>]*>', without_code(projected)):
        parts.extend((projected[position:match.start()], '\n' * match[0].count('\n')))
        position = match.end()
    return ''.join((*parts, projected[position:]))


def heading_anchors(text):
    """GitHub-like Unicode heading slugs, duplicate suffixes and explicit a anchors."""
    anchors = set()
    for tag in re.finditer(r'<a\s+[^>]*>', without_code(text), re.IGNORECASE):
        for attribute in re.finditer(
                r'''\s+([\w:.-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|[^\s>]+))?''', tag[0]):
            if attribute[1].lower() in ('id', 'name'):
                value = attribute[2] if attribute[2] is not None else attribute[3]
                if value is not None:
                    anchors.add(unescape(value))
    # Inline code contributes its text to heading slugs, unlike examples.
    counts = {}
    heading_slugs = set()
    previous = None
    for line in _heading_text(text).splitlines():
        heading = re.match(r'^ {0,3}#{1,6}(?:[ \t]+(.*?)|[ \t]*)$', line)
        if heading:
            value = re.sub(r'[ \t]+#+[ \t]*$', '', heading[1] or '')
        elif previous and re.match(r'^ {0,3}(?:=+|-+)[ \t]*$', line):
            value = previous.strip()
        else:
            previous = line if line.strip() else None
            continue
        masked = without_code(value)
        value = re.sub(r'(?<!\\)(\*{1,3}|_{1,3}|~~)(?=\S)(.+?)(?<=\S)\1',
                       lambda match: match[2] if (
                           masked[match.start():match.start() + len(match[1])] == match[1]
                           and masked[match.end() - len(match[1]):match.end()] == match[1])
                       else match[0], value)
        value = _decode(value).lower()
        value = ''.join(char for char in value if char in '-_' or char.isspace()
                        or unicodedata.category(char)[0] not in 'PS')
        slug = re.sub(r'\s', '-', value.strip())
        suffix = counts.get(slug, 0)
        candidate = f'{slug}-{suffix}' if suffix else slug
        while candidate in heading_slugs:
            suffix += 1
            candidate = f'{slug}-{suffix}'
        counts[slug] = suffix + 1
        heading_slugs.add(candidate)
        anchors.add(candidate)
        previous = None
    return anchors


def protected_artifact_exists(target):
    """Use only the approved metadata reader, only within this checkout's evidence."""
    original = Path(os.path.join(os.getcwd(), target))
    target = Path(os.path.abspath(original))
    if not target.is_relative_to(ROOT / 'output/test-runs'):
        return False
    try:
        if '..' in original.parts:
            last_parent = max(i for i, part in enumerate(original.parts) if part == '..')
            prefix = Path(*original.parts[:last_parent + 1])
            # Collapsing parent steps must not change the filesystem target
            # when an earlier component is a symlink.
            if prefix.resolve(strict=True) != Path(os.path.abspath(prefix)):
                return False
        result = subprocess.run(
            ['/usr/bin/pkexec', '--keep-cwd', '/usr/local/libexec/onpc-test-artifacts',
             'stat', str(target)], cwd=ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, check=False, timeout=15)
        metadata = json.loads(result.stdout) if result.returncode == 0 else None
        return isinstance(metadata, dict) and metadata.get('kind') in ('file', 'directory')
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError):
        return False


def link_condition(path, text, link, *, anchors=None):
    """Inspect one explicit local link; semantic evidence stays with its owner.

    The policy caller supplies roles independently. A denied read is never
    reported as expiry, and this operation neither fetches nor executes text.
    """
    from evidence_policy import Condition
    target = local_destination(link.destination)
    if target is None or (not target.path and target.fragment is None):
        return None
    target_path = path.parent / target.path if target.path else path
    anchors = {} if anchors is None else anchors
    try:
        target_path.stat()
        if target.fragment and target_path.suffix.lower() in ('.md', '.markdown'):
            if target_path not in anchors:
                anchors[target_path] = heading_anchors(text if target_path == path else read_text(target_path))
            if target.fragment not in anchors[target_path]:
                return Condition.FRAGMENT
    except (FileNotFoundError, NotADirectoryError):
        return Condition.MISSING
    except PermissionError:
        if not protected_artifact_exists(target_path):
            return Condition.DENIED
    except (OSError, ValueError, UnicodeError):
        return Condition.INTEGRITY
    return None


def check_links(paths):
    checked = missing = inaccessible = 0
    anchors = {}
    for document, path in enumerate(paths, 1):
        text = read_text(path)
        for link in references(text):
            target = local_destination(link.destination)
            if target is None or (not target.path and target.fragment is None):
                continue
            checked += 1
            target_path = path.parent / target.path if target.path else path
            failure = None
            try:
                target_path.stat()
            except (FileNotFoundError, NotADirectoryError):
                failure = 'missing local target'
            except PermissionError:
                if not protected_artifact_exists(target_path):
                    inaccessible += 1
                    print(f'links: document={document} line={link.line} inaccessible local target')
                continue
            if failure is None and target.fragment and target_path.suffix.lower() in ('.md', '.markdown'):
                if target_path not in anchors:
                    anchors[target_path] = heading_anchors(text if target_path == path else read_text(target_path))
                if target.fragment not in anchors[target_path]:
                    failure = 'missing local fragment'
            if failure:
                missing += 1
                # Do not echo source prose, URLs, filenames or account data.
                print(f'links: document={document} line={link.line} {failure}')
    suffix = f' inaccessible={inaccessible}' if inaccessible else ''
    print(f'links: documents={len(paths)} checked={checked} missing={missing}{suffix}')
    if inaccessible:
        return 2
    return 1 if missing else 0


def count_words(path, *, after=None, before=None):
    text = read_text(path)
    for name, marker in (('after', after), ('before', before)):
        if marker is None:
            continue
        if not marker or text.count(marker) != 1:
            raise ValueError(f'{name} marker must occur exactly once in the selected text')
        head, _, tail = text.partition(marker)
        text = tail if name == 'after' else head
    return len(text.split())


def main(argv=None):
    try:
        if os.geteuid() == 0:
            raise ValueError('run document checks without privilege')
        parser = Parser(description=__doc__, allow_abbrev=False)
        actions = parser.add_subparsers(dest='action', required=True)
        links = actions.add_parser('links', allow_abbrev=False)
        links.add_argument('paths', type=Path, nargs='+')
        words = actions.add_parser('words', allow_abbrev=False)
        words.add_argument('--after')
        words.add_argument('--before')
        words.add_argument('path', type=Path)
        args = parser.parse_args(argv)
        if args.action == 'links':
            return check_links(args.paths)
        count = count_words(args.path, after=args.after, before=args.before)
        print(f'words: {count}')
        return 0
    except OSError as error:
        print(f'document-check: document read or metadata check failed (errno={error.errno})', file=sys.stderr)
    except UnicodeError:
        print('document-check: document is not UTF-8', file=sys.stderr)
    except ValueError as error:
        # Our diagnostics are fixed text. URL parser diagnostics can contain
        # input values, so keep all unexpected ValueError messages private.
        message = str(error)
        if message in (
            'after marker must occur exactly once in the selected text',
            'before marker must occur exactly once in the selected text',
            'expected a regular UTF-8 document of at most 8 MiB',
            'document exceeded 8 MiB while reading',
        ):
            print(f'document-check: {message}', file=sys.stderr)
        else:
            print('document-check: invalid document check; use tools/read-only --help', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
