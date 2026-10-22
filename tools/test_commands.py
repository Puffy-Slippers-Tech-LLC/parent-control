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
    scope: str = 'host'

    def __post_init__(self):
        if self.scope not in ('host', 'vm'):
            raise ValueError('test category scope must be host or vm')


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
    'fixtures': CategorySpec('build, verify PATH; native-runtime also supports prepare; --kind native-runtime --target ubuntu|fedora; generated build output', leaf=False),
    'artifacts': CategorySpec('two fresh package/fixture builds and reproducibility; build, prepare (verified reuse), verify PATH, compare FIRST SECOND'),
    'integration': CategorySpec('installed dispatcher for check_* basenames; --list lists bindings; no script arguments', leaf=False, scope='vm'),
    'system': CategorySpec('sequential tests per VM; stable numeric --id N[,N...] or --area/--test selectors; optional --artifacts (otherwise prepare each VM\'s declared package format); --previous-artifacts, --list', scope='vm'),
    'e2e': CategorySpec('all runnable E2E cases by default; --id N[,N...] selects exact coverage IDs; --list; optional --artifacts (otherwise built automatically)', scope='vm'),
    'fast': CategorySpec('reserved for the make test-fast target', leaf=False, implemented=False, scope='vm'),
    'all': CategorySpec('complete established regression (default with no arguments); metadata-only VM backing verification; --continue-on-errors disables stop on first error', leaf=False),
    'all-verify': CategorySpec('compatibility alias for all; metadata-only VM verification; --continue-on-errors disables stop on first error', leaf=False),
    'host': CategorySpec('all host tests, publishing and two reproducibility builds in four branches; no VM; host + vm = all', leaf=False),
    'vm': CategorySpec('all VM tests: system and e2e; no host suites; host + vm = all', leaf=False, scope='vm'),
    'host-builds': CategorySpec('compatibility alias for host; optional --serial-builds for scheduling comparison', leaf=False),
}

AGGREGATES = ('all', 'all-verify', 'host', 'host-builds', 'vm')
PHASES = ('host', 'system', 'e2e')
COMPLETE = (*PHASES, 'vm')
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
                            'scope': leaves[kind].scope,
                            'args': list(HOST_ARGS) if kind == 'ui' else []}
                     for kind in order}
    if not categories:
        return inventory
    selected = set()
    for argument in categories:
        for category in argument.split():
            if category in ('all', 'all-verify'):
                selected.update(inventory)
            elif category in ('host', 'host-builds'):
                selected.update(name for name, spec in inventory.items() if inventory_scope(name, spec) == 'host')
            elif category == 'vm':
                selected.update(name for name, spec in inventory.items() if inventory_scope(name, spec) == 'vm')
            elif category in inventory:
                selected.add(category)
            else:
                raise ValueError(f'unknown or unsupported inventory category: {category}')
    if not selected:
        raise ValueError('no categories selected')
    return {name: spec for name, spec in inventory.items() if name in selected}


def inventory_scope(name, spec):
    """Runner-owned scope, including older inventories without scope metadata."""
    scope = spec.get('scope', CATEGORIES[name].scope if name in CATEGORIES else 'host')
    if scope not in ('host', 'vm'):
        raise ValueError('test inventory scope must be host or vm')
    return scope


def repair_inventory(root, requested, *, inventory=None):
    """Expand repair selections using the runner's categories and parser."""
    inventory = suite_inventory(inventory=inventory)
    if not requested:
        return inventory
    if len(requested) == 1 or requested[0] in AGGREGATES:
        return suite_inventory(requested, inventory=inventory)
    try:
        groups = selections(root, requested)
    except ValueError as error:
        try:
            return suite_inventory(requested, inventory=inventory)
        except ValueError:
            raise error
    if not any(options for _, options in groups) and any(arg.startswith('-') for arg in requested):
        raise ValueError('runner coordinator options cannot select a repair run')
    selected = {}
    for category, options in groups:
        expanded = suite_inventory([category], inventory=inventory)
        if options and category not in inventory:
            raise ValueError('aggregate repair selections do not accept options')
        if any(option in INSPECTION_FLAGS for option in options):
            raise ValueError('inspection options cannot select a repair run')
        for name, spec in expanded.items():
            value = dict(spec, args=list(options)) if options else spec
            if name in selected and selected[name] != value:
                raise ValueError(f'conflicting repair selections for {name}')
            selected[name] = value
    return {name: selected[name] for name in inventory if name in selected}


