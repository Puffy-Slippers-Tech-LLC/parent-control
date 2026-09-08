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


def preflight(argv, *, root=ROOT):
    """Read declarations only. Never import worker/VM code or create artifacts."""
    parser = ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--scenario')
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--qualify-transfer', action='store_true')
    args = parser.parse_args(argv)
    if args.qualify_transfer:
        if args.list or args.scenario is not None:
            raise ValueError('e2e:qualification-cannot-select-scenarios')
        validate_artifact_path(args.artifacts)
        if not args.artifacts.is_dir():
            raise ValueError('e2e:missing-artifact-directory')
        return {'mode': 'asset-transfer-qualification', 'artifacts': str(args.artifacts)}
    if args.list and args.artifacts is not None:
        raise ValueError('e2e:listing-does-not-use-artifacts')
    api = runpy.run_path(str(confined_file(root, 'tests/e2e/inventory.py')))
    document, digest = api['read_json'](confined_file(root, 'tests/e2e/scenarios.json'))
    plan = api['resolve_selection'](document, args.scenario,
                                    require_runnable=not args.list, root=root)
    plan['inventory_sha256'] = digest
    plan['mode'] = 'list-only' if args.list else 'execution-preflight'
    if args.list:
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
    if path is None:
        raise ValueError('e2e:artifacts-required')
    if (not path.is_absolute() or '..' in path.parts
            or not any(path.is_relative_to(base) and len(path.parts) > len(base.parts)
                       and re.fullmatch(r'onpc-[A-Za-z0-9_.-]+', path.parts[len(base.parts)])
                       for base in (Path('/tmp'), Path('/var/tmp')))
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
        plan = preflight(argv)
        if plan['mode'] == 'asset-transfer-qualification':
            sys.path.insert(0, str(ROOT / 'tests/integration'))
            import check_graphical_smoke
            return check_graphical_smoke.main(assets=Path(plan['artifacts']))
        if plan['mode'] == 'execution-preflight':
            sys.path.insert(0, str(ROOT / 'tests/e2e'))
            import execution
            return execution.main(plan)
        print(json.dumps(plan, indent=2))
        return 0
    except (ValueError, OSError) as error:
        detail = str(error) if isinstance(error, ValueError) else 'e2e:input-or-execution-failure'
        print(detail, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
