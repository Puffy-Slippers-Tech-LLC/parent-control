"""Shared operator descriptions for baseline help and confirmation warnings."""

SNAPSHOT = 'onpc_baseline'
APP_SNAPSHOT_STEP = 'Delete all onpc-[version] app snapshots, including onpc-v[version], after confirmation.'
MODE_STEPS = {
    'auto': (
        'Require the VM to be off and an existing accepted onpc_baseline.',
        APP_SNAPSHOT_STEP,
        'Restore onpc_baseline and boot the VM.',
        'Run the no-app prerequisite setup.',
        'Perform Ubuntu system updates and reboot if required.',
        'Shut down the VM and validate preparation.',
        'Replace the old onpc_baseline with a new onpc_baseline snapshot.',
    ),
    'manual': (
        'Require the VM to be off.',
        APP_SNAPSHOT_STEP,
        'Boot the VM from its current state.',
        'Run the no-app prerequisite setup.',
        'Shut down the VM and validate preparation.',
        'Take a new onpc_baseline snapshot, replacing the existing one if present.',
    ),
}


def mode_message(mode):
    return mode + ' mode:\n' + '\n'.join('  - ' + step for step in MODE_STEPS[mode])


def help_message():
    return ('Choose tools/prepare-baseline --mode auto or tools/prepare-baseline --mode manual.\n\n'
            + '\n\n'.join(mode_message(mode) for mode in MODE_STEPS))