def repair_host_only_request(root, requested):
    """Repair consumers use the runner's scopes, including legacy packed names."""
    if host_only_request(requested):
        return True
    try:
        return all(inventory_scope(name, spec) == 'host'
                   for name, spec in repair_inventory(root, requested).items())
    except ValueError:
        # Invalid VM requests still select their VM before argument validation.
        return False


def execution_arguments(argv):
    """The leading coordinator option does not alter category arguments."""
    resume = '--resume' in argv
    replay = [arg.partition('=')[2] for arg in argv if arg.startswith('--resume-case=')]
    if replay:
        from regression_events import completed_cases
        if not resume or len(replay) != 1:
            raise ValueError('--resume-case requires --resume and one case')
        completed_cases(json.dumps(replay))
    argv = [arg for arg in argv if arg != '--resume' and not arg.startswith('--resume-case=')]
    if resume and not argv:
        argv = ['all']
    stop = argv[:1] == ['--stop-on-error']
    args = argv[1:] if stop else argv
    if stop and (not args or '--continue-on-errors' in args):
        raise ValueError('--stop-on-error requires categories and conflicts with --continue-on-errors')
    return args, stop


def vm_request(argv):
    from vm_selection import vm_config, execution_selection, extract_execution, selected
    args, selector = vm_config.extract_selector(argv)
    if not is_inspection(args) and args != ['--stop'] and not host_only_request(args):
        _, vms = execution_selection(selector)
        if len(vms) > 1 and any(value == '--native-artifacts' or value.startswith('--native-artifacts=')
                                 for value in args):
            raise ValueError('explicit native artifacts require a single VM; use --native-inputs for a queue')
    elif selector is not None:
        extract_execution(argv)
    return args, selected() if selector is not None else None


