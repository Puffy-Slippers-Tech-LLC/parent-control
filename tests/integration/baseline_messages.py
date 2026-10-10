"""Shared operator descriptions for baseline help and confirmation warnings."""

SNAPSHOT = 'onpc_baseline'
APP_SNAPSHOT_STEP = 'Delete all onpc-[version] app snapshots, including onpc-v[version], after confirmation or --y.'
FINAL_STEPS = (
    'Prepare the current online app snapshot through prepare-appsnapshot shared code.',
    'Restore onpc_baseline, leaving the VM powered off.',
    'Keep the exclusive VM lock throughout all preparation steps.',
)
MODE_STEPS = {
    'auto': (
        'Require the VM to be off and an existing accepted onpc_baseline.',
        APP_SNAPSHOT_STEP,
        'Restore onpc_baseline and boot the VM.',
        'Run the no-app prerequisite setup.',
        'Perform guest system updates (APT on Ubuntu, DNF5 on Fedora) and reboot if required.',
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
    return mode + ' mode:\n' + '\n'.join('  - ' + step for step in (*MODE_STEPS[mode], *FINAL_STEPS))


def help_message():
    return ('Choose tools/prepare-vm --mode auto or tools/prepare-vm --mode manual.\n\n'
            'Launcher/session work: include --y to suppress y/n confirmation.\n'
            'Use --vm NAME, ID, a comma-separated list, all-enabled (default), or all.\n'
            'Manual work: omit --y to keep confirmation. All safety checks still apply.\n\n'
            + '\n\n'.join(mode_message(mode) for mode in MODE_STEPS))
