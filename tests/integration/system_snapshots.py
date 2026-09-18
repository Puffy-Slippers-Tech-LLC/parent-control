"""Installed-system starting states, using the E2E app-snapshot lease."""

from dataclasses import replace
import json
import shutil
import sys

import system_runner as system


def attempts(selection, *, fresh_install=False):
    """Keep lifecycle transitions together; restore before each installed area."""
    if fresh_install:
        return [(selection, False)]
    groups = [('installed', 'rebooted'), ('authorization',), ('enforcement',), ('session',)]
    result = []
    for phases in groups:
        selected = tuple(phase for phase in phases if phase in selection.phases)
        if selected:
            result.append((replace(selection, phases=selected,
                executions=tuple(item for item in selection.executions if item.phase in selected)),
                selected[0] not in ('installed', 'rebooted')))
    return result


def create_suite(source, guestfs, commands, *, verify_backing_bytes):
    # Reuse the same preparation/retention code as prepare-appsnapshot and E2E;
    # launching the public tool here would compete for our already-held lease.
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from suite_lease import Suite
    suite = Suite(lambda: (source, guestfs), verify_backing_bytes=verify_backing_bytes)
    suite.commands = commands
    return suite


def installed_case(installed):
    return {'preconditions': ['installed-digest-verified-product'] if installed else []}


def run_attempts(suite, directory, selection, manifest, selected_inputs_sha256, ledger,
                 *, fresh_install=False):
    from e2e_watch import running_display
    from vm_transport import Transport

    lease, source = suite.lease, suite.source
    planned = attempts(selection, fresh_install=fresh_install)
    results = directory / 'guest-results'
    results.mkdir(mode=0o700)
    for index, (selected, installed) in enumerate(planned):
        attempt = directory / ('attempt-' + selected.phases[0])
        attempt.mkdir(mode=0o700)
        shutil.copytree(directory / 'input', attempt / 'input')
        suite.next_case = (installed_case(planned[index + 1][1])
                           if index + 1 < len(planned) else None)
        try:
            with lease:
                with ledger.measure('preparation'):
                    if installed:
                        # prepare_case calls the shared preparation with overwrite=False
                        # and keeps the completed version snapshot across invocations.
                        suite.prepare_case(installed_case(True), directory, directory / 'input',
                            {'schema_version': 1, 'scope': 'system-installed-setup'}, root=system.ROOT)
                    else:
                        lease.prepare()
                with ledger.measure('bootstrap'):
                    host_key = system.bootstrap(suite.commands, lease, attempt, suite.guestfs)
                    lease.start()
                    hostname = system.address(source)
                (attempt / 'known-hosts').write_text(f'{hostname} {host_key}\n')
                config = {'directory': str(attempt), 'hostname': hostname, 'run': lease.state['run'],
                          'domain_uuid': source.uuid, 'domain_id': lease.view.domain_id}
                vm = Transport(config, suite.commands, guard=lambda _: lease.guard())
                lease.guard()
                with running_display(lease):
                    system.installed_run(vm, lease, attempt, selected, ledger,
                                         already_installed=installed)
                verify_result(attempt, manifest, selected_inputs_sha256, ledger)
                lease.guard()
        finally:
            # Each phase has its own JUnit filename. Keep all diagnostics under
            # the attempt and copy phase results for the existing suite evidence.
            captured = attempt / 'guest-results'
            if captured.exists():
                shutil.copytree(captured, results / attempt.name)
                for phase in selected.phases:
                    path = captured / (phase + '.xml')
                    if path.is_file():
                        shutil.copyfile(path, results / path.name)
        if suite.verified is not None:
            suite.verified.recheck()


def verify_result(directory, manifest, selected_inputs_sha256, ledger):
    try:
        result = json.loads((directory / 'guest-results/result.json').read_text())
        system.require(result['outcome'] == 'passed' and result['package_sha256'] ==
                       manifest['artifacts']['package']['sha256'] and
                       result['selected_inputs_sha256'] == selected_inputs_sha256,
                       'pytest:guest-evidence')
    except (OSError, json.JSONDecodeError, KeyError, TypeError, system.Error) as error:
        category = ('pytest:guest-evidence' if isinstance(error, system.Error)
                    else 'collection:missing-or-invalid-guest-result')
        ledger.fail_outcome('collection', category)
        raise system.Error(category) from error
