#!/usr/bin/python3 -IB
"""Install host rules and validate the tracked portable Codex files."""
import json
import os
import re
from pathlib import Path
import sys
import stat
import tempfile
import tomllib


SYSTEM_RULES = Path('/etc/codex/rules/onpc-read-only.rules')
REQUIRED_TOOLS = ('run-unit-tests', 'run-ui-tests', 'run-tests', 'diagnose', 'test-vm',
                  'cleanup-screenshots', 'read-only')
TOOL_PLACEHOLDER = '"@PROJECT_TOOL_PATHS@"'


def install_system_rules(root, destination=SYSTEM_RULES):
    """Manage only our rule file; preserve all other system and user policies."""
    data = (root / 'config/codex-read-only.rules').read_bytes()
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError('symlink in system rules path')
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    for path in destination.parents:
        info = path.stat()
        # Repair only the two root-owned Codex directories managed by setup.
        # Ancestors such as /etc must already be trusted; never relax checks.
        if (path in (destination.parent, destination.parent.parent)
                and info.st_uid == info.st_gid == 0 and info.st_mode & 0o022):
            path.chmod(stat.S_IMODE(info.st_mode) & ~0o022)
            info = path.stat()
            print('codex-rules-install: secured managed Codex directory permissions')
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('unsafe system rules directory')
    if destination.exists():
        info = destination.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('unsafe system rules file')
        if (destination.read_bytes() == data and info.st_uid == 0 and info.st_gid == 0
                and stat.S_IMODE(info.st_mode) == 0o644):
            print('codex-rules-install: machine-wide read rules already current')
            return
    descriptor, temporary = tempfile.mkstemp(prefix='.onpc-rules-', dir=destination.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fchown(stream.fileno(), 0, 0)
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print('codex-rules-install: installed machine-wide read rules')


def project_tool_paths(root):
    """Enumerate executable tools as literal argv tokens, without following links."""
    directory = root / 'tools'
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('unsafe project tools directory')
    paths = []
    for path in sorted(directory.rglob('*')):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('symlink in project tools path')
        if stat.S_ISREG(info.st_mode) and info.st_mode & 0o111:
            relative = path.relative_to(root).as_posix()
            paths.extend((relative, './' + relative))
    if not paths:
        raise ValueError('no executable project tools')
    return paths


def render(root):
    for name in REQUIRED_TOOLS:
        path = root / 'tools' / name
        if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
            raise ValueError('missing or nonexecutable launcher; restore checkout executable modes')
    source = (root / 'config/codex-tests.rules').read_text()
    placeholder = TOOL_PLACEHOLDER
    if source.count(placeholder) != 1:
        raise ValueError('project tool paths placeholder must occur exactly once')
    # JSON quoting produces literal Starlark tokens even for spaces and quotes.
    paths = '[\n        ' + ',\n        '.join(
        json.dumps(path) for path in project_tool_paths(root)) + '\n    ]'
    return source.replace(placeholder, paths)


def missing_optional_grants(root, saved):
    """Accept only an unchanged policy with an older, canonical tool subset."""
    template = (root / 'config/codex-tests.rules').read_text()
    before, _, after = template.partition(TOOL_PLACEHOLDER)
    if not saved.startswith(before) or not saved.endswith(after):
        return None
    inventory = saved[len(before):len(saved) - len(after)] if after else saved[len(before):]
    try:
        paths = json.loads(inventory)
    except ValueError:
        return None
    if (not isinstance(paths, list) or not paths
            or any(not isinstance(path, str) for path in paths)):
        return None
    current = project_tool_paths(root)
    retained = set(paths)
    required = {prefix + name for name in REQUIRED_TOOLS for prefix in ('tools/', './tools/')}
    # Reject removed tools, missing required grants, unpaired aliases, duplicates,
    # reordering and all other policy drift. This never creates or loads a grant.
    if (not required <= retained or not retained < set(current)
            or paths != [path for path in current if path.removeprefix('./') in retained]):
        return None
    canonical = '[\n        ' + ',\n        '.join(json.dumps(path) for path in paths) + '\n    ]'
    if inventory != canonical:
        return None
    return [path for path in current if path not in retained]


def main():
    root = Path(__file__).resolve().parents[1]
    if sys.argv[1:] == ['--system'] and os.geteuid() == 0:
        install_system_rules(root)
        return
    if sys.argv[1:] not in ([], ['--headless'], ['--check'], ['--write-rules']):
        raise ValueError('use setup.sh, --check or --write-rules')
    if sys.argv[1:] == ['--write-rules']:
        write_checkout_file(root / '.codex/rules/tests.rules', render(root))
        return
    prepare_checkout(root, headless='--headless' in sys.argv,
                     check=sys.argv[1:] == ['--check'])


def prepare_checkout(root, *, headless=False, check=False):
    """Prepare only Codex-owned files; preserve personal settings and trust."""
    source = render(root)
    destination = root / '.codex/rules/tests.rules'
    saved = destination.read_text()
    if saved != source:
        missing = None if check else missing_optional_grants(root, saved)
        if missing is None:
            raise ValueError('tracked rules are stale; regenerate with python3 -IB tools/install_codex_rules.py --write-rules and commit them')
        print('codex-rules-install: warning: new tools lack saved command grants: '
              + ', '.join(missing))
        print('codex-rules-install: existing grants remain unchanged; regenerate with '
              'python3 -IB tools/install_codex_rules.py --write-rules and restart Codex '
              'before using the new tools unattended')
    tomllib.loads((root / '.codex/config.toml').read_text())
    if check:
        print('codex-rules-install: tracked settings and tool inventory valid')
        return
    codex_home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    marketplace = codex_home / '.tmp/bundled-marketplaces/openai-bundled'
    if not headless and marketplace.is_dir():
        desktop = (root / 'config/codex-desktop.toml').read_text().replace(
            '"@MARKETPLACE@"', json.dumps(str(marketplace)))
        install_desktop_defaults(codex_home / 'config.toml', desktop)
    else:
        print('codex-rules-install: desktop integrations omitted; run setup again after desktop app initialization if needed')
    print('codex-rules-install: tracked project settings ready; trust this checkout in Codex and restart')


def install_desktop_defaults(destination, desktop):
    """Add absent desktop tables to user config, preserving personal settings."""
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError('symlink in user configuration path')
    existing = destination.read_text() if destination.exists() else ''
    parsed = tomllib.loads(existing)
    additions = []
    for block in re.split(r'\n(?=\[)', desktop):
        table = tomllib.loads(block)
        current = parsed
        # Each template block is one table; inspect its complete dotted path.
        while len(table) == 1:
            key, value = next(iter(table.items()))
            if not isinstance(value, dict):
                break
            if key not in current:
                additions.append(block)
                break
            current = current[key]
            if not isinstance(current, dict):
                raise ValueError('conflicting desktop configuration table')
            table = value
    if additions:
        configuration = existing.rstrip() + '\n\n' + '\n\n'.join(additions) + '\n'
        tomllib.loads(configuration)
        write_checkout_file(destination, configuration, mode=0o600)


def write_checkout_file(destination, source, mode=0o644):
    """Replace only managed checkout files, refusing redirected destinations."""
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError('symlink in checkout configuration path')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        info = destination.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('unsafe checkout configuration file')
        if destination.read_text() == source:
            return
    descriptor, temporary = tempfile.mkstemp(prefix='.onpc-codex-', dir=destination.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(source)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        sys.exit(f'codex-rules-install: {error}')
    except OSError as error:
        sys.exit(f'codex-rules-install: filesystem operation failed (errno={error.errno})')
