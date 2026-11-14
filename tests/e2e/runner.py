"""Host-safe E2E preflight and dispatch to the guarded scenario controller.

Preflight is repeated by the category dispatcher before any privilege check or
cleanup prerequisite. It cannot turn worker diagnostics into scenario evidence.
"""

import argparse
import json
import os
from pathlib import Path
import re
import runpy
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
import test_account_password as password_config
import vm_config
sys.path.pop(0)


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's normal message can echo a credential-bearing caller value.
        raise ValueError('e2e:invalid-arguments; use --help')


def confined_file(root, relative):
    path = root / relative
    if (any(part.is_symlink() for part in (path, *path.parents))
            or not path.is_file() or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError('e2e:missing-or-unsafe-input')
    return path


def preflight(argv, *, root=ROOT, allow_missing_artifacts=False):
    """Read declarations only. Never import worker/VM code or create artifacts."""
    argv, configured = vm_config.extract(argv, required=False, path=root / 'config/environment.json')
    parser = ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--vm', help='required configured VM name or ID; optional for --list')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--subcategory', help='select one registered E2E subcategory')
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument('--scenario', help='exact E2E-NNN family or E2E-NNN/variant')
    selectors.add_argument('--id', help='comma-separated numeric case IDs in docs/Test-Coverage.md')
    selectors.add_argument('--ready', action='store_true', help='run all ready variants; report pending exclusions')
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--fixture-selection', help=argparse.SUPPRESS)
    parser.add_argument('--skip-backing-verification', action='store_true',
                        help='compatibility option; VM verification is always metadata-only')
    qualification = parser.add_mutually_exclusive_group()
    qualification.add_argument('--qualify-transfer', action='store_true')
    qualification.add_argument('--qualify-install', action='store_true')
    qualification.add_argument('--qualify-install-refusal', action='store_true')
    qualification.add_argument('--qualify-lunar-profile', action='store_true')
    qualification.add_argument('--qualify-lunar-launch-quit', action='store_true')
    qualification.add_argument('--qualify-lunar-tray', action='store_true')
    qualification.add_argument('--qualify-lunar-autostart', action='store_true')
    qualification.add_argument('--qualify-lunar-denial', action='store_true')
    qualification.add_argument('--qualify-lunar-login-denial', action='store_true')
    qualification.add_argument('--qualify-minecraft-entry-exit', action='store_true')
    qualification.add_argument('--qualify-minecraft-access', action='store_true')
    args = parser.parse_args(argv)
    if (args.qualify_lunar_profile or args.qualify_lunar_launch_quit or args.qualify_lunar_tray
            or args.qualify_lunar_denial or args.qualify_minecraft_entry_exit
            or args.qualify_minecraft_access or args.qualify_lunar_autostart
            or args.qualify_lunar_login_denial):
        if (args.list or args.scenario is not None or args.id is not None or args.ready
                or args.fixture_selection is not None and not (
                    args.qualify_lunar_denial or args.qualify_lunar_login_denial
                    or args.qualify_minecraft_access)):
            raise ValueError('e2e:qualification-cannot-select-scenarios')
        if args.subcategory not in (None, 'e2e-heavy'):
            raise ValueError('e2e:lunar-profile-requires-heavy-subcategory')
        password_config.read_password()
        if args.artifacts is not None or not allow_missing_artifacts:
            validate_artifact_path(args.artifacts)
            if not args.artifacts.is_dir():
                raise ValueError('e2e:missing-artifact-directory')
        selection = None
        if args.fixture_selection is not None:
            if len(args.fixture_selection) > 8192:
                raise ValueError('e2e:invalid-fixture-selection')
            sys.path.insert(0, str(root / 'tools'))
            try:
                from fixture_execution import Selection
            finally:
                sys.path.pop(0)
            selection = Selection.from_record(json.loads(args.fixture_selection)).record()
        return {'mode': ('lunar-login-denial-qualification' if args.qualify_lunar_login_denial else
                         'lunar-autostart-qualification' if args.qualify_lunar_autostart else
                         'minecraft-access-qualification' if args.qualify_minecraft_access else
                         'minecraft-entry-exit-qualification' if args.qualify_minecraft_entry_exit else
                         'lunar-denial-qualification' if args.qualify_lunar_denial else
                         'lunar-tray-qualification' if args.qualify_lunar_tray else
                         'lunar-launch-quit-qualification' if args.qualify_lunar_launch_quit
                         else 'lunar-profile-qualification'), 'subcategory': 'e2e-heavy',
                **({'artifacts': str(args.artifacts)} if args.artifacts is not None else {}),
                **({'fixture_selection': selection} if selection is not None else {})}
    if (args.qualify_transfer or args.qualify_install or args.qualify_install_refusal) and (
            args.list or args.scenario is not None or args.id is not None or args.ready
            or args.subcategory is not None):
        raise ValueError('e2e:qualification-cannot-select-scenarios')
    fixture_selection = None
    serial = args.qualify_install or args.qualify_install_refusal
    if serial and configured is not None and configured.name not in vm_config.fixture_targets(root / 'config/environment.json'):
        raise ValueError('fixtures:serial-target-not-qualified')
    if args.fixture_selection is not None:
        if (args.list
                or configured is not None and configured.name not in vm_config.fixture_targets(root / 'config/environment.json')):
            raise ValueError('e2e:unexpected-fixture-selection')
        if len(args.fixture_selection) > 8192:
            raise ValueError('e2e:invalid-fixture-selection')
        sys.path.insert(0, str(root / 'tools'))
        try:
            from fixture_execution import Selection
        finally:
            sys.path.pop(0)
        selected = Selection.from_record(json.loads(args.fixture_selection))
        targets = vm_config.fixture_targets(root / 'config/environment.json')
        if (selected.target not in targets.values() or configured is not None
                and selected.target != targets.get(configured.name)):
            raise ValueError('e2e:fixture-target-not-qualified')
        fixture_selection = selected.record()
        if serial and selected.target not in ('ubuntu', 'fedora'):
            raise ValueError('fixtures:serial-target-not-qualified')
    if serial and fixture_selection is None and not allow_missing_artifacts:
        raise ValueError('fixtures:execution-selection-required')
    if args.qualify_transfer:
        if configured is not None and configured.name not in vm_config.fixture_targets(root / 'config/environment.json'):
            raise ValueError('fixtures:transfer-target-not-qualified')
        if fixture_selection is None:
            if not allow_missing_artifacts:
                raise ValueError('fixtures:execution-selection-required')
        elif fixture_selection['target'] not in ('ubuntu', 'fedora'):
            raise ValueError('fixtures:transfer-target-not-qualified')
    if not args.list:
        password_config.read_password()
    if args.qualify_transfer or args.qualify_install or args.qualify_install_refusal:
        if args.list or args.scenario is not None or args.id is not None or args.ready:
            raise ValueError('e2e:qualification-cannot-select-scenarios')
        if args.artifacts is not None or not allow_missing_artifacts:
            validate_artifact_path(args.artifacts)
            if not args.artifacts.is_dir():
                raise ValueError('e2e:missing-artifact-directory')
        return {'mode': ('deliberate-installation-refusal-qualification'
                         if args.qualify_install_refusal else
                         'authenticated-installation-qualification' if args.qualify_install
                         else 'asset-transfer-qualification'),
                **({'artifacts': str(args.artifacts)} if args.artifacts is not None else {}),
                **({'fixture_selection': fixture_selection} if fixture_selection is not None else {})}
    if args.list and args.artifacts is not None:
        raise ValueError('e2e:listing-does-not-use-artifacts')
    api = runpy.run_path(str(confined_file(root, 'tests/e2e/inventory.py')))
    document, digest = api['read_json'](confined_file(root, 'tests/e2e/scenarios.json'))
    ready_only = args.ready or (not args.list and args.scenario is None and args.id is None)
    try:
        plan = api['resolve_selection'](document, args.scenario, ready_only=ready_only,
                                        coverage_id=args.id,
                                        subcategory=args.subcategory,
                                        require_runnable=not args.list, root=root)
    except api['InventoryError'] as error:
        if str(error) == 'selection:pending':
            # Diagnose the exact refused in-memory selection without rereading
            # a changing inventory or relaxing the execution refusal.
            refused = api['resolve_selection'](document, args.scenario,
                ready_only=ready_only, coverage_id=args.id, subcategory=args.subcategory, root=root)
            error.add_note('e2e:pending-selection ' + json.dumps({
                'inventory_sha256': digest,
                'selector_kind': 'id' if args.id is not None else 'scenario' if args.scenario else 'ready',
                'selector': refused['selector'],
                'selected_count': len(refused['cases']),
                'selected': [{key: case[key] for key in ('coverage_id', 'case_id', 'status')}
                             for case in refused['cases'][:16]],
                'snapshot_active': getattr(sys.modules.get('tools.vm_source_snapshot'),
                                           '_active', None) is not None,
            }, sort_keys=True))
        raise
    plan['inventory_sha256'] = digest
    plan['mode'] = 'list-only' if args.list else 'execution-preflight'
    if fixture_selection is not None:
        plan['fixture_selection'] = fixture_selection
    if args.list:
        return plan
    if args.artifacts is None and allow_missing_artifacts:
        return plan
    validate_artifact_path(args.artifacts)
    if not args.artifacts.is_dir():
        raise ValueError('e2e:missing-artifact-directory')
    for case in plan['cases']:
        path = confined_file(root, case['executable']['path'])
        if path.suffix != '.py':
            raise ValueError('e2e:python-controller-callback-required')
    plan['artifacts'] = str(args.artifacts)
    return plan