def usage():
    """Human-readable launcher help. ``--list`` remains the JSON inventory."""
    width = max(map(len, CATEGORIES))
    inventory = suite_inventory()
    listing = '\n'.join(f'  {name:<{width}}  {CATEGORIES[name].description}' for name in inventory)
    helpers = '\n'.join(f'  {name:<{width}}  {spec.description}'
                        for name, spec in CATEGORIES.items() if name not in inventory)
    return f'''Usage: tools/run-tests [--vm NAME] [--resume] [--stop-on-error] [category [args ...]] ...
       tools/run-tests --help
       tools/run-tests --list
       tools/run-tests --stop

With no categories, start the all aggregate. An active run or
unread result takes precedence over new execution categories. Attach to a
configured queue without --vm; narrowed runs require their original --vm NAME.
Help, listing and collection return immediately without attaching.
--resume reuses the last matching category/test checkpoint, skipping completed
cases and retrying failed or interrupted cases. Without it, a new execution
resets the checkpoint. Keep the original selectors; a changed selection refuses
resume. Required preparation and lifecycle prerequisites still run.
--stop requests cancellation of the active run and waits for owned cleanup.
VM categories read config/test-vm.json and execute every entry with enabled
equal to the string "true", using at most concurrency VMs simultaneously.
--vm accepts a name or ID, a comma-separated list, all-enabled, or all.
Explicit names/IDs and all include disabled entries. Free slots refill immediately.
Each invocation resolves IDs
from the current file; changing IDs needs no tool refresh or baseline replacement.
Host-only tests and declaration listing need no VM.

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
  vm           all VM work: system + e2e; no host suites

  all = host + vm
  vm = system + e2e

  tools/run-tests host
  tools/run-tests vm --vm NAME
  tools/run-tests host vm --vm NAME           (same as all)
  tools/run-tests system e2e --vm NAME
  tools/run-tests e2e --vm NAME
  tools/run-tests host system --vm NAME
  tools/run-tests host system e2e --vm NAME    (same as all)

  Each VM retains its report; configured queues retain a combined result summary.
  VM execution automatically records the shared watch layout, including all
  active VMs in this runner's queue and their SSH output, with or without tools/watch open.
  Latest category-ID-VMs.webm files live in output/test-runs/recordings/.
  VM names follow numeric config IDs; no timestamp, age or size rotation.
  system --id N[,N...] selects persistent IDs shown by system --list.
  Narrowed combined categories share one report and reuse host's package artifacts.
  Without host, VM categories prepare verified package inputs (reuse or build).
  Focused system --area AREA --test CASE also prepares inputs per VM when
  --artifacts is omitted. Each VM must declare package_format (deb or rpm) in
  config/test-vm.json; there is no default. Configured concurrency still applies.
  After host and e2e, only system remains.
  Separate host and vm runs may execute in parallel, with independent locks,
  sessions and cancellation. Combined host/VM runs reserve both scopes.

Aggregate aliases (no suite selectors)
  all          complete established regression; default with no arguments;
               metadata-only VM backing verification
  all-verify   compatibility alias for all; metadata-only VM verification
  host-builds  compatibility alias for host
  --continue-on-errors   continue independent tests after failures
  --serial-builds        host-builds only: publish/builds after the host join

  Host includes unit (including cleanup regressions), component, ui,
  fixture-runtime, source/traceability, static, child-node, child-gjs,
  backend, publish, package builds A/B and their comparison.
  All VM operations use metadata-only verification; image contents are never
  scanned. Focused system/e2e options remain available.
  The granular inventory supplies both host's suites and fix-tests round 1.
  Bare artifacts runs two builds and their reproducibility comparison.
  artifacts prepare reuses matching verified inputs or builds on a miss.
  artifacts prepare --for-vm --vm NAME selects RPM/DEB from the verified baseline.
  Add --upgrade-inputs to build pinned earlier-release/current inputs in a new retained bundle.
  artifacts prepare --for-vm --native-inputs prepares the reviewed native dependency
  pair in retained storage; it does not install packages or qualify the live history.
  artifacts prepare --native-inputs --package-format deb|rpm prepares that finite
  pair without a VM probe; installed-baseline compatibility still needs preflight.
  system --upgrade-inputs prepares that pair independently in each VM worker
  and supplies --artifacts/--previous-artifacts to the existing installed runner.
  It requires the VM's declared format to match its verified baseline; no format defaults.
  Explicit artifact paths cannot be combined with system --upgrade-inputs.
  system --native-inputs prepares current product and finite native dependency
  inputs independently per VM, then supplies --artifacts/--native-artifacts.
  It cannot be combined with --upgrade-inputs or explicit artifact paths.
  Add --output PATH to prepare a new named input without replacing existing data.
  artifacts build --output '/REPO/output/test-runs/host/allocations/onpc-NAME'
  builds into a new named directory
  for fixed integration consumers; existing paths are never overwritten.
  Pending E2E variants remain excluded.

UI-only validation (same UI buckets and resource limits as host)
  tools/run-tests ui --timeout 1800s
  tools/run-tests ui 'tests/ui/test_request*.py' -q

  Runs only selected UI tests; serial owned cleanup precedes parallel work.
  Cleanup never launches regression tests or package builds.
  Compatible UI buckets use up to four branches. Unknown modules stay exclusive.
  File/case selectors, -k, -m and --ignore retain the exact selected inventory.
  Default execution timeout is 1800s per bucket; explicit --timeout is preserved.
  -x/--exitfirst or positive --maxfail keeps one serial UI invocation.
  Category groups stay ordered; parallelism occurs within the UI category.
  The UI category is host-only and always excludes VM-dependent live_e2e checks.

Unit-only validation (same unit buckets and resource limits as host)
  tools/run-tests unit
  tools/run-tests unit 'tests/unit/test_test_launchers.py' --timeout 180s
  tools/run-tests unit 'tests/unit/test_regression*.py' -q

  Balances selected modules across up to four branches; fixtures stay together.
  Unknown modules stay exclusive; reviewed fixture builds use artifact limits.
  Preserves exact file/case selectors, -k, -m and scoped ignores.
  Adds no other suites, package stages, or cleanup prerequisite inventory.
  -x/--exitfirst or positive --maxfail keeps one serial unit invocation.
  Direct tools/run-unit-tests remains serial for narrow iteration/diagnosis.

  Unit, component and UI accept --timeout DURATION before or after test paths,
  including --timeout=DURATION. The runner owns this positive, finite worker
  deadline (s/m/h/d suffixes); it is not a pytest plugin option. Parallel
  selections apply it separately to collection and each scheduled worker.
  Unit/component have no deadline by default. Direct UI defaults to 60s;
  scheduled UI buckets default to 1800s. Explicit limits replace those defaults.

Granular categories (all's partition)
{listing}

Helper commands (composites, focused checks and diagnostic operations)
{helpers}'''


