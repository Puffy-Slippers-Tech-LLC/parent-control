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
    argv, configured = vm_config.extract(argv, required=False, path=root / 'config/test-vm.json')
    parser = ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--vm', help='required configured VM name or ID; optional for --list')
    parser.add_argument('--list', action='store_true')
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
    args = parser.parse_args(argv)
    fixture_selection = None
    if args.fixture_selection is not None:
        if (args.list or args.qualify_transfer or args.qualify_install or args.qualify_install_refusal
                or configured is not None and configured.name != 'onpc-Ubuntu26.04'):
            raise ValueError('e2e:unexpected-fixture-selection')
        if len(args.fixture_selection) > 8192:
            raise ValueError('e2e:invalid-fixture-selection')
        sys.path.insert(0, str(root / 'tools'))
        try:
            from fixture_execution import Selection
        finally:
            sys.path.pop(0)
        selected = Selection.from_record(json.loads(args.fixture_selection))
        if selected.target != 'ubuntu':
            raise ValueError('e2e:fixture-target-not-qualified')
        fixture_selection = selected.record()
    if not args.list:
        password_config.read_password(root)
    if args.qualify_transfer or args.qualify_install or args.qualify_install_refusal:
        if args.list or args.scenario is not None or args.id is not None or args.ready:
            raise ValueError('e2e:qualification-cannot-select-scenarios')
        validate_artifact_path(args.artifacts)
        if not args.artifacts.is_dir():
            raise ValueError('e2e:missing-artifact-directory')
        return {'mode': ('deliberate-installation-refusal-qualification'
                         if args.qualify_install_refusal else
                         'authenticated-installation-qualification' if args.qualify_install
                         else 'asset-transfer-qualification'), 'artifacts': str(args.artifacts)}
    if args.list and args.artifacts is not None:
        raise ValueError('e2e:listing-does-not-use-artifacts')
    api = runpy.run_path(str(confined_file(root, 'tests/e2e/inventory.py')))
    document, digest = api['read_json'](confined_file(root, 'tests/e2e/scenarios.json'))
    ready_only = args.ready or (not args.list and args.scenario is None and args.id is None)
    plan = api['resolve_selection'](document, args.scenario, ready_only=ready_only,
                                    coverage_id=args.id,
                                    require_runnable=not args.list, root=root)
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
    storage = ROOT / 'output/test-runs'
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
            if plan['mode'] in ('asset-transfer-qualification', 'authenticated-installation-qualification',
                                'deliberate-installation-refusal-qualification'):
                import check_graphical_smoke
                if plan['mode'] == 'authenticated-installation-qualification':
                    return check_graphical_smoke.main(assets=Path(plan['artifacts']),
                                                     provision_credentials=True, serial=True, install=True)
                if plan['mode'] == 'deliberate-installation-refusal-qualification':
                    return check_graphical_smoke.main(assets=Path(plan['artifacts']),
                                                     provision_credentials=True, serial=True,
                                                     install_refusal=True)
                return check_graphical_smoke.main(assets=Path(plan['artifacts']))
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
