"""Run-tests group routing and case passes; vm_queue owns VM workers and leases."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from collections import Counter
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass, field
from functools import partial

# Workers use isolated Python; restore only this checkout's sibling modules.
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_source
if __name__ == '__main__':
    _source_imports = test_source.startup(Path(__file__).resolve().parents[1], sys.argv[1:])
    _source_imports.__enter__()

import test_activity
import test_launcher
from test_progress import OverallProgress, case_counts, overall_line, recorded_cases
import test_retention
from test_results import OBSERVATION_BLOCKED_STATUS, PENDING_STATUS
from regression_process import Control, FRAME_PREFIX
from vm_selection import BATCH, VARIABLE, WORKER, vm_config
from vm_queue import Executor
from vm_pool import reservation
import launcher_reload
from vm_case_queue import case_inventory, work_items, arguments, replay_case

if __name__ == '__main__':
    _source_imports.__exit__(None, None, None)

FAMILY_WORK = 'ONPC_TEST_FAMILY_WORK'
CHECKPOINT_READY = 'Family checkpoint ready: '




def split(root, argv):
    from test_commands import execution_arguments, selections, AGGREGATES, PHASES
    args, stop = execution_arguments(argv or ['all'])
    selected = selections(root, args)
    if len(selected) == 1 and selected[0][0] in AGGREGATES:
        selected = [(kind, []) for kind in PHASES]
    host = [(kind, options) for kind, options in selected if kind not in ('system', 'e2e')]
    guests = [(kind, options) for kind, options in selected if kind in ('system', 'e2e')]
    def flatten(groups):
        result = [*(['--resume'] if '--resume' in argv else []),
                  *(['--resume-case-only'] if '--resume-case-only' in argv else []),
                  *(['--resume-area-only'] if '--resume-area-only' in argv else []),
                  *[arg for arg in argv if arg.startswith('--resume-case=')],
                  *(['--stop-on-error'] if stop else []),
                  *(value for kind, options in groups for value in (kind, *options))]
        if '--continue-on-errors' in args and all(kind in PHASES and not options
                                                for kind, options in groups):
            result.append('--continue-on-errors')
        return result
    return flatten(host) if host else [], flatten(guests) if guests else []


@test_source.protected
def _plan(root, argv, *, targets=None):
    """Load one coherent inventory before waiting for any VM reservation."""
    from test_commands import selections
    host_args, guest_args = split(root, argv)
    snapshot = json.loads(os.environ[BATCH]) if BATCH in os.environ else dict(concurrency=1, vms=[])
    configured = vm_config.registry() if snapshot['vms'] else {}
    vms = tuple(configured[name] for name in (snapshot['vms'] if targets is None else targets))
    if targets is not None:
        from host_compute import units
        feasible = tuple(vm for vm in vms if units(vm.compute_unit) <= units(vm.host.max_compute_unit))
        missing = {vm.family for vm in vms} - {vm.family for vm in feasible}
        if missing:
            raise ValueError('no selected VM fits its host compute limit for families: ' + ', '.join(sorted(missing)))
        vms = feasible
    if not vms and guest_args:
        raise ValueError('VM work requires its configured allowed pool')
    guest_selection = selections(root, guest_args) if guest_args else []
    families = collect_families(root, vms, guest_selection, area_retry='--resume-area-only' in guest_args)
    replay = next((arg.partition('=')[2] for arg in guest_args if arg.startswith('--resume-case=')), None)
    if replay and len(guest_selection) == 1:
        from upgrade_history import upgrade_from
        if upgrade_from(guest_selection[0][1]):
            matches = {case for items in families.values() for work in items
                       if (case := replay_case(work, replay)) is not None}
            if len(matches) == 1:
                current, = matches
                guest_args[guest_args.index('--resume-case=' + replay)] = '--resume-case=' + current
                replay = current
    if replay and (len(guest_selection) != 1 or any(
            not any(replay in work['cases'] for work in items) for items in families.values())):
        raise ValueError('case retry requires one category and a selected case')
    return snapshot, vms, host_args, guest_args, guest_selection, families


def collect_families(root, vms, selection, *, area_retry=False):
    from test_commands import execution_selections
    from upgrade_history import FROM_OPTION, main_revision, supported_releases, upgrade_from, upgrade_matrix

    families = {}
    build = None
    original_vm = os.environ.get(VARIABLE)
    try:
        for vm in vms:
            if vm.family in families:
                continue
            vm_config.select(vm.name)
            items = families[vm.family] = []
            for category, options in execution_selections(root, selection):
                cases = case_inventory(root, category, options, vm=vm.name,
                                       pass_fds=test_source.descriptors())
                if category != 'system' or '--upgrade-inputs' not in options:
                    items.extend(work_items(category, options, cases, area_retry=area_retry))
                    continue
                package_format = vm.require_package_format()
                if build is None:
                    from package_inputs import digest, paths
                    revision = main_revision(root)
                    build = revision or digest(root, paths(root))
                source = upgrade_from(options)
                if source:
                    # Explicit replays keep their source even after it ages out.
                    current, history = supported_releases(root, package_format, revision=revision)
                    if source[1:] not in {version for version, _ in history}:
                        raise ValueError(f'{source} is not a supported earlier release on {vm.family}')
                    previous = [source[1:]]
                else:
                    current, previous = upgrade_matrix(root, package_format, revision=revision)
                for version in previous:
                    flags = options if source else [*options, FROM_OPTION + 'v' + version]
                    items.extend(work_items(category, flags, cases,
                                            upgrade=f'@v{version}-to-v{current}-{build[:16]}',
                                            area_retry=area_retry))
    finally:
        if original_vm is None:
            os.environ.pop(VARIABLE, None)
        else:
            vm_config.select(original_vm)
    return families


def selected_cases(families, guest_args):
    replay = next((arg.partition('=')[2] for arg in guest_args if arg.startswith('--resume-case=')), None)
    focused = '--resume-case-only' in guest_args or '--resume-area-only' in guest_args
    return {(family, work['category'], case)
            for family, items in families.items() for work in items
            if not focused or replay in work['cases']
            for case in work['cases']
            if not focused or '--resume-area-only' in guest_args or case == replay}


class FamilyAdmission:
    """Balance ready workers, rotating ties without preempting active work."""

    def __init__(self, vms):
        self.families = {vm.name: vm.family for vm in vms}
        self.compute = {vm.name: vm.compute_unit for vm in vms}
        self.order = list(dict.fromkeys(self.families.values()))

    def choose(self, ready, active):
        from host_compute import units
        counts = {family: sum((units(self.compute[name]) for name in active
                              if self.families[name] == family), units(0))
                  for family in self.order}
        candidates = {self.families[name] for name in ready}
        family = min((family for family in self.order if family in candidates),
                     key=lambda family: counts[family])
        self.order.remove(family)
        self.order.append(family)
        return next(name for name in ready if self.families[name] == family)


def source_identity(root):
    """Describe a transferred source snapshot for diagnostics only."""
    origin = vm_config.remote_origin()
    if origin is not None and 'source_identity' in origin:
        return dict(origin['source_identity'])
    from regression_inputs import identity
    return dict(digest=identity(root))


@dataclass
class GroupHistory:
    """In-memory results retained when a pass refreshes its source."""

    failed_work: set = field(default_factory=set)
    observed_failures: set = field(default_factory=set)
    replayed_families: set = field(default_factory=set)
    validated_area_cases: dict = field(default_factory=dict)


class PassGroup:
    """One existing checkpoint and argument scope in a shared dispatch pass."""

    def __init__(self, root, stack, scope, plan, progress, results, history):
        from test_checkpoint import PassCheckpoint
        _, vms, host_args, self.args, self.selection, self.families = plan
        self.targets = {vm.name: vm.family for vm in vms}
        self.scope = scope
        self.progress = progress
        self.results = results
        self.history = history
        self.deferred_work = set()
        self.focus_finished = set()
        self.failed = self.blocked = False
        self.replay = next((arg.partition('=')[2] for arg in self.args if arg.startswith('--resume-case=')), None)
        self.area = '--resume-area-only' in self.args
        self.focused = self.area or '--resume-case-only' in self.args
        self.selected = selected_cases(self.families, self.args)
        self.split_areas = {}
        if self.area:
            workers = Counter(self.targets.values())
            reverse = os.environ.get('ONPC_TEST_REVERSE') == '1'
            self.families = {family: self.partition_area(family, items, reverse=reverse)
                             if workers[family] > 1 or reverse else items
                             for family, items in self.families.items()}
        self.checkpoint = stack.enter_context(PassCheckpoint(root, [['_host', host_args], ['_guest', self.args]],
            self.targets, self.families, resume='--resume' in (*host_args, *self.args), scope=scope))
        if self.replay:
            for family in self.families:
                if family in self.split_areas:
                    # An older durable case pass cannot validate this operation.
                    # A source refresh can carry forward this invocation's own passes.
                    validated = history.validated_area_cases.get(family, set())
                    for case in self.split_areas[family]['cases']:
                        if case not in validated:
                            self.checkpoint.retry(family, case)
                elif family not in history.replayed_families:
                    self.checkpoint.retry(family, self.replay, area=self.area)

    def partition_area(self, family, items, *, reverse):
        partition = []
        for work in items:
            if work['area'] and self.replay in work['cases']:
                self.split_areas[family] = dict(work, case=self.replay)
                cases = reversed(work['cases']) if reverse else work['cases']
                partition.extend(dict(work, case=case, cases=[case], area=False) for case in cases)
            else:
                partition.append(work)
        return partition

    @staticmethod
    def key(family, work):
        from vm_case_queue import work_key
        return family, work_key(work)

    def next_work(self, family):
        if self.focused and family in self.focus_finished:
            return None
        area = self.split_areas.get(family)
        for work in self.checkpoint.pending(family):
            key = self.key(family, work)
            selected = (work['case'] in area['cases'] if area else
                        not self.focused or self.replay in work['cases'])
            if selected and key not in self.history.failed_work and key not in self.deferred_work:
                return work

    def publish_counts(self):
        if self.progress is not None:
            passed = {key for key in self.selected if key[2] in self.checkpoint.passed(key[0], key[1])}
            _, failures = recorded_cases(self.results.failures(), options=self.args)
            self.progress(*case_counts(self.selected, passed, self.history.observed_failures | failures))

    def status(self):
        if self.failed or self.history.failed_work:
            return 1
        if self.blocked:
            return OBSERVATION_BLOCKED_STATUS
        if self.deferred_work or self.checkpoint.claims() or any(self.next_work(family) for family in self.families):
            return PENDING_STATUS
        return 0


def execute_pass(root, plan, control, execute, *, host=None,
                 checkpoint_scope='ordinary', continue_on_errors=False, sources=None,
                 progress=None, histories=None, group_plans=None):
    """Run current pending work, stop on failure and join all normal bookings."""
    from test_results import ResultStore
    from test_commands import selections
    snapshot, vms, host_args, *_ = plan
    lock = threading.RLock()
    admission = FamilyAdmission(vms)
    result_store = ResultStore()
    failed = threading.Event()
    observation_blocked = threading.Event()
    inflight, probing, results = {}, {}, {}
    host_completed = []
    histories = {} if histories is None else histories
    plans = group_plans or ({checkpoint_scope: (plan, progress)} if vms else {})
    with ExitStack() as stack:
        groups = [PassGroup(root, stack, scope, group, report, result_store, histories.setdefault(scope, GroupHistory()))
                  for scope, (group, report) in plans.items()]
        for group in groups:
            group.publish_counts()

        if host_args:
            value = host() if host is not None else dict(status=2, cleanup=False)
            results['host'] = value
            host_completed = value.get('completed_categories', [])
            if value['status']:
                if value['status'] not in (130, launcher_reload.STATUS) and not continue_on_errors:
                    failed.set()
                for work in value.get('failure_works', []):
                    if not any(record['category'] == work['category'] and record['family'] == 'host'
                               for record in result_store.failures()):
                        result_store.record(work['category'], 'host', work['case'] or '', value['status'],
                                            vm='', options=work['options'],
                                            output_tail=value.get('output_tail', ''),
                                            handoffs=value.get('handoffs', []))
                if not value.get('failure_works') and value['status'] not in (130, launcher_reload.STATUS):
                    category, options = selections(root, host_args)[0]
                    result_store.record(category, 'host', '', value['status'], options=options,
                                        output_tail=value.get('output_tail', ''), handoffs=value.get('handoffs', []))

        def available(vm):
            for group in groups:
                if vm.name in group.targets and (work := group.next_work(vm.family)) is not None:
                    return group, work

        def accepting():
            return not (failed.is_set() or observation_blocked.is_set() or control.stopped.is_set())

        def needed(vm):
            with lock:
                return accepting() and available(vm) is not None

        def choose(candidates, active):
            with lock:
                ready = {name: item for name in candidates
                         if (item := available(targets[name])) is not None}
                if ready and accepting():
                    first = min(priority[group.scope] for group, _ in ready.values())
                    chosen = admission.choose([name for name, (group, _) in ready.items()
                                               if priority[group.scope] == first], active)
                    probing[chosen] = ready[chosen]
                    return chosen

        targets = {vm.name: vm for vm in vms}
        priority = {group.scope: order for order, group in enumerate(groups)}

        def record_operation_failure(group, vm, work, value):
            work = group.split_areas.get(vm.family, work)
            context = {}
            if work['area']:
                context['validation_vms'] = [name for name, family in group.targets.items()
                                             if family == vm.family]
            result_store.record(work['category'], vm.family, '', value['status'],
                vm=vm.name, options=work['options'], work=work,
                output_tail=value.get('traceback', value.get('output_tail', '')),
                handoffs=value.get('handoffs', []), **context)

        def attempt(worker):
            vm = worker.vm
            with lock:
                candidate = available(vm) if accepting() else None
                if candidate is None:
                    return dict(status=0, handoffs=[])
                group, work = candidate
                checkpoint = group.checkpoint
                execution = None
                if group.focused and vm.family not in group.split_areas:
                    execution = dict(work, case=group.replay, area=group.area,
                                     cases=work['cases'] if group.area else [group.replay])
                assignment = checkpoint.claim(vm.family, vm.name, work, execution=execution)
                if assignment is None:
                    return dict(status=0, handoffs=[])
                inherited = {kind: sorted(checkpoint.passed(vm.family, kind)) for kind, _ in group.selection}
                inflight[vm.name] = group, assignment
            return execute(worker, assignment, inherited, group)

        def completed(vm, value):
            with lock:
                attempt = inflight.pop(vm.name, None)
                probe = probing.pop(vm.name, None)
                if attempt is None:
                    if value['status'] not in (0, 130, launcher_reload.STATUS):
                        failed.set()
                        if probe is not None:
                            group, work = probe
                            group.failed = True
                            record_operation_failure(group, vm, work, value)
                            value['category'] = work['category']
                    return value
                group, assignment = attempt
                checkpoint = group.checkpoint
                work = assignment['execution']
                area = group.split_areas.get(vm.family)
                evidence = value.get('evidence')
                check_status = value['status']
                reloading = check_status == 130 and launcher_reload.pending() and not control.stopped.is_set()
                if reloading and isinstance(evidence, dict) and evidence.get('status') == 0:
                    check_status = 0  # The assignment and its cleanup are still checked below.
                accepted = checkpoint.accept(assignment, evidence, check_status)
                observed = evidence if accepted is not None else {}
                cleanup = observed.get('cleanup') is True and value.get('cleanup') is not False
                value = dict(value, category=work['category'], cleanup=cleanup)
                for case in set(observed.get('passed', [])) & set(work['cases']):
                    group.history.observed_failures.discard((vm.family, work['category'], case))
                    result_store.record(work['category'], vm.family, case, 0, vm=vm.name,
                                        options=work['options'])
                actual_failures = set(observed.get('failed', [])) & set(work['cases'])
                if not area and (group.replay in observed.get('passed', []) or group.replay in actual_failures):
                    group.history.replayed_families.add(vm.family)
                for case in actual_failures:
                    group.history.observed_failures.add((vm.family, work['category'], case))
                    result_store.record(work['category'], vm.family, case, 1, vm=vm.name,
                        options=work['options'], output_tail=value.get('output_tail', ''),
                        handoffs=value.get('handoffs', []))
                if check_status == OBSERVATION_BLOCKED_STATUS:
                    # Only the joined, assignment-bound controller result can
                    # distinguish an observation blocker from a command error.
                    if not actual_failures and cleanup and observed.get('status') == check_status:
                        observation_blocked.set()
                        group.blocked = True
                        group.publish_counts()
                        return dict(value, pending=True, cleanup=True)
                    value = dict(value, status=1, cleanup=cleanup)
                    if not actual_failures:
                        value['output_tail'] = (value.get('output_tail', '') +
                            '\nThe VM worker could not confirm the observation blocker and its cleanup.')
                if reloading and not actual_failures:
                    worker_status = observed.get('status')
                    if cleanup and (worker_status == 0 or (
                            worker_status == 130 and observed.get('interrupted') is True)):
                        value = dict(value, status=launcher_reload.STATUS)
                    else:
                        value = dict(value, status=1, interrupted=False, cleanup=cleanup,
                                     output_tail=value.get('output_tail', '') +
                                     '\nVM reload could not confirm a successful or cleanly interrupted attempt.')
                interrupted = value.get('interrupted') or value['status'] in (130, launcher_reload.STATUS)
                complete = accepted is not None and (set(work['cases']) <= checkpoint.passed(vm.family, work['category'])
                            if work['cases'] else accepted is True)
                if area:
                    complete = complete and cleanup and work['case'] in observed.get('passed', [])
                if complete and not work['cases']:
                    result_store.record(work['category'], vm.family, '', 0, vm=vm.name,
                                        options=work['options'], complete=True)
                if complete and check_status == 0:
                    if area:
                        group.history.validated_area_cases.setdefault(vm.family, set()).add(work['case'])
                    else:
                        result_store.finish_command(work['category'], work['options'], family=vm.family, work=work)
                if not value['status'] and not complete:
                    group.deferred_work.add(group.key(vm.family, assignment['work']))
                    value = dict(value, pending=True)
                    interrupted = True
                if actual_failures or value['status'] and not interrupted:
                    group.history.failed_work.add(group.key(vm.family, assignment['work']))
                    if not continue_on_errors or not actual_failures or not observed.get('cleanup'):
                        failed.set()
                    if not actual_failures:
                        record_operation_failure(group, vm, work, value)
                if group.focused and not area:
                    group.focus_finished.add(vm.family)
                group.publish_counts()
                return value

        for group in groups:
            for family, items in group.families.items():
                if failed.is_set():
                    break
                eligible = tuple(name for name, kind in group.targets.items() if kind == family)
                # A reverse pass may queue an area's cases individually. Match
                # a saved operation against the full selected inventory.
                scopes = {}
                for work in items:
                    key = (work['category'], tuple(work['options']))
                    scopes.setdefault(key, []).extend(work['cases'])
                if any(result_store.select_failure(category, family, cases, list(options), vms=eligible)
                       for (category, options), cases in scopes.items()):
                    failed.set()
                    group.failed = True
        if vms and not failed.is_set() and not control.stopped.is_set():
            with Executor(root, vms, snapshot['concurrency'], control.stopped, sources=sources) as executor:
                results.update(executor.run_ready(attempt, choose=choose, needed=needed,
                    completed=completed, **({'stop_on_error': False} if continue_on_errors else {})))
        blocked = observation_blocked.is_set()
        group_statuses = {group.scope: group.status() for group in groups}
        unfinished = any(status in (PENDING_STATUS, OBSERVATION_BLOCKED_STATUS) for status in group_statuses.values())
        statuses = [value['status'] for value in results.values()]
        cleanup_complete = all(value.get('cleanup', True) for value in results.values())
        hard_failure = failed.is_set() or any(
            value['status'] not in (0, 1, 130, launcher_reload.STATUS, OBSERVATION_BLOCKED_STATUS, PENDING_STATUS)
            or value['status'] == 1 and value.get('cleanup') is False for value in results.values())
        if hard_failure:
            status = 1
        elif control.stopped.is_set():
            status = 130
        elif cleanup_complete and (launcher_reload.STATUS in statuses or vms and launcher_reload.pending()):
            status = launcher_reload.STATUS
        elif 1 in group_statuses.values() or 1 in statuses:
            status = 1
        elif blocked:
            status = OBSERVATION_BLOCKED_STATUS
        elif 130 in statuses:
            status = 130
        else:
            status = PENDING_STATUS if unfinished else 0
        if status == 0 and cleanup_complete:
            for group in groups:
                for family, area in group.split_areas.items():
                    result_store.finish_command(area['category'], area['options'], family=family, work=area)
        can_refresh = cleanup_complete and not hard_failure and (
            status in (0, PENDING_STATUS) or continue_on_errors and status == 1)
        return dict(status=status, results=results, failures=result_store.failures(),
                    cleanup_complete=cleanup_complete, can_refresh=can_refresh,
                    completed_categories=host_completed,
                    pending=unfinished,
                    stopped=control.stopped.is_set() and not failed.is_set(),
                    group_statuses=group_statuses)


def execution_groups(root, argv, vms):
    """Resolve test routing before shared capacity admission sees candidates."""
    from test_commands import CATEGORIES, selections
    host_args, guest_args = split(root, argv)
    groups = []
    by_key = {}
    if host_args:
        groups.append(dict(key='host', category='host', args=host_args, vm_tags=None, vms=[]))
    controls = [arg for arg in guest_args if arg in ('--stop-on-error',)
                or arg.startswith('--resume-case=')
                or arg in ('--resume-case-only', '--resume-area-only')]
    focused_retry = any(arg.startswith('--resume-case=') for arg in controls)
    classic_coverage = set()

    def add_group(key, category, tag, args, candidates):
        if key in by_key:
            by_key[key]['args'].extend((category, *args))
        else:
            group = dict(key=key, category=category, args=[*controls, category, *args],
                         vm_tags=tag, vms=[vm.name for vm in candidates])
            groups.append(group)
            by_key[key] = group

    for category, options in selections(root, guest_args) if guest_args else []:
        spec = CATEGORIES[category]
        desktop_session = None
        classic_ids = []
        children = [(None, spec.vm_tags or 'general', list(options))]
        if spec.subcategories:
            if category != 'e2e':
                raise ValueError('subcategory inventory requires a category case binding')
            import runpy
            runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
            selected = runner['preflight'](list(options), root=root, allow_missing_artifacts=True)
            desktop_session = selected.get('desktop_session')
            if not desktop_session and not focused_retry:
                classic_ids = sorted({case['coverage_id'] for case in selected.get('cases', ())}
                                     .intersection(runner['CLASSIC_COVERAGE_IDS']) - classic_coverage)
            if 'cases' in selected or 'subcategory' in selected:
                membership = ({case['subcategory'] for case in selected['cases']}
                              if 'cases' in selected else {selected['subcategory']})
                if not membership <= {child.name for child in spec.subcategories}:
                    raise ValueError('E2E case belongs to an unregistered test subcategory')
                # An exact selector can name a case from a later group. Do not
                # manufacture an empty earlier group or rerun another selection.
                base = []
                tokens = iter(options)
                for token in tokens:
                    if token == '--subcategory':
                        next(tokens, None)
                    elif not token.startswith('--subcategory='):
                        base.append(token)
                children = [(child.name, child.vm_tags or spec.vm_tags or 'general',
                             [*base, '--subcategory', desktop_session or child.name])
                            for child in spec.subcategories if child.name in membership]
        for name, tag, args in children:
            candidates = [vm for vm in vms if tag in vm.vm_tags]
            missing = {vm.family for vm in vms} - {vm.family for vm in candidates}
            key = category + ('.' + name if name else '')
            if desktop_session:
                key += '.' + desktop_session
            if missing:
                raise ValueError(f'{key}: no selected VM with vm_tags={tag} for families: '
                                 + ', '.join(sorted(missing)))
            if not candidates:
                raise ValueError(f'{key}: no selected VM with vm_tags={tag}')
            add_group(key, category, tag, args, candidates)
            if name == 'general' and classic_ids:
                classic_vms = [vm for vm in candidates if runner['classic_capable'](vm)]
                if classic_vms:
                    classic_args = ['--subcategory=gnome-classic', '--id=' + ','.join(map(str, classic_ids))]
                    if 'artifacts' in selected:
                        classic_args.extend(('--artifacts', selected['artifacts']))
                    if 'fixture_selection' in selected:
                        classic_args.extend(('--fixture-selection', json.dumps(selected['fixture_selection'])))
                    add_group(key + '.gnome-classic', category, tag, classic_args, classic_vms)
                    classic_coverage.update(classic_ids)
    return groups


def run(root, argv, *, reloading=False, upstream_run=None, accounting=None):
    """Run the host selection, then dispatch ready VM groups together."""
    from test_checkpoint import PassCheckpoint
    from test_commands import selections
    from test_results import ResultStore
    progress = OverallProgress()
    with test_source.startup(root, argv):
        snapshot = json.loads(os.environ[BATCH]) if BATCH in os.environ else dict(vms=[])
        configured = vm_config.registry() if snapshot['vms'] else {}
        vms = [configured[name] for name in snapshot['vms']]
        queue_vm = vms[0].name if len(vms) == 1 else None
        progress_scope = 'ordinary' if queue_vm is None else 'ordinary/vm-' + queue_vm
        groups = execution_groups(root, argv, vms)
        selected_groups = groups
        if accounting is not None:
            try:
                selected_groups = execution_groups(root, accounting, vms)
            except ValueError:
                # A group outside the repair task cap owns its dispatch errors.
                progress.update('undiscovered', 0, 0, None)
        selection = selections(root, argv)
        results = ResultStore()
        if len(selected_groups) > 1 or len({vm.family for vm in vms}) > 1:
            records = results.load()
            for group in selected_groups:
                key, args = group['key'], group['args']
                if key == 'host':
                    progress.update(key, 0, 0, None)
                    continue
                try:
                    families = collect_families(root, [configured[name] for name in group['vms']],
                                                selections(root, args), area_retry='--resume-area-only' in args)
                except (OSError, ValueError, subprocess.CalledProcessError):
                    # Dispatch still owns discovery errors for this group.
                    progress.update(key, 0, 0, None)
                    continue
                selected = selected_cases(families, args)
                recorded_passes, recorded_failures = recorded_cases(records, options=args)
                passed = (PassCheckpoint.retained_passes(root, progress_scope + '/' + key, families)
                          if '--resume' in argv else set())
                progress.update(key, *case_counts(selected, recorded_passes | passed, recorded_failures))

        full_host = next((group for group in selected_groups if group['key'] == 'host'), None)
        active_host = next((group for group in groups if group['key'] == 'host'), None)
        host_accounting = (selections(root, full_host['args']) if full_host and accounting is not None else None)
        vm_groups = [group for group in groups if group['vms']]

    def validate_routing():
        from launcher_source_sync import SyncError
        current = vm_config.registry()
        try:
            current_groups = execution_groups(root, argv, [current[vm.name] for vm in vms])
        except (KeyError, ValueError) as error:
            raise SyncError(f'cannot route the selected VM groups after the source changed: {error}; resume to reselect') from error
        if current_groups != groups:
            raise SyncError('the selected VM group routing changed; resume to use the new routing')

    original = {key: os.environ.get(key) for key in (BATCH, VARIABLE)}
    continue_on_errors = '--continue-on-errors' in argv
    completed = set()
    host_status = status = 0

    try:
        from launcher_control import CancellationEvent
        if CancellationEvent().is_set():
            status = 130
        elif full_host:
            launcher_reload.check()
            os.environ.pop(BATCH, None)
            os.environ.pop(VARIABLE, None)
            group = active_host or full_host
            host = _run_pass(root, group['args'], reloading=reloading,
                             checkpoint_scope='ordinary/host', continue_on_errors=continue_on_errors,
                             overall_counts=partial(progress.update, 'host'),
                             host_accounting=host_accounting, accounting_only=active_host is None)
            host_status = status = host['status']
            completed.update(host.get('completed_categories', ()))
        if vm_groups and (not status or continue_on_errors and status == 1):
            if CancellationEvent().is_set():
                status = 130
            else:
                launcher_reload.check()
                for key, value in original.items():
                    if value is not None:
                        os.environ[key] = value
                owner = launcher_reload.current.run if launcher_reload.current is not None else None
                from vm_recording import recording
                with recording(root, enabled='--record' in argv, run=owner) as media:
                    guest = _run_pass(root, argv, reloading=reloading,
                                      checkpoint_scope=progress_scope, vm_groups=vm_groups,
                                      queue_vm=queue_vm, continue_on_errors=continue_on_errors,
                                      overall_counts=progress.update, upstream_run=upstream_run,
                                      validate_routing=validate_routing)
                status = guest['status']
                if media is not None and owner is not None:
                    media.write_index(owner, status)
                if not any(arg.startswith('--resume-case=') for arg in argv):
                    group_statuses = guest.get('group_statuses', {})
                    incomplete = {group['category'] for group in vm_groups
                                  if group_statuses.get(progress_scope + '/' + group['key'], status)}
                    completed.update(group['category'] for group in vm_groups if group['category'] not in incomplete)
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    for category, options in selection:
        if category in completed:
            results.finish_command(category, options)
    if progress.groups:
        print(overall_line(*progress.counts()), flush=True)
    return 1 if host_status == 1 and status in (0, OBSERVATION_BLOCKED_STATUS) else status


def _run_pass(root, argv, *, reloading=False, checkpoint_scope='ordinary',
              continue_on_errors=False, upstream_run=None, validate_routing=None,
              overall_counts=None, host_accounting=None, accounting_only=False,
              queue_vm=None, vm_groups=None):
    from detached_launcher import Stopped
    from launcher_controller import synchronize_boundary
    from launcher_source_sync import SyncError, STATUS as SYNC_STATUS
    from remote_sources import FrozenSources
    histories = {}
    stopped = Control().stopped
    while True:
        if stopped.is_set():
            return dict(status=130, stopped=True, cleanup_complete=True)
        launcher_reload.check()
        group_plans = None
        with ExitStack() as capture:
            with test_source.startup(root, argv):
                if vm_groups:
                    group_plans = {}
                    targets = {}
                    snapshot = json.loads(os.environ[BATCH])
                    for group in vm_groups:
                        args = group['args']
                        if '--resume' in argv and '--resume' not in args:
                            args = ['--resume', *args]
                        try:
                            selected = _plan(root, args, targets=group['vms'])
                        except (OSError, ValueError, subprocess.CalledProcessError) as error:
                            from test_commands import selections
                            from test_results import ResultStore
                            kind, selected_options = selections(root, args)[0]
                            detail = f'{group["key"]}: {error}'
                            command = ['tools/run-tests', *[arg for arg in args if arg != '--resume'],
                                       '--vm', ','.join(group['vms'])]
                            ResultStore().record(kind, 'command', '', 2, options=selected_options,
                                                 command=command, detail=detail)
                            print(f'run-tests: {detail}', file=sys.stderr, flush=True)
                            return dict(status=2, cleanup_complete=True)
                        targets.update((vm.name, vm) for vm in selected[1])
                        group_plans[checkpoint_scope + '/' + group['key']] = (
                            selected, partial(overall_counts, group['key']))
                    vms = tuple(targets[name] for name in snapshot['vms'] if name in targets)
                    plan = snapshot, vms, [], [], [], {}
                else:
                    plan = _plan(root, argv)
                sources = None
                if plan[1]:
                    from upgrade_history import transfer_release_tags
                    plans = [group for group, _ in group_plans.values()] if group_plans is not None else [plan]
                    options = (work['options'] for group in plans for items in group[-1].values() for work in items)
                    sources = capture.enter_context(FrozenSources(root, upgrade_tags=transfer_release_tags(options)))
            outcome = _run_workers(root, plan, reloading=reloading,
                checkpoint_scope=checkpoint_scope, sources=sources,
                continue_on_errors=continue_on_errors, histories=histories, overall_counts=overall_counts,
                host_accounting=host_accounting, accounting_only=accounting_only,
                queue_vm=queue_vm, group_plans=group_plans)
        # Keep assigning from the same snapshot until the pass finishes cleanup.
        if sources is None or not outcome['can_refresh']:
            return outcome
        if stopped.is_set():
            outcome.update(status=130, stopped=True)
            return outcome
        launcher_reload.check()
        try:
            if upstream_run is not None and not synchronize_boundary(
                    root, sources.branch, upstream_run, defer_if_live=True):
                print('Git: checkout is busy. Deferring upstream synchronization.', flush=True)
            if stopped.is_set():
                raise Stopped()
            launcher_reload.check()
            with test_source.startup(root, argv, stopped=stopped.is_set, wait=False):
                if sources.source == source_identity(root):
                    return outcome
                if validate_routing is not None:
                    validate_routing()
        except test_source.SourceBusy:
            return outcome
        except SyncError as error:
            print(f'run-tests: upstream synchronization failed: {error}', file=sys.stderr, flush=True)
            outcome['status'] = SYNC_STATUS
            return outcome
        except (KeyboardInterrupt, Stopped):
            outcome.update(status=130, stopped=True)
            return outcome
        argv = ['--resume', *[argument for argument in argv if argument != '--resume']]


def _run_workers(root, plan, *, reloading=False, checkpoint_scope='ordinary',
                 continue_on_errors=False, sources=None, histories=None, overall_counts=None,
                 host_accounting=None, accounting_only=False, queue_vm=None, group_plans=None):
    snapshot, vms, host_args, *_ = plan
    from test_commands import _main, selections
    from test_checkpoint import Checkpoint
    def execute_host():
        activity = nullcontext() if accounting_only else test_activity.activity(root, host_only=True)
        with activity, test_source.reader(root):
            groups = [] if accounting_only else selections(root, host_args)
            saved = Checkpoint(root, groups, resume='--resume' in host_args) if groups else None
            stream = sys.stdout
            handoffs, output_tail = [], ''
            class Output:
                def __getattr__(self, name):
                    return getattr(stream, name)
                def write(self, value):
                    nonlocal output_tail
                    output_tail = (output_tail + value)[-16000:]
                    for line in value.splitlines():
                        if line.startswith('Failure handoff: '):
                            handoffs.append(line.removeprefix('Failure handoff: '))
                    return stream.write(value)
            try:
                sys.stdout = Output()
                sys.stdout.overall_counts = overall_counts
                if host_accounting is None:
                    status = _main(host_args, detached=True, checkpoint=saved)
                else:
                    from regression import main as run_selected
                    status = run_selected(root, selections=groups, accounting=host_accounting,
                                          stop_on_error='--stop-on-error' in host_args, checkpoint=saved)
            finally:
                sys.stdout = stream
            result = dict(status=status, handoffs=handoffs, output_tail=output_tail,
                          cleanup=bool(getattr(saved, 'queue_finalized', False)),
                          completed_categories=[kind for kind, _ in groups if saved.complete(kind)])
            if status and groups:
                failures = []
                for path in handoffs:
                    try:
                        failures.extend(json.loads(Path(path).read_text()).get('failures', []))
                    except (OSError, ValueError):
                        continue
                works = []
                for failure in failures or [{}]:
                    kind, selected = next((group for group in groups if group[0] == failure.get('category')), groups[0])
                    case = failure.get('case') or None
                    work = dict(category=kind, options=selected, case=case, cases=[case] if case else [], area=False)
                    if work not in works:
                        works.append(work)
                result['failure_works'] = works
            return result

    if accounting_only:
        # A capped repair can reach VM work with all host categories already
        # complete. Discover their counts without creating a dispatch verdict.
        try:
            status = execute_host()['status']
        except (OSError, ValueError):
            status = 0
        if status not in (130, launcher_reload.STATUS):
            status = 0
        return dict(status=status, cleanup_complete=True)

    with Control().installed() as control:
        if host_accounting is not None and not vms:
            # The host runner owns retention for this batch. There are no VM
            # workers or VM artifacts to retain under a second owner.
            return execute_pass(root, plan, control, None, host=execute_host,
                                checkpoint_scope=checkpoint_scope, continue_on_errors=continue_on_errors)
        path = test_activity.retention_path(root)
        if vms and queue_vm is not None:
            # Keep the coordinator's output distinct from its VM worker's
            # journal and from independent single-VM queues in this checkout.
            path = path.parent / 'vm-queues' / queue_vm / path.name
        store = test_retention.Store(path)
        # The inherited owner lease excludes live workers; every VM still
        # separately recovers its own journal and guest state.
        with store.execution_session():
            directory = Path(test_retention.allocate(tempfile.mkdtemp, prefix='onpc-vm-queue-'))
            # Named inputs are VM-bound. Each worker prepares them inside its
            # own retention session, before its independent guest execution.
            # A batch-owned allocation would conflict with that VM's old claim
            # after an interrupted input was removed and recreated.
            output_lock = threading.Lock()
            # VMs join the dashboard when they start an assigned attempt.
            frames = {}
            group_names = {}
            case_summary = []

            def publish_frames():
                if hasattr(sys.stdout, 'frame'):
                    lines = [f'VM queue | concurrency {snapshot["concurrency"]}']
                    lines.extend(case_summary)
                    displayed = (vm.name for vm in vms if vm.name in frames)
                    for index, name in enumerate(displayed):
                        if index:
                            lines.append('')
                        lines.append(f'VM: {name}')
                        if name in group_names:
                            lines.append(f'Test group: {group_names[name].rsplit("/", 1)[-1]}')
                        lines.extend(frames[name])
                    sys.stdout.frame(lines)

            def progress(counts, passed, failed, total):
                with output_lock:
                    if counts is not None:
                        passed, failed, total = counts(passed, failed, total)
                    case_summary[:] = [overall_line(passed, failed, total)]
                    publish_frames()
                    if hasattr(sys.stdout, 'controller'):
                        sys.stdout.controller('test-group', case_summary)

            def execute_worker(worker, assignment, inherited, args):
                vm, receipt = worker.vm, worker.receipt
                from vm_pool import remote
                route = remote()
                detached = sources is not None
                if detached:
                    from remote_sources import RemoteVM
                    route = RemoteVM(root, vm, sources=sources)
                work = assignment.get('execution', assignment['work'])
                if launcher_reload.pending():
                    return dict(status=launcher_reload.STATUS, handoffs=[], evidence=dict(
                        assignment, status=launcher_reload.STATUS, passed=[], failed=[], cleanup=True,
                        interrupted=True))
                environment = test_launcher.environment(root)
                # The coordinator interrupts this attempt through its owned
                # stop path so the worker always finalizes its attempt evidence.
                environment.pop(BATCH, None)
                # A worker starts its own retention session, never another VM's.
                environment.pop(test_retention.VARIABLE, None)
                environment[VARIABLE] = vm.name
                environment[WORKER] = '1'
                from vm_pool import VARIABLE as CHECKOUT
                environment[CHECKOUT] = receipt
                environment.pop('ONPC_RUNNER_INVOCATION', None)
                request = directory / (vm.name + '-work.json')
                attempt = assignment['attempt']
                request.write_text(json.dumps(dict(selection=args, passed=inherited,
                                                  assignment=assignment)))
                request.chmod(0o600)
                environment[FAMILY_WORK] = str(request)
                worker_args = arguments(work, worker=True)
                if (work['category'] == 'system' and not work['options']
                        and (work['case'] or '').startswith('check_')):
                    # The family already resolved this named check. Dispatch it
                    # directly so the worker does not rediscover the full suite.
                    worker_args.append(work['case'])
                if '--stop-on-error' in args:
                    worker_args.insert(0, '--stop-on-error')
                command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                           '--execute-reload' if reloading else '--execute', vm.name, *worker_args]
                pending = b''
                handoffs = []
                ready = False
                with (directory / (vm.name + '.log')).open('ab') as log:
                    os.fchmod(log.fileno(), 0o600)
                    log.seek(0, os.SEEK_END)
                    attempt_output_start = log.tell()
                    def output(data):
                        nonlocal pending, ready
                        log.write(data)
                        log.flush()
                        pending += data
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            value = line.decode('utf-8', errors='replace')
                            if value.startswith('Runner case failed: '):
                                try:
                                    failure = json.loads(value.removeprefix('Runner case failed: '))
                                    case = failure.get('case', '') + work.get('upgrade', '')
                                    if (failure.get('category') == work['category']
                                            and case in work['cases']):
                                        from test_results import ResultStore
                                        ResultStore().record(work['category'], vm.family, case, 1,
                                            vm=vm.name, options=work['options'])
                                        if not continue_on_errors:
                                            control.stop()
                                except (TypeError, ValueError):
                                    pass
                            if value == CHECKPOINT_READY + attempt:
                                ready = True
                                continue
                            if value.startswith('Failure handoff: '):
                                handoffs.append(value.removeprefix('Failure handoff: '))
                            with output_lock:
                                if value.startswith(FRAME_PREFIX):
                                    frame = json.loads(value[len(FRAME_PREFIX):])
                                    # Clearing a dashboard does not finish its worker.
                                    frames[vm.name] = frame or ['Running (waiting for progress)']
                                    publish_frames()
                                else:
                                    print(f'[{vm.name}] {value}', flush=True)
                    attempt_control = Control()
                    attempt_control.stopped = threading.Event()
                    spawned = False
                    def started():
                        nonlocal spawned
                        spawned = True
                    def interrupt():
                        if (control.stopped.is_set() or launcher_reload.pending()
                                or worker.interrupt.is_set()):
                            attempt_control.stop()
                    interrupt()
                    refused_start = attempt_control.stopped.is_set()
                    if refused_start:
                        status = 130
                    elif detached:
                        status = route.run(attempt_control, command, cwd=root, env=environment,
                            output=output, cooperative=True, tick=interrupt, started=started,
                            preserve_exit=True)
                    else:
                        status = attempt_control.run(command, cwd=root, env=environment, output=output,
                            cooperative=True, tick=interrupt, started=started, preserve_exit=True)
                    if pending:
                        with output_lock:
                            print(f'[{vm.name}] ' + pending.decode('utf-8', errors='replace'), flush=True)
                evidence = None
                if route is not None:
                    evidence = route.result.get('evidence')
                    handoffs = []
                    for index, received in enumerate(route.result.get('handoffs', [])):
                        handoff = dict(received['failure'])
                        path = directory / (vm.name + '-remote-' + attempt + '-' + str(index) + '.json')
                        context = received.get('context')
                        if received.get('context_error'):
                            handoff['evidence_error'] = dict(host=received['host'],
                                                            error=received['context_error'])
                        prefix = ('This failure ran on VM host ' + received['host'] +
                                  '; original artifact paths below belong to that host. ')
                        if context is not None:
                            context_path = path.with_name(path.stem + '-context.json')
                            context_path.write_text(json.dumps(context))
                            context_path.chmod(0o600)
                            handoff['evidence_context'] = dict(file=context_path.name,
                                host=received['host'], vm=vm.name, attempt=attempt,
                                )
                            prefix += 'Read the retained bounded failure context at ' + str(context_path) + '. '
                        handoff['prompt'] = prefix + '\n' + handoff['prompt']
                        path.write_text(json.dumps(handoff))
                        path.chmod(0o600)
                        handoffs.append(str(path))
                elif ready:
                    evidence = Checkpoint.worker_result(root, vm.name)
                if (status == 130 and attempt_control.stopped.is_set() and not spawned
                        and (refused_start or route is None or route.result)):
                    # The remote completion receipt also confirms no start
                    # when it arrives without a preceding worker start event.
                    evidence = dict(assignment, status=130, passed=[], failed=[], cleanup=True,
                                    interrupted=True, diagnostic=False)
                with (directory / (vm.name + '.log')).open('rb') as log:
                    log.seek(0, os.SEEK_END)
                    log.seek(max(attempt_output_start, log.tell() - 16000))
                    output_tail = log.read(16000).decode('utf-8', errors='replace')
                result = dict(status=status, handoffs=handoffs, evidence=evidence, output_tail=output_tail)
                if (status == 130 and attempt_control.stopped.is_set() and isinstance(evidence, dict)
                        and evidence.get('interrupted') is True and not evidence.get('failed', [])):
                    # The coordinator validates the exact assignment and cleanup
                    # before returning unfinished work to pending. No synthetic
                    # failure or passing attempt is created by preemption.
                    result.update(interrupted=True, handoffs=[])
                for path in handoffs:
                    try:
                        failed = json.loads(Path(path).read_text()).get('failures', [])
                        suffix = work.get('upgrade', '')
                        case = next((item['case'] + suffix for item in failed
                                     if item.get('case') and item['case'] + suffix in work['cases']), None)
                        if case is not None:
                            result['failure_case'] = case
                            break
                    except (OSError, ValueError):
                        continue
                return result

            def execute_case(worker, assignment, inherited, group):
                vm = worker.vm
                with output_lock:
                    group_names[vm.name] = group.scope
                    frames[vm.name] = ['Starting worker']
                    publish_frames()
                try:
                    result = execute_worker(worker, assignment, inherited, group.args)
                except (ValueError, OSError) as error:
                    if isinstance(error, test_source.SourceBusy):
                        raise
                    from detached_launcher import record_exception
                    reporter = lambda context, error, **identity: record_exception(directory, context, error, **identity)
                    details = reporter('VM case execution', error,
                        vm=vm.name, case=assignment.get('execution', assignment['work'])['case'],
                        attempt=assignment['attempt'])
                    with output_lock:
                        frames[vm.name] = ['Failed (worker error)']
                        publish_frames()
                    # A failed operation reaches repair with its original error;
                    # it does not become an exception in the coordinator.
                    result = dict(status=2, handoffs=[], evidence=None, **details,
                                  output_tail=details.get('traceback', str(error))[-16000:])
                status = result['status']
                state = {0: 'Finished', 130: 'Stopped',
                         OBSERVATION_BLOCKED_STATUS: 'Blocked (incomplete product fault observation)',
                         launcher_reload.STATUS: 'Reload pending'}.get(status, f'Failed (exit {status})')
                with output_lock:
                    frames[vm.name] = [state]
                    publish_frames()
                return result

            try:
                if group_plans is not None:
                    group_plans = {scope: (group_plan, partial(progress, counts))
                                   for scope, (group_plan, counts) in group_plans.items()}
                outcome = execute_pass(root, plan, control, execute_case, host=execute_host,
                                       checkpoint_scope=checkpoint_scope,
                                       continue_on_errors=continue_on_errors, sources=sources, histories=histories,
                                       progress=partial(progress, overall_counts) if vms else None,
                                       group_plans=group_plans)
            except Exception as error:
                from detached_launcher import Stopped, record_exception
                if not isinstance(error, (launcher_reload.ReloadRequested, Stopped)):
                    record_exception(directory, 'VM pass coordinator', error)
                raise
            results = outcome['results']
            from detached_launcher import atomic
            try:
                atomic(directory / 'outcome.json', outcome)
                (directory / 'outcome.json').chmod(0o600)
            except OSError as error:
                from detached_launcher import record_exception
                record_exception(directory, 'Saving VM pass outcome', error)
            if not results:
                return outcome
            # Keep the actual joined results even if failure-detail processing
            # below cannot read a diagnostic handoff.
            (directory / 'results.json').write_text(json.dumps(results, indent=2))
            (directory / 'results.json').chmod(0o600)
            print(f'VM results: {directory / "results.json"}', flush=True)
            if outcome['status'] == OBSERVATION_BLOCKED_STATUS:
                if hasattr(sys.stdout, 'frame'):
                    sys.stdout.frame([])
                print('VM tests blocked by incomplete product fault observation. Resume to retry pending work.',
                      flush=True)
                return outcome
            if outcome['status'] == launcher_reload.STATUS:
                launcher_reload.check()
            categories = []
            failures = []
            error_details = []
            for vm in vms:
                result = results[vm.name]
                if isinstance(result, dict) and result['status'] == OBSERVATION_BLOCKED_STATUS:
                    continue
                vm_categories = []
                vm_failures = []
                if isinstance(result, dict) and result['status']:
                    for path in result['handoffs']:
                        try:
                            handoff = json.loads(Path(path).read_text())
                            if (not isinstance(handoff, dict)
                                    or not isinstance(handoff.get('categories'), list)
                                    or any(not isinstance(kind, str) for kind in handoff['categories'])
                                    or not isinstance(handoff.get('failures', []), list)
                                    or any(not isinstance(item, dict)
                                        or not isinstance(item.get('category'), str)
                                        or not isinstance(item.get('case'), str)
                                        for item in handoff.get('failures', []))):
                                raise ValueError('invalid failure handoff')
                        except (OSError, ValueError) as error:
                            print(f'[{vm.name}] Failure details unavailable ({type(error).__name__}); '
                                  f'see {directory / (vm.name + ".log")}.', flush=True)
                            continue
                        vm_categories.extend(handoff['categories'])
                        details = handoff.get('error_details', [])
                        details = details if isinstance(details, list) else []
                        error_details.extend(dict(detail, detail=vm.name + ': ' + detail['detail'])
                            for detail in details
                            if isinstance(detail, dict) and isinstance(detail.get('category'), str)
                            and isinstance(detail.get('detail'), str))
                        vm_failures.extend(dict(item, vm=vm.name)
                                           for item in handoff.get('failures', []))
                if (result['status'] if isinstance(result, dict) else result) != 0:
                    if not vm_categories and result.get('category'):
                        vm_categories.append(result['category'])
                    for category in dict.fromkeys(vm_categories):
                        if not any(item['category'] == category for item in vm_failures):
                            vm_failures.append(dict(category=category, case='', vm=vm.name))
                categories.extend(vm_categories)
                failures.extend(vm_failures)
            failed = any((result['status'] if isinstance(result, dict) else result)
                         not in (0, OBSERVATION_BLOCKED_STATUS)
                         for result in results.values())
            if hasattr(sys.stdout, 'frame'):
                sys.stdout.frame([])
            if failed and not control.stopped.is_set():
                prompt = f'Investigate the VM failures in {directory / "results.json"} and adjacent VM logs. Preserve expected behavior and all unrelated work.'
                handoff = directory / 'failure.json'
                handoff.write_text(json.dumps({'prompt': prompt, 'categories': list(dict.fromkeys(categories)),
                                              'failures': failures, 'error_details': error_details}))
                handoff.chmod(0o600)
                print(f'Failure handoff: {handoff}', flush=True)
            # Each directly spawned worker returns only after its guarded
            # execution and cleanup. Its exit status owns the result; report
            # archives and diagnostic file lifetimes do not qualify it again.
            return outcome


def worker(argv):
    from detached_launcher import Stopped
    finished = []
    request = os.environ.get(FAMILY_WORK)
    try:
        status = _worker(argv, finished)
    except (Stopped, KeyboardInterrupt):
        status = 130
    if status == 130 and not finished:
        # Startup may have been interrupted before its checkpoint existed.
        # Reuse original-VM recovery, without starting preparation or tests,
        # and publish proof only after that recovery and all owners close.
        if request is not None:
            os.environ[FAMILY_WORK] = request
        status = _worker(argv, finished, cleanup_only=True)
    # Both the guest controller and this child's enclosing leases have now
    # finished cleanup. A failed context exit publishes no attempt evidence.
    for checkpoint, evidence in finished:
        checkpoint.state['queue_evidence'] = evidence
        checkpoint.save()
    return status


def _worker(argv, finished, *, cleanup_only=False):
    mode, name, *args = argv
    if mode not in ('--execute', '--execute-reload'):
        raise ValueError('private VM queue entry only')
    vm_config.select(name)
    os.environ.pop(BATCH, None)
    os.environ[WORKER] = '1'
    root = Path(__file__).resolve().parents[1]
    from regression_process import PipeFrameOutput
    sys.stdout = PipeFrameOutput(sys.stdout)
    # The batch's checkout-local gate is not a VM reservation or cleanup proof.
    os.environ.pop(test_activity.VARIABLE, None)
    sys.stdout.frame(['Queued (waiting for VM checkout)'])
    from prepare_appsnapshot import baseline_ready_reservation
    control = Control()
    if cleanup_only:
        control.stopped = threading.Event()
    owner = (reservation(name, stopped=control.stopped) if cleanup_only else
             baseline_ready_reservation(root, name, control))
    with control.installed(pipe=not cleanup_only), owner, \
            test_activity.activity(root, named_vm=True), test_source.reader(root, stopped=control.stopped.is_set):
        # Nested aggregate controllers observe the same parent cancellation.
        import regression_process
        regression_process.session_stop = control.stopped
        from test_recovery import cleanup
        if control.stopped.is_set():
            return 130
        sys.stdout.frame(['Preparing tests'])
        status = cleanup(root)
        if status:
            return status
        from test_commands import _main
        from test_checkpoint import Checkpoint
        from test_commands import selections
        work_path = os.environ.pop(FAMILY_WORK, None)
        work = json.loads(Path(work_path).read_text()) if work_path else None
        assignment = work['assignment'] if work else None
        executed = assignment.get('execution', assignment['work']) if assignment else {}
        upgrade = executed.get('upgrade', '')
        original = work['selection'] if work else args
        if upgrade:
            original = [executed['category'], *executed['options']]
        checkpoint = Checkpoint(root, selections(root, original), resume=not work and '--resume' in args)
        if work:
            # The parent owns shared family credit. This VM writes only its
            # private attempt checkpoint; concurrent workers never overwrite it.
            if upgrade:
                checkpoint.results = None
            for category in checkpoint.selected:
                passed = work['passed'][category]
                if upgrade:
                    passed = [case.removesuffix(upgrade) for case in passed if case.endswith(upgrade)]
                checkpoint.entry(category).update(passed=passed, complete=False)
                checkpoint.excluded[category] = set(passed)
                checkpoint.snapshot(category)
            if assignment['vm'] != name:
                raise ValueError('assignment belongs to another VM')
            checkpoint.state['queue_assignment'] = assignment
            checkpoint.save()
            print(CHECKPOINT_READY + assignment['attempt'], flush=True)
            if cleanup_only:
                finished.append((checkpoint, dict(assignment, status=130, passed=[], failed=[], cleanup=True,
                                                   interrupted=True, diagnostic=False)))
                return 130
        if cleanup_only:
            return 130
        replay = [arg.partition('=')[2] for arg in args if arg.startswith('--resume-case=')]
        if replay:
            groups = selections(root, args)
            if len(groups) != 1:
                raise ValueError('case retry requires one category')
            area = '--resume-area-only' in args
            # Family admission already applies the caller's explicit replay.
            checkpoint.retry(groups[0][0], replay[0], area=area, clear_pass=not (work and area))
        status = _main([*args, '--vm', name], detached=True, checkpoint=checkpoint)
        if work:
            # An inherited pass is never evidence that this attempt executed it.
            # The report owns case teardown; main returns through retained-output
            # finalization before this bounded result is made available.
            category = assignment['work']['category']
            observed = {case + upgrade for case in checkpoint.executed_passes.get(category, ())} & set(executed['cases'])
            finalized = getattr(checkpoint, 'queue_finalized', False)
            started = getattr(checkpoint, 'queue_vm_started', False)
            vm_exit = getattr(checkpoint, 'queue_vm_exit', None)
            # The enclosing control may see STOP after the suite has already
            # exited successfully. Its final report still has to close cleanly.
            verdict = 0 if status == 130 and finalized and vm_exit == 0 else status
            cleanup = finalized and (verdict == 0 or
                    not control.stopped.is_set() or getattr(checkpoint, 'queue_vm_cleanup', False)
                    or not started)
            if status == 130 and not cleanup and (not started or vm_exit == 130):
                return status  # Join the existing guarded interruption recovery.
            evidence = dict(assignment, status=verdict, passed=sorted(observed), cleanup=cleanup,
                failed=[case + upgrade for case in getattr(checkpoint, 'queue_failures', [])],
                interrupted=getattr(checkpoint, 'queue_vm_interrupted', False) or (status == 130 and not started),
                diagnostic=False)
            finished.append((checkpoint, evidence))
        return status


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