def phase_arguments(argv):
    """Recognize complete phases without consuming focused category options."""
    if not argv or argv[0] not in COMPLETE or any(
            arg not in (*COMPLETE, '--continue-on-errors') for arg in argv):
        return None
    if len(argv) != len(set(argv)):
        raise ValueError('categories and flags must not be repeated')
    phases = tuple(kind for kind in PHASES if kind in argv or (kind != 'host' and 'vm' in argv))
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
    from vm_selection import extract_execution as extract
    argv, _ = extract(argv, required=False)
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


def has_artifacts(argv):
    return any(value == '--artifacts' or value.startswith('--artifacts=') for value in argv)


def vm_input_options(category, argv):
    """Keep package preparation in infrastructure, before privileged dispatch.

    Each VM worker resolves its own format through vm_artifacts' pinned-baseline
    probe. Explicit existing bundles and automatically built pairs are exclusive.
    """
    upgrade = '--upgrade-inputs' in argv
    native = '--native-inputs' in argv
    if native and (category != 'system' or argv.count('--native-inputs') != 1 or upgrade
                   or any(value in ('--artifacts', '--previous-artifacts', '--native-artifacts')
                          or value.startswith(('--artifacts=', '--previous-artifacts=', '--native-artifacts='))
                          for value in argv)):
        raise ValueError('native inputs require system and no upgrade or explicit artifact paths')
    if upgrade and (category != 'system' or argv.count('--upgrade-inputs') != 1
                    or any(value in ('--artifacts', '--previous-artifacts', '--native-artifacts')
                           or value.startswith(('--artifacts=', '--previous-artifacts=', '--native-artifacts='))
                           for value in argv)):
        raise ValueError('upgrade inputs require system and no explicit artifact paths')
    return [value for value in argv if value not in ('--upgrade-inputs', '--native-inputs')], upgrade


def vm_preparation_flags(category, argv):
    _, upgrade = vm_input_options(category, argv)
    return (['--system-native-inputs'] if '--native-inputs' in argv else
            ['--upgrade-inputs'] if upgrade else [])


def prepared_vm_options(category, argv, directory):
    options, upgrade = vm_input_options(category, argv)
    if '--native-inputs' in argv:
        return [*options, '--artifacts=' + str(Path(directory) / 'product'),
                '--native-artifacts=' + str(Path(directory) / 'native')]
    if upgrade:
        return [*options, '--artifacts=' + str(Path(directory) / 'current'),
                '--previous-artifacts=' + str(Path(directory) / 'previous')]
    return [*options, '--artifacts=' + str(directory)]


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


def qualification_input_options(root, selector):
    """Read the wrapper's literal input declaration without importing its code."""
    import ast

    path = host.confined_file(root, 'tests/integration/' + selector.removesuffix('.py') + '.py')
    tree = ast.parse(Path(path).read_text())
    declarations = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'named_input'):
            if node.args or any(keyword.arg not in (
                    'package_source', 'fixture_source', 'upgrade_source', 'vm_source')
                    or not isinstance(keyword.value, ast.Constant)
                    or type(keyword.value.value) is not bool for keyword in node.keywords):
                raise ValueError('qualification input declaration must use literal boolean options')
            options = {keyword.arg: keyword.value.value for keyword in node.keywords}
            if len(options) != len(node.keywords):
                raise ValueError('duplicate qualification input option')
            declarations.append(options)
    if not declarations:
        return None
    if any(options != declarations[0] for options in declarations):
        raise ValueError('qualification must declare one input profile')
    return declarations[0]


