"""Exercise the installed product and leave the fault verdict to the runner."""
import json
import os
import sys
from unittest.mock import patch

import system_runner as system
from owned_commands import CommandError
from qualification_storage import run_qualification

sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
from execution import open_source
from installed_setup import InstalledSetup, inputs, stage
from provenance import VerifiedInputs
from suite_lease import Suite


def exercise(transport, lease, variant):
    def engineering(action):
        return json.loads(transport.call(['env', 'ONPC_EXPECTED_RUN=' + lease.state['run'],
            '/usr/bin/python3', '-B', system.PAYLOAD + '/system_kiosk_feedback.py',
            action], timeout=150))

    system.require(engineering('seed-preferences') == {'preferences_verified': True},
                   'fault-qualification:preferences-not-ready')
    if variant == 'log-only':
        fault = engineering('broker-log-only')
        system.require(fault['operation_observed'] and fault['backend_occurrences'] == 0
                       and fault['restored'], 'fault-qualification:log-only-witness')
        return {'fault': fault}

    observer = transport.product_failures
    system.require(observer is not None, 'fault-qualification:observer-missing')
    if variant == 'expired-allowance':
        with observer.allow('broker', 'backend'):
            allowed = engineering('broker-backend')
        fault = engineering('broker-backend')
        system.require(all(item['backend_occurrences'] == 1 and item['restored']
                           for item in (allowed, fault)),
                       'fault-qualification:repeated-fault-witness')
        return {'allowed': allowed, 'fault': fault}

    previous = observer.boundary()
    system.require(previous is not None, 'fault-qualification:departing-boot-unavailable')
    at_startup = variant in ('startup', 'both-edges')
    if at_startup:
        armed = engineering('arm-reboot-startup')
        system.require(armed == {'armed': 'startup', 'boot': previous.boot_id},
                       'fault-qualification:reboot-probe-not-ready')

    faults = {}
    if variant in ('departure', 'both-edges'):
        checkpoint = observer.before_reboot

        def inject_after_checkpoint():
            checkpoint()
            faults['departure'] = engineering('broker-backend')

        # The transport still submits the guarded, single reboot request.
        # This witness occurs after its pre-request read, while broker
        # dependencies remain available in the departing boot.
        with patch.object(observer, 'before_reboot', inject_after_checkpoint):
            transport.reboot()
    else:
        transport.reboot()
    current = observer.boundary()
    system.require(current is not None and current.boot_id != previous.boot_id,
                   'fault-qualification:reboot-not-observed')
    if at_startup:
        try:
            faults['startup'] = json.loads(transport.call(
                ['cat', system.PAYLOAD + '/private/fault-startup.json'], timeout=30))
        except CommandError:
            transport.call(['/usr/bin/journalctl', '--no-pager', '--lines', '30',
                            '--boot=' + current.boot_id,
                            '--unit=onpc-product-fault-qualification.service'],
                           timeout=20, check=False)
            raise
    for edge, fault in faults.items():
        start, end = fault['fault_start'], fault['fault_end']
        boot = previous if edge == 'departure' else current
        system.require(fault['backend_occurrences'] == 1 and fault['restored']
                       and start['boot_id'] == end['boot_id'] == boot.boot_id
                       and (start['monotonic_usec'] > boot.monotonic_usec if edge == 'departure'
                            else end['monotonic_usec'] < boot.monotonic_usec),
                       'fault-qualification:reboot-fault-witness')
    transport.call(system.guest_command(lease.state['run'], 'verify-installed'), timeout=660)
    return {'departing_boot': previous.boot_id, 'arriving_boot': current.boot_id, 'faults': faults}


def qualify(directory, assets, variant):
    ledger = system.RunLedger()
    suite = Suite(open_source)
    suite.snapshot_mode = 'offline'
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite.commands = system.EvidenceCommands(private)
    suite.commands.directory = private
    selection = {'scope': 'installed-product-fault-qualification', 'variant': variant}
    staged = directory / 'assets'
    result = {'outcome': 'passed', 'variant': variant}
    try:
        system.stage_assets(system.artifact_source(assets), staged, suite.commands, package_only=True)
        source, guestfs, lease = suite.acquire(ledger)
        with lease:
            suite.prepare_case({'preconditions': ['installed-digest-verified-product']},
                               directory, staged, selection, root=system.ROOT)
            stage(directory, staged, selection, bundle=inputs(system.ROOT, product_failure_signal=True),
                  package_only=True)
            host_key = system.bootstrap(suite.commands, lease, directory, guestfs, system_installed=True)
            lease.save('isolated')
            verified = VerifiedInputs(lease=lease, assets=directory / 'input', root=system.ROOT,
                                      package_only=True)
            transport = suite.start_transport(directory, host_key)
            InstalledSetup(directory, verified, transport).provision(lease.guard)
            transport.call(system.guest_command(lease.state['run'], 'verify-installed'), timeout=660)
            result.update(exercise(transport, lease, variant))
            result.update(vm=source.domain.name(), assertions_passed=True)
    finally:
        suite.close(retain_installed=True)
    system.require(ledger.first_failure_category is None,
                   ledger.first_failure_category or 'fault-qualification:unexpected-ledger-state')
    return result


def main(assets, variant):
    return run_qualification('product-fault-' + variant, lambda directory: qualify(directory, assets, variant),
        preflight=lambda: system.require(os.geteuid() == 0, 'fault-qualification:root-required'))
