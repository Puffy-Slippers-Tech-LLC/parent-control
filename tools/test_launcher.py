#!/usr/bin/python3 -B
"""Validated command construction shared by the checkout test launchers."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error includes caller-supplied paths and values.
        raise ValueError('invalid arguments; use --help for supported options')


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise ValueError('expected a nonnegative integer')
    return number


def arguments(argv, category='unit'):
    prog = f'tools/run-{category}-tests' if category in ('unit', 'ui') else f'tools/run-tests {category}'
    help_text = ('Quote patterns and parametrized node IDs. Scoped exclusions: '
                 f'--ignore=tests/{category}/PATH_OR_PATTERN.')
    if category == 'ui':
        help_text += ' Put --timeout DURATION before selections/options (default 60s; s/m/h/d suffixes).'
    parser = ArgumentParser(
        prog=prog, description=__doc__, allow_abbrev=False, epilog=help_text)
    parser.add_argument('selectors', nargs='*', metavar='TEST_PATH',
                        help='checkout-relative path or quoted glob, optionally with ::test_id')
    parser.add_argument('-q', '--quiet', action='count', default=0)
    parser.add_argument('-v', '--verbose', action='count', default=0)
    parser.add_argument('-x', '--exitfirst', action='store_true')
    parser.add_argument('-s', action='store_true', help='disable output capture')
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--disable-warnings', action='store_true')
    parser.add_argument('-k', metavar='EXPRESSION')
    parser.add_argument('-m', metavar='EXPRESSION')
    parser.add_argument('--maxfail', type=nonnegative)
    parser.add_argument('--durations', type=nonnegative)
    parser.add_argument('--tb', choices=('auto', 'long', 'short', 'line', 'native', 'no'))
    args = parser.parse_intermixed_args(argv)
    options = ['-q'] * args.quiet + ['-v'] * args.verbose
    for enabled, flag in ((args.exitfirst, '-x'), (args.s, '-s'),
                          (args.collect_only, '--collect-only'),
                          (args.disable_warnings, '--disable-warnings')):
        if enabled:
            options.append(flag)
    for name in ('k', 'm', 'maxfail', 'durations', 'tb'):
        value = getattr(args, name)
        if value is not None:
            flag = '-' + name if len(name) == 1 else '--' + name
            options.append(f'{flag}={value}')
    return args.selectors or [f'tests/{category}'], options


def validate_path(root, path, category='unit'):
    unit = root / 'tests' / category
    if not path.resolve().is_relative_to(unit):
        raise ValueError('selection escapes its test category')
    # Check every component, including the tests/unit directory itself.
    for component in (path, *path.parents):
        if component == root:
            break
        if component.is_symlink():
            raise ValueError('symlink selections are not supported')
    patterns = ('*.test.mjs', '*.test.js', '*_test.js') if category == 'child' else ('test_*.py',)
    if not path.is_dir() and not (path.is_file() and any(path.match(p) for p in patterns)):
        raise ValueError('expected a test directory or a category test filename')


def selection(root, selectors, category='unit'):
    root = root.resolve()
    if category not in ('unit', 'component', 'ui', 'child'):
        raise ValueError('unsupported host test category')
    validate_path(root, root / 'tests' / category, category)
    selected = {}
    for selector in selectors:
        if not selector or any(ord(char) < 32 for char in selector):
            raise ValueError('empty selector or control character')
        filename, separator, node = selector.partition('::')
        relative = Path(filename)
        if (relative.is_absolute() or relative.parts[:2] != ('tests', category)
                or '..' in relative.parts or (separator and not node)):
            raise ValueError('expected a checkout-relative selection inside its test category')
        for parent in (root / relative, *(root / relative).parents):
            if parent == root:
                break
            if parent.is_symlink():
                raise ValueError('symlink selections are not supported')
        # Expand only the filename; brackets in parametrized node IDs are literal.
        matches = sorted(root.glob(str(relative)))
        if not matches:
            raise ValueError('a selection matched no test paths')
        for path in matches:
            validate_path(root, path, category)
            if path.is_dir():
                if separator:
                    raise ValueError('test IDs require a test file')
                # pytest can follow links during directory collection. Inspect
                # the subtree without following links before handing it over.
                for child in path.rglob('*'):
                    if child.is_symlink():
                        raise ValueError('selected directory contains a symlink')
            target = path.relative_to(root).as_posix() + separator + node
            selected[target] = None
    return list(selected)


def environment(root):
    # Do not inherit interpreter/plugin, loader, compiler, or make injection.
    allowed = ('HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'TERM', 'COLORTERM',
               'DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
               'XDG_RUNTIME_DIR', 'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP',
               'PYTEST_DISABLE_PLUGIN_AUTOLOAD')
    result = {key: os.environ[key] for key in allowed if key in os.environ}
    result.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', PYTHONDONTWRITEBYTECODE='1',
                  PYTHONPATH=f'{root}/broker:{root}/kiosk:{root}')
    return result


def confined_file(root, relative):
    path = root / relative
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('test entry point is missing or external')
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError('symlink entry points are not supported')
    return str(path)


def prerequisites(root):
    targets = selection(root, ['tests/unit/test_*cleanup_safety.py',
                               'tests/unit/test_graphical_lease.py'])
    print('run-tests: isolated cleanup prerequisites starting', file=sys.stderr, flush=True)
    status = subprocess.run(['/usr/bin/python3', '-B', '-m', 'pytest',
                             '-p', 'no:cacheprovider', '-q', '--', *targets],
                            cwd=root, env=environment(root), check=False).returncode
    if status:
        raise ValueError('cleanup prerequisites failed; selected operation refused')


def duration(value):
    if not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]+)?)(?:[smhd])?', value):
        raise ValueError('invalid timeout duration')
    number = float(value.rstrip('smhd'))
    if not 0 < number < float('inf'):
        raise ValueError('timeout must be positive and finite')
    return value


def pytest_command(root, argv, category):
    timeout = '60s'
    if category == 'ui' and argv[:1] == ['--timeout']:
        if len(argv) < 2:
            raise ValueError('timeout value required')
        timeout = duration(argv[1])
        argv = argv[2:]
    ignores = [arg.removeprefix('--ignore=') for arg in argv if arg.startswith('--ignore=')]
    argv = [arg for arg in argv if not arg.startswith('--ignore=')]
    selectors, options = arguments(argv, category)
    targets = selection(root, selectors, category)
    for ignored in ignores:
        if '::' in ignored:
            raise ValueError('ignore expects file paths')
        options.extend('--ignore=' + path for path in selection(root, [ignored], category))
    python = '/usr/bin/python3'
    prefix = []
    if category == 'ui':
        python = str(root / '.venv/onpc-ui-tests/bin/python')
        # A venv Python is intentionally a symlink to the system interpreter.
        if not os.access(python, os.X_OK):
            raise ValueError('UI test environment missing; run ./setup.sh')
        prefix = ['/usr/bin/timeout', '--foreground', timeout]
    return [*prefix, python, '-B', '-m', 'pytest', *options, '--', *targets]


def run_host(root, category, argv):
    command = pytest_command(root, argv, category)
    if category != 'unit' and '--collect-only' not in command:
        prerequisites(root)
    os.chdir(root)
    count = len(command) - command.index('--') - 1
    print(f'run-{category}-tests: starting pytest with {count} validated selection(s)',
          file=sys.stderr, flush=True)
    os.execve(command[0], command, environment(root))


def main(argv=None, *, category='unit'):
    try:
        if os.geteuid() == 0:
            raise ValueError('run host tests as an unprivileged user')
        root = Path(__file__).resolve().parents[1]
        run_host(root, category, sys.argv[1:] if argv is None else argv)
    except (ValueError, OSError) as error:
        detail = str(error) if isinstance(error, ValueError) else 'filesystem or execution failure'
        print(f'run-tests: {detail}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