def qualification_artifact_command(root, category, args):
    """Prepare every declared qualification input for the selected VM."""
    if (category != 'integration' or len(args) != 1
            or args[0] in INSPECTION_FLAGS):
        return None
    options = qualification_input_options(root, args[0])
    if options is None:
        return None
    from test_storage import named_input
    from vm_selection import arguments

    output = str(named_input(**options))
    flags = ['--upgrade-inputs'] if options.get('upgrade_source') else []
    if os.path.lexists(output):
        artifact_path(output)
        # Recheck format against pinned baseline provenance, even on a cache hit.
        return python_file(root, 'tools/vm_artifacts.py', *flags,
                           '--candidate', output, '--output', output, *arguments())
    directory = allocate_artifact_output(output)
    print('run-tests: output=' + directory, flush=True)
    return python_file(root, 'tools/vm_artifacts.py', *flags, '--output', directory, *arguments())


def qualification_fixture_options(root, category, args, *, control=None, environment=None):
    """Freeze F05's caller-owned fixture input before the privileged VM lease.

    The selection is a locator, not authority: the privileged consumer repeats
    the authenticated journal and complete bundle checks before acquiring a VM.
    Ordinary runners remain unavailable on clean captures.
    """
    if category != 'integration' or len(args) != 1 or args[0].removesuffix('.py') != 'check_fixture_provisioning':
        return []
    from vm_selection import selected
    if selected().name != 'onpc-Ubuntu26.04':
        raise ValueError('fixture provisioning qualification is Ubuntu-only')
    from fixture_execution import Selection
    if control is None:
        from regression_process import Control
        with Control().installed() as owned:
            return qualification_fixture_options(root, category, args, control=owned,
                                                 environment=host.environment(root))
    # Build in an owned child: STOP must reach cold compilers/containers too.
    # Control forwards the caller retention/producer descriptors and waits for
    # its recorded child before the privileged consumer can acquire the VM.
    pending, records, invalid = b'', [], False
    prefix = b'fixture-execution: selection='
    def output(data):
        nonlocal pending, invalid
        sys.stdout.write(data.decode('utf-8', errors='replace'))
        sys.stdout.flush()
        pending += data
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            if line.startswith(prefix):
                if len(line) > 8192:
                    invalid = True
                else:
                    records.append(line[len(prefix):])
        if len(pending) > 65536:
            invalid, pending = True, b''
    status = control.run(python_file(root, 'tools/fixture_execution.py', '--target', 'ubuntu'),
                         cwd=root, env=environment, output=output, timeout=600.0)
    if status:
        raise ValueError('fixture preparation failed; status=' + str(status))
    if invalid or len(records) != 1:
        raise ValueError('fixture preparation returned no unique selection')
    selection = Selection.from_record(json.loads(records[0]))
    if selection.target != 'ubuntu':
        raise ValueError('fixture preparation returned an incompatible selection')
    return ['--fixture-selection', json.dumps(selection.record(), sort_keys=True)]


def make_command(root, target, assignments=()):
    makefile = host.confined_file(root, 'Makefile')
    if not re.search(r'^' + re.escape(target) + r'\s*:', Path(makefile).read_text(), re.M):
        raise ValueError('this roadmap runner is not implemented yet')
    return ['/usr/bin/make', '--no-print-directory', '--directory=' + str(root),
            '--file=' + makefile, '--', target, *assignments]


