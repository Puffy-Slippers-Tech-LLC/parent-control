"""Category dispatch, with no caller-selected commands, makefiles or interpreters."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import test_launcher as host


CATEGORIES = {
    'unit': 'unit, property, contract and harness regressions; quoted test_*.py patterns',
    'component': 'private-D-Bus pytest; quoted test_*.py patterns',
    'ui': 'isolated GTK and nested-Shell pytest through run-ui-tests',
    'child-node': 'tests/child/**/*.test.mjs or *.test.js',
    'child-gjs': 'tests/child/**/*_test.js',
    'static': 'shell, gjs, or all (default)',
    'backend': 'read-only graphical backend package/API prerequisite check',
    'source': 'established syntax, traceability and source guards',
    'publish': 'local source packaging, clean sbuild and Lintian; no publication',
    'fixture-runtime': 'all established fixture runtime pytest cases',
    'traceability': 'stage (default) or final requirement checks',
    'coverage': 'unit and private-D-Bus Python coverage in a new private directory',
    'check': 'the current make check aggregate',
    'component-all': 'the current make check-component aggregate',
    'fixtures': 'build, verify PATH; generated build output',
    'artifacts': 'build, verify PATH, compare FIRST SECOND; generated build output',
    'integration': 'installed dispatcher for check_* basenames; no script arguments',
    'system': 'guarded installed runner; --artifacts, --previous-artifacts, --area, --test, --list',
    'e2e': 'host-safe graphical inventory --list; invalid/pending execution refused before privilege',
    'fast': 'reserved for the Task 28 make test-fast target',
    'all': 'all established regression suites; live report and no narrowing selectors',
}


def artifact_path(value):
    path = Path(value)
    roots = (Path('/tmp'), Path('/var/tmp'))
    if (not path.is_absolute() or '..' in path.parts or
            not any(path.is_relative_to(root) and len(path.parts) > len(root.parts) and
                    re.fullmatch(r'onpc-[A-Za-z0-9_.-]+', path.parts[len(root.parts)])
                    for root in roots)):
        raise ValueError('expected an absolute project test-artifact directory')
    if not path.is_dir() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('artifact directory is missing or contains a symlink')
    return str(path)


def python_file(root, path, *options):
    return ['/usr/bin/python3', '-B', host.confined_file(root, path), *options]


def make_command(root, target, assignments=()):
    makefile = host.confined_file(root, 'Makefile')
    if not re.search(r'^' + re.escape(target) + r'\s*:', Path(makefile).read_text(), re.M):
        raise ValueError('this roadmap runner is not implemented yet')
    return ['/usr/bin/make', '--no-print-directory', '--directory=' + str(root),
            '--file=' + makefile, '--', target, *assignments]


def plan(root, category, argv):
    """Validate everything before prerequisites, output creation or execution."""
    if category == 'publish':
        if argv:
            raise ValueError('publishing tests accept no arguments')
        return [python_file(root, 'tools/publishing_checks.py')], False
    if category == 'source':
        if argv:
            raise ValueError('source checks accept no arguments')
        return [make_command(root, 'check-source')], False
    if category == 'fixture-runtime':
        _, options = host.arguments(argv, 'fixtures')
        if any(not value.startswith('-') for value in argv):
            raise ValueError('fixture runtime accepts options only')
        paths = sorted((root / 'tests/fixtures').rglob('test_*.py'))
        if not paths:
            raise ValueError('fixture runtime suite is empty')
        targets = [host.confined_file(root, path.relative_to(root)) for path in paths]
        return [['/usr/bin/python3', '-B', '-m', 'pytest', *options, '--', *targets]], '--collect-only' not in options
    if category == 'backend':
        if argv:
            raise ValueError('backend readiness accepts no arguments')
        return [python_file(root, 'tests/integration/graphical_backend.py')], False
    if category in ('integration', 'system', 'e2e'):
        # Validation is shared with the installed root-owned dispatcher, which
        # repeats it after pkexec. Loading this checkout copy confers no privilege.
        import runpy
        dispatcher = runpy.run_path(host.confined_file(root, 'tools/onpc-test-runner'))
        command = dispatcher['selection'](root, [category, *argv])
        if '--list' in argv and category != 'integration':
            return [command], False
        return [['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner', category, *argv]], False
    if category in ('child-node', 'child-gjs'):
        defaults = [path.relative_to(root).as_posix() for path in sorted((root / 'tests/child').rglob('*'))
                    if (path.name.endswith(('.test.mjs', '.test.js')) if category == 'child-node'
                        else path.name.endswith('_test.js'))]
        if not argv and not defaults:
            raise ValueError('no child tests matched this category')
        paths = host.selection(root, argv or defaults, 'child')
        files = []
        for item in paths:
            if '::' in item or (root / item).is_dir():
                raise ValueError('child runners require test files or quoted filename patterns')
            valid = (item.endswith(('.test.mjs', '.test.js')) if category == 'child-node'
                     else item.endswith('_test.js'))
            if not valid:
                raise ValueError('child test filename belongs to a different runner')
            files.append(str(root / item))
        if category == 'child-node':
            return [['/usr/bin/node', '--test', *files]], False
        return [['/usr/bin/gjs', '-m', path] for path in files], False
    if category in ('static', 'traceability'):
        choice = argv[0] if argv else ('all' if category == 'static' else 'stage')
        if len(argv) > 1 or choice not in (('shell', 'gjs', 'all') if category == 'static'
                                         else ('stage', 'final')):
            raise ValueError('invalid check selection')
        if category == 'traceability':
            return [python_file(root, 'tools/verify_test_traceability.py', '--mode', choice)], False
        names = ('shell', 'gjs') if choice == 'all' else (choice,)
        return [python_file(root, f'tools/check_{name}.py') for name in names], False
    if category in ('check', 'component-all', 'fast', 'all'):
        assignments = []
        if category == 'fast':
            parser = host.ArgumentParser(allow_abbrev=False)
            parser.add_argument('--component')
            parser.add_argument('--type')
            parser.add_argument('--list', action='store_true')
            args = parser.parse_args(argv)
            for key in ('component', 'type'):
                value = getattr(args, key)
                if value is not None:
                    # make variable values are executable syntax even without a shell.
                    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', value):
                        raise ValueError('invalid aggregate selector')
                    assignments.append(f'{key.upper()}={value}')
            if args.list:
                assignments.append('LIST=1')
        elif argv:
            raise ValueError('this aggregate accepts no arguments')
        target = {'check': 'check', 'component-all': 'check-component',
                  'fast': 'test-fast', 'all': 'test-all'}[category]
        return [make_command(root, target, assignments)], 'LIST=1' not in assignments
    if category == 'coverage':
        if argv:
            raise ValueError('coverage accepts no arguments; reports use a new private directory')
        targets = host.selection(root, ['tests/unit']) + host.selection(root, ['tests/component'], 'component')
        # Output creation happens only after successful validation in main().
        return [['/usr/bin/python3', '-B', '-m', 'pytest', '--cov=broker', '--cov=parent',
                 '--cov=kiosk', '--cov=common', '--cov=tools', '--cov-branch',
                 '--cov-report=term-missing', '--', *targets]], True
    if category in ('fixtures', 'artifacts'):
        action = argv[0] if argv else 'build'
        path = ('tests/fixtures/build_test_applications.py' if category == 'fixtures'
                else 'tools/build_test_artifacts.py')
        command = python_file(root, path)
        if action == 'build' and len(argv) <= 1:
            return [command], False
        if action == 'verify' and len(argv) == 2:
            return [[*command, '--verify', '--output', artifact_path(argv[1])]], False
        if category == 'artifacts' and action == 'compare' and len(argv) == 3:
            return [[*command, '--compare', *map(artifact_path, argv[1:])]], False
        raise ValueError('invalid artifact operation')
    raise ValueError('unknown test category; use --list')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv in (['--help'], ['-h'], ['--list']):
        print(json.dumps(CATEGORIES, indent=2))
        return 0
    try:
        if os.geteuid() == 0:
            raise ValueError('use this launcher as an unprivileged user')
        root = Path(__file__).resolve().parents[1]
        category, args = argv[0], argv[1:]
        if category == 'all':
            if args:
                raise ValueError('all accepts no arguments')
            from regression import main as regression_main
            return regression_main(root)
        if args[:1] == ['--unattended']:
            from regression_process import host_run, category_run
            if category in ('unit', 'component', 'ui'):
                return host_run(root, category, args[1:])
            if category not in ('child-node', 'child-gjs', 'static', 'backend',
                                'traceability', 'fixtures', 'fixture-runtime', 'source',
                                'artifacts', 'system', 'e2e', 'publish'):
                raise ValueError('unsupported unattended category')
            return category_run(root, category, args[1:])
        if category in ('unit', 'component'):
            host.run_host(root, category, args)
            return 0
        if category == 'ui':
            # Preserve the one documented UI environment and timeout entry point.
            host.pytest_command(root, args, 'ui')
            command = [host.confined_file(root, 'tools/run-ui-tests'), *args]
            os.execve(command[0], command, host.environment(root))
            return 0
        commands, safety = plan(root, category, args)
        if safety:
            host.prerequisites(root)
        env = host.environment(root)
        if category in ('fixtures', 'artifacts') and (not args or args == ['build']):
            directory = tempfile.mkdtemp(prefix=f'onpc-test-{category}-', dir='/tmp')
            commands[0] += ['--output', directory]
            print('run-tests: output=' + directory, flush=True)
        if category == 'coverage':
            directory = tempfile.mkdtemp(prefix='onpc-coverage-', dir='/tmp')
            command = commands[0]
            command.insert(command.index('--'), '--cov-report=xml:' + directory + '/coverage.xml')
            env['COVERAGE_FILE'] = directory + '/.coverage'
            print('run-tests: output=' + directory, flush=True)
        if category == 'child-gjs':
            directory = tempfile.mkdtemp(prefix='onpc-gjs-coverage-', dir='/tmp')
            for command in commands:
                command[1:1] = ['--coverage-prefix=' + str(root / 'child'),
                                '--coverage-output=' + directory]
            print('run-tests: output=' + directory, flush=True)
        os.chdir(root)
        for command in commands[:-1]:
            status = subprocess.run(command, env=env, check=False).returncode
            if status:
                return status if status > 0 else 128 - status
        if commands[-1][0] == '/usr/bin/pkexec':
            from dev_privileges import check
            check(commands[-1][1])
        print('run-tests: validated category starting', file=sys.stderr, flush=True)
        os.execve(commands[-1][0], commands[-1], env)
    except (ValueError, OSError) as error:
        detail = str(error) if isinstance(error, ValueError) else 'filesystem or execution failure'
        print('run-tests: ' + detail, file=sys.stderr)
        return 2