def validate_artifact_path(path):
    # Direct and runpy entry points need not have the checkout on sys.path.
    sys.path.insert(0, str(ROOT))
    try:
        from tools.test_storage import storage_root
        storage = storage_root(ROOT) / 'output/test-runs'
    finally:
        sys.path.pop(0)
    if path is None:
        raise ValueError('e2e:artifacts-required')
    if (not path.is_absolute() or '..' in path.parts
            or not any(path.is_relative_to(base) and len(path.parts) > len(base.parts)
                       and re.fullmatch(r'onpc-[A-Za-z0-9_.-]+', path.parts[len(base.parts)])
                       for base in (Path('/tmp'), Path('/var/tmp'), storage / 'host/allocations',
                                    storage / 'privileged/allocations'))
            or any(part.is_symlink() for part in (path, *path.parents))):
        raise ValueError('e2e:invalid-artifact-directory')


def make_arguments(environment):
    """Decode literal Make values without putting caller values in shell code."""
    if environment.get('ONPC_E2E_VM_IMAGE', ''):
        raise ValueError('e2e:VM_IMAGE-refused; only the guarded fixed baseline is supported')
    listing = environment.get('ONPC_E2E_LIST', '')
    if listing not in ('', '1'):
        raise ValueError('e2e:LIST-must-be-1')
    argv = ['--list'] if listing else []
    name = environment.get('ONPC_E2E_VM') or None
    configured = vm_config.load(name) if name is not None or not listing else None
    if configured is not None:
        argv.extend(('--vm', configured.name))
    for variable, option in (('ARTIFACT_DIR', 'artifacts'), ('SCENARIO', 'scenario')):
        value = environment.get('ONPC_E2E_' + variable, '')
        if value:
            argv.append(f'--{option}={value}')
    return argv


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv == ['--from-make']:
            arguments = make_arguments(os.environ)
            # Use exactly the approved category path, including its clean
            # environment and privilege gates when execution is implemented.
            launcher = confined_file(ROOT, 'tools/run-tests')
            os.execv(str(launcher), [str(launcher), 'e2e', *arguments])
            return 0
        argv, _ = vm_config.extract(argv, required='--list' not in argv)
        plan = preflight(argv)
        if plan['mode'] == 'list-only':
            print(json.dumps(plan, indent=2))
            return 0
        requested_run = os.environ.get('ONPC_QUALIFICATION_RETENTION_RUN')
        if requested_run is not None and not re.fullmatch('[0-9a-f]{32}', requested_run):
            raise ValueError('retention: invalid qualification run')
        sys.path.insert(0, str(ROOT / 'tests/integration'))
        import qualification_storage
        with qualification_storage.session(run=requested_run, require_owner=True):
            if plan['mode'] in ('lunar-profile-qualification', 'lunar-launch-quit-qualification',
                                'lunar-tray-qualification', 'lunar-autostart-qualification',
                                'lunar-denial-qualification', 'lunar-login-denial-qualification',
                                'minecraft-entry-exit-qualification', 'minecraft-access-qualification'):
                import lunar_profile_qualification
                return lunar_profile_qualification.main(assets=Path(plan['artifacts']),
                    launch_quit=plan['mode'] == 'lunar-launch-quit-qualification',
                    tray=plan['mode'] == 'lunar-tray-qualification',
                    autostart=plan['mode'] == 'lunar-autostart-qualification',
                    denial=plan['mode'] == 'lunar-denial-qualification',
                    login_denial=plan['mode'] == 'lunar-login-denial-qualification',
                    minecraft=plan['mode'] == 'minecraft-entry-exit-qualification',
                    minecraft_access=plan['mode'] == 'minecraft-access-qualification',
                    fixture_selection=plan.get('fixture_selection'))
            if plan['mode'] in ('asset-transfer-qualification', 'authenticated-installation-qualification',
                                'deliberate-installation-refusal-qualification'):
                import check_graphical_smoke
                if plan['mode'] == 'authenticated-installation-qualification':
                    return check_graphical_smoke.main(assets=Path(plan['artifacts']),
                                                     provision_credentials=True, serial=True, install=True,
                                                     fixture_selection=plan['fixture_selection'])
                if plan['mode'] == 'deliberate-installation-refusal-qualification':
                    return check_graphical_smoke.main(assets=Path(plan['artifacts']),
                                                     provision_credentials=True, serial=True,
                                                     install_refusal=True,
                                                     fixture_selection=plan['fixture_selection'])
                return check_graphical_smoke.main(assets=Path(plan['artifacts']),
                    transfer_qualification=True, fixture_selection=plan['fixture_selection'])
            if plan['mode'] == 'execution-preflight':
                sys.path.insert(0, str(ROOT / 'tests/e2e'))
                import execution
                return execution.main(plan)
    except (ValueError, OSError) as error:
        detail = str(error) if isinstance(error, ValueError) else 'e2e:input-or-execution-failure'
        print(detail, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
