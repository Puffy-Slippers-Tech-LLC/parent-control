"""Public disaster-recovery launchers; privileged paths come only from the registry."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from dev_privileges import check
from vm_selection import vm_config

ROOT = Path(__file__).resolve().parents[1]
HELPER = '/usr/local/libexec/onpc-setup'


def failure(tool, message):
    print(f'\033[31m{tool}: FAILED: {message}\033[0m', file=sys.stderr, flush=True)


class FailureParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        failure(self.prog, message)
        self.exit(2)


def main(action, argv=None):
    tool = 'backupvm' if action == 'backup' else 'restorevm'
    parser = FailureParser(prog=tool, description=(
        'Restore the baseline, delete baseline/app snapshots, then back up powered-off VMs.' if action == 'backup' else
        'Restore complete VM backups, then run prepare-vm --mode auto.'), allow_abbrev=False)
    parser.add_argument('--vm', default='all', help=(
        'VM name or ID, comma-separated names/IDs, all-enabled, or all (default; '
        'includes disabled VMs). Archive copying/restoration is serial; restored VM '
        'preparation uses registry concurrency.'))
    args = parser.parse_args(argv)
    try:
        _, vms = vm_config.execution(args.vm)
        vm_config.backup_root()
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        check(HELPER)
        selector = ','.join(vm.name for vm in vms)
        status = subprocess.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            HELPER, tool, '--vm', selector], cwd=ROOT,
            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}).returncode
        if status:
            failure(tool, f'archive operation failed (status {status}); selected VMs were not all backed up.'
                    if action == 'backup' else f'restore operation failed (status {status}).')
            return status
        if action != 'restore':
            print(f'{tool}: SUCCESS: backed up {selector}.', flush=True)
            return status
        # The preparation launcher refreshes accepted helper pins after its queue.
        status = subprocess.run([str(ROOT / 'tools/prepare-vm'), '--vm', selector,
                                 '--mode', 'auto', '--y'], cwd=ROOT).returncode
        if status:
            failure(tool, 'VMs restored; automatic preparation failed. Rerun '
                    'tools/prepare-vm --vm ' + selector + ' --mode auto --y.')
        return status
    except (ValueError, OSError) as error:
        failure(tool, str(error))
        return 2
    except KeyboardInterrupt:
        failure(tool, 'interrupted; selected VMs were not all completed.')
        return 130
