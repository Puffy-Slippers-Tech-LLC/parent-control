"""Public disaster-recovery launchers; privileged paths come only from the registry."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from dev_privileges import check
from vm_selection import vm_config
from test_storage import scratch_descriptors

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
        'offline VMs/hosts are skipped). Archive copying/restoration is serial; restored VM '
        'preparation uses registry concurrency.'))
    args = parser.parse_args(argv)
    try:
        _, vms = vm_config.execution(args.vm)
        for vm in vms:
            vm_config.backup_root(vm=vm)
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        selector = ','.join(vm.name for vm in vms)
        from vm_pool import arguments as checkout_arguments, check_queue, reservation
        check_queue(vms)
        from host_dispatch import tool_host
        owner = tool_host(ROOT).name
        if any(vm.host.name != owner for vm in vms):
            if any(vm.host.name == owner for vm in vms):
                check(HELPER)
            from regression_process import Control
            import test_launcher
            # Finish every archive before preparation begins. The reservation's
            # routing sends only the archive helper operation to its VM host.
            with Control().installed() as control:
                for vm in vms:
                    with reservation(vm.name, stopped=control.stopped):
                        status = control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                            HELPER, tool, '--vm', vm.name], cwd=ROOT,
                            env=test_launcher.environment(ROOT), wait_on_cancel=True)
                    if status:
                        failure(tool, f'archive operation failed (status {status}); remaining archives preserved.')
                        return status
        else:
            check(HELPER)
            status = subprocess.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                HELPER, *checkout_arguments(), tool, '--vm', selector], cwd=ROOT,
                env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'},
                pass_fds=scratch_descriptors()).returncode
            if status:
                failure(tool, f'archive operation failed (status {status}); remaining archives preserved.')
                return status
        if action != 'restore':
            print(f'{tool}: SUCCESS: backed up {selector}.', flush=True)
            return status
        # The preparation launcher refreshes accepted helper pins after its queue.
        status = subprocess.run([str(ROOT / 'tools/prepare-vm'), '--vm', selector,
                                 '--mode', 'auto', '--y'], cwd=ROOT,
                                pass_fds=scratch_descriptors()).returncode
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
