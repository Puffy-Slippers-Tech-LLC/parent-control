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
    tool = 'backupvms' if action == 'backup' else 'restorevms'
    parser = FailureParser(prog=tool, description=(
        'Run prepare-baseline --mode auto, then back up powered-off registered VMs.' if action == 'backup' else
        'Restore the latest complete VM backups, preserving displaced files.'), allow_abbrev=False)
    parser.add_argument('--vm', default='all', help=(
        'VM name or ID, comma-separated names/IDs, all-enabled, or all (default; '
        'includes disabled VMs). Archive copying/restoration is serial; baseline '
        'preparation uses registry concurrency.'))
    args = parser.parse_args(argv)
    try:
        _, vms = vm_config.execution(args.vm)
        vm_config.backup_root()
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        check(HELPER)
        selector = ','.join(vm.name for vm in vms)
        if action == 'backup':
            status = subprocess.run([str(ROOT / 'tools/prepare-baseline'), '--vm', selector,
                                     '--mode', 'auto', '--y'], cwd=ROOT).returncode
            if status:
                failure(tool, 'baseline preparation failed; no backup was started.')
                return status
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
        # Refresh runtime helper pins through the sole setup entry point.
        status = subprocess.run([str(ROOT / 'setup.sh'), '--test-tools-only'], cwd=ROOT).returncode
        if status:
            failure(tool, 'VMs restored; helper refresh failed. Rerun '
                    './setup.sh --test-tools-only before VM maintenance/tests.')
        return status
    except (ValueError, OSError) as error:
        failure(tool, str(error))
        return 2
    except KeyboardInterrupt:
        failure(tool, 'interrupted; selected VMs were not all completed.')
        return 130