def plan(root, category, argv):
    """Validate everything before prerequisites, output creation or execution."""
    native_inputs = category == 'system' and '--native-inputs' in argv
    if category in ('integration', 'system', 'e2e'):
        from vm_selection import extract_execution as extract
        argv, _ = extract(argv, required=False)
        argv, _ = vm_input_options(category, argv)
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
        from vm_selection import arguments
        vm_args = arguments() if '--list' not in argv else []
        command = dispatcher['selection'](root, [category, *argv, *vm_args],
                                          allow_missing_artifacts=category in ('system', 'e2e'))
        selectors = dict(value.split('=', 1) for value in command
                         if value.startswith(('--area=', '--test=', '--id=')))
        explicit_native = any(value == '--native-artifacts' or value.startswith('--native-artifacts=')
                              for value in argv)
        native_selection = native_inputs or explicit_native
        if category == 'system' and '--list' not in argv and (
                native_selection or '--id' in selectors or '--test' in selectors):
            # Resolve the finite history before allocating or building either
            # bundle, using the installed runner's selector and inventory owner.
            sys.path.insert(0, str(root / 'tests/integration'))
            try:
                import system_runner
            finally:
                sys.path.pop(0)
            if '--id' in selectors:
                from system_case_ids import parse_recording_ids
                native_selection = native_selection or any(
                    identity.case_id == system_runner.NATIVE_UPDATE_CASE
                    for identity in parse_recording_ids(selectors['--id']))
            native_selection = native_selection or selectors.get('--test') == system_runner.NATIVE_UPDATE_CASE
        if native_selection and '--list' not in argv:
            from vm_selection import selected
            try:
                system_runner.resolve_selection(
                    selectors.get('--area'), selectors.get('--test'),
                    **({'recording_ids': selectors['--id']} if '--id' in selectors else {}),
                    qualification_failure='--qualification-failure' in argv,
                    fresh_install=any(value == '--previous-artifacts' or
                                      value.startswith('--previous-artifacts=') for value in argv),
                    native_inputs=native_inputs or explicit_native,
                    target_package_format=selected().require_package_format())
            except system_runner.Error as error:
                raise ValueError(str(error)) from error
        if '--list' in argv:
            return [command], False
        # Forward the validated E2E options, preserving a multi-case selection.
        forwarded = command[3:] if category == 'e2e' else [*argv, *vm_args]
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
        if category == 'fixtures' and '--kind' in argv:
            options = argv[1:] if action in ('build', 'prepare') else argv[2:]
            if (action not in ('build', 'prepare', 'verify') or len(options) != 4
                    or options[:3] != ['--kind', 'native-runtime', '--target']
                    or options[3] not in ('ubuntu', 'fedora')):
                raise ValueError('invalid native-runtime fixture operation')
            arguments = ['--target', options[3]]
            if action == 'prepare':
                return [python_file(root, 'tools/fixture_execution.py', *arguments)], False
            if action == 'verify':
                arguments += ['--verify', '--output', artifact_path(argv[1])]
            return [python_file(root, 'tools/fixture_bundle.py', *arguments)], False
        path = ('tests/fixtures/build_test_applications.py' if category == 'fixtures'
                else 'tools/build_test_artifacts.py')
        command = python_file(root, path)
        if action == 'build' and len(argv) <= 1:
            return [[*command, *(['--package-format', 'deb'] if category == 'artifacts' else [])]], False
        if category == 'artifacts' and argv == ['prepare']:
            return [[*command, '--package-format', 'deb', '--reuse']], False
        if category == 'artifacts' and argv == ['prepare', '--for-vm', '--upgrade-inputs']:
            from vm_selection import arguments
            return [python_file(root, 'tools/vm_artifacts.py', '--upgrade-inputs', *arguments())], False
        if category == 'artifacts' and argv == ['prepare', '--for-vm', '--native-inputs']:
            from vm_selection import arguments
            return [python_file(root, 'tools/vm_artifacts.py', '--native-inputs', *arguments())], False
        if (category == 'artifacts' and len(argv) == 4 and
                argv[:3] == ['prepare', '--native-inputs', '--package-format'] and
                argv[3] in ('deb', 'rpm')):
            return [[*command, '--native-inputs', '--package-format', argv[3]]], False
        if category == 'artifacts' and (argv == ['prepare', '--for-vm'] or
                len(argv) == 4 and argv[:3] == ['prepare', '--for-vm', '--candidate']):
            from vm_selection import arguments
            candidate = ['--candidate', artifact_path(argv[3])] if len(argv) == 4 else []
            return [python_file(root, 'tools/vm_artifacts.py', *candidate, *arguments())], False
        if category == 'artifacts' and len(argv) == 4 and argv[:3] == ['prepare', '--for-vm', '--output']:
            from vm_selection import arguments
            return [python_file(root, 'tools/vm_artifacts.py', '--output',
                                artifact_output(argv[3]), *arguments())], False
        if category == 'artifacts' and len(argv) == 3 and argv[:2] == ['build', '--output']:
            return [[*command, '--package-format', 'deb', '--output', artifact_output(argv[2])]], False
        if action == 'verify' and len(argv) == 2:
            return [[*command, '--verify', '--output', artifact_path(argv[1])]], False
        if category == 'artifacts' and action == 'verify-native' and len(argv) == 2:
            return [[*command, '--verify-native-inputs', '--output', artifact_path(argv[1])]], False
        if category == 'artifacts' and action == 'compare' and len(argv) == 3:
            return [[*command, '--compare', *map(artifact_path, argv[1:])]], False
        raise ValueError('invalid artifact operation')
    raise ValueError('unknown test category; use --help or --list')


