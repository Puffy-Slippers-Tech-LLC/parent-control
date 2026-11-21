"""Pure finite VM inventory, ordering and prerequisite planning."""

import hashlib
import json
import os
import re
import subprocess


def case_inventory(root, category, options, *, vm=None, pass_fds=()):
    """Collect existing public identities without starting a VM."""
    if category == 'system':
        import test_launcher
        from test_commands import system_check_selection
        from test_storage import scratch_descriptors
        from vm_selection import selected
        check = system_check_selection(options)
        if check:
            cases = [check]
        else:
            command = [str(root / 'tools/run-tests'), 'system', *options,
                       '--vm', vm or selected().name, '--list']
            environment = test_launcher.environment(root)
            # Keep inspection on the controller's checkout under the sanitized environment.
            environment['ONPC_LAUNCHER_CONTROLLER_ROOT'] = str(root)
            try:
                result = subprocess.run(command, cwd=root, env=environment,
                                        capture_output=True, text=True, check=True,
                                        pass_fds=tuple(dict.fromkeys((*scratch_descriptors(), *pass_fds))))
            except subprocess.CalledProcessError as error:
                print((error.stdout or '')[-8000:] + (error.stderr or '')[-8000:], flush=True)
                raise
            cases = [match[1] for line in result.stdout.splitlines()
                     if (match := re.fullmatch(r'    (\S+::\S+) \[selected\](?: \[system-\d+\])?', line))]
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
    from vm_selection import vm_config
    if not vm_config.snap_tests_enabled():
        retained = [case for case in cases if re.search(r'(?:^|[_/-])snap(?:[_/-]|$)', case) is None]
        if len(retained) != len(cases):
            print(f'{category}: skipped {len(cases) - len(retained)} Snap cases (snap_tests_enabled=false)',
                  flush=True)
        cases = retained
    return cases


def work_items(category, options, cases, *, upgrade=None):
    """Keep independent areas and stateful system histories indivisible."""
    from test_checkpoint import INDEPENDENT_SYSTEM_AREAS
    def item(selected, *, area=False):
        if upgrade:
            selected = [case + upgrade for case in selected]
        return dict(category=category, options=list(options), cases=list(selected),
                    case=selected[-1] if selected else None, area=area,
                    **({'upgrade': upgrade} if upgrade else {}))
    if cases is None:
        return [item([])]
    if category != 'system':
        result = [item([case]) for case in cases]
        return result[::-1] if os.environ.get('ONPC_TEST_REVERSE') == '1' else result
    groups = {}
    reverse = os.environ.get('ONPC_TEST_REVERSE') == '1'
    for case in cases:
        if case.startswith('check_'):
            groups[('check', case)] = [case]
            continue
        phase, _, logical = case.partition('::')
        area = phase in INDEPENDENT_SYSTEM_AREAS
        key = ('case', case) if area and reverse else (('area', phase) if area else ('history', logical))
        groups.setdefault(key, []).append(case)
    result = [item(selected, area=key[0] == 'area') for key, selected in groups.items()]
    return result[::-1] if reverse else result


def work_key(work):
    return hashlib.sha256(json.dumps(work, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def arguments(work, *, worker=False):
    args = ['--resume', work['category'], *work['options']]
    if work['case'] is not None:
        case = work['case'].removesuffix(work.get('upgrade', '')) if worker else work['case']
        args[1:1] = ['--resume-case=' + case,
                     '--resume-area-only' if work['area'] else '--resume-case-only']
    return args


def replay_case(work, requested):
    """Rebind a focused source-release retry after the main build changes."""
    suffix = work.get('upgrade')
    if not suffix:
        return requested if requested in work['cases'] else None
    chosen_source = suffix.split('-to-', 1)[0]
    for case in work['cases']:
        raw = case.removesuffix(suffix)
        if requested == raw or requested.split('-to-', 1)[0] == raw + chosen_source:
            return case
