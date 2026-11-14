"""Installed launch assertions; execute only through the guarded VM controller."""

import pytest

from system_enforcement import (
    broker_save_failure_recovery,
    native_policy_transition, native_probe_lifecycle, native_probe_storage_lifecycle,
    observe_catalog, partial_termination_retry, provision_catalog, provision_native,
)
from system_assertions import validation_stage

pytestmark = [pytest.mark.system, pytest.mark.guest_mutating]


def test_broker_save_failure_recovery(record_testsuite_property):
    """Retain prior child policy after a real storage fault, then retry."""
    broker_save_failure_recovery(record_testsuite_property)


def test_partial_app_termination_retry(record_testsuite_property):
    """Preserve real partial app closure and fail-closed state, then retry."""
    partial_termination_retry(record_testsuite_property)


def run_checks(record, checks):
    """Keep each finite check's evidence and original failure within its group."""
    for stage, check in checks:
        def observed(key, value):
            record(f'{key}.{stage}', value)
        with validation_stage('enforcement-check', stage):
            check(observed)


def test_kiosk_execution_confinement(record_testsuite_property):
    """Run every finite enforcement validation on one prepared live guest."""
    run_checks(record_testsuite_property, (
        ('kiosk-integration', _kiosk_execution_confinement),
        ('native-command-policy', _native_command_policy_is_uid_scoped),
        ('native-probe-lifecycle', _native_probe_systemd_lifecycle),
        ('pattern-and-launcher-retention', _native_future_pattern_is_uid_scoped),
        ('offline-expiry-and-pam', _kiosk_expiry_installed_runtime),
    ))


def _kiosk_execution_confinement(record_testsuite_property):
    # Stable ID 267 now observes the selected session composition. Reachable
    # escape attempts remain separate pending engineering obligations.
    from system_kiosk_confinement import verify_session_composition
    from system_kiosk_admission import verify as verify_admission
    from system_kiosk_scope import verify as verify_scope
    run_checks(record_testsuite_property, (
        ('session-composition', verify_session_composition),
        ('login-admission', verify_admission),
        ('integration-scope', verify_scope),
    ))


def _native_command_policy_is_uid_scoped(record_testsuite_property):
    from system_caller import PersistentCaller
    native_accounts = provision_native()

    def catalog(record):
        provision_catalog(native_accounts)
        observe_catalog(native_accounts, record, caller=caller)

    with PersistentCaller(native_accounts['parent']) as caller:
        run_checks(record_testsuite_property, (
            ('command-policy', lambda record: native_policy_transition(
                native_accounts, record, caller=caller)),
            ('whitespace-policy', lambda record: native_policy_transition(
                provision_native('whitespace'), record, variant='whitespace', caller=caller)),
            ('selected-child-catalog', catalog),
        ))


def _native_probe_systemd_lifecycle(record_testsuite_property):
    # One continuous scenario also proves a settled refusal permits a fresh
    # independent generation; retain each stage's distinct evidence.
    from system_probe_sandbox import native_probe_broker_sandbox
    run_checks(record_testsuite_property, (
        ('refusal', lambda record: native_probe_lifecycle(record, refuse_admission=True)),
        ('after-refusal', native_probe_lifecycle),
        ('broker-storage', native_probe_storage_lifecycle),
        ('broker-sandbox', native_probe_broker_sandbox),
        ('lost-sender', lambda record: native_probe_lifecycle(record, lose_sender=True)),
        ('fresh-after-loss', native_probe_lifecycle),
    ))


def _native_future_pattern_is_uid_scoped(record_testsuite_property):
    """Keep pattern growth and missing-launcher persistence in one finite case."""
    from system_caller import PersistentCaller
    accounts = provision_native('pattern')
    with PersistentCaller(accounts['parent']) as caller:
        run_checks(record_testsuite_property, (
            ('future-pattern', lambda record: native_policy_transition(
                accounts, record, variant='pattern', caller=caller)),
            ('missing-launcher', lambda record: native_policy_transition(
                provision_native('retention'), record, variant='retention', caller=caller)),
        ))


def _kiosk_expiry_installed_runtime(record_testsuite_property):
    import json
    import re
    import system_guest as guest
    from system_session_expiry import verify_offline_recovery, verify_pam_scopes

    guest.guard()

    def record_backend(stage):
        # An earlier native fixture can fail to restore policy after losing
        # fapolicyd. Observe this case's entry/exit without restarting it,
        # refreshing trust, or replacing the original setup failure.
        previous_returncode = guest.commands.last_returncode
        observation = {'read': 'unavailable'}
        try:
            raw = guest.commands.run([
                'systemctl', 'show', 'fapolicyd.service',
                '--property=ActiveState,Result,MainPID,ExecMainStatus,ExecMainExitTimestampMonotonic'],
                timeout=3, check=False, merge_stderr=False).decode('ascii')
            observation['read'] = 'read' if guest.commands.last_returncode == 0 else 'failed'
            fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
            for key, allowed in (
                    ('ActiveState', ('active', 'inactive', 'failed', 'activating',
                                     'deactivating', 'reloading')),
                    ('Result', ('success', 'exit-code', 'signal', 'core-dump',
                                'timeout', 'watchdog', 'start-limit-hit', 'oom-kill'))):
                value = fields.get(key)
                observation[key] = value if value in allowed else 'unknown'
            for key in ('MainPID', 'ExecMainStatus', 'ExecMainExitTimestampMonotonic'):
                value = fields.get(key, '')
                if re.fullmatch(r'[0-9]{1,20}', value) and int(value) < 2 ** 64:
                    if key == 'MainPID':
                        observation['process_present'] = int(value) > 0
                    else:
                        observation[key] = int(value)
        except Exception:
            # Diagnostic errors and raw output must not reach assertions.
            observation['read'] = 'unavailable'
        finally:
            guest.commands.last_returncode = previous_returncode
        try:
            record_testsuite_property('onpc.expiry.backend.' + stage,
                                      json.dumps(observation, sort_keys=True))
        except Exception:
            pass

    record_backend('before-offline-recovery')
    try:
        verify_offline_recovery(record_testsuite_property)
    finally:
        record_backend('after-offline-recovery')
    verify_pam_scopes(record_testsuite_property)
