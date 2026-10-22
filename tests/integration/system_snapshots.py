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
    independent = ('authorization', 'enforcement', 'session')
    groups = ([((*lifecycle, *independent), False)] if fresh_install else
              [(lifecycle, full.start == 'installed'), *(((phase,), True) for phase in independent)])
    # Each destructive focused history starts from its own product-free
    # baseline, even when an earlier history erased or purged the product.
    groups[1:1] = [((*history.prerequisites, *history.phases), history.start == 'installed')
                   for history in system.REMOVAL_HISTORIES[1:]]
    groups.insert(1, (system.FIRST_CONFIGURE_PHASES, False))
    groups[2:2] = [(history.phases, False) for history in system.PAM_HISTORIES]
    groups.append(((system.TRUSTED_FIXTURES_PHASE,), False))
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
                 *, fresh_install=False, fixture_selection=None, preparation_only=False,
                 preparation_observer=None):
    from system_progress import watching
    planned = attempts(selection, fresh_install=fresh_install)
    # Lifecycle histories can run in a different order from the phase registry.
    # Count every selected/prerequisite execution in its actual attempt order.
    executions = tuple(item for selected, _ in planned for item in selected.executions)
    with watching(executions, suite.lease) as progress:
        options = ({'fixture_selection': fixture_selection,
                    'preparation_only': preparation_only,
                    'preparation_observer': preparation_observer}
                   if fixture_selection is not None or preparation_only else {})
        return _run_attempts(suite, directory, selection, manifest, selected_inputs_sha256,
                             ledger, planned=planned, progress=progress, **options)


def _run_attempts(suite, directory, selection, manifest, selected_inputs_sha256, ledger,
                  *, planned, progress, fixture_selection=None, preparation_only=False,
                  preparation_observer=None):
    from vm_transport import Transport
    from guest_inputs import Bundle

    lease, source = suite.lease, suite.source
    # Snapshot setup uses the same recipe/helpers frozen before VM acquisition,
    # even if the checkout changes during preceding package lifecycle tests.
    suite._input_bundle = Bundle.from_staged(system.ROOT, directory / 'input')
    results = directory / 'guest-results'
    results.mkdir(mode=0o700)
    prepared = []
    for index, (selected, installed) in enumerate(planned):
        progress.prepare_execution(selected.executions[0])
        attempt = directory / ('attempt-' + selected.phases[0])
        attempt.mkdir(mode=0o700)
        inputs = directory / 'input'
        if (inputs / 'package-input.json').is_file():
            # Broad runs stage a small union once; each restored attempt keeps
            # only its own scenario's comparison bytes, never another history's.
            required = set(system.scenario_fixture_files(selected))
            def excluded(parent, names):
                from pathlib import Path
                return [name for name in names
                        if (path := Path(parent) / name).is_file()
                        and (relative := path.relative_to(inputs).as_posix()).startswith('fixtures/')
                        and relative not in required]
            shutil.copytree(inputs, attempt / 'input', ignore=excluded)
            inventory = {p.relative_to(attempt / 'input').as_posix(): system.baseline.digest(p)
                         for p in sorted((attempt / 'input').rglob('*'))
                         if p.is_file() and p.name != 'transfer-sha256.json'}
            (attempt / 'input/transfer-sha256.json').write_bytes(system.baseline.encode(inventory))
        else:
            shutil.copytree(inputs, attempt / 'input')
        suite.next_case = (installed_case(planned[index + 1][1])
                           if index + 1 < len(planned) else None)
        try:
            with lease:
                with ledger.measure('preparation'):
                    if lease.__dict__.get('_fixture_provision_state') is not None:
                        from tools.fixture_provision import reset_after_restore
                        reset_after_restore(lease)
                    system.verify_history_target(selected, lease.capture)
                    if installed:
                        system.require(lease.capture.state['guest'].get('fixture_boundary') != 'clean',
                                       'fixtures:system-installed-target-not-qualified')
                        # prepare_case calls the shared preparation with overwrite=False
                        # and keeps the completed version snapshot across invocations.
                        suite.prepare_case(installed_case(True), directory, directory / 'input',
                            {'schema_version': 1, 'scope': 'system-installed-setup'}, root=system.ROOT)
                    else:
                        lease.prepare()
                with ledger.measure('bootstrap'):
                    clean = lease.capture.state['guest'].get('fixture_boundary') == 'clean'
                    options = {'system_product_free': True} if clean and not installed else {}
                    host_key = system.bootstrap(suite.commands, lease, attempt, suite.guestfs,
                                                **options)
                    lease.start()
                    hostname = system.address(source)
                (attempt / 'known-hosts').write_text(f'{hostname} {host_key}\n')
                config = {'directory': str(attempt), 'hostname': hostname, 'run': lease.state['run'],
                          'domain_uuid': source.uuid, 'domain_id': lease.view.domain_id}
                vm = Transport(config, suite.commands, guard=lambda _: lease.guard(), lease=lease)
                lease.guard()
                options = ({'fixture_selection': fixture_selection,
                            'preparation_only': preparation_only,
                            'preparation_observer': preparation_observer}
                           if fixture_selection is not None or preparation_only else {})
                result = system.installed_run(vm, lease, attempt, selected, ledger,
                                             already_installed=installed, **options)
                if preparation_only:
                    prepared.append(result)
                else:
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
    return prepared if preparation_only else None


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
