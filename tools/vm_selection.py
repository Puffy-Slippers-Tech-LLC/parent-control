"""Shared explicit VM selection for unprivileged development launchers."""

from pathlib import Path
import os
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/integration'))
import vm_config
sys.path.pop(0)

extract = vm_config.extract
arguments = vm_config.arguments
select = vm_config.select
selected = vm_config.selected
registry = vm_config.registry
VARIABLE = vm_config.VARIABLE


def check_binding(run, name):
    path = run / 'vm.json'
    previous = json.loads(path.read_text())['vm'] if path.exists() else None
    if previous != name:
        raise ValueError('vm-config: launcher requires its original --vm NAME')


def save_binding(run, name):
    from detached_launcher import atomic
    atomic(run / 'vm.json', {'vm': name})


def make_command(root, target, environment):
    """Decode literal Make variables; never interpolate a VM name into shell code."""
    if target not in ('all', 'all-verify', 'system', 'appsnapshot', 'watch'):
        raise ValueError('vm-config:unsupported Make target')
    name = environment.get('ONPC_MAKE_VM') or None
    if target == 'watch':
        if name is not None or environment.get('ONPC_WATCH_VM_ORIGIN', 'undefined') != 'undefined':
            raise ValueError('watch: VM parameter refused; watches all registered VMs')
        return [str(root / 'tools/watch')]
    options = []
    if target == 'system':
        if environment.get('ONPC_SYSTEM_VM_IMAGE'):
            raise ValueError('VM_IMAGE-refused; choose VM=NAME')
        for key, option in (('LIST', '--list'), ('QUALIFICATION_FAILURE', '--qualification-failure')):
            value = environment.get('ONPC_SYSTEM_' + key, '')
            if value not in ('', '1'):
                raise ValueError(key + '-must-be-1')
            if value:
                options.append(option)
        for key, option in (('ARTIFACT_DIR', '--artifacts'), ('AREA', '--area'), ('TEST', '--test')):
            value = environment.get('ONPC_SYSTEM_' + key, '')
            if value:
                options.extend((option, value))
    configured = vm_config.load(name) if name is not None or '--list' not in options else None
    vm_args = ['--vm', configured.name] if configured else []
    if target == 'appsnapshot':
        return [str(root / 'tools/prepare-appsnapshot'), *vm_args]
    return [str(root / 'tools/run-tests'), target, *options, *vm_args]


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3 or sys.argv[1] != '--from-make':
            raise ValueError('vm-config:internal Make entry only')
        command = make_command(Path(__file__).resolve().parents[1], sys.argv[2], os.environ)
        os.execv(command[0], command)
    except (ValueError, OSError) as error:
        sys.exit(str(error))
