"""Read-only document checks with guarded metadata access for test evidence."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from urllib.parse import unquote, urlsplit


MAX_BYTES = 8 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]


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


def without_code(text):
    """Mask fenced blocks and inline code spans while preserving line offsets."""
    def mask(value):
        return re.sub(r'[^\n]', ' ', value)

    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = re.match(r'^ {0,3}(`{3,}|~{3,})([^\n]*)', line)
        if fence:
            lines.append(mask(line))
            if (match and match[1][0] == fence[0] and len(match[1]) >= len(fence)
                    and not match[2].strip()):
                fence = None
        elif match:
            fence = match[1]
            lines.append(mask(line))
        else:
            lines.append(line)
    text = ''.join(lines)
    runs = list(re.finditer(r'`+', text))
    parts = []
    position = 0
    index = 0
    while index < len(runs):
        opening = runs[index]
        closing = next((other for other in range(index + 1, len(runs))
                        if runs[other][0] == opening[0]), None)
        if closing is None:
            index += 1
            continue
        end = runs[closing].end()
        parts.extend([text[position:opening.start()], mask(text[opening.start():end])])
        position = end
        index = closing + 1
    return ''.join([*parts, text[position:]])


def inline_destinations(text):
    """Yield inline link/image destinations, including balanced or escaped parentheses.

    This is a file-existence check for inline links, not a full Markdown renderer:
    reference-style links, HTML links and fragment identifiers are outside its scope.
    """
    text = without_code(text)
    for match in re.finditer(r'(?<!\\)\]\(\s*', text):
        start = match.end()
        index = start
        destination = []
        angle = text[index:index + 1] == '<'
        if angle:
            index += 1
        depth = 0
        while index < len(text):
            char = text[index]
            if char == '\\' and index + 1 < len(text):
                destination.append(text[index + 1])
                index += 2
                continue
            if angle:
                if char == '>' or char == '\n':
                    break
            else:
                if char.isspace() or (char == ')' and not depth):
                    break
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
            destination.append(char)
            index += 1
        if angle:
            if text[index:index + 1] != '>':
                continue
            index += 1
        if depth or not destination:
            continue
        # Optional Markdown titles are data; none is interpreted as a command.
        if not re.match(r'''(?:\s+(?:"[^"\n]*"|'[^'\n]*'|\([^\n)]*\)))?\s*\)''', text[index:]):
            continue
        yield text.count('\n', 0, match.start()) + 1, ''.join(destination)


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


def check_links(paths):
    checked = missing = inaccessible = 0
    for document, path in enumerate(paths, 1):
        for line, destination in inline_destinations(read_text(path)):
            if re.match(r'^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#)', destination):
                continue
            target = urlsplit(destination)
            if target.scheme or target.netloc or not target.path:
                continue
            checked += 1
            try:
                (path.parent / unquote(target.path)).stat()
            except (FileNotFoundError, NotADirectoryError):
                missing += 1
                # Do not echo source prose, URLs, filenames or account data.
                print(f'links: document={document} line={line} missing local target')
            except PermissionError:
                if not protected_artifact_exists(path.parent / unquote(target.path)):
                    inaccessible += 1
                    print(f'links: document={document} line={line} inaccessible local target')
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