def _main(argv=None, *, detached=False, checkpoint=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if is_inspection(argv):
        argv = [arg for arg in argv if arg != '--resume']
    try:
        argv, _ = vm_request(argv)
    except ValueError as error:
        print('run-tests: ' + str(error), file=sys.stderr)
        return 2
    if argv in HELP_ARGV:
        print(usage())
        return 0
    if argv == ['--list']:
        print(json.dumps(suite_inventory(), indent=2))
        return 0
    if not argv:
        argv = ['all']
    if not is_inspection(argv) and not host_only_request(argv):
        from vm_selection import BATCH
        if BATCH in os.environ:
            from vm_test_queue import run
            return run(Path(__file__).resolve().parents[1], argv)
    try:
        argv, stop_on_error = execution_arguments(argv)
        if os.geteuid() == 0:
            raise ValueError('use this launcher as an unprivileged user')
        root = Path(__file__).resolve().parents[1]
        phases = phase_arguments(argv)
        if phases is not None:
            from regression import main as regression_main
            return regression_main(root, **phases, **({'checkpoint': checkpoint} if checkpoint else {}))
        if detached:
            selected = selections(root, argv)
            # --unattended selects child control, not a raw-output observer.
            # Detached owners must still publish the shared live dashboard.
            if selected[0][0] not in AGGREGATES and not any(
                    '--list' in args or '--help' in args or '-h' in args or '--collect-only' in args
                    for _, args in selected):
                from regression import main as regression_main
                return regression_main(root, selections=selected,
                                       **({'checkpoint': checkpoint} if checkpoint else {}),
                                       **({'stop_on_error': True} if stop_on_error else {}))
        category, args = argv[0], argv[1:]
        if category in AGGREGATES:
            aggregate_arguments(category, args)
            from regression import main as regression_main
            options = {'continue_on_errors': True} if '--continue-on-errors' in args else {}
            if category == 'host-builds':
                return regression_main(root, phases=('host',), serial_builds='--serial-builds' in args,
                                       **options, **({'checkpoint': checkpoint} if checkpoint else {}))
            return regression_main(root, **options, **({'checkpoint': checkpoint} if checkpoint else {}))
        if detached:
            from regression_process import host_run, category_run
            options = args[1:] if args[:1] == ['--unattended'] else args
            if category in ('unit', 'component', 'ui'):
                return host_run(root, category, options, pipe=False)
            return category_run(root, category, options, pipe=False)
        if category in ('system', 'e2e') and '--list' not in args:
            options = args[1:] if args[:1] == ['--unattended'] else args
            planned, _ = plan(root, category, options)
            if not has_artifacts(planned[0]):
                from test_retention import allocate
                from vm_selection import arguments as vm_arguments
                directory = allocate(tempfile.mkdtemp, prefix='onpc-test-artifacts-')
                print('run-tests: output=' + directory, flush=True)
                status = subprocess.run(
                    python_file(root, 'tools/vm_artifacts.py',
                                *vm_preparation_flags(category, options),
                                '--output', directory,
                                *vm_arguments()),
                    cwd=root, env=host.environment(root), check=False).returncode
                if status:
                    return status if status > 0 else 128 - status
                args = prepared_vm_options(category, args, directory)
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
        commands, _ = plan(root, category, args)
        env = host.environment(root)
        if category in ('fixture-runtime', 'coverage'):
            env = host.test_environment(root)
        if (category in ('fixtures', 'artifacts') and
                (not args or args in (['build'], ['prepare']) or
                 category == 'fixtures' and args[:3] == ['build', '--kind', 'native-runtime'] or
                 category == 'artifacts' and args[:3] ==
                 ['prepare', '--native-inputs', '--package-format'])):
            from test_retention import allocate
            directory = allocate(tempfile.mkdtemp, prefix=f'onpc-test-{category}-')
            commands[0] += ['--output', directory]
            print('run-tests: output=' + directory, flush=True)
        elif category == 'artifacts' and args[:2] == ['build', '--output']:
            directory = allocate_artifact_output(args[2])
            print('run-tests: output=' + directory, flush=True)
        elif category == 'artifacts' and args[:3] == ['prepare', '--for-vm', '--output']:
            directory = allocate_artifact_output(args[3])
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
        commands[-1] += qualification_fixture_options(root, category, args)
        if commands[-1][0] == '/usr/bin/pkexec':
            from dev_privileges import check
            check(commands[-1][1])
            commands[-1].insert(1, '--keep-cwd')
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
    if category in AGGREGATES:
        aggregate_arguments(category, args)
        return
    if args[:1] == ['--unattended']:
        args = args[1:]
    if category in ('unit', 'component', 'ui'):
        host.pytest_command(root, args, category)
    else:
        plan(root, category, args)


def validate(root, argv):
    argv, _ = vm_request(argv)
    if not argv or argv in HELP_ARGV or argv == ['--list']:
        return
    selected = selections(root, argv)
    if len(selected) > 1 and any('--list' in args or '--help' in args or '-h' in args or '--collect-only' in args
                                 for _, args in selected):
        raise ValueError('listing/help requires a single category')
    return selected


def host_only_selection(selected):
    """VM and privileged integration selections retain the VM checkout lock."""
    return bool(selected) and all(kind in CATEGORIES and kind not in ('all', 'all-verify')
                                 and CATEGORIES[kind].scope == 'host' for kind, _ in selected)


def host_only_request(argv):
    """Classify a request before validation so it reaches the right session.

    Reconnection intentionally precedes full option validation. Only complete
    phase combinations can contain more than one category; focused category
    arguments must not be mistaken for category names (for example ``-m e2e``).
    """
    from vm_selection import extract_execution as extract
    args, _ = extract(argv, required=False)
    args = args or ['all']
    args = [arg for arg in args if arg != '--resume' and not arg.startswith('--resume-case=')] or ['all']
    if args[:1] == ['--stop-on-error']:
        args = args[1:] or ['all']
    category = args[0]
    if category in COMPLETE:
        phases = [argument for argument in args if argument in COMPLETE]
        return bool(phases) and all(phase == 'host' for phase in phases)
    if category in CATEGORIES and any(argument in CATEGORIES and CATEGORIES[argument].scope == 'vm'
                                      for argument in args[1:]):
        # A valid focused host selection may contain a category word as an
        # option value. Otherwise a mixed category request owns the VM scope.
        try:
            validate_one(Path(__file__).resolve().parents[1], args)
        except ValueError:
            return False
    return host_only_selection([(category, [])])


def includes_host_request(root, argv):
    """Whether a validated request also reserves the host scope."""
    from vm_selection import extract_execution as extract
    args, _ = extract(argv, required=False)
    args, _ = execution_arguments(args or ['all'])
    if args[0] in ('all', 'all-verify') or host_only_request(args):
        return True
    phases = phase_arguments(args)
    if phases is not None:
        return 'host' in phases['phases']
    if not any(arg in CATEGORIES and CATEGORIES[arg].scope == 'host' for arg in args[1:]):
        return False
    return any(CATEGORIES[kind].scope == 'host' for kind, _ in selections(root, args))


def is_inspection(argv):
    """Return whether an invocation only requests help, listing, or collection."""
    return any(flag in argv for flag in INSPECTION_FLAGS)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        from test_checkpoint import resume_arguments
        argv = resume_arguments(Path(__file__).resolve().parents[1], argv)
        vm_request(argv)
    except ValueError as error:
        print('run-tests: ' + str(error), file=sys.stderr)
        return 2
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
