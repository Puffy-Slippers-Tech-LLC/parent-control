"""Installed-system starting states, using the E2E app-snapshot lease."""

from dataclasses import replace
import json
import shutil
import sys

import system_runner as system


def attempts(selection, *, fresh_install=False):
    """Keep lifecycle transitions together; restore before each installed area."""
    full = system.REMOVAL_HISTORIES[0]
    lifecycle = ('previous-policy', *full.prerequisites, *full.phases)
    independent = (system.SIBLING_PHASE, system.REQUIRED_PHASE, *system.RETAINED_PHASES,
                   'authorization', 'enforcement', 'session')
    groups = ([((*lifecycle, *independent), False)] if fresh_install else
              [(lifecycle, full.start == 'installed'), *(((phase,), True) for phase in independent)])
    # Each destructive focused history starts from its own product-free
    # baseline, even when an earlier history erased or purged the product.
    groups[1:1] = [((*history.prerequisites, *history.phases), history.start == 'installed')
                   for history in system.REMOVAL_HISTORIES[1:]]
    groups.insert(1, (system.FIRST_CONFIGURE_PHASES, False))
    groups[2:2] = [(history.phases, False) for history in system.PAM_HISTORIES]
    groups.append(((system.TRUSTED_FIXTURES_PHASE,), False))
    groups.append((system.NATIVE_UPDATE_PHASES, False))
    result = []
    for phases, installed in groups:
        selected = tuple(phase for phase in phases if phase in selection.phases)
        if selected:
            result.append((replace(selection, phases=selected,
                executions=tuple(item for item in selection.executions if item.phase in selected)),
                installed))
    return result


def create_suite(source, guestfs, commands):
    # Reuse the same preparation/retention code as prepare-appsnapshot and E2E;
    # launching the public tool here would compete for our already-held lease.
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from suite_lease import Suite
    suite = Suite(lambda: (source, guestfs))
    suite.commands = commands
    return suite


def installed_case(installed):
    return {'preconditions': ['installed-digest-verified-product'] if installed else []}


def run_attempts(suite, directory, selection, manifest, selected_inputs_sha256, ledger,
                 *, fresh_install=False, native_artifacts=None):
    from system_progress import watching
    planned = attempts(selection, fresh_install=fresh_install)
    # Lifecycle histories can run in a different order from the phase registry.
    # Count every selected/prerequisite execution in its actual attempt order.
    executions = tuple(item for selected, _ in planned for item in selected.executions)
    with watching(executions, suite.lease) as progress:
        return _run_attempts(suite, directory, selection, manifest, selected_inputs_sha256,
                             ledger, planned=planned, progress=progress,
                             native_artifacts=native_artifacts)


def _run_attempts(suite, directory, selection, manifest, selected_inputs_sha256, ledger,
                  *, planned, progress, native_artifacts=None):
    from vm_transport import Transport
    from guest_inputs import Bundle

    lease, source = suite.lease, suite.source
    # Snapshot setup uses the same recipe/helpers frozen before VM acquisition,
    # even if the checkout changes during preceding package lifecycle tests.
    suite._input_bundle = Bundle.from_staged(system.ROOT, directory / 'input')
    results = directory / 'guest-results'
    results.mkdir(mode=0o700)
    for index, (selected, installed) in enumerate(planned):
        progress.prepare_execution(selected.executions[0])
        attempt = directory / ('attempt-' + selected.phases[0])
        attempt.mkdir(mode=0o700)
        shutil.copytree(directory / 'input', attempt / 'input')
        suite.next_case = (installed_case(planned[index + 1][1])
                           if index + 1 < len(planned) else None)
        try:
            with lease:
                with ledger.measure('preparation'):
                    system.verify_history_target(selected, lease.capture)
                    if installed:
                        # prepare_case calls the shared preparation with overwrite=False
                        # and keeps the completed version snapshot across invocations.
                        suite.prepare_case(installed_case(True), directory, directory / 'input',
                            {'schema_version': 1, 'scope': 'system-installed-setup'}, root=system.ROOT)
                    else:
                        lease.prepare()
                    if system.NATIVE_UPDATE_PHASES[0] in selected.phases:
                        system.require(not installed and native_artifacts is not None,
                                       'selection:native-update-requires-native-artifacts')
                        system.require(system.native_update_host_inputs() == json.loads(
                            (attempt / 'input/selected-inputs.json').read_bytes())['host_files'],
                            'native-update:host-inputs-changed')
                        system.stage_native_assets(native_artifacts, attempt / 'input',
                            package_format=system.package_format(lease.capture.state['guest']),
                            baseline_provenance_sha256=lease.state['baseline_sha256'],
                            selected_inputs_sha256=selected_inputs_sha256)
                        inventory = {str(path.relative_to(attempt / 'input')):
                                     system.baseline.digest(path)
                                     for path in sorted((attempt / 'input').rglob('*'))
                                     if path.is_file() and path.name != 'transfer-sha256.json'}
                        (attempt / 'input/transfer-sha256.json').write_bytes(
                            system.baseline.encode(inventory))
                with ledger.measure('bootstrap'):
                    host_key = system.bootstrap(suite.commands, lease, attempt, suite.guestfs)
                    lease.start()
                    hostname = system.address(source)
                (attempt / 'known-hosts').write_text(f'{hostname} {host_key}\n')
                config = {'directory': str(attempt), 'hostname': hostname, 'run': lease.state['run'],
                          'domain_uuid': source.uuid, 'domain_id': lease.view.domain_id}
                vm = Transport(config, suite.commands, guard=lambda _: lease.guard(), lease=lease)
                lease.guard()
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
