"""Standalone entry point for the recovery module used by run-tests."""
import argparse
import os
from pathlib import Path
import re
import sys
from contextlib import nullcontext

import test_activity
import test_retention
import test_source
from test_recovery import cleanup, cleanup_host
from vm_selection import select, vm_config, BATCH
from vm_pool import Busy, reservation, check_queue


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--vm', help='VM name/ID, comma-separated list, all-enabled (default), or all; cleanup remains serial')
    scope.add_argument('--host-only', action='store_true', help='host retention only; no VM access')
    parser.add_argument('--vm-only', action='store_true',
                        help='recover explicit --vm selection without host retention cleanup')
    parser.add_argument('--discard-completed', action='store_true',
                        help='explicitly remove all completed execution-retention results; not workflow/session logs')
    parser.add_argument('--if-available', action='store_true',
                        help='return status 75 if VM checkout is busy; preserve recovery for a later run')
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument('--discard-unpublished-input', metavar='CHECK',
                        help='recover one evidenced interrupted qualification build; requires one explicit VM')
    recovery.add_argument('--transfer-batch-input', metavar='CHECK',
                          help='preserve and transfer one published batch-owned input to its explicit VM')
    recovery.add_argument('--transfer-batch-appsnapshot', metavar='ALLOCATION',
                          help='transfer one evidenced standalone snapshot package allocation by basename')
    args = vm_config.parse_vm_arguments(parser, argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        if args.vm_only and (not args.vm or args.host_only):
            raise ValueError('--vm-only requires an explicit --vm selection')
        if args.if_available and (args.host_only or args.discard_completed
                or args.discard_unpublished_input or args.transfer_batch_input
                or args.transfer_batch_appsnapshot):
            raise ValueError('--if-available requires ordinary VM cleanup')
        root = Path(__file__).resolve().parents[1]
        def remote_cleanup(vm):
            from host_dispatch import vm_tool
            options = ['--vm', vm.name, '--vm-only']
            for name in ('discard_completed', 'if_available'):
                if getattr(args, name):
                    options.append('--' + name.replace('_', '-'))
            for name in ('discard_unpublished_input', 'transfer_batch_input', 'transfer_batch_appsnapshot'):
                if getattr(args, name):
                    options += ['--' + name.replace('_', '-'), getattr(args, name)]
            return vm_tool(root, vm, 'cleanup-e2e', options)
        snapshot = args.transfer_batch_appsnapshot
        transferring = bool(args.transfer_batch_input or snapshot)
        if args.discard_unpublished_input or transferring:
            if args.host_only or args.discard_completed or not args.vm:
                raise ValueError('input recovery requires only one explicit VM and input selector')
            _, vms = vm_config.execution(args.vm)
            if len(vms) != 1 or args.vm in ('all', 'all-enabled'):
                raise ValueError('unpublished input recovery requires one explicit VM')
            if snapshot:
                if not re.fullmatch(r'onpc-test-artifacts-[A-Za-z0-9_-]+', snapshot):
                    raise ValueError('invalid standalone snapshot allocation basename')
                selector = 'prepare_appsnapshot'
            else:
                selector = (args.discard_unpublished_input or args.transfer_batch_input).removesuffix('.py')
                if not re.fullmatch(r'check_[a-z][a-z0-9_]*', selector):
                    raise ValueError('invalid qualification selector')
                from test_commands import qualification_input_options
                options = qualification_input_options(root, selector)
                if options is None or options.get('upgrade_source'):
                    raise ValueError('qualification has no ordinary artifact input declaration')
            status = remote_cleanup(vms[0])
            if status is not None:
                return status
            os.environ.pop(BATCH, None)
            select(vms[0].name)
            with (reservation(vms[0].name) if transferring else nullcontext()), \
                    test_activity.activity(root, includes_host=True):
                from test_storage import named_input, directory
                path = directory('allocations', root=root) / snapshot if snapshot else named_input(**options)
                destination = test_retention.Store(test_activity.retention_path(root))
                if transferring:
                    from test_input_transfer import transfer
                    from vm_artifacts import prepare
                    from regression_process import Control
                    import test_launcher
                    source = test_retention.Store(destination.path.with_name('retention-batch'))
                    with Control().installed(pipe=False) as control:
                        changed = transfer(source, destination, path, selector=selector, vm=vms[0].name,
                            verify=lambda candidate: prepare(root, control, test_launcher.environment(root),
                                                            candidate=candidate, output=candidate))
                    print('cleanup-e2e: published input ownership ' +
                          ('transferred' if changed else 'already transferred'), flush=True)
                    return 0
                removed = destination.discard_unpublished_input(path)
            print('cleanup-e2e: unpublished input ' + ('removed' if removed else 'already removed'), flush=True)
            return 0
        if args.host_only:
            if args.discard_completed:
                with test_activity.activity(root, host_only=True):
                    test_retention.Store(test_activity.retention_path(root)).discard_completed(lambda paths: None)
            return cleanup_host(root)
        _, vms = vm_config.execution(args.vm)
        check_queue(vms)
        os.environ.pop(BATCH, None)
        for vm in vms:
            select(vm.name)
            # Acquire the VM first, then borrow recovery source without waiting
            # on a writer that may itself need this VM. Keep this scope around
            # remote dispatch and explicit retirement as well as ordinary cleanup.
            with reservation(vm.name, wait=not args.if_available), test_activity.activity(root), \
                    test_source.startup(root, ['--resume'], repair=True, wait=False):
                status = remote_cleanup(vm)
                if status is None and args.discard_completed:
                    from regression_process import category_run
                    from vm_selection import arguments
                    status = category_run(root, 'system',
                        ['check_retained_runs_cleanup', *arguments()], pipe=False)
                    if status:
                        return status
                    test_retention.Store(test_activity.retention_path(root)).discard_completed(lambda paths: None)
                    status = None
                if status is None:
                    status = cleanup(root)
                if not status:
                    from test_checkpoint import recover_family_claims
                    recovered = recover_family_claims(root, vm.name)
                    if recovered:
                        print(f'cleanup-e2e: returned {recovered} interrupted family cases to pending', flush=True)
            if status:
                return status
        return 0 if args.vm_only else cleanup_host(root)
    except (Busy, test_source.SourceBusy) as error:
        print('cleanup-e2e: ' + str(error), file=sys.stderr)
        return Busy.status
    except (ValueError, OSError) as error:
        print('cleanup-e2e: ' + str(error), file=sys.stderr)
        return 2
