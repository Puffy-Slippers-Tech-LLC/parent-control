"""Category dispatch, with no caller-selected commands, makefiles or interpreters."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import test_launcher as host
import test_activity


@dataclass(frozen=True)
class CategorySpec:
    description: str
    leaf: bool = True
    implemented: bool = True


# Register readiness and coverage ownership beside the public command. New
# implemented leaves automatically join both all and fix-tests; aliases,
# diagnostics and pending commands never become extra test coverage.
CATEGORIES = {
    'unit': CategorySpec('selected unit, property, contract and harness tests in up to four reviewed module buckets'),
    'component': CategorySpec('private-D-Bus pytest; quoted test_*.py patterns'),
    'ui': CategorySpec('selected GTK and nested-Shell tests in up to four qualified UI branches; no other host suites'),
    'child-node': CategorySpec('tests/child/**/*.test.mjs or *.test.js'),
    'child-gjs': CategorySpec('tests/child/**/*_test.js'),
    'static': CategorySpec('shell, gjs, or all (default)'),
    'backend': CategorySpec('read-only graphical backend package/API prerequisite check'),
    'source': CategorySpec('established syntax, traceability and source guards'),
    'publish': CategorySpec('local source packaging, clean sbuild and Lintian; no publication'),
    'fixture-runtime': CategorySpec('all established fixture runtime pytest cases'),
    'traceability': CategorySpec('stage (default) or final requirement checks', leaf=False),
    'coverage': CategorySpec('unit and private-D-Bus Python coverage in a new private directory', leaf=False),
    'check': CategorySpec('the current make check aggregate', leaf=False),
    'component-all': CategorySpec('the current make check-component aggregate', leaf=False),
    'fixtures': CategorySpec('build, verify PATH; generated build output', leaf=False),
    'artifacts': CategorySpec('two fresh package/fixture builds and reproducibility; build, prepare (verified reuse), verify PATH, compare FIRST SECOND'),
    'integration': CategorySpec('installed dispatcher for check_* basenames; no script arguments', leaf=False),
    'system': CategorySpec('sequential installed VM tests; bare category builds inputs; focused --artifacts, --previous-artifacts, --area, --test, --list'),
    'e2e': CategorySpec('all runnable E2E cases by default; --id N[,N...] selects exact coverage IDs; --list; optional --artifacts (otherwise built automatically)'),
    'fast': CategorySpec('reserved for the make test-fast target', leaf=False, implemented=False),
    'all': CategorySpec('complete established regression (default with no arguments); metadata-only VM backing verification; --continue-on-errors disables stop on first error', leaf=False),
    'all-verify': CategorySpec('compatibility alias for all; metadata-only VM verification; --continue-on-errors disables stop on first error', leaf=False),
    'host': CategorySpec('all host tests, publishing and two reproducibility builds in four branches; no VM; combines with system and e2e', leaf=False),
    'host-builds': CategorySpec('compatibility alias for host; optional --serial-builds for scheduling comparison', leaf=False),
}

AGGREGATES = ('all', 'all-verify', 'host', 'host-builds')
PHASES = ('host', 'system', 'e2e')
HELP_ARGV = (['--help'], ['-h'])
INSPECTION_FLAGS = ('--help', '-h', '--list', '--collect-only')


def suite_inventory(categories=(), *, inventory=None):
    """The exact, ordered granular partition consumed by all and fix-tests.

    Arguments are explicit. The shared UI launcher enforces its host-only
    marker boundary for aggregate, focused and direct execution.

    Composite selections expand to implemented leaves in inventory order. An
    already discovered inventory may be supplied by reconnectable consumers;
    its explicit argument arrays remain authoritative.
    """
    if inventory is None:
        from regression_ui import HOST_ARGS
        leaves = {kind: spec for kind, spec in CATEGORIES.items() if spec.leaf and spec.implemented}
        order = [*(kind for kind in ('unit', 'ui') if kind in leaves),
                 *(kind for kind in leaves if kind not in ('unit', 'ui', 'system', 'e2e')),
                 *(kind for kind in ('system', 'e2e') if kind in leaves)]
        inventory = {kind: {'description': leaves[kind].description,
                            'args': list(HOST_ARGS) if kind == 'ui' else []}
                     for kind in order}
    if not categories:
        return inventory
    selected = set()
    for argument in categories:
        for category in argument.split():
            if category == 'all':
                selected.update(inventory)
            elif category in ('host', 'host-builds'):
                selected.update(name for name in inventory if name not in ('system', 'e2e'))
            elif category in inventory:
                selected.add(category)
            else:
                raise ValueError(f'unknown or unsupported inventory category: {category}')
    if not selected:
        raise ValueError('no categories selected')
    return {name: spec for name, spec in inventory.items() if name in selected}


def execution_arguments(argv):
    """The leading coordinator option does not alter category arguments."""
    stop = argv[:1] == ['--stop-on-error']
    args = argv[1:] if stop else argv
    if stop and (not args or '--continue-on-errors' in args):
        raise ValueError('--stop-on-error requires categories and conflicts with --continue-on-errors')
    return args, stop


def usage():
    """Human-readable launcher help. ``--list`` remains the JSON inventory."""
    width = max(map(len, CATEGORIES))
    inventory = suite_inventory()
    listing = '\n'.join(f'  {name:<{width}}  {CATEGORIES[name].description}' for name in inventory)
    helpers = '\n'.join(f'  {name:<{width}}  {spec.description}'
                        for name, spec in CATEGORIES.items() if name not in inventory)
    return f'''Usage: tools/run-tests [--stop-on-error] [category [args ...]] ...
       tools/run-tests --help
       tools/run-tests --list

With no arguments, start the all aggregate unless a previous run is still
active or has an unread result; then this invocation attaches to that run.

Inspection
  --help, -h   this usage, including how all breaks down into pieces
  --list       ordered JSON granular inventory: descriptions and explicit args
               Iterating these selections covers exactly all, without aliases.
  --stop-on-error  leading option: cancel selected work at the first reported
                   failure, preserving parallel scheduling and owned cleanup

Complete categories (combine in any order; execute host, then system, then e2e)
  host         all host/dev-machine work in four balanced branches, including
               publishing, two package builds and reproducibility; no VM
  system       installed-system VM tests, sequential
  e2e          ready GUI-driven VM scenarios, sequential

  all = host + system + e2e

  tools/run-tests host
  tools/run-tests system e2e
  tools/run-tests e2e
  tools/run-tests host system
  tools/run-tests host system e2e    (same as all)

  Combined categories share one report and reuse host's package artifacts.
  Without host, VM categories prepare verified package inputs (reuse or build).
  After host and e2e, only system remains.

Aggregate aliases (no suite selectors)
  all          complete established regression; default with no arguments;
               metadata-only VM backing verification
  all-verify   compatibility alias for all; metadata-only VM verification
  host-builds  compatibility alias for host
  --continue-on-errors   continue independent tests after failures
  --serial-builds        host-builds only: publish/builds after the host join

  Host includes cleanup-safety prerequisites, unit, component, ui,
  fixture-runtime, source/traceability, static, child-node, child-gjs,
  backend, publish, package builds A/B and their comparison.
  All VM operations use metadata-only verification; image contents are never
  scanned. Focused system/e2e options remain available.
  The granular inventory supplies both host's suites and fix-tests round 1.
  Bare artifacts runs two builds and their reproducibility comparison.
  artifacts prepare reuses matching verified inputs or builds on a miss.
  artifacts build --output '/REPO/output/test-runs/host/allocations/onpc-NAME'
  builds into a new named directory
  for fixed integration consumers; existing paths are never overwritten.
  Pending E2E variants remain excluded.

UI-only validation (same UI buckets and resource limits as host)
  tools/run-tests ui --timeout 1800s
  tools/run-tests ui 'tests/ui/test_request*.py' -q

  Runs only selected UI tests and mandatory cleanup prerequisites; no builds.
  Compatible UI buckets use up to four branches. Unknown modules stay exclusive.
  File/case selectors, -k, -m and --ignore retain the exact selected inventory.
  Default execution timeout is 1800s per bucket; explicit --timeout is preserved.
  -x/--exitfirst or positive --maxfail keeps one serial UI invocation.
  Category groups stay ordered; parallelism occurs within the UI category.
  The UI category is host-only and always excludes VM-dependent live_e2e checks.

Unit-only validation (same unit buckets and resource limits as host)
  tools/run-tests unit
  tools/run-tests unit 'tests/unit/test_regression*.py' -q

  Balances selected modules across up to four branches; fixtures stay together.
  Unknown modules stay exclusive; reviewed fixture builds use artifact limits.
  Preserves exact file/case selectors, -k, -m and scoped ignores.
  Adds no other suites, package stages, or cleanup prerequisite inventory.
  -x/--exitfirst or positive --maxfail keeps one serial unit invocation.
  Direct tools/run-unit-tests remains serial for narrow iteration/diagnosis.

Granular categories (all's partition)
{listing}

Helper commands (composites, focused checks and diagnostic operations)
{helpers}'''


def phase_arguments(argv):
    """Recognize complete phases without consuming focused category options."""
    if not argv or argv[0] not in PHASES or any(
            arg not in (*PHASES, '--continue-on-errors') for arg in argv):
        return None
    if len(argv) != len(set(argv)):
        raise ValueError('categories and flags must not be repeated')
    phases = tuple(kind for kind in PHASES if kind in argv)
    options = {'phases': phases}
    if '--continue-on-errors' in argv:
        options['continue_on_errors'] = True
    return options


def selections(root, argv):
    """Split validated category/argument groups without consuming option values.

    Prefer a valid single selection (notably ``static all`` and ``unit -k
    component``). Only split at another category when the complete group is
    invalid, and validate every group before starting any work.
    """
    argv, _ = execution_arguments(argv)
    phases = phase_arguments(argv)
    if phases is not None:
        return [(kind, []) for kind in phases['phases']]
    try:
        validate_one(root, argv)
        return [(argv[0], argv[1:])]
    except ValueError as error:
        if argv[0] not in AGGREGATES:
            for index in range(1, len(argv)):
                if argv[index] not in CATEGORIES or argv[index] in AGGREGATES:
                    continue
                try:
                    validate_one(root, argv[:index])
                    rest = selections(root, argv[index:])
                except ValueError:
                    continue
                return [(argv[0], argv[1:index]), *rest]
        raise error


def aggregate_arguments(category, args):
    allowed = {'--continue-on-errors'}
    if category == 'host-builds':
        allowed.add('--serial-builds')
    if len(args) != len(set(args)) or any(arg not in allowed for arg in args):
        raise ValueError('aggregate accepts --continue-on-errors and host-builds --serial-builds only')


def artifact_path(value):
    path = Path(value)
    from test_storage import BASE
    roots = (Path('/tmp'), Path('/var/tmp'), BASE / 'host/allocations', BASE / 'privileged/allocations')
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


def artifact_output(value):
    """Accept a new direct managed allocation; never replace inputs."""
    path = Path(value)
    from test_storage import allocation_parent
    if (str(path) != value or path.parent != allocation_parent() or
            not re.fullmatch(r'onpc-[A-Za-z0-9_.-]+', path.name) or
            os.path.lexists(path)):
        raise ValueError('artifact output must be a new output/test-runs/host/allocations/onpc-* directory')
    return str(path)


def allocate_artifact_output(value):
    import test_retention

    def create():
        path = Path(artifact_output(value))
        path.mkdir(mode=0o700)
        return str(path)

    return test_retention.allocate(create)


def qualification_artifact_command(root, category, args):
    """Prepare fixed Parent inputs in this run, including after retention expiry."""
    if category != 'integration' or args not in (
            ['check_e2e_gdm_navigation'], ['check_e2e_gdm_navigation.py'],
            ['check_e2e_gdm_recipient'], ['check_e2e_gdm_recipient.py'],
            ['check_e2e_challenges'], ['check_e2e_challenges.py'],
            ['check_e2e_fresh_desktop'], ['check_e2e_fresh_desktop.py'],
            ['check_e2e_desktop_keyring'], ['check_e2e_desktop_keyring.py'],
            ['check_e2e_shell_search_results'], ['check_e2e_shell_search_results.py'],
            ['check_e2e_shell_search'], ['check_e2e_shell_search.py'],
            ['check_e2e_parent_search_launch'], ['check_e2e_parent_search_launch.py'],
            ['check_e2e_terminal_provider'], ['check_e2e_terminal_provider.py'],
            ['check_e2e_license_viewer'], ['check_e2e_license_viewer.py'],
            ['check_e2e_give_repeated_public_operations_distinct_stages'],
            ['check_e2e_give_repeated_public_operations_distinct_stages.py'],
            ['check_e2e_gdm_product_free'], ['check_e2e_gdm_product_free.py'],
            ['check_e2e_product_free_entry'], ['check_e2e_product_free_entry.py'],
            ['check_e2e_package_authority'], ['check_e2e_package_authority.py'],
            ['check_e2e_package_command'], ['check_e2e_package_command.py'],
            ['check_e2e_customer_reboot'], ['check_e2e_customer_reboot.py'],
            ['check_e2e_toggle'], ['check_e2e_toggle.py'],
            ['check_e2e_app_row_observations'], ['check_e2e_app_row_observations.py'],
            ['check_e2e_feedback_read'], ['check_e2e_feedback_read.py'],
            ['check_e2e_text'], ['check_e2e_text.py'],
            ['check_e2e_kiosk_eligible_choices'], ['check_e2e_kiosk_eligible_choices.py'],
            ['check_e2e_request_choices'], ['check_e2e_request_choices.py'],
            ['check_e2e_kiosk_no_child'], ['check_e2e_kiosk_no_child.py'],
            ['check_e2e_kiosk_fixtures'], ['check_e2e_kiosk_fixtures.py'],
            ['check_e2e_parent_save'], ['check_e2e_parent_save.py'],
            ['check_e2e_allowance_presets'], ['check_e2e_allowance_presets.py']):
        return None
    from test_storage import named_input
    output = str(named_input())
    if os.path.lexists(output):
        artifact_path(output)
        return None  # The privileged consumer verifies the frozen manifest.
    directory = allocate_artifact_output(output)
    print('run-tests: output=' + directory, flush=True)
    return python_file(root, 'tools/build_test_artifacts.py', '--output', directory)


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
        return [['/usr/bin/python3', '-B', '-m', 'pytest', '-p', 'no:cacheprovider', *options, '--', *targets]], '--collect-only' not in options
    if category == 'backend':
        if argv:
            raise ValueError('backend readiness accepts no arguments')
        return [python_file(root, 'tests/integration/graphical_backend.py')], False
    if category in ('integration', 'system', 'e2e'):
        # Validation is shared with the installed root-owned dispatcher, which
        # repeats it after pkexec. Loading this checkout copy confers no privilege.
        import runpy
        dispatcher = runpy.run_path(host.confined_file(root, 'tools/onpc-test-runner'))
        command = dispatcher['selection'](root, [category, *argv],
                                          allow_missing_artifacts=category == 'e2e')
        if '--list' in argv and category != 'integration':
            return [command], False
        # Forward the validated E2E options, preserving a multi-case selection.
        forwarded = command[3:] if category == 'e2e' else argv
        return [['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner', category, *forwarded]], False
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
            return [['/usr/bin/node', '--test', '--test-concurrency=2', *files]], False
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
    if category in ('check', 'component-all', 'fast', 'all', 'all-verify'):
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
                  'fast': 'test-fast', 'all': 'test-all', 'all-verify': 'test-all-verify'}[category]
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
        if category == 'artifacts' and argv == ['prepare']:
            return [[*command, '--reuse']], False
        if category == 'artifacts' and len(argv) == 3 and argv[:2] == ['build', '--output']:
            return [[*command, '--output', artifact_output(argv[2])]], False
        if action == 'verify' and len(argv) == 2:
            return [[*command, '--verify', '--output', artifact_path(argv[1])]], False
        if category == 'artifacts' and action == 'compare' and len(argv) == 3:
            return [[*command, '--compare', *map(artifact_path, argv[1:])]], False
        raise ValueError('invalid artifact operation')
    raise ValueError('unknown test category; use --help or --list')


def _main(argv=None, *, detached=False):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in HELP_ARGV:
        print(usage())
        return 0
    if argv == ['--list']:
        print(json.dumps(suite_inventory(), indent=2))
        return 0
    if not argv:
        argv = ['all']
    try:
        argv, stop_on_error = execution_arguments(argv)
        if os.geteuid() == 0:
            raise ValueError('use this launcher as an unprivileged user')
        root = Path(__file__).resolve().parents[1]
        phases = phase_arguments(argv)
        if phases is not None:
            from regression import main as regression_main
            return regression_main(root, **phases)
        if detached:
            selected = selections(root, argv)
            if selected[0][0] not in AGGREGATES and not any(
                    '--list' in args or '--help' in args or '-h' in args or '--collect-only' in args
                    for _, args in selected):
                from regression import main as regression_main
                return regression_main(root, selections=selected,
                                       **({'stop_on_error': True} if stop_on_error else {}))
        category, args = argv[0], argv[1:]
        if category in ('all', 'all-verify', 'host', 'host-builds'):
            aggregate_arguments(category, args)
            from regression import main as regression_main
            options = {'continue_on_errors': True} if '--continue-on-errors' in args else {}
            if category == 'host-builds':
                return regression_main(root, phases=('host',), serial_builds='--serial-builds' in args, **options)
            return regression_main(root, **options)
        if detached:
            from regression_process import host_run, category_run
            options = args[1:] if args[:1] == ['--unattended'] else args
            if category in ('unit', 'component', 'ui'):
                return host_run(root, category, options, pipe=False)
            return category_run(root, category, options, pipe=False)
        if category == 'e2e' and '--list' not in args:
            options = args[1:] if args[:1] == ['--unattended'] else args
            planned, _ = plan(root, category, options)
            if not any(value.startswith('--artifacts=') for value in planned[0]):
                from test_retention import allocate
                directory = allocate(tempfile.mkdtemp, prefix='onpc-test-artifacts-')
                print('run-tests: output=' + directory, flush=True)
                status = subprocess.run(
                    python_file(root, 'tools/build_test_artifacts.py', '--reuse', '--output', directory),
                    cwd=root, env=host.environment(root), check=False).returncode
                if status:
                    return status if status > 0 else 128 - status
                args = [*args, '--artifacts=' + directory]
        if args[:1] == ['--unattended']:
            from regression_process import host_run, category_run
            if category in ('unit', 'component', 'ui'):
                return host_run(root, category, args[1:])
            if category not in CATEGORIES:
                raise ValueError('unsupported unattended category')
            return category_run(root, category, args[1:])
        if category in ('unit', 'component'):
            return host.run_host(root, category, args)
        if category == 'ui':
            # Preserve the one documented UI environment and timeout entry point.
            host.pytest_command(root, args, 'ui')
            command = [host.confined_file(root, 'tools/run-ui-tests'), *args]
            from test_storage import scratch_descriptors
            environment = host.environment(root)
            return subprocess.run(command, env=environment, pass_fds=scratch_descriptors(),
                                  check=False).returncode
        commands, safety = plan(root, category, args)
        if safety:
            host.prerequisites(root)
        env = host.environment(root)
        if category in ('fixture-runtime', 'coverage'):
            env = host.test_environment(root)
        if category in ('fixtures', 'artifacts') and (not args or args in (['build'], ['prepare'])):
            from test_retention import allocate
            directory = allocate(tempfile.mkdtemp, prefix=f'onpc-test-{category}-')
            commands[0] += ['--output', directory]
            print('run-tests: output=' + directory, flush=True)
        elif category == 'artifacts' and args[:2] == ['build', '--output']:
            directory = allocate_artifact_output(args[2])
            print('run-tests: output=' + directory, flush=True)
        if category == 'coverage':
            from test_retention import allocate
            directory = allocate(tempfile.mkdtemp, prefix='onpc-coverage-')
            command = commands[0]
            command.insert(command.index('--'), '--cov-report=xml:' + directory + '/coverage.xml')
            env['COVERAGE_FILE'] = directory + '/.coverage'
            print('run-tests: output=' + directory, flush=True)
        if category == 'child-gjs':
            from test_retention import allocate
            directory = allocate(tempfile.mkdtemp, prefix='onpc-gjs-coverage-')
            for command in commands:
                command[1:1] = ['--coverage-prefix=' + str(root / 'child'),
                                '--coverage-output=' + directory]
            print('run-tests: output=' + directory, flush=True)
        os.chdir(root)
        preparation = qualification_artifact_command(root, category, args)
        if preparation is not None:
            commands.insert(0, preparation)
        for command in commands[:-1]:
            status = subprocess.run(command, env=env, check=False).returncode
            if status:
                return status if status > 0 else 128 - status
        if commands[-1][0] == '/usr/bin/pkexec':
            from dev_privileges import check
            check(commands[-1][1])
        print('run-tests: validated category starting', file=sys.stderr, flush=True)
        from test_storage import scratch_descriptors
        return subprocess.run(commands[-1], env=env, pass_fds=scratch_descriptors(),
                              check=False).returncode
    except (ValueError, OSError) as error:
        detail = str(error) if isinstance(error, ValueError) else 'filesystem or execution failure'
        if isinstance(error, OSError) and getattr(error, '__notes__', None):
            detail = f'{type(error).__name__}: {error}'
        print('run-tests: ' + detail, file=sys.stderr)
        for note in getattr(error, '__notes__', ()):
            print(note, file=sys.stderr)
        return 2


def validate_one(root, argv):
    category, args = argv[0], argv[1:]
    if category in ('all', 'all-verify', 'host', 'host-builds'):
        aggregate_arguments(category, args)
        return
    if args[:1] == ['--unattended']:
        args = args[1:]
    if category in ('unit', 'component', 'ui'):
        host.pytest_command(root, args, category)
    else:
        plan(root, category, args)


def validate(root, argv):
    if not argv or argv in HELP_ARGV or argv == ['--list']:
        return
    selected = selections(root, argv)
    if len(selected) > 1 and any('--list' in args or '--help' in args or '-h' in args or '--collect-only' in args
                                 for _, args in selected):
        raise ValueError('listing/help requires a single category')
    return selected


def host_only_selection(selected):
    """VM and privileged integration selections retain the VM checkout lock."""
    return bool(selected) and all(kind in CATEGORIES and kind not in (
        'all', 'all-verify', 'system', 'e2e', 'integration', 'fast')
        for kind, _ in selected)


def host_only_request(argv):
    """Classify a request before validation so it reaches the right session.

    Reconnection intentionally precedes full option validation. Only complete
    phase combinations can contain more than one category; focused category
    arguments must not be mistaken for category names (for example ``-m e2e``).
    """
    args = list(argv) or ['all']
    if args[:1] == ['--stop-on-error']:
        args = args[1:] or ['all']
    category = args[0]
    if category in PHASES:
        phases = [argument for argument in args if argument in PHASES]
        return bool(phases) and all(phase == 'host' for phase in phases)
    return category in CATEGORIES and category not in (
        'all', 'all-verify', 'system', 'e2e', 'integration', 'fast')


def is_inspection(argv):
    """Return whether an invocation only requests help, listing, or collection."""
    return any(flag in argv for flag in INSPECTION_FLAGS)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Inspection must never wait for, attach to, or even inspect execution
    # ownership. Its underlying command still validates its own arguments.
    if is_inspection(argv):
        return _main(argv)
    if os.geteuid() == 0:
        return _main(argv)
    try:
        root = Path(__file__).resolve().parents[1]
        if test_activity.descriptors() or test_activity.VARIABLE in os.environ:
            # Internal workers inherit a verified lock, and must execute their
            # assigned category instead of observing their own parent session.
            with test_activity.activity(root):
                validate(root, argv)
                return _main(argv)
        from regression_session import main as session_main
        return session_main(root, argv)
    except (ValueError, OSError) as error:
        detail = str(error) if isinstance(error, ValueError) else 'test activity ownership unavailable'
        print('run-tests: ' + detail, file=sys.stderr)
        return 2
