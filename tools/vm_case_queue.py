"""Finite VM case work shared by the ordinary and repair queues."""

import hashlib
import json
import re
import subprocess
from contextlib import contextmanager, ExitStack


def family_binding(family, workers=None):
    # Family names are opaque values, including names resembling VM names.
    return json.dumps(['family', family, *([] if workers is None else [sorted(workers)])],
                      separators=(',', ':'))


def case_inventory(root, category, options, *, vm=None, pass_fds=()):
    """Collect existing public identities without starting a VM."""
    from test_commands import execution_selections
    if category == 'integration':
        return list(dict.fromkeys(args[0] for _, args in execution_selections(
            root, [(category, list(options))])))
    if category == 'system':
        import test_launcher
        from test_storage import scratch_descriptors
        from vm_selection import selected
        name = vm or selected().name
        cases = []
        for _, arguments in execution_selections(root, [('system', list(options))]):
            command = [str(root / 'tools/run-tests'), 'system', *arguments,
                       '--vm', name, '--list']
            result = subprocess.run(command, cwd=root, env=test_launcher.environment(root),
                                    capture_output=True, text=True, check=True,
                                    pass_fds=tuple(dict.fromkeys((*scratch_descriptors(), *pass_fds))))
            cases.extend(match[1] for line in result.stdout.splitlines()
                         if (match := re.fullmatch(r'    (\S+::\S+) \[selected\](?: \[system-\d+\])?', line)))
    elif category == 'e2e':
        import runpy
        runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
        plan = runner['preflight'](list(options), root=root, allow_missing_artifacts=True)
        if 'cases' not in plan:
            return None
        cases = [case['case_id'] for case in plan['cases']]
    else:
        raise ValueError('case queue requires a VM test category')
    cases = list(dict.fromkeys(cases))
    if not cases:
        raise ValueError(f'{category} collection returned no case identities for bounded verification')
    return cases


def work_items(category, options, cases):
    """Keep independent areas and stateful system histories indivisible."""
    from test_checkpoint import INDEPENDENT_SYSTEM_AREAS
    def item(selected, *, area=False):
        return dict(category=category, options=list(options), cases=list(selected),
                    case=selected[-1] if selected else None, area=area)
    if cases is None:
        return [item([])]
    if category != 'system':
        return [item([case]) for case in cases]
    groups = {}
    for case in cases:
        phase, _, logical = case.partition('::')
        area = phase in INDEPENDENT_SYSTEM_AREAS
        key = ('area', phase) if area else ('history', logical)
        groups.setdefault(key, []).append(case)
    return [item(selected, area=key[0] == 'area') for key, selected in groups.items()]


def work_key(work):
    return hashlib.sha256(json.dumps(work, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def claim(items, completed, claims, owner):
    """Caller holds its shared lock; claims stay owned until cleanup finishes."""
    active = {(work['category'], case) for work in items if work_key(work) in claims
              for case in work['cases']}
    for work in items:
        key = work_key(work)
        identities = {(work['category'], case) for case in work['cases']}
        if key not in completed and key not in claims and not identities & active:
            claims[key] = owner
            return work
    return None


def arguments(work):
    args = ['--resume', work['category'], *work['options']]
    if work['case'] is not None:
        args[1:1] = ['--resume-case=' + work['case'],
                     '--resume-area-only' if work['area'] else '--resume-case-only']
    return args


@contextmanager
def available_worker(vm, slots, stopped, *, needed=lambda: True):
    """Obtain the VM before a case slot, without changing process environment.

    Yield None when other workers drained this VM's work while it was queued.
    The ordinary reservation still verifies and owns the receipt in the child.
    """
    import launcher_reload
    from detached_launcher import Stopped
    from vm_pool import reservation
    def cancelled():
        return stopped() if callable(stopped) else stopped.is_set()
    def abort():
        return cancelled() or launcher_reload.pending() or not needed()
    with ExitStack() as lifetime:
        try:
            receipt = lifetime.enter_context(reservation(
                getattr(vm, 'name', vm), stopped=abort, bind=False))
        except KeyboardInterrupt:
            if launcher_reload.pending():
                raise launcher_reload.ReloadRequested
            if cancelled():
                raise Stopped
            yield None
            return
        while not slots.acquire(timeout=.1):
            if abort():
                if launcher_reload.pending():
                    raise launcher_reload.ReloadRequested
                if cancelled():
                    raise Stopped
                yield None
                return
        try:
            if launcher_reload.pending():
                raise launcher_reload.ReloadRequested
            if cancelled():
                raise Stopped
            yield receipt if needed() else None
        finally:
            slots.release()
