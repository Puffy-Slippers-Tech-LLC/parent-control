"""Standalone entry point for the recovery module used by run-tests."""
import argparse
import os
from pathlib import Path
import re
import sys

import test_activity
import test_retention
from test_recovery import cleanup, cleanup_host
from vm_selection import select, vm_config, BATCH


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--vm', help='VM name/ID, comma-separated list, all-enabled (default), or all; cleanup remains serial')
    scope.add_argument('--host-only', action='store_true', help='host retention only; no VM access')
    parser.add_argument('--discard-completed', action='store_true',
                        help='explicitly remove all completed execution-retention results; not workflow/session logs')
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument('--discard-unpublished-input', metavar='CHECK',
                        help='recover one evidenced interrupted qualification build; requires one explicit VM')
    recovery.add_argument('--transfer-batch-input', metavar='CHECK',
                          help='preserve and transfer one published batch-owned input to its explicit VM')
    args = parser.parse_args(argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        root = Path(__file__).resolve().parents[1]
        if args.discard_unpublished_input or args.transfer_batch_input:
            if args.host_only or args.discard_completed or not args.vm:
                raise ValueError('unpublished input recovery requires only one explicit VM and check selector')
            _, vms = vm_config.execution(args.vm)
            if len(vms) != 1 or args.vm in ('all', 'all-enabled'):
                raise ValueError('unpublished input recovery requires one explicit VM')
            selector = (args.discard_unpublished_input or args.transfer_batch_input).removesuffix('.py')
            if not re.fullmatch(r'check_[a-z][a-z0-9_]*', selector):
                raise ValueError('invalid qualification selector')
            from test_commands import qualification_input_options
            from test_storage import named_input
            options = qualification_input_options(root, selector)
            if options is None or options.get('upgrade_source'):
                raise ValueError('qualification has no ordinary artifact input declaration')
            os.environ.pop(BATCH, None)
            select(vms[0].name)
            with test_activity.activity(root, includes_host=True):
                path = named_input(**options)
                destination = test_retention.Store(test_activity.retention_path(root))
                if args.transfer_batch_input:
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
        os.environ.pop(BATCH, None)
        for vm in vms:
            select(vm.name)
            with test_activity.activity(root):
                if args.discard_completed:
                    from regression_process import category_run
                    from vm_selection import arguments
                    status = category_run(root, 'integration',
                        ['check_retained_runs_cleanup', *arguments()], pipe=False)
                    if status:
                        return status
                    test_retention.Store(test_activity.retention_path(root)).discard_completed(lambda paths: None)
                status = cleanup(root)
            if status:
                return status
        return cleanup_host(root)
    except (ValueError, OSError) as error:
        print('cleanup-e2e: ' + str(error), file=sys.stderr)
        return 2
