#!/usr/bin/python3
"""Run installed-system pytest on the configured VM, resetting its retained snapshot.

Root host controller. No product installation command executes on the host.
All VM/storage operations are injectable; imports have no machine side effects.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, replace
import fcntl
import hashlib
import importlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET

# Root runs must not create private bytecode caches in the developer checkout,
# including when this controller is invoked directly instead of through make.
if __name__ == '__main__':
    sys.dont_write_bytecode = True

import prepare_baseline as baseline
from system_case_ids import identity_for_case, parse_recording_ids, validate_inventory

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = '/var/tmp/onpc-system-input'
TAG = 'onpc-system-run:'
QUALIFICATION_CASE = 'test_method_role_matrix[ListManagedUsers-parent1]'
QUALIFICATION_FAILURE = 'harness:qualification-failure'
REMOVAL_PHASES = ('removal', 'removed-rebooted', 'reinstalled-rebooted',
                  'purged-rebooted', 'purge-reinstalled-rebooted')
FIRST_CONFIGURE_CASE = 'test_first_configuration_interruption_retry'
FIRST_CONFIGURE_PHASES = ('first-configure', 'first-configure-rebooted')
PREVIOUS_POLICY_CASE = 'test_previous_package_policy_preservation'
PREVIOUS_POLICY_PHASES = ('previous-policy', 'installed', 'rebooted')
TRUSTED_FIXTURES_CASE = 'test_trusted_native_upgrade_fixtures'
TRUSTED_FIXTURES_PHASE = 'trusted-fixtures'


@dataclass(frozen=True)
class History:
    case_id: str
    phases: tuple[str, ...]
    prerequisites: tuple[str, ...]
    start: str = 'baseline'
    package_format: str | None = None


PAM_CASE = 'test_pam_environment_installation_variants'
PAM_VARIANTS = ('plain', 'distro-profile', 'administrator-override', 'pending-vendor')
PAM_HISTORIES = tuple(
    History(f'{PAM_CASE}[{variant}]',
            (f'pam-{variant}', f'pam-{variant}-rebooted',
             f'pam-{variant}-configured-rebooted', f'pam-{variant}-removed-rebooted'), ())
    for variant in PAM_VARIANTS)
PAM_PHASES = tuple(phase for history in PAM_HISTORIES for phase in history.phases)


REMOVAL_HISTORIES = (
    History('test_remove_reboot_reinstall', REMOVAL_PHASES, ('installed', 'rebooted')),
    History('test_aborted_cleanup_rollback_retry', ('rollback', 'rollback-rearmed-rebooted'),
            ('rollback-installed', 'rollback-rebooted')),
    *(History(f'test_interrupted_finalization_retry[{variant}]',
              (variant, variant + '-retry-rebooted'),
              (variant + '-installed', variant + '-rebooted'))
      for variant in ('denial-publication', 'mac-unload', 'account-finalization')),
    *(History(f'test_ownership_refusal_retry[{variant}]',
              (variant, variant + '-retry-rebooted'),
              (variant + '-installed', variant + '-rebooted'))
      for variant in ('systemd-user-edit', 'gdm-password-link', 'systemd-user-link',
                      'gdm-hook-link', 'confinement-record-owner',
                      'confinement-record-link', 'confinement-record-uid')),
    *(History(f'test_identity_filesystem_refusal_retry[{variant}]',
              (variant, variant + '-retry-rebooted'),
              (variant + '-installed', variant + '-rebooted'))
      for variant in ('kiosk-marker-uid', 'home-owner', 'home-link', 'home-mount',
                      'state-owner', 'state-link', 'state-mount')),
    History('test_rpm_posterase_recovery',
            ('rpm-posterase', 'rpm-posterase-reinstalled-rebooted'),
            ('rpm-posterase-installed', 'rpm-posterase-rebooted'), package_format='rpm'),
)
REMOVAL_FAMILIES = {
    'test_ownership_refusal_retry': tuple(
        history.case_id for history in REMOVAL_HISTORIES
        if history.case_id.startswith('test_ownership_refusal_retry[')),
    'test_identity_filesystem_refusal_retry': tuple(
        history.case_id for history in REMOVAL_HISTORIES
        if history.case_id.startswith('test_identity_filesystem_refusal_retry[')),
}
ROLLBACK_PHASES = (*REMOVAL_HISTORIES[1].prerequisites, *REMOVAL_HISTORIES[1].phases)
PHASE_SEMANTICS = {phase: semantic for history in REMOVAL_HISTORIES[1:]
                   for phase, semantic in zip(history.prerequisites, ('installed', 'rebooted'))}
PHASE_ORDER = (TRUSTED_FIXTURES_PHASE, 'previous-policy', 'installed', 'rebooted', *FIRST_CONFIGURE_PHASES, *PAM_PHASES, *REMOVAL_PHASES,
               *(phase for history in REMOVAL_HISTORIES[1:]
                 for phase in (*history.prerequisites, *history.phases)),
               'authorization', 'enforcement', 'session')
AREA_SOURCES = {
    'package': ROOT / 'tests/system/test_install_smoke.py',
    'removal': ROOT / 'tests/system/test_removal.py',
    'authorization': ROOT / 'tests/system/test_authorization.py',
    'enforcement': ROOT / 'tests/system/test_enforcement.py',
    'session': ROOT / 'tests/system/test_session_expiry.py',
}
COMMON_SELECTED_INPUTS = (
    ('tests/fixtures/baseline_assets.py', 'baseline_assets.py'),
    ('tests/fixtures/native_assets.py', 'native_assets.py'),
    ('tests/fixtures/native_trust.py', 'native_trust.py'),
    ('tests/integration/system_guest.py', 'system_guest.py'),
    ('tests/integration/guest_test_dependencies.py', 'guest_test_dependencies.py'),
    ('tests/integration/owned_commands.py', 'owned_commands.py'),
    ('tests/integration/guest/redact.py', 'guest/redact.py'),
    ('tests/system/pytest.ini', 'pytest.ini'),
    ('tools/regression_events.py', 'system_progress.py'),
)
KIOSK_ACTIVATION_CASE = 'test_kiosk_account_classification_survives_reboot'
# Host entry/transport and the public observer's embedded source closure. Keep
# these identities separate from guest imports; no host module runs in the VM.
KIOSK_ACTIVATION_HOST_INPUTS = (
    'tests/integration/system_runner.py', 'tests/integration/system_case_ids.py',
    'tests/integration/system_snapshots.py',
    'tests/integration/vm_transport.py', 'tests/integration/watch_activity.py',
    'tests/e2e/kiosk_entry.py', 'tests/e2e/ui_observations.py',
    'tests/e2e/private_artifacts.py',
    'tests/e2e/accessible_ui.py', 'tests/e2e/application_ui.py',
    'tests/e2e/session_control.py', 'tests/e2e/public_atspi.py',
    'tests/e2e/block_semantics.py', 'tests/e2e/feedback_formats.py',
    'tests/e2e/download_destination.py', 'tests/e2e/fixture_ui.py',
    'tests/support/application_ui.py',
    'common/oh_no_parent_control_ui/application_ui.py',
    'common/oh_no_parent_control_ui/application_ui_client.py', 'data/app.json',
)
PHASE_DEPENDENCIES = {
    TRUSTED_FIXTURES_PHASE: (),
    'previous-policy': (),
    'installed': (),
    'rebooted': ('installed',),
    FIRST_CONFIGURE_PHASES[0]: (),
    FIRST_CONFIGURE_PHASES[1]: (FIRST_CONFIGURE_PHASES[0],),
    **{phase: history.phases[:index]
       for history in PAM_HISTORIES for index, phase in enumerate(history.phases)},
    **{phase: (*history.prerequisites, *history.phases[:index])
       for history in REMOVAL_HISTORIES
       for index, phase in enumerate(history.phases)},
    **{phase: history.prerequisites[:index] for history in REMOVAL_HISTORIES[1:]
       for index, phase in enumerate(history.prerequisites)},
    'authorization': (),
    'enforcement': (),
    'session': (),
}
PHASE_PREREQUISITES = {
    TRUSTED_FIXTURES_PHASE: ('genuine-earlier-package', 'previous-install-and-reboot',
                            'trusted-native-baseline-fixtures', 'fixture-passwords'),
    'previous-policy': ('genuine-earlier-package', 'previous-install-and-reboot',
                        'saved-child-policy-and-authenticated-grant', 'fixture-passwords'),
    'installed': ('accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap', 'package-install'),
    'rebooted': ('installed-phase', 'guest-reboot', 'boot-readiness'),
    FIRST_CONFIGURE_PHASES[0]: ('accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap',
                              'owned-configure-interruption-retry'),
    FIRST_CONFIGURE_PHASES[1]: ('first-configure-phase', 'guest-reboot', 'boot-readiness'),
    **{history.phases[0]: ('accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap',
                         'owned-pam-environment-installation') for history in PAM_HISTORIES},
    **{phase: (history.phases[index - 1] + '-phase', 'guest-reboot', 'boot-readiness')
       for history in PAM_HISTORIES for index, phase in enumerate(history.phases) if index},
    'removal': ('installed-phase', 'guest-reboot', 'native-enforcement-fixture'),
    'removed-rebooted': ('removal-phase', 'guest-reboot', 'desktop-health'),
    'reinstalled-rebooted': ('reinstall-phase', 'guest-reboot', 'boot-readiness'),
    'purged-rebooted': ('purge-phase', 'guest-reboot', 'desktop-health'),
    'purge-reinstalled-rebooted': ('purge-reinstall-phase', 'guest-reboot', 'boot-readiness'),
    **{history.prerequisites[0]:
       ('accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap', 'package-install')
       for history in REMOVAL_HISTORIES[1:]},
    **{history.prerequisites[1]: ('installed-phase', 'guest-reboot', 'boot-readiness')
       for history in REMOVAL_HISTORIES[1:]},
    **{history.phases[0]: ('installed-phase', 'guest-reboot', 'native-enforcement-fixture')
       for history in REMOVAL_HISTORIES[1:]},
    **{history.phases[1]: (history.phases[0] + '-phase', 'guest-reboot', 'boot-readiness')
       for history in REMOVAL_HISTORIES[1:]},
    'authorization': ('retained-app-snapshot', 'authorization-accounts'),
    'enforcement': ('retained-app-snapshot', 'native-enforcement-fixture'),
    'session': ('retained-app-snapshot', 'one-shot-gdm-grant-fixture-and-second-reboot'),
}
require = baseline.require
Error = baseline.CaptureError

from owned_commands import Commands, CommandError


watch_progress = None

from watch_activity import observed, operation


def log(stage):
    from watch_activity import event
    event(stage)
    print(f'check-system: [{stage}]', file=sys.stderr, flush=True)
    if watch_progress is not None:
        watch_progress.preparation_output(f'check-system: [{stage}]')


STAGE_NAMES = ('preparation', 'bootstrap', 'install', 'reboot', 'test',
               'collection', 'cleanup', 'finalization')
OUTCOME_NAMES = ('product', 'infrastructure', 'collection', 'cleanup')
HOST_EXECUTABLES = ('ssh', 'qemu-img', 'ssh-keygen', 'virt-customize',
                    'dpkg-deb', 'dpkg-query')

# These validators deliberately raise ValueError with fixed, nonsecret reasons.
# Preserve their actionable prerequisite failures without publishing arbitrary
# ValueError text from parsers, subprocess adapters or guest-controlled input.
PREREQUISITE_FAILURES = frozenset(
    'guest-tools:' + reason for reason in (
        'unsupported-os', 'unsupported-package-version', 'ambiguous-package-status',
        'missing-or-mismatched-package', 'package-not-configured')) | frozenset(
    'baseline:chinese-' + reason + '; run tools/prepare-vm' for reason in (
        'changed', 'locale-command', 'read-command', 'command-bound', 'locale-runtime',
        'parent', 'missing-file', 'file', 'release', 'selinux', 'package-status', 'missing-package',
        'font-table', 'font-format', 'font-faces', 'font-face', 'font-tables', 'font-cmap',
        'font-groups', 'font-group-order', 'font-coverage', 'unsupported-platform',
        'package-version', 'package-identity', 'package-bytes', 'locale',
        'catalogue-identity', 'translation-fallback', 'unowned-collision',
        'response-bound', 'response', 'receipt', 'receipt-platform', 'receipt-catalogue', 'receipt-files')) | {
    'guest-tools:missing-or-mismatched-package; run tools/prepare-vm on the host'}


def error_category(error):
    """Return only the runner's fixed public failure categories."""
    if isinstance(error, (Error, CommandError)):
        return str(error)
    evidence = sys.modules.get('private_artifacts')
    if evidence is not None and isinstance(error, evidence.EvidenceError):
        # This type's contract permits fixed codes only, never arbitrary text.
        return str(error)
    if isinstance(error, baseline.guest_contract.PreparationError):
        return error.category
    if type(error) is ValueError and str(error) in PREREQUISITE_FAILURES:
        return str(error)
    return 'unexpected-failure-or-interruption'


def package_format(guest):
    """Select from the verified baseline, never the VM's display name."""
    if guest.get('ubuntu_version') == '26.04':
        return 'deb'
    if guest.get('os_id') == 'fedora' and guest.get('version') == '44':
        return 'rpm'
    raise Error('guest:unsupported-package-platform')


def package_version(commands, package):
    argv = (['rpm', '-qp', '--queryformat', '%{VERSION}', str(package)]
            if package.suffix == '.rpm' else ['dpkg-deb', '-f', str(package), 'Version'])
    return commands.run(argv, merge_stderr=False).decode().strip()


class RunLedger:
    """Accumulate monotonic stage timings and independent first-failure results."""

    def __init__(self, monotonic=time.monotonic):
        self.monotonic = monotonic
        self.durations = {name: 0.0 for name in STAGE_NAMES}
        self.outcomes = {name: {'outcome': 'not-run', 'category': None}
                         for name in OUTCOME_NAMES}
        self.first_failure_category = None

    @contextmanager
    def measure(self, stage):
        require(stage in self.durations, 'timing:unknown-stage')
        started = self.monotonic()
        try:
            yield
        finally:
            duration = max(0.0, self.monotonic() - started)
            self.durations[stage] += duration
            log(f'timing:stage={stage} duration_seconds={duration:.3f}')

    def pass_outcome(self, name):
        require(name in self.outcomes, 'outcome:unknown-domain')
        if self.outcomes[name]['outcome'] != 'failed':
            self.outcomes[name] = {'outcome': 'passed', 'category': None}

    def fail_outcome(self, name, category):
        require(name in self.outcomes, 'outcome:unknown-domain')
        require(isinstance(category, str) and category, 'outcome:invalid-category')
        # A later failure in the same domain must not replace its first failure.
        if self.outcomes[name]['outcome'] != 'failed':
            self.outcomes[name] = {'outcome': 'failed', 'category': category}
        if self.first_failure_category is None:
            self.first_failure_category = category
        log(f'outcome:domain={name} outcome=failed category={category}')

    def data(self):
        return {
            'stage_durations_seconds': {
                name: round(self.durations[name], 6) for name in STAGE_NAMES
            },
            'outcomes': {name: dict(self.outcomes[name]) for name in OUTCOME_NAMES},
        }


def record_caught_failure(ledger, error):
    """Classify a caught failure without losing an earlier domain diagnosis."""
    caught_category = error_category(error)
    if not any(ledger.outcomes[name]['outcome'] == 'failed'
               for name in ('product', 'collection', 'cleanup')):
        ledger.fail_outcome('infrastructure', caught_category)
    elif ledger.outcomes['infrastructure']['outcome'] == 'not-run':
        ledger.pass_outcome('infrastructure')
    return ledger.first_failure_category or caught_category


@dataclass(frozen=True)
class CaseExecution:
    phase: str
    area: str
    case_id: str
    prerequisite: bool


@dataclass(frozen=True)
class Selection:
    area: str | None
    test: str | None
    scope: str
    phases: tuple[str, ...]
    prerequisites: tuple[str, ...]
    executions: tuple[CaseExecution, ...]
    available: dict[str, tuple[str, ...]]
    qualification_failure: bool = False


def collect_area_cases(area, *, invoke=None):
    """Collect registered pytest IDs without running guest fixtures or VM code."""
    require(area in AREA_SOURCES, 'selection:unknown-area')
    source = AREA_SOURCES[area]
    command = [
        '/usr/bin/env',
        f'PYTHONPATH={ROOT / "tests/integration"}',
        'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
        'PYTHONDONTWRITEBYTECODE=1',
        '/usr/bin/python3', '-m', 'pytest', '-c', str(ROOT / 'tests/system/pytest.ini'),
        '--noconftest', '--rootdir', str(ROOT / 'tests/system'), '--collect-only', '-q', str(source),
    ]
    try:
        output = (invoke or Commands().run)(command, timeout=60)
    except CommandError as error:
        raise Error(f'selection:collection-failed:{area}') from error
    prefix = source.name + '::'
    cases = tuple(line.removeprefix(prefix) for line in output.decode().splitlines()
                  if line.startswith(prefix))
    require(cases and len(cases) == len(set(cases)), f'selection:invalid-registry:{area}')
    try:
        validate_inventory({area: cases})
    except ValueError as error:
        raise Error('selection:unregistered-numeric-case-id') from error
    return cases


def case_phases(area, case_id):
    if area == 'removal':
        history = next((item for item in REMOVAL_HISTORIES if item.case_id == case_id), None)
        require(history is not None, 'selection:unregistered-removal-case')
        return history.phases
    if area in ('authorization', 'enforcement', 'session'):
        return (area,)
    package = {
        TRUSTED_FIXTURES_CASE: (TRUSTED_FIXTURES_PHASE,),
        PREVIOUS_POLICY_CASE: PREVIOUS_POLICY_PHASES,
        **{history.case_id: history.phases for history in PAM_HISTORIES},
        FIRST_CONFIGURE_CASE: FIRST_CONFIGURE_PHASES,
        'test_installed_package': ('installed', 'rebooted'),
        'test_first_install_requests_reboot': ('installed',),
        'test_reboot_applies_installation': ('rebooted',),
        'test_kiosk_account_classification_survives_reboot': ('installed', 'rebooted'),
    }
    require(case_id in package, 'selection:unregistered-package-case')
    return package[case_id]


def resolve_selection(area=None, test=None, *, inventories=None, qualification_failure=False,
                      fresh_install=False, target_package_format=None, recording_ids=None):
    """Resolve an exact case or registered family and its phase prerequisites."""
    require(recording_ids is None or area is test is None, 'selection:numeric-id-selector-conflict')
    require(area is None or area != '', 'selection:empty-area')
    require(test is None or test != '', 'selection:empty-test')
    require(area is None or area in AREA_SOURCES, 'selection:unknown-area')
    require(test is None or area is not None, 'selection:test-requires-area')
    try:
        identities = parse_recording_ids(recording_ids) if recording_ids is not None else ()
    except ValueError as error:
        raise Error(str(error)) from error
    require(not qualification_failure or (area == 'authorization' and test == QUALIFICATION_CASE)
            or (len(identities) == 1 and identities[0].area == 'authorization'
                and identities[0].case_id == QUALIFICATION_CASE),
            'qualification:requires-allowlisted-case')
    if inventories is None:
        inventories = {name: collect_area_cases(name) for name in AREA_SOURCES}
    else:
        inventories = {name: tuple(cases) for name, cases in inventories.items()}
    require(set(inventories) == set(AREA_SOURCES), 'selection:incomplete-registry')
    for name, cases in inventories.items():
        require(cases and len(cases) == len(set(cases)), f'selection:invalid-registry:{name}')
    require(all(identity.case_id in inventories.get(identity.area, ()) for identity in identities),
            'selection:numeric-id-not-runnable')

    require(target_package_format in (None, 'deb', 'rpm'), 'selection:invalid-package-format')
    incompatible_histories = {history.case_id for history in REMOVAL_HISTORIES
                             if target_package_format is not None and history.package_format
                             and history.package_format != target_package_format}
    require(test not in incompatible_histories, 'selection:history-package-format-mismatch')
    require(not any(identity.case_id in incompatible_histories for identity in identities),
            'selection:history-package-format-mismatch')
    inventories['removal'] = tuple(case for case in inventories['removal']
                                  if case not in incompatible_histories)

    family = REMOVAL_FAMILIES.get(test) if area == 'removal' else (
        tuple(history.case_id for history in PAM_HISTORIES)
        if area == 'package' and test == PAM_CASE else None)
    if family is not None:
        registered = tuple(case for case in inventories[area] if case.startswith(test + '['))
        require(family and set(registered) == set(family), 'selection:invalid-family-registry')
    elif test is not None and test not in inventories[area]:
        incompatible = any(test in cases for name, cases in inventories.items() if name != area)
        require(not incompatible, 'selection:incompatible-test')
        raise Error('selection:unknown-test')

    chosen_areas = tuple(AREA_SOURCES) if area is None else (area,)
    chosen = {name: inventories[name] for name in chosen_areas}
    if test is not None:
        chosen[area] = family if family is not None else (test,)
    if identities:
        selected = {(identity.area, identity.case_id) for identity in identities}
        chosen = {name: tuple(case for case in cases if (name, case) in selected)
                  for name, cases in chosen.items()}
        chosen = {name: cases for name, cases in chosen.items() if cases}
    # Qualification is an explicit, isolated old-package history. In particular,
    # --previous-artifacts alone must not add it to an upgrade suite.
    if test != TRUSTED_FIXTURES_CASE and not identities and 'package' in chosen:
        chosen['package'] = tuple(case for case in chosen['package']
                                  if case != TRUSTED_FIXTURES_CASE)
    trusted_fixtures = TRUSTED_FIXTURES_CASE in chosen.get('package', ())
    require(not trusted_fixtures or chosen == {'package': (TRUSTED_FIXTURES_CASE,)},
            'selection:trusted-fixtures-requires-isolated-history')
    # This optional history needs explicit earlier-package inputs. Ordinary
    # current-package suites keep their independent baseline histories.
    if not fresh_install and test is None and not identities and 'package' in chosen:
        chosen['package'] = tuple(case for case in chosen['package']
                                  if case != PREVIOUS_POLICY_CASE)
    require(not fresh_install or not any(history.case_id in chosen.get('removal', ())
            for history in REMOVAL_HISTORIES[1:]), 'selection:recovery-requires-current-package')
    require(not fresh_install or FIRST_CONFIGURE_CASE not in chosen.get('package', ()),
            'selection:first-configure-requires-current-package')
    require(not fresh_install or not any(history.case_id in chosen.get('package', ())
                                        for history in PAM_HISTORIES),
            'selection:pam-variants-require-current-package')

    terminal_phases = {phase for name, cases in chosen.items() for case in cases
                       for phase in case_phases(name, case)}
    dependencies = {phase for item in terminal_phases for phase in PHASE_DEPENDENCIES[item]}
    if fresh_install and not trusted_fixtures:
        dependencies.update(('installed', 'rebooted'))
    phases = tuple(phase for phase in PHASE_ORDER if phase in terminal_phases or
                   phase in dependencies)
    require(phases, 'selection:no-compatible-tests')

    executions = []
    for phase in phases:
        if phase in terminal_phases:
            for name, cases in chosen.items():
                for case in cases:
                    if phase in case_phases(name, case):
                        executions.append(CaseExecution(phase, name, case, False))
        if phase not in terminal_phases:
            for case in inventories['package']:
                if PHASE_SEMANTICS.get(phase, phase) in case_phases('package', case):
                    executions.append(CaseExecution(phase, 'package', case, True))

    prerequisites = ['accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap']
    for phase in phases:
        for item in PHASE_PREREQUISITES[phase]:
            if item not in prerequisites and not (fresh_install and item == 'retained-app-snapshot'):
                prerequisites.append(item)
    if (test or identities) and any(case in ('test_authenticated_request_rejects_deleted_target',
                         'test_requester_disconnect_during_approval',
                         'test_administrator_eligibility_predicates') or
                 case.startswith('test_authenticated_request_revalidates_live_state[') or
                 case.startswith('test_request_rejects_locked_approver_during_authentication[') or
                 case.startswith('test_real_selected_parent_authentication[')
           for cases in chosen.values() for case in cases):
        prerequisites.append('fixture-passwords')
    available = {name: inventories[name] for name in chosen_areas}
    if any(item.case_id == 'test_remote_accounts_are_excluded' for item in executions):
        prerequisites.append('remote-ldap-nss-fixtures')
    return Selection(area, test, 'full' if area is None and recording_ids is None else 'partial', phases,
                     tuple(prerequisites), tuple(executions), available, qualification_failure)


def print_selection(selection, stream=None):
    """Print deterministic, host-safe scope information for operators."""
    if stream is None:
        stream = sys.stdout
    print('check-system selection:', file=stream)
    print('  mode: list-only (no root, artifacts, VM, or guest fixtures)', file=stream)
    print(f'  scope: {selection.scope}', file=stream)
    print('  purpose: ' + ('harness-qualification' if selection.qualification_failure
                          else 'product-tests'), file=stream)
    print('  area: ' + (selection.area or 'all'), file=stream)
    print('  test: ' + (selection.test or 'all'), file=stream)
    print('  vm-required-for-execution: yes', file=stream)
    print('  phases: ' + ','.join(selection.phases), file=stream)
    print('  prerequisites: ' + ','.join(selection.prerequisites), file=stream)
    for history in REMOVAL_HISTORIES:
        if history.package_format and any(item.case_id == history.case_id
                                          for item in selection.executions):
            print(f'  required-package-format: {history.case_id}={history.package_format}', file=stream)
    print(f'  expected-executions: {len(selection.executions)}', file=stream)
    for execution in selection.executions:
        kind = 'prerequisite' if execution.prerequisite else 'selected'
        identity = identity_for_case(execution.area, execution.case_id)
        suffix = f' [system-{identity.numeric_id}]' if identity else ''
        print(f'    {execution.phase}::{execution.case_id} [{kind}]{suffix}', file=stream)
    print('  available-selectors:', file=stream)
    for name, cases in selection.available.items():
        print(f'    {name}:', file=stream)
        for case in cases:
            identity = identity_for_case(name, case)
            suffix = f' [system-{identity.numeric_id}]' if identity else ''
            print(f'      {case}{suffix}', file=stream)


def resume_selection(selection, completed, *, fresh_install=False):
    """Omit completed independent cases; reconstruct lifecycle prerequisites."""
    identities = {item.phase + '::' + item.case_id for item in selection.executions}
    require(completed <= identities, 'selection:resume-inventory-changed')
    remaining = tuple(item for item in selection.executions
                      if item.phase + '::' + item.case_id not in completed)
    # A failed suite audit after the final case needs a real guarded attempt.
    remaining = remaining or selection.executions[-1:]
    if fresh_install:
        # Upgrade attempts reinstall from the baseline before dependent areas.
        lifecycle = ('installed', 'rebooted')
        remaining = tuple(item for item in selection.executions
                          if item in remaining or item.phase in lifecycle)
    if any(item.phase in FIRST_CONFIGURE_PHASES for item in remaining):
        remaining = tuple(item for item in selection.executions
                          if item in remaining or item.phase in FIRST_CONFIGURE_PHASES)
    if any(item.case_id == PREVIOUS_POLICY_CASE for item in remaining):
        remaining = tuple(item for item in selection.executions
                          if item in remaining or item.case_id == PREVIOUS_POLICY_CASE)
    for history in (*REMOVAL_HISTORIES, *PAM_HISTORIES):
        # State-changing histories cannot splice retained predecessor passes
        # into a newly restored guest.
        lifecycle = (*history.prerequisites, *history.phases)
        if any(item.phase in lifecycle for item in remaining):
            remaining = tuple(item for item in selection.executions
                              if item in remaining or item.phase in lifecycle)
    phases = tuple(phase for phase in selection.phases if any(item.phase == phase for item in remaining))
    return replace(selection, phases=phases, executions=remaining)


def announce_selection(selection):
    """Publish the resolved total before any VM work, including focused runs."""
    from tools.regression_events import emit
    emit('collection', total=len(selection.executions), nodeids=[
        item.phase + '::' + item.case_id for item in selection.executions])


def verify_history_target(selection, capture):
    """Check restricted histories against accepted guest provenance, not VM names."""
    for history in REMOVAL_HISTORIES:
        if history.package_format and any(item.case_id == history.case_id
                                          for item in selection.executions):
            require(package_format(capture.state['guest']) == history.package_format,
                    'selection:history-package-format-mismatch')


def isolated_xml(xml, expected_uuid, run, *, graphics_type='spice'):
    """Use the fixed guest disk and private test display and transport."""
    baseline.domain_layout(xml, expected_uuid)
    root = ET.fromstring(xml)
    require(not root.findall('{http://libvirt.org/schemas/domain/qemu/1.0}commandline'), 'guard:qemu-override')
    devices = root.find('devices')
    # Host filesystem backends are outside the guest disk/RAM snapshot boundary.
    # In particular, virtiofs backend state must not enter a reusable app snapshot.
    for name in ('filesystem', 'redirdev', 'channel', 'graphics', 'audio', 'sound', 'rng'):
        for node in devices.findall(name):
            devices.remove(node)
    require(graphics_type in ('spice', 'vnc'), 'guard:graphics-type')
    # Keep SPICE first for interactive viewers and their keyboard capture.
    # Automation uses a separate private VNC endpoint, selected by protocol.
    # Neither console listens on a host port/socket.
    from baseline_guest import configure_clipboard
    configure_clipboard(root)
    if graphics_type == 'vnc':
        graphics = ET.SubElement(devices, 'graphics', type='vnc')
        ET.SubElement(graphics, 'listen', type='none')
    # Every lease has the same private output collector, including system and
    # maintenance work. Users receive copies, never this QEMU connection.
    from e2e_watch import display_endpoint
    display_endpoint(root)
    for name in ('serial', 'console'):
        require(all(node.get('type') == 'pty' for node in devices.findall(name)), 'guard:host-character-device')
    interfaces = devices.findall('interface')
    require(len(interfaces) == 1 and interfaces[0].get('type') == 'network' and
            interfaces[0].find('source').attrib == {'network': 'default'}, 'guard:network')
    for item in interfaces[0].findall('filterref'):
        interfaces[0].remove(item)
    for node in root.findall('description'):
        root.remove(node)
    ET.SubElement(root, 'description').text = TAG + run
    return ET.tostring(root, encoding='unicode')


def validate_private_vnc(root):
    """Refuse display replacement or any host listener, including normalized XML."""
    displays = root.findall('devices/graphics')
    validate_observer(displays)
    # Retain legacy VNC-only layouts for recorded cleanup and recovery.
    if displays[0].get('type') == 'spice':
        validate_private_spice(displays[0])
        require(len(displays) == 3, 'guard:graphics-count')
        display = displays[1]
    else:
        display = displays[0]
    require(display.get('type') == 'vnc' and
            set(display.attrib) <= {'type', 'port', 'autoport'} and
            display.get('port', '-1') == '-1' and
            display.get('autoport', 'no') == 'no', 'guard:graphics-endpoint')
    require(len(display) == 1 and display[0].tag == 'listen' and
            display[0].attrib == {'type': 'none'} and len(display[0]) == 0,
            'guard:graphics-listener')


def validate_observer(displays):
    # Accept the previous VNC-only layout for durable interrupted-run recovery.
    require(len(displays) in (1, 2, 3), 'guard:graphics-count')
    if len(displays) == 3:
        require([display.get('type') for display in displays[:2]] == ['spice', 'vnc'],
                'guard:graphics-endpoint')
    if len(displays) >= 2:
        observer = displays[-1]
        require(observer.attrib == {'type': 'dbus', 'p2p': 'yes'} and
                len(observer) == 1 and observer[0].tag == 'gl' and
                observer[0].attrib == {'enable': 'no'} and len(observer[0]) == 0,
                'guard:graphics-observer-endpoint')


def validate_private_spice(display):
    """Preserve keyboard capture without reintroducing SPICE host transfers."""
    require(display.get('type') == 'spice' and
            set(display.attrib) <= {'type', 'port', 'tlsPort', 'autoport'} and
            display.get('port', '-1') == display.get('tlsPort', '-1') == '-1' and
            # libvirt omits autoport when normalizing listen type='none'.
            # The exact listener and disabled ports remain mandatory below.
            display.get('autoport', 'yes') == 'yes', 'guard:graphics-endpoint')
    clipboard = display.find('clipboard')
    # Disabled legacy layouts remain valid for their recorded owner's cleanup.
    # Fresh snapshot reuse separately requires clipboard sharing enabled.
    require(clipboard is not None and clipboard.get('copypaste') in {'no', 'yes'},
            'guard:graphics-clipboard')
    require(len(display) == 3 and
            {child.tag: dict(child.attrib) for child in display} == {
                'listen': {'type': 'none'}, 'clipboard': dict(clipboard.attrib),
                'filetransfer': {'enable': 'no'}} and
            all(len(child) == 0 for child in display), 'guard:graphics-listener')
    require(set(clipboard.attrib) == {'copypaste'}, 'guard:graphics-clipboard')


def validate_host_sharing(root, *, category='guard:host-sharing'):
    """Allow only the private display agent, including libvirt normalization.

    Channel-free layouts remain valid for recorded pre-change recovery.
    """
    require(not root.findall('devices/hostdev') and
            not root.findall('devices/redirdev'), category)
    channels = root.findall('devices/channel')
    require(len(channels) <= 1, category)
    if not channels:
        return
    channel = channels[0]
    require(channel.attrib == {'type': 'spicevmc'} and
            all(node.tag in ('target', 'alias', 'address') and len(node) == 0
                for node in channel) and
            len(channel.findall('target')) == 1 and
            len(channel.findall('alias')) <= 1 and
            len(channel.findall('address')) <= 1, category)
    target = channel.find('target')
    require(set(target.attrib) <= {'type', 'name', 'state'} and
            target.get('type') == 'virtio' and
            target.get('name') == 'com.redhat.spice.0' and
            target.get('state', 'disconnected') in ('connected', 'disconnected'), category)
    alias = channel.find('alias')
    require(alias is None or (set(alias.attrib) == {'name'} and
            re.fullmatch(r'channel[0-9]+', alias.get('name', '')) is not None), category)
    address = channel.find('address')
    require(address is None or (set(address.attrib) == {'type', 'controller', 'bus', 'port'} and
            address.get('type') == 'virtio-serial' and
            all(re.fullmatch(r'[0-9]+', address.get(key, '')) is not None
                for key in ('controller', 'bus', 'port'))), category)
    displays = root.findall('devices/graphics')
    require(bool(displays) and displays[0].get('type') == 'spice', category)
    validate_private_spice(displays[0])


class SourceView:
    """Retain disk checks and attest the owned running instance."""

    def __init__(self, source):
        self.source = source
        self.run = None
        self.domain_id = None
        self.graphics_type = 'spice'

    def snapshot(self):
        layout, off = self.source.snapshot()
        if self.run is not None:
            domain = self.source.connection.lookupByName(baseline.DOMAIN)
            root = ET.fromstring(domain.XMLDesc(0))
            require(len(root.findall('description')) == 1 and
                    root.findtext('description') == TAG + self.run, 'guard:run-identity')
            if self.graphics_type == 'vnc':
                validate_private_vnc(root)
            else:
                validate_observer(root.findall('devices/graphics'))
            validate_host_sharing(root)
            if not off:
                require(self.domain_id is not None and domain.ID() == self.domain_id, 'guard:domain-replaced')
        return layout, off

    def baseline(self):
        return self.source.baseline()


class Lease:
    """Serializes prepare-vm/system runners; durable state refuses interrupted ownership."""

    def __init__(self, source, commands, inspect, *, directory=None,
                 anchor=None, ledger=None, graphics_type='spice', finalize=None):
        self.source, self.commands, self.inspect = source, commands, inspect
        self.view = SourceView(source)
        self.view.graphics_type = graphics_type
        self.capture = baseline.Capture(self.view, commands, inspect, directory=directory, anchor=anchor)
        self.directory = self.capture.directory
        self.journal = self.directory / 'system-run.json'
        self.fd = None
        self.compatibility_fd = None
        self.state = None
        self.original_xml = None
        self.original_id = None
        self.mutated = False
        self.ledger = ledger
        # Trusted read/report callback, after the sole cleanup attempt and while
        # the lease is held. It must never restore or release this lease itself.
        self.finalize = finalize
        self.ownership_run = None
        self.watch = None
        self.watch_detached = False
        self.restored_by_callback = False
        self.shutdown_request = None

    def save(self, phase):
        if self.capture.vm_ownership is not None:
            self.capture.vm_ownership.check_owner()
        self.state['phase'] = phase
        require(self.capture.private_directory() == self.capture.directory_identity, 'guard:directory-changed')
        fd, path = tempfile.mkstemp(prefix='.system-run-', dir=self.directory)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(baseline.encode(self.state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, self.journal)
        baseline.sync_directory(self.directory)
        log('stage:' + phase)

    @observed('Validating VM ownership and baseline')
    def __enter__(self):
        try:
            self.capture.directory_identity = self.capture.private_directory()
            self.compatibility_fd = baseline.compatibility_lock(self.directory)
            self.fd = baseline.open_controller_lock(self.capture.lock_path)
            baseline.identity(self.capture.lock_path, private=True, mode=0o600)
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Error('state:busy-controller') from error
            self.commands.lock_fd = self.fd
            self.commands.compatibility_fd = self.compatibility_fd
            from e2e_watch import begin
            begin(self)
            self.capture.state = self.capture.read_state()
            require(self.capture.state['phase'] == 'finalized', 'baseline:not-finalized')
            self.capture.require_idle_attempt()
            # A new preparation contract needs a deliberately accepted baseline.
            # Refuse before hashing, journal writes or snapshot mutation; cleanup
            # must not discover the incompatible marker only after restoration.
            require(self.capture.state['script_digest'] == self.capture.script_digest,
                    'baseline:preparation-outdated')
            log('stage:baseline-verification')
            run = uuid.uuid4().hex
            self.ownership_run = run
            # Record metadata checks on refusal and interruption too, before
            # any VM mutation is permitted.
            with self.ledger.measure('preparation') if self.ledger else nullcontext():
                self.capture.begin_vm_ownership(self)
                require(self.capture.verify_snapshot(boundary='acquisition') ==
                        self.capture.state['proof'], 'baseline:changed')
            if self.journal.exists():
                baseline.identity(self.journal, private=True, mode=0o600)
                previous = baseline.parse_json(self.journal.read_bytes())
                require(previous.get('phase') == 'complete', 'state:interrupted-run; preserve state for recovery')
            self.original_xml = self.source.domain.XMLDesc(self.source.api.VIR_DOMAIN_XML_INACTIVE)
            self.original_id = self.source.domain.ID()
            require(not self.source.domain.autostart(), 'guard:autostart')
            # Validate isolation before creating state or shutting down a VM.
            self.test_xml = isolated_xml(self.original_xml, self.source.uuid, run,
                                         graphics_type=self.view.graphics_type)
            self.state = {'schema_version': 1, 'run': run, 'phase': 'validated',
                          'domain_uuid': self.source.uuid, 'domain_id': None,
                          'original_xml': self.original_xml,
                          'baseline_sha256': baseline.baseline_sha256(self.capture.state, self.directory)}
            self.save('validated')
            return self
        except BaseException:
            try:
                self.release()
            except BaseException:
                if self.ledger:
                    self.ledger.fail_outcome('cleanup', 'cleanup:lease-release-failed')
                log('cleanup:lease-release-failed')
            raise

    def guard(self, *, off=False):
        if self.capture.vm_ownership is not None:
            self.capture.vm_ownership.check_owner()
        self.capture.revalidate(off=off)
        require(self.source.baseline() == self.snapshot_xml, 'baseline:snapshot-metadata-changed')

    def verify_baseline(self):
        return self.capture.verify_snapshot()

    @property
    def attempt_released(self):
        return self.fd is None

    @observed('Preparing an isolated VM attempt')
    def prepare(self):
        self.snapshot_xml = self.source.baseline()
        # The initial shutdown is authorized for this identity-recorded source VM.
        self.save('shutdown-requested')
        self.source.shutdown(self.guard, requested=False)
        self.guard(off=True)
        self.save('restore-requested')
        self.mutated = True
        self.restore()
        require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                             self.capture.state['script_digest']) == self.capture.state['guest'], 'baseline:guest-changed')
        self.source.connection.defineXML(self.test_xml)
        self.view.run = self.state['run']
        self.guard(off=True)
        self.save('isolated')

    @contextmanager
    def snapshot_status(self, action, name):
        progress = getattr(self, 'watch_progress', None) or watch_progress
        label = f'{action} snapshot "{name}"'
        with operation(label), progress.snapshot_operation(label) if progress is not None else nullcontext():
            yield

    def restore(self):
        # snapshot revert defaults to its saved shutoff state; never pass RUNNING.
        self.guard(off=True)
        snap = self.source.domain.snapshotLookupByName(self.capture.state['proof']['name'], 0)
        require(snap.getXMLDesc(0) == self.snapshot_xml, 'baseline:snapshot-metadata-changed')
        with self.snapshot_status('Restoring', self.capture.state['proof']['name']):
            self.source.domain.revertToSnapshot(snap, 0)
        self.refresh_domain()
        self.view.run = None
        self.view.domain_id = None
        self.guard(off=True)
        self._recording_safe_after_shutdown()

    def _recording_safe_after_shutdown(self):
        """Caller has just proved this owned guest off; release its seals only."""
        from tools.vm_recording import capture_safe_after_shutdown
        capture_safe_after_shutdown(root=ROOT)

    def refresh_domain(self):
        # Revert changes the runtime instance without updating virDomain.ID().
        # Keep the journal's expected instance intact; refresh only the handle.
        domain = self.source.connection.lookupByUUIDString(self.source.uuid)
        require(domain.UUIDString() == self.source.uuid == self.state['domain_uuid'],
                'guard:domain-identity')
        self.source.domain = domain

    @observed('Starting the VM')
    def start(self):
        self.shutdown_request = None
        if getattr(self, 'online_pending', False) is True:
            from online_snapshot import start
            require(self.online_bootstrap is not None, 'online-snapshot:bootstrap-required')
            self.online_pending = False
            return start(self)
        self.guard(off=True)
        # Retire the current ownership interval before the disk transition.
        # Metadata checks resume after the domain instance has been recorded.
        self.capture.retire_vm_ownership()
        self.save('start-requested')
        self.source.domain.create()
        self.view.domain_id = self.source.domain.ID()
        require(self.view.domain_id >= 0, 'start:identity-unavailable')
        self.state['domain_id'] = self.view.domain_id
        self.guard()
        if self.ownership_run is not None:
            self.capture.begin_vm_ownership(self)
        self.save('running')
        from e2e_watch import attach
        attach(self)

    @observed('Stopping the VM')
    def stop(self):
        """Stop the recorded instance without restoring between backend callbacks."""
        self.guard()
        try:
            self.capture.retire_vm_ownership()
        except BaseException:
            # Metadata failure remains latched for final acceptance. Still
            # stop/restore our recorded guest if ownership is intact; a lost
            # VM lock instead makes the next guard refuse before any mutation.
            log('cleanup:metadata-check-failed')
        self.guard()
        if not self.view.snapshot()[1]:
            # Only the domain instance started and identity-recorded by this run.
            require(self.view.domain_id is not None, 'cleanup:unowned-domain')
            try:
                self.source.shutdown(self.guard, requested=False, request=self.shutdown_request)
            except Error as error:
                if str(error) != 'shutdown:timeout':
                    raise
                self.guard()
                self.source.domain.destroyFlags(0)
        self.guard(off=True)
        self._recording_safe_after_shutdown()

    @observed('Stopping the VM by restoring its baseline')
    def stop_by_restore(self):
        """Complete a graphical worker's off callback without an ACPI wait."""
        require(self.view.graphics_type == 'vnc', 'cleanup:graphics-required')
        self.guard()
        require(self.view.domain_id is not None and
                self.state['domain_id'] == self.view.domain_id,
                'cleanup:unowned-domain')
        from vm_internet import restore as restore_internet
        restore_internet(self)
        self.capture.retire_vm_ownership()
        self.guard()
        self.save('cleanup-requested')
        snap = self.source.domain.snapshotLookupByName(self.capture.state['proof']['name'], 0)
        require(snap.getXMLDesc(0) == self.snapshot_xml, 'baseline:snapshot-metadata-changed')
        with self.snapshot_status('Restoring', self.capture.state['proof']['name']):
            self.source.domain.revertToSnapshot(snap, self.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE)
        self.refresh_domain()
        self.view.run = None
        self.view.domain_id = None
        self.guard(off=True)
        self._recording_safe_after_shutdown()
        self.restored_by_callback = True

    def close_watch(self):
        if self.watch is not None:
            observer = self.watch
            observer.close()
            self.watch = None

    @observed('Restoring the VM and verifying cleanup')
    def finish(self):
        from vm_internet import restore as restore_internet
        restore_internet(self)
        if not self.mutated:
            self.save('complete')
            return
        if self.restored_by_callback:
            self.guard(off=True)
        else:
            self.save('cleanup-requested')
            self.stop()
            self.restore()
        self.delete_suite_snapshot()
        log('stage:restored-baseline-verification')
        if self.ownership_run is not None:
            self.capture.begin_vm_ownership(self)
        require(self.capture.verify_snapshot(boundary='restoration') ==
                self.capture.state['proof'], 'cleanup:baseline-changed')
        require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                             self.capture.state['script_digest']) == self.capture.state['guest'], 'cleanup:guest-changed')
        # Revert restores the snapshot's XML; restore the validated pre-run config.
        self.source.connection.defineXML(self.original_xml)
        self.capture.revalidate(off=True)
        self.save('complete')

    def delete_suite_snapshot(self):
        """Recovery may remove only the journaled E2E version, while off."""
        name = self.state.get('e2e_snapshot')
        if name is None:
            return
        require(isinstance(name, str) and
                re.fullmatch(r'onpc-(?:v[0-9]+(?:\.[0-9]+)*|[0-9][A-Za-z0-9.+:~\-]*)', name),
                'suite:invalid-snapshot-name')
        self.guard(off=True)
        if name in self.source.domain.snapshotListNames(0):
            with self.snapshot_status('Deleting', name):
                self.source.domain.snapshotLookupByName(name, 0).delete(0)

    def release(self):
        pending = None
        if self.capture.vm_ownership is not None:
            try:
                self.capture.vm_ownership.close()
            except BaseException as error:
                pending = error
        # A refused concurrent lease may share this command adapter. It must
        # not clear the active owner's inherited-lock reference.
        if self.fd is not None and self.commands.lock_fd == self.fd:
            self.commands.lock_fd = None
            self.commands.compatibility_fd = None
        if self.fd is not None:
            try:
                os.close(self.fd)
            except BaseException as error:
                pending = pending if pending is not None else error
            finally:
                self.fd = None
        if self.compatibility_fd is not None:
            try:
                os.close(self.compatibility_fd)
            except BaseException as error:
                pending = pending if pending is not None else error
            finally:
                self.compatibility_fd = None
        try:
            if self.watch_detached and self.watch is not None:
                self.watch.detach()
                self.watch = None
            else:
                self.close_watch()
        except BaseException as error:
            pending = pending if pending is not None else error
        if pending is not None:
            raise pending

    def recover_graphical_cleanup(self):
        """Resume a recorded VNC cleanup, or verify an already restored off guest.

        No start, preparation or new baseline is allowed. An off guest either
        matches the restored original XML or the recorded pre-start isolation.
        """
        require(self.fd is None and self.view.graphics_type == 'vnc', 'recovery:invalid-lease')
        self._recover_recorded_cleanup()

    def recover_system_cleanup(self):
        """Resume recorded installed-system cleanup or verify its restored state."""
        require(self.fd is None and self.view.graphics_type == 'spice', 'recovery:invalid-lease')
        self._recover_recorded_cleanup()

    @observed('Validating and recovering the recorded VM attempt')
    def _recover_recorded_cleanup(self):
        """Reacquire ownership and verify every saved identity before mutation."""
        try:
            self.capture.directory_identity = self.capture.private_directory()
            self.compatibility_fd = baseline.compatibility_lock(self.directory)
            self.fd = baseline.open_controller_lock(self.capture.lock_path)
            baseline.identity(self.capture.lock_path, private=True, mode=0o600)
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Error('state:busy-controller') from error
            self.commands.lock_fd = self.fd
            self.commands.compatibility_fd = self.compatibility_fd
            self.capture.state = self.capture.read_state()
            require(self.capture.state['phase'] == 'finalized', 'baseline:not-finalized')
            baseline.identity(self.journal, private=True, mode=0o600)
            state = baseline.parse_json(self.journal.read_bytes())
            isolated = isinstance(state, dict) and (
                state.get('phase') == 'isolated' or
                (state.get('phase') == 'cleanup-requested' and state.get('domain_id') is None))
            require(isinstance(state, dict) and set(state) - {'e2e_snapshot', 'internet_isolation'} == {
                'schema_version', 'run', 'phase', 'domain_uuid', 'domain_id',
                'original_xml', 'baseline_sha256'} and state['schema_version'] == 1 and
                state['phase'] in ('running', 'cleanup-requested', 'isolated') and
                isinstance(state['run'], str) and re.fullmatch(r'[0-9a-f]{32}', state['run']) and
                ((isolated and state['domain_id'] is None) or
                 (not isolated and type(state['domain_id']) is int and state['domain_id'] >= 0)) and
                state['domain_uuid'] == self.source.uuid and
                state['baseline_sha256'] == baseline.baseline_sha256(self.capture.state, self.directory),
                'recovery:journal-identity')
            require('e2e_snapshot' not in state or (
                self.view.graphics_type == 'vnc' and isinstance(state['e2e_snapshot'], str) and
                re.fullmatch(r'onpc-(?:v[0-9]+(?:\.[0-9]+)*|[0-9][A-Za-z0-9.+:~\-]*)', state['e2e_snapshot'])),
                'recovery:snapshot-identity')
            maintenance = self.directory / 'vm-control.json'
            if os.path.lexists(maintenance):
                baseline.identity(maintenance, private=True, mode=0o600)
                owner = baseline.parse_json(maintenance.read_bytes())
                require(isinstance(owner, dict) and owner.get('run') != state['run'],
                        'recovery:maintenance-owned; use tools/test-vm stop')
            off = self.source.domain.ID() == -1
            require(not self.source.domain.autostart() and
                    (off if isolated else (off or self.source.domain.ID() == state['domain_id'])),
                    'recovery:domain-replaced-or-off')
            active_xml = self.source.domain.XMLDesc(0)
            restored_off = (off and state['phase'] != 'isolated' and
                            self.source.domain.XMLDesc(self.source.api.VIR_DOMAIN_XML_INACTIVE) ==
                            state['original_xml'])
            off_isolated = off and state['phase'] != 'isolated' and not restored_off
            if off_isolated:
                # The recorded guest is off but still has one isolated configuration.
                # Cleanup may already have been requested, or the attempt may still
                # be marked running because libvirtd or the host stopped first.
                # A split active/inactive configuration is not that guest.
                require(state['phase'] in ('running', 'cleanup-requested') and
                        self.source.domain.XMLDesc(self.source.api.VIR_DOMAIN_XML_INACTIVE) == active_xml,
                        'recovery:off-configuration-changed')
            if not restored_off:
                display_root = ET.fromstring(active_xml)
                displays = display_root.findall('devices/graphics')
                if self.view.graphics_type == 'vnc':
                    validate_private_vnc(display_root)
                else:
                    validate_observer(displays)
                    require(displays[0].get('type') == self.view.graphics_type,
                            'recovery:graphics-changed')
            self.original_xml = state['original_xml']
            require(baseline.domain_layout(self.original_xml, self.source.uuid) ==
                    baseline.recorded_layout(self.capture.state['source']['layout']), 'recovery:original-layout')
            isolated_xml(self.original_xml, self.source.uuid, state['run'],
                         graphics_type=self.view.graphics_type)
            self.state = state
            self.view.run = None if restored_off else state['run']
            self.view.domain_id = None if off else state['domain_id']
            self.snapshot_xml = self.source.baseline()
            if (off_isolated and state['domain_id'] is None and
                    ET.fromstring(active_xml).findtext('description') != TAG + state['run']):
                # Interrupted online startup can restore the saved snapshot's
                # tag before recording the new attempt. Only an off graphical
                # guest with its exact private snapshot/isolation proof may be
                # restored here. Never adopt or stop an unrecorded live instance.
                require(self.view.graphics_type == 'vnc' and
                        state['phase'] == 'cleanup-requested', 'guard:run-identity')
                from online_snapshot import recover_identity
                self.view.run = recover_identity(self)
            if off:
                self.guard(off=True)
            else:
                self.guard()
            require(self.capture.verify_snapshot(boundary='recovery') ==
                    self.capture.state['proof'], 'recovery:baseline-changed')
            from vm_internet import restore as restore_internet
            restore_internet(self)
            if restored_off:
                # No domain mutation is authorized by the off-state branch.
                # Independently audit the restored guest and reconcile the
                # exact inactive configuration again before completing cleanup.
                require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                                     self.capture.state['script_digest']) ==
                        self.capture.state['guest'], 'recovery:guest-changed')
                self.guard(off=True)
                require(self.source.domain.ID() == -1 and
                        self.source.domain.XMLDesc(self.source.api.VIR_DOMAIN_XML_INACTIVE) ==
                        self.original_xml, 'recovery:off-configuration-changed')
                self.delete_suite_snapshot()
                self.save('complete')
                log('recovery:verified-restored-off')
                return
            if off_isolated:
                # The recorded instance is gone. Restore its outer baseline and
                # the original domain configuration. Never start or adopt it.
                self.restore()
                self.delete_suite_snapshot()
                require(self.capture.verify_snapshot(boundary='restoration') ==
                        self.capture.state['proof'], 'cleanup:baseline-changed')
                require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                                     self.capture.state['script_digest']) ==
                        self.capture.state['guest'], 'cleanup:guest-changed')
                self.source.connection.defineXML(self.original_xml)
                self.capture.revalidate(off=True)
                self.save('complete')
                log('recovery:restored-interrupted-off')
                return
            self.mutated = True
            # An interrupted bootstrap may leave a never-started isolated
            # guest. The held lock, null instance ID, run-tagged configuration,
            # unchanged disk identities and full snapshot proof above authorize
            # only the existing outer restoration, never starting the guest.
            log('recovery:recorded-cleanup')
            self.finish()
        finally:
            self.release()

    def __exit__(self, exc_type, exc_value, traceback):
        if (self.ledger and exc_type is not None and
                all(self.ledger.outcomes[name]['outcome'] != 'failed'
                    for name in ('product', 'infrastructure', 'collection'))):
            self.ledger.fail_outcome('infrastructure', error_category(exc_value))
        pending = exc_value
        try:
            try:
                measurement = self.ledger.measure('cleanup') if self.ledger else nullcontext()
                with measurement:
                    self.finish()
                if self.ledger:
                    self.ledger.pass_outcome('cleanup')
            except BaseException as error:
                if self.ledger:
                    self.ledger.fail_outcome('cleanup', error_category(error))
                pending = pending if pending is not None else error
                log('cleanup:failed')
            # Also retain incomplete-cleanup evidence. Callback failure cannot
            # retry restoration, skip release, or replace an earlier failure.
            if self.finalize is not None:
                try:
                    with self.ledger.measure('finalization') if self.ledger else nullcontext():
                        self.finalize(self)
                except BaseException as error:
                    if self.ledger:
                        record_caught_failure(self.ledger, error)
                    pending = pending if pending is not None else error
                    log('finalization:failed')
        finally:
            try:
                self.release()
            except BaseException as error:
                if self.ledger:
                    self.ledger.fail_outcome('cleanup', 'cleanup:lease-release-failed')
                pending = pending if pending is not None else error
        if exc_type is None and pending is not None:
            raise pending


def check_tree(root):
    root = baseline.canonical(root)
    require(root.is_dir(), 'assets:directory')
    for path in root.rglob('*'):
        info = path.lstat()
        require(not path.is_symlink() and (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)),
                'assets:special-file')
    return root


def artifact_source(path):
    """Validate supplied inputs before creating run storage; never log paths."""
    require(path is not None, 'assets:directory-required')
    try:
        source = check_tree(path.resolve(strict=True))
    except FileNotFoundError as error:
        raise Error('assets:source-missing') from error
    except PermissionError as error:
        raise Error('assets:source-inaccessible') from error
    except OSError as error:
        raise Error('assets:source-unavailable') from error
    log('assets:source-validated')
    return source


def stage_assets(source, destination, commands):
    """Freeze user-built artifacts in root-private storage, then recheck all bytes."""
    sys.path.insert(0, str(ROOT / 'tools'))
    sys.path.insert(0, str(ROOT / 'tests/fixtures'))
    from build_test_artifacts import verify
    from build_test_applications import verify as verify_fixtures
    check_tree(source)
    shutil.copytree(source, destination)
    check_tree(destination)
    manifest = verify(destination)
    package = destination / manifest['artifacts']['package']['path']
    fixtures = destination / manifest['artifacts']['fixtures']['path']
    verify_fixtures(fixtures)
    require((fixtures / 'onpc-test-application.flatpak').is_file(), 'assets:fixture-bundle-missing')
    require(package.suffix in ('.deb', '.rpm'), 'assets:package-format')
    shutil.copyfile(package, destination / ('package' + package.suffix))
    if package.suffix == '.rpm':
        require(commands.run(['rpm', '-qp', '--queryformat', '%{NAME}', str(package)],
                             merge_stderr=False).decode().strip() ==
                'oh-no-parent-control', 'assets:package-name')
        raw = commands.run(['rpm', '-qp', '--queryformat',
            '[%{FILENAMES}\t%{FILEMODES}\t%{FILELINKTOS}\n]', str(package)], merge_stderr=False)
        entries = []
        for row in raw.decode().splitlines():
            path, mode, target = row.split('\t')
            require(path.startswith('/') and '..' not in Path(path).parts, 'assets:package-path')
            mode = int(mode)
            if stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                entries.append({'path': path, 'kind': 'symlink' if stat.S_ISLNK(mode) else 'file',
                                'mode': stat.S_IMODE(mode), 'target': target})
            else:
                require(stat.S_ISDIR(mode), 'assets:package-special-file')
        require(entries, 'assets:empty-package')
        (destination / 'installed-files.json').write_bytes(baseline.encode(entries))
        inventory = {str(p.relative_to(destination)): baseline.digest(p)
                     for p in sorted(destination.rglob('*')) if p.is_file()}
        (destination / 'transfer-sha256.json').write_bytes(baseline.encode(inventory))
        return manifest
    require(commands.run(['dpkg-deb', '-f', str(package), 'Package']).decode().strip() ==
            'oh-no-parent-control', 'assets:package-name')
    archive = commands.run(['dpkg-deb', '--fsys-tarfile', str(package)])
    import io
    entries = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
        for entry in tar:
            require(not Path(entry.name).is_absolute() and '..' not in Path(entry.name).parts, 'assets:package-path')
            if entry.isfile() or entry.issym():
                entries.append({'path': '/' + entry.name.removeprefix('./'),
                                'kind': 'file' if entry.isfile() else 'symlink',
                                'mode': entry.mode, 'target': entry.linkname})
            else:
                require(entry.isdir(), 'assets:package-special-file')
    (destination / 'installed-files.json').write_bytes(baseline.encode(entries))
    # Every transferred file, including Flatpak's varying delivery container,
    # receives an exact run digest in addition to the stable payload digest.
    inventory = {str(p.relative_to(destination)): baseline.digest(p)
                 for p in sorted(destination.rglob('*')) if p.is_file()}
    (destination / 'transfer-sha256.json').write_bytes(baseline.encode(inventory))
    return manifest


def stage_previous_assets(source, destination, commands, current, *, genuine=False):
    """Bind an explicit prior package to the same platform as the current one."""
    previous = stage_assets(source, destination, commands)
    old_format = Path(previous['artifacts']['package']['path']).suffix
    new_format = Path(current['artifacts']['package']['path']).suffix
    require(old_format == new_format, 'assets:previous-package-format')
    require(previous['artifacts']['package']['sha256'] !=
            current['artifacts']['package']['sha256'], 'assets:identical-update-payload')
    upgrade_identity = None
    if genuine:
        from build_test_artifacts import verify_upgrade
        # Reuse the independently verified release/current pair validator after
        # freezing both inputs. No mutable input-parent layout is trusted.
        upgrade_identity = verify_upgrade(destination.parent, staged=True, repository=ROOT)
    payload = destination.parent if genuine else destination.parent / 'input'
    shutil.copyfile(destination / ('package' + old_format),
                    payload / ('previous-package' + old_format))
    current['previous_package'] = {
        'sha256': previous['artifacts']['package']['sha256'], 'source': previous['source']}
    if upgrade_identity is not None:
        current['previous_package']['upgrade_identity'] = upgrade_identity
    (payload / 'previous-inputs.json').write_bytes(baseline.encode(current['previous_package']))


def stage_upgrade_assets(source, destination, commands):
    """Finite pinned-release/current binding; no arbitrary bundle interface."""
    from build_test_artifacts import verify_upgrade
    from provenance import snapshot
    before = snapshot(source)
    verify_upgrade(source, repository=ROOT)
    manifest = stage_assets(source / 'current', destination, commands)
    stage_assets(source / 'previous', destination / 'previous', commands)
    require(snapshot(source) == before, 'assets:upgrade-source-changed')
    # These finite files are created by staging, rather than copied source
    # metadata. Make their privacy independent of the controller's umask.
    for root in (destination, destination / 'previous'):
        package = 'package' + Path(manifest['artifacts']['package']['path']).suffix
        for name in (package, 'installed-files.json', 'transfer-sha256.json'):
            (root / name).chmod(0o600)
    (destination / 'previous').chmod(0o700)
    inventory = {str(p.relative_to(destination)): baseline.digest(p)
                 for p in sorted(destination.rglob('*'))
                 if p.is_file() and p != destination / 'transfer-sha256.json'}
    (destination / 'transfer-sha256.json').write_bytes(baseline.encode(inventory))
    verify_upgrade(destination, staged=True, repository=ROOT)
    return manifest


def stage_selected_inputs(selection, destination):
    """Freeze and identify only the test/helper files needed by this selection."""
    selected_areas = {execution.area for execution in selection.executions}
    inputs = [('Makefile', 'install-source/Makefile'), *COMMON_SELECTED_INPUTS]
    if selection.qualification_failure:
        inputs.append(('tests/integration/system_qualification.py', 'system_qualification.py'))
    for area in AREA_SOURCES:
        if area not in selected_areas:
            continue
        inputs.append((str(AREA_SOURCES[area].relative_to(ROOT)), AREA_SOURCES[area].name))
    # Areas share transport/assertion helpers. Coalesce identical declarations
    # in stable order, but still refuse two different sources for one target.
    inputs = list(dict.fromkeys(inputs))
    require(len({target for _, target in inputs}) == len(inputs),
            'selection:duplicate-input-target')

    from guest_inputs import Bundle
    files = Bundle(ROOT, inputs).stage(destination)
    identity = {
        'schema_version': 1,
        'selection': {
            'scope': selection.scope,
            'area': selection.area,
            'test': selection.test,
            'qualification_failure': selection.qualification_failure,
            'phases': list(selection.phases),
            'executions': [
                {'phase': item.phase, 'area': item.area, 'case_id': item.case_id,
                 'prerequisite': item.prerequisite}
                for item in selection.executions
            ],
        },
        'files': files,
    }
    if any(item.area == 'package' and item.case_id == KIOSK_ACTIVATION_CASE
           for item in selection.executions):
        identity['host_files'] = kiosk_activation_host_inputs()
    path = destination / 'selected-inputs.json'
    path.write_bytes(baseline.encode(identity))
    digest = baseline.digest(path)
    log(f'provenance:selected-inputs files={len(files)} sha256={digest}')
    return digest


def kiosk_activation_host_inputs():
    from guest_inputs import read
    return {source: hashlib.sha256(read(ROOT, source)).hexdigest()
            for source in KIOSK_ACTIVATION_HOST_INPUTS}


def observe_kiosk_activation(vm, lease, directory, selection, phase):
    """Extend only the declared continuous native activation history."""
    if not any(item.area == 'package' and item.case_id == KIOSK_ACTIVATION_CASE
               for item in phase_executions(selection, phase)):
        return
    from kiosk_entry import observe_activation
    semantic = PHASE_SEMANTICS.get(phase, phase)
    inputs = json.loads((directory / 'input/selected-inputs.json').read_bytes())
    require(kiosk_activation_host_inputs() == inputs['host_files'],
            'kiosk-activation:host-inputs-changed')
    before = json.loads(vm.call(guest_command(lease.state['run'], 'activation-state', semantic)))
    if semantic == 'installed':
        vm.call(guest_command(lease.state['run'], 'prepare-activation-greeter'), timeout=150)
    lease.save('gdm-activation-' + phase)
    observed = observe_activation(vm, lease, semantic)
    after = json.loads(vm.call(guest_command(lease.state['run'], 'activation-state', semantic)))
    require(before == after and observed['boot_sha256'] == before['boot_sha256'],
            'kiosk-activation:boot-or-policy-changed')
    require(kiosk_activation_host_inputs() == inputs['host_files'],
            'kiosk-activation:host-inputs-changed')
    if semantic == 'rebooted':
        installed_phase = phase.removesuffix('rebooted') + 'installed'
        previous = json.loads((directory / ('guest-results/gdm-' + installed_phase + '.json')).read_bytes())
        require(previous['boot_sha256'] != observed['boot_sha256'],
                'kiosk-activation:boot-not-changed')
    observed['activation_state'] = after
    observed['host_files'] = inputs['host_files']
    output = directory / 'guest-results'
    output.mkdir(mode=0o700, exist_ok=True)
    (output / ('gdm-' + phase + '.json')).write_bytes(baseline.encode(observed))


def run_kiosk_activation(vm, lease, directory, selection, phase, ledger):
    """Keep assertion failures distinct from transport and input-safety failures."""
    from private_artifacts import EvidenceError
    try:
        observe_kiosk_activation(vm, lease, directory, selection, phase)
    except EvidenceError as error:
        # Recipient/boot/freshness refusals are harness safety failures. Public
        # product observations retain their own fixed actionable assertion code.
        domain = 'infrastructure' if str(error).startswith('kiosk-activation:') else 'product'
        ledger.fail_outcome(domain, error_category(error))
        raise
    except CommandError as error:
        domain = 'product' if vm.commands.last_returncode == 1 else 'infrastructure'
        ledger.fail_outcome(domain, 'kiosk-activation:guest-check-failed' if domain == 'product'
                            else error_category(error))
        raise
    except Error as error:
        domain = 'product' if str(error) == 'kiosk-activation:boot-or-policy-changed' else 'infrastructure'
        ledger.fail_outcome(domain, error_category(error))
        raise


@contextmanager
def mounted_guest(guestfs, lease, *, readonly=False, with_root=False):
    """Open the guarded offline disk; always close it before another writer."""
    lease.guard(off=True)
    disk = Path(lease.capture.state['source']['layout']['disk'])
    g = guestfs.GuestFS(python_return_dict=True)
    try:
        g.set_backend('direct')
        g.set_network(False)
        g.add_drive_opts(str(disk), format='qcow2', readonly=readonly)
        g.launch()
        roots = g.inspect_os()
        require(len(roots) == 1, 'bootstrap:guest-root')
        mounts = g.inspect_get_mountpoints(roots[0])
        for point in sorted(mounts, key=lambda v: (len(v), v)):
            (g.mount_ro if readonly else g.mount)(mounts[point], point)
        yield (g, roots[0]) if with_root else g
        if not readonly:
            g.sync()
    finally:
        g.close()
    lease.guard(off=True)


def retire_snapshot_payload(g, run):
    """Keep old fixture evidence outside the next attempt's executable input tree."""
    require(re.fullmatch(r'[0-9a-f]{32}', run or ''), 'bootstrap:payload-run')
    require(g.realpath('/var/tmp') == '/var/tmp' and not g.is_symlink(PAYLOAD),
            'bootstrap:payload-path')
    if not g.exists(PAYLOAD):
        return
    info = g.lstatns(PAYLOAD)
    require(stat.S_ISDIR(info['st_mode']) and info['st_uid'] == info['st_gid'] == 0
            and not stat.S_IMODE(info['st_mode']) & 0o022, 'bootstrap:payload-owner')
    # Snapshot creation and later cases can share one lease/run identity.
    previous = PAYLOAD + '-snapshot-' + run + '-' + uuid.uuid4().hex
    require(not g.exists(previous) and not g.is_symlink(previous),
            'bootstrap:payload-archive-exists')
    g.mv(PAYLOAD, previous)
    require(not g.exists(PAYLOAD) and g.exists(previous), 'bootstrap:payload-retirement')


@observed('Preparing the VM SSH transport and guest inputs')
def bootstrap(commands, lease, directory, guestfs, *, observation_only=False):
    """Prepare SSH only on the reset, powered-off active disk via libguestfs."""
    if getattr(lease, 'online_pending', False) is True:
        require(not observation_only, 'online-snapshot:installed-inputs-required')
        from online_snapshot import stage
        return stage(commands, lease, directory)
    lease.guard(off=True)
    key = directory / 'ssh-key'
    commands.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'onpc-system-test', '-f', str(key)])
    lease.save('ssh-bootstrap')
    with mounted_guest(guestfs, lease, with_root=True) as (g, root):
        os_id, version = baseline.guest_contract.inspected_release(g, root)
        package = directory / 'input' / ('package.rpm' if os_id == 'fedora' else 'package.deb')
        if not observation_only:
            require(package.is_file(), 'assets:package-platform-mismatch:' + os_id)
        if os_id == 'ubuntu':
            baseline.guest_contract.guest_tools.verify_packages(g.read_file('/var/lib/dpkg/status').decode())
            from chinese_language_assets import verify as verify_chinese
            verify_chinese(g)
            sources_path = '/etc/apt/sources.list.d/ubuntu.sources'
            sources = g.read_file(sources_path).decode()
            require(baseline.guest_contract.guest_tools.ubuntu_archive_sources(sources) == sources,
                    'bootstrap:archive-not-prepared')
            log('bootstrap:ubuntu-archive-https-ready')
        else:
            baseline.guest_contract.selinux_policy(g.read_file('/etc/selinux/config').decode())
            baseline.guest_contract.guest_tools.verify_fedora_packages(
                (row['app2_name'], row['app2_version'])
                for row in g.inspect_list_applications2(root))
            from chinese_language_assets import verify as verify_chinese
            verify_chinese(g, os_id)
            log('bootstrap:fedora-tools-ready')
        marker = {'purpose': 'onpc-system-test', 'run': lease.state['run'],
                  'domain_uuid': lease.source.uuid,
                  'machine_id': g.read_file('/etc/machine-id').decode().strip(),
                  'host_machine_id': Path('/etc/machine-id').read_text().strip(),
                  'baseline_sha256': lease.state['baseline_sha256'],
                  'preparation_sha256': lease.capture.state['guest']['preparation_record_sha256'],
                  'selected_inputs_sha256': baseline.digest(
                      directory / 'input/selected-inputs.json')}
        if observation_only:
            marker['scope'] = 'graphical-observation-only'
        else:
            marker['package_sha256'] = baseline.digest(package)
            # A restored installation snapshot may contain helpers, bytecode
            # and assets removed from the new input manifest. Start fresh;
            # overwriting just the files still declared would retain them.
            retire_snapshot_payload(g, lease.state['run'])
        require(marker['machine_id'] != marker['host_machine_id'], 'bootstrap:host-identity')
        g.write('/etc/onpc-system-test.json', baseline.encode(marker))
        g.chown(0, 0, '/etc/onpc-system-test.json')
        g.chmod(0o600, '/etc/onpc-system-test.json')
        # OpenSSH is prepared in the clean baseline. Only this attempt's public
        # key is added, using the documented authorized_keys file interface.
        public_key = key.with_suffix('.pub').read_bytes()
        require(re.fullmatch(rb'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]*)?\n?', public_key),
                'bootstrap:public-key')
        root_accounts = [row.split(':') for row in g.read_file('/etc/passwd').decode().splitlines()
                         if row.startswith('root:')]
        require(len(root_accounts) == 1 and len(root_accounts[0]) == 7 and
                root_accounts[0][2:4] == ['0', '0'] and root_accounts[0][5] == '/root',
                'bootstrap:root-home')
        require(g.realpath('/root') == '/root', 'bootstrap:root-home')
        ssh_directory = '/root/.ssh'
        authorized = ssh_directory + '/authorized_keys'
        require(not g.is_symlink(ssh_directory) and not g.is_symlink(authorized),
                'bootstrap:ssh-path')
        if not g.exists(ssh_directory):
            g.mkdir(ssh_directory)
        ssh_info = g.lstatns(ssh_directory)
        require(stat.S_ISDIR(ssh_info['st_mode']) and ssh_info['st_uid'] == ssh_info['st_gid'] == 0,
                'bootstrap:ssh-directory')
        prior = b''
        if g.exists(authorized):
            info = g.lstatns(authorized)
            require(stat.S_ISREG(info['st_mode']) and info['st_uid'] == info['st_gid'] == 0
                    and info['st_nlink'] == 1 and g.filesize(authorized) <= 1024 * 1024,
                    'bootstrap:authorized-keys')
            prior = g.read_file(authorized)
        authorized_contents = prior.rstrip(b'\n') + (b'\n' if prior else b'') + public_key.rstrip(b'\n') + b'\n'
        g.chmod(0o700, ssh_directory)
        g.write(authorized, authorized_contents)
        g.chown(0, 0, authorized)
        g.chmod(0o600, authorized)
        if os_id == 'fedora':
            policy = baseline.guest_contract.selinux_policy(g.read_file('/etc/selinux/config').decode())
            paths = ['/etc/onpc-system-test.json', ssh_directory]
            # Match baseline preparation's supported mounted-guest setfiles
            # route when the host appliance lacks SELinux relabel support.
            if not g.feature_available(['selinuxrelabel']):
                require(g.is_file('/usr/sbin/setfiles'), 'bootstrap:selinux-setfiles-missing')
                g.command(['/usr/sbin/setfiles', '-m', policy, *paths])
            else:
                for path in paths:
                    g.selinux_relabel(policy, path)
    # Keep independent readback after sync/close; eliminate only the intervening
    # package-install appliance, not the post-write or host-key verification.
    with mounted_guest(guestfs, lease, readonly=True) as g:
        require(g.read_file('/etc/onpc-system-test.json') == baseline.encode(marker)
                and g.read_file(authorized) == authorized_contents, 'bootstrap:write-readback')
        for path, mode in ((authorized, 0o600), ('/etc/onpc-system-test.json', 0o600)):
            info = g.lstatns(path)
            require(stat.S_ISREG(info['st_mode']) and stat.S_IMODE(info['st_mode']) == mode
                    and info['st_uid'] == info['st_gid'] == 0, 'bootstrap:write-permissions')
        host_key = g.read_file('/etc/ssh/ssh_host_ed25519_key.pub').decode().split()
        require(len(host_key) >= 2 and host_key[0] == 'ssh-ed25519', 'bootstrap:ssh-host-key')
    return ' '.join(host_key[:2])


@observed('Waiting for the VM network address')
def address(source, timeout=300):
    """Wait on libvirt's DHCP lease list with a bounded event-loop timer."""
    deadline = time.monotonic() + timeout
    event = threading.Event()
    timer = source.api.virEventAddTimeout(500, lambda *_: event.set(), None)
    observed_count = 0
    try:
        while time.monotonic() < deadline:
            interfaces = source.domain.interfaceAddresses(source.api.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE, 0)
            addresses = [a['addr'] for item in interfaces.values() for a in item.get('addrs', [])
                         if a['type'] == source.api.VIR_IP_ADDR_TYPE_IPV4]
            observed_count = len(addresses)
            if len(addresses) == 1:
                value = ipaddress.ip_address(addresses[0])
                require(value.is_private and not value.is_loopback, 'network:address')
                return str(value)
            event.wait(max(0, deadline - time.monotonic()))
            event.clear()
        log(f'network:readiness-timeout ipv4-lease-count={observed_count}')
        raise Error('network:readiness-timeout')
    finally:
        source.api.virEventRemoveTimeout(timer)


def guest_command(run, *args):
    return ['env', f'ONPC_EXPECTED_RUN={run}', 'PYTHONDONTWRITEBYTECODE=1',
            '/usr/bin/python3', PAYLOAD + '/system_guest.py', *args]


def phase_executions(selection, phase):
    """Return the exact registered executions assigned to one guest phase."""
    require(phase in selection.phases, 'pytest:unselected-phase')
    executions = tuple(item for item in selection.executions if item.phase == phase)
    require(executions, 'pytest:empty-phase')
    return executions


def pytest_command(run, phase, selection):
    require(phase in PHASE_ORDER, 'pytest:phase')
    selectors = [f'{PAYLOAD}/{AREA_SOURCES[item.area].name}::{item.case_id}'
                 for item in phase_executions(selection, phase)]
    qualification = (['-p', 'system_qualification', '--onpc-qualification-failure']
                     if selection.qualification_failure and phase == 'authorization' else [])
    return ['env', f'ONPC_EXPECTED_RUN={run}', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
            f'ONPC_SYSTEM_PHASE={PHASE_SEMANTICS.get(phase, phase)}',
            'ONPC_REGRESSION_EVENTS=1', f'ONPC_REGRESSION_PRIVATE={PAYLOAD}/results',
            f'PYTHONPATH={PAYLOAD}',
            'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-m', 'pytest',
            '-c', PAYLOAD + '/pytest.ini', '--noconftest', '--rootdir', PAYLOAD,
            '--junitxml', f'{PAYLOAD}/results/{phase}.xml', '-q', '-p', 'system_progress',
            *qualification, *selectors]


def junit_executions(path, phase):
    """Read exact registered execution identities from one pytest JUnit file."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError, ValueError) as error:
        raise Error(f'pytest:missing-or-invalid-junit:{phase}') from error
    sources = {path.stem: area for area, path in AREA_SOURCES.items()}
    executions = []
    for case in root.iter('testcase'):
        name = case.get('name')
        module = (case.get('classname') or '').rsplit('.', 1)[-1]
        require(module in sources and name, f'pytest:incorrect-test-identity:{phase}')
        executions.append((sources[module], name))
    require(executions, f'pytest:missing-tests:{phase}')
    return root, tuple(executions)


def reconcile_junit(directory, phase, selection):
    """Reject failed, skipped, missing, duplicate, or unexpected guest cases."""
    root, executed = junit_executions(directory / f'guest-results/{phase}.xml', phase)
    try:
        unhealthy = any(int(suite.get(key, '0')) != 0
                        for suite in root.iter('testsuite')
                        for key in ('errors', 'failures', 'skipped'))
    except ValueError as error:
        raise Error(f'pytest:missing-or-invalid-junit:{phase}') from error
    unhealthy = unhealthy or any(case.find(key) is not None
                                 for case in root.iter('testcase')
                                 for key in ('error', 'failure', 'skipped'))
    require(not unhealthy, f'pytest:failed-or-skipped-tests:{phase}')
    expected = tuple((item.area, item.case_id) for item in phase_executions(selection, phase))
    require(len(executed) == len(set(executed)) and set(executed) == set(expected),
            f'pytest:missing-extra-or-duplicate-tests:{phase}')
    return executed


def is_qualification_failure(directory, selection):
    """Recognize only the fixed fault with the complete, otherwise healthy scope."""
    if not selection.qualification_failure:
        return False
    try:
        for phase in selection.phases:
            if phase != 'authorization':
                reconcile_junit(directory, phase, selection)
        root, identities = junit_executions(directory / 'guest-results/authorization.xml',
                                           'authorization')
        if identities != (('authorization', QUALIFICATION_CASE),):
            return False
        failures = list(root.iter('failure'))
        return (len(failures) == 1 and
                failures[0].get('message') == 'Failed: ' + QUALIFICATION_FAILURE and
                next(root.iter('error'), None) is None and
                next(root.iter('skipped'), None) is None and
                all(int(suite.get('errors', '0')) == int(suite.get('skipped', '0')) == 0
                    and int(suite.get('failures', '0')) == 1
                    for suite in root.iter('testsuite')))
    except (Error, ValueError):
        return False


@observed('Capturing the VM screen after session diagnostics')
def capture_session_screen(lease, output):
    """Capture the already-owned VM after fixed session diagnostics complete.

    A fixed non-text modifier wakes the display after the foreground VT check.
    It cannot submit credentials or dismiss the lock. No caller-selected input
    is accepted; images remain in private test storage.
    """
    lease.guard()
    lease.source.domain.sendKey(lease.source.api.VIR_KEYCODE_SET_LINUX, 100, [42], 1, 0)
    lease.guard()
    time.sleep(1)
    lease.guard()
    output.mkdir(mode=0o700, exist_ok=True)
    stream = lease.source.connection.newStream(0)
    try:
        mime = lease.source.domain.screenshot(stream, 0, 0)
        require(mime in ('image/png', 'image/x-portable-pixmap'), 'session-capture:image-format')
        path = output / ('session-screen.png' if mime == 'image/png' else 'session-screen.ppm')
        size = 0
        with path.open('xb') as target:
            def receive(_stream, data, _opaque):
                nonlocal size
                size += len(data)
                require(size <= 32 * 1024 * 1024, 'session-capture:image-size')
                target.write(data)
                return 0
            stream.recvAll(receive, None)
        stream.finish()
        require(size > 0, 'session-capture:empty-image')
        lease.guard()
    except BaseException:
        stream.abort()
        raise


def run_pytest(vm, run, phase, selection):
    """Forward only registered test events; raw SSH output stays private."""
    from system_progress import Progress
    previous = getattr(vm.commands, 'progress', None)
    vm.commands.progress = Progress(phase, phase_executions(selection, phase), watch=watch_progress)
    try:
        return vm.call(pytest_command(run, phase, selection),
                       timeout=2400 if phase in (*FIRST_CONFIGURE_PHASES, *PAM_PHASES, 'previous-policy', TRUSTED_FIXTURES_PHASE) or any(phase in history.phases
                                           for history in REMOVAL_HISTORIES) else 900)
    finally:
        vm.commands.progress.close()
        vm.commands.progress = previous


def installed_run(vm, lease, directory, selection, ledger=None, *, already_installed=False):
    ledger = ledger or RunLedger()
    run = lease.state['run']
    outcome = 'failed'
    qualification_pending = False
    try:
        with ledger.measure('bootstrap'):
            vm.ready()
            vm.copy(False, str(directory / 'input') + '/', PAYLOAD + '/')
        previous = [directory / 'input' / ('previous-package.' + extension)
                    for extension in ('deb', 'rpm')]
        require(sum(path.exists() for path in previous) <= 1, 'assets:ambiguous-previous-package')
        has_previous = any(path.exists() for path in previous)
        previous_policy = any(item.case_id == PREVIOUS_POLICY_CASE for item in selection.executions)
        trusted_fixtures = any(item.case_id == TRUSTED_FIXTURES_CASE for item in selection.executions)
        require(not trusted_fixtures or (has_previous and not already_installed and
                selection.phases == (TRUSTED_FIXTURES_PHASE,) and
                selection.executions == (CaseExecution(TRUSTED_FIXTURES_PHASE, 'package',
                                                       TRUSTED_FIXTURES_CASE, False),)),
                'selection:trusted-fixtures-requires-isolated-old-package')
        require(not previous_policy or (has_previous and not already_installed and
                selection.phases == PREVIOUS_POLICY_PHASES),
                'selection:previous-policy-requires-isolated-upgrade')
        first_configure = any(phase in FIRST_CONFIGURE_PHASES for phase in selection.phases)
        pam_history = next((history for history in PAM_HISTORIES
                            if any(phase in selection.phases for phase in history.phases)), None)
        install_phases = tuple(phase for phase in selection.phases
                               if PHASE_SEMANTICS.get(phase, phase) == 'installed')
        reboot_phases = tuple(phase for phase in selection.phases
                              if PHASE_SEMANTICS.get(phase, phase) == 'rebooted')
        require(len(install_phases) <= 1 and len(reboot_phases) <= 1,
                'selection:multiple-installation-histories')
        require(not already_installed or (not has_previous and
                not install_phases and not reboot_phases and not first_configure and not pam_history),
                'selection:installation-requires-baseline')
        require(not first_configure or (not has_previous and not install_phases and
                not reboot_phases and selection.phases == FIRST_CONFIGURE_PHASES),
                'selection:first-configure-requires-isolated-baseline')
        require(pam_history is None or (not has_previous and not install_phases and
                not reboot_phases and selection.phases == pam_history.phases),
                'selection:pam-variants-require-isolated-baseline')
        if already_installed:
            lease.save('snapshot-readiness')
            with ledger.measure('bootstrap'):
                vm.call(guest_command(run, 'verify-installed'), timeout=660)
        elif has_previous:
            lease.save('package-install')
            with ledger.measure('install'):
                vm.call(guest_command(run, 'install-previous'), timeout=2400)
            if trusted_fixtures:
                # Preserve the verified old installation before its required
                # boot can lose transport. Qualification still runs only after
                # that boot, with the same installation and baseline attempt.
                with ledger.measure('collection'):
                    vm.call(guest_command(run, 'collect', 'installed'), timeout=180)
                    vm.copy(True, PAYLOAD + '/results/', str(directory / 'guest-results') + '/')
            lease.save('previous-package-reboot')
            with ledger.measure('reboot'):
                vm.reboot()
            if previous_policy:
                lease.save('pytest-previous-policy')
                with ledger.measure('test'):
                    try:
                        run_pytest(vm, run, 'previous-policy', selection)
                    except CommandError as error:
                        domain = ('product' if getattr(vm.commands, 'last_returncode', None) == 1
                                  else 'infrastructure')
                        ledger.fail_outcome(domain, 'pytest:failed:previous-policy'
                                            if domain == 'product' else error_category(error))
                        raise
                with ledger.measure('collection'):
                    vm.call(guest_command(run, 'collect', 'installed'), timeout=180)
                    vm.copy(True, PAYLOAD + '/results/', str(directory / 'guest-results') + '/')
        if not already_installed and not first_configure and pam_history is None and not trusted_fixtures:
            lease.save('package-install')
            with ledger.measure('install'):
                vm.call(guest_command(run, 'upgrade' if has_previous else 'install'), timeout=2400)
        if install_phases:
            phase = install_phases[0]
            # Observe fresh installation before deliberate metadata/fault
            # fixtures establish their retained reboot oracle. The public exit
            # leaves no graphical kiosk session for the native manager probes.
            with ledger.measure('test'):
                run_kiosk_activation(vm, lease, directory, selection, phase, ledger)
            lease.save('pytest-' + phase)
            with ledger.measure('test'):
                try:
                    run_pytest(vm, run, phase, selection)
                except CommandError as error:
                    domain = ('product' if getattr(vm.commands, 'last_returncode', None) == 1
                              else 'infrastructure')
                    ledger.fail_outcome(domain, 'pytest:failed:' + phase if domain == 'product'
                                        else error_category(error))
                    raise
            # Preserve the successful first phase if a required reboot loses transport.
            with ledger.measure('collection'):
                vm.call(guest_command(run, 'collect', 'installed'), timeout=180)
                vm.copy(True, PAYLOAD + '/results/', str(directory / 'guest-results') + '/')
            ledger.pass_outcome('collection')
        if reboot_phases:
            phase = reboot_phases[0]
            lease.save('reboot-requested')
            with ledger.measure('reboot'):
                vm.reboot()
            lease.save('pytest-' + phase)
            with ledger.measure('test'):
                try:
                    run_pytest(vm, run, phase, selection)
                except CommandError as error:
                    domain = ('product' if getattr(vm.commands, 'last_returncode', None) == 1
                              else 'infrastructure')
                    ledger.fail_outcome(domain, 'pytest:failed:' + phase if domain == 'product'
                                        else error_category(error))
                    raise
            with ledger.measure('test'):
                run_kiosk_activation(vm, lease, directory, selection, phase, ledger)
        recovery_phases = tuple(phase for history in REMOVAL_HISTORIES
                                for phase in history.phases)
        rebooted_recovery_phases = tuple(phase for history in REMOVAL_HISTORIES
                                         for phase in history.phases[1:])
        for phase in (TRUSTED_FIXTURES_PHASE, *FIRST_CONFIGURE_PHASES, *PAM_PHASES, *recovery_phases,
                      'authorization', 'enforcement', 'session'):
            if phase not in selection.phases:
                continue
            if phase in (*rebooted_recovery_phases, FIRST_CONFIGURE_PHASES[1],
                         *(item for history in PAM_HISTORIES for item in history.phases[1:])):
                # Keep removal, the health boot and reinstallation in one
                # attempt. Restoration is cleanup, never a lifecycle step.
                if phase in PAM_PHASES:
                    # Save the prior phase before a real reboot can lose the
                    # transport. Every variant remains one owned history.
                    with ledger.measure('collection'):
                        vm.call(guest_command(run, 'collect', 'installed'), timeout=180)
                        vm.copy(True, PAYLOAD + '/results/', str(directory / 'guest-results') + '/')
                        prior = pam_history.phases[pam_history.phases.index(phase) - 1]
                        retained = directory / 'phase-results' / prior
                        retained.mkdir(parents=True, mode=0o700)
                        vm.copy(True, PAYLOAD + '/results/', str(retained) + '/')
                lease.save('reboot-' + phase)
                with ledger.measure('reboot'):
                    vm.reboot()
            if phase == 'session':
                lease.save('graphical-expiry-fixture')
                with ledger.measure('test'):
                    vm.call(['env', f'ONPC_EXPECTED_RUN={run}', 'PYTHONDONTWRITEBYTECODE=1',
                             '/usr/bin/python3', '-B', PAYLOAD + '/system_graphical_expiry.py',
                             'prepare'], timeout=300)
                lease.save('graphical-expiry-reboot')
                with ledger.measure('reboot'):
                    vm.reboot()
            lease.save('pytest-' + phase)
            with ledger.measure('test'):
                try:
                    run_pytest(vm, run, phase, selection)
                except CommandError as error:
                    domain = ('product' if getattr(vm.commands, 'last_returncode', None) == 1
                              else 'infrastructure')
                    qualification_pending = (selection.qualification_failure and
                                             phase == 'authorization' and domain == 'product')
                    if not qualification_pending:
                        ledger.fail_outcome(domain, 'pytest:failed:' + phase if domain == 'product'
                                            else error_category(error))
                    if phase == 'session':
                        try:
                            with ledger.measure('collection'):
                                capture_session_screen(lease, directory / 'guest-results')
                        except Exception as capture_error:
                            ledger.fail_outcome('collection', error_category(capture_error))
                    raise
            if phase == 'session':
                with ledger.measure('collection'):
                    capture_session_screen(lease, directory / 'guest-results')
        outcome = 'passed'
    except BaseException as error:
        if not qualification_pending and all(ledger.outcomes[name]['outcome'] != 'failed'
                                             for name in ('product', 'infrastructure')):
            ledger.fail_outcome('infrastructure', error_category(error))
        raise
    finally:
        original_failure = sys.exc_info()[0] is not None
        collection_error = None
        try:
            with ledger.measure('collection'):
                lease.guard()
                vm.call(guest_command(run, 'collect', outcome), timeout=180)
                vm.copy(True, PAYLOAD + '/results/', str(directory / 'guest-results') + '/')
            ledger.pass_outcome('collection')
        except BaseException as error:
            collection_error = error
        if qualification_pending:
            if collection_error is None and is_qualification_failure(directory, selection):
                ledger.fail_outcome('infrastructure', QUALIFICATION_FAILURE)
            else:
                ledger.fail_outcome('product', 'pytest:failed:authorization')
        if collection_error is not None:
            ledger.fail_outcome('collection', error_category(collection_error))
            if not original_failure:
                raise collection_error
            # Retain the original failure even if the guest cannot return logs.
            log('evidence:guest-collection-failed')
    try:
        result = {phase: reconcile_junit(directory, phase, selection)
                  for phase in selection.phases}
    except Error as error:
        ledger.fail_outcome('product', error_category(error))
        raise
    if selection.qualification_failure:
        ledger.fail_outcome('infrastructure', 'harness:qualification-fault-missing')
        raise Error('harness:qualification-fault-missing')
    ledger.pass_outcome('product')
    return result


def host_fingerprint(commands):
    """Detect product or login-integration changes on the development host."""
    paths = ('/etc/pam.d/common-auth', '/etc/pam.d/common-account', '/etc/pam.d/common-session',
             '/etc/fapolicyd/fapolicyd.conf',
             '/etc/oh-no-parent-control/config.json',
             '/usr/lib/systemd/system/oh-no-parent-control-broker.service',
             '/etc/fapolicyd/rules.d/01-oh-no-parent-control-deny.rules',
             '/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
    result = {path: baseline.digest(Path(path)) if Path(path).is_file() else None for path in paths}
    result['package-status'] = hashlib.sha256(commands.run(
        ['dpkg-query', '-W', '-f=${Status} ${Version}', 'oh-no-parent-control'], check=False)).hexdigest()
    return result


def selection_evidence(directory, selection):
    """Describe planned and observed identities without weakening a run failure."""
    expected = [{'phase': item.phase, 'area': item.area, 'case_id': item.case_id,
                 'prerequisite': item.prerequisite} for item in selection.executions]
    executed = []
    junit = {}
    for phase in selection.phases:
        try:
            _, identities = junit_executions(directory / f'guest-results/{phase}.xml', phase)
            executed.extend({'phase': phase, 'area': area, 'case_id': case_id}
                            for area, case_id in identities)
            junit[phase] = 'collected'
        except Error as error:
            junit[phase] = str(error)
    return {
        'scope': selection.scope,
        'area': selection.area,
        'test': selection.test,
        'purpose': ('harness-qualification' if selection.qualification_failure else 'product-tests'),
        'qualification_failure': selection.qualification_failure,
        'phases': list(selection.phases),
        'expected_executions': expected,
        'executed_cases': executed,
        'junit_collection': junit,
    }


def evidence(directory, manifest, lease, passed, category, selection,
             selected_inputs_sha256, ledger):
    output = directory / 'evidence'
    output.mkdir(exist_ok=True)
    collected = directory / 'guest-results'
    if collected.is_dir():
        try:
            check_tree(collected)
            shutil.copytree(collected, output / 'guest', dirs_exist_ok=True)
        except Exception:
            collection_category = 'collection:unsafe-or-unavailable-evidence'
            ledger.fail_outcome('collection', collection_category)
            if passed:
                category = collection_category
            passed = False
    data = {'schema_version': 1, 'test': 'install-smoke', 'outcome': 'passed' if passed else 'failed',
            'category': category, 'package_sha256': manifest['artifacts']['package']['sha256'],
            'fixture_sha256': manifest['artifacts']['fixtures']['sha256'],
            'selected_inputs_sha256': selected_inputs_sha256,
            'baseline_provenance_sha256': lease.state['baseline_sha256'],
            'source': manifest['source'], 'cleanup_phase': lease.state['phase'],
            'previous_package': manifest.get('previous_package'),
            'transport': 'guarded-ssh-pytest', 'virtualization': 'libvirt-qemu-snapshot',
            'baseline_verification': dict(lease.capture.verification_totals),
            'selection': selection_evidence(directory, selection), **ledger.data()}
    (output / 'result.json').write_bytes(baseline.encode(data))
    suite = ET.Element('testsuite', name='onpc-system', tests='1', failures='0' if passed else '1')
    case = ET.SubElement(suite, 'testcase', name='install-smoke')
    if not passed:
        ET.SubElement(case, 'failure', message=category)
    ET.ElementTree(suite).write(output / 'results.xml', encoding='utf-8', xml_declaration=True)
    (output / 'results.tap').write_text('TAP version 13\n1..1\n' +
                                       ('ok' if passed else 'not ok') + ' 1 - install-smoke\n')
    for path in output.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    output.chmod(0o755)
    # Keep the registered allocation private. The installed artifact reader
    # provides access without invalidating retention's ownership/mode proof.
    return passed, category


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    argv, configured = baseline.guest_contract.vm_config.extract(argv, required='--list' not in argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vm', help='required configured VM name or ID; optional for --list')
    parser.add_argument('--artifacts', type=Path, help='Verified package and fixture artifact directory')
    parser.add_argument('--previous-artifacts', type=Path,
                        help='verified prior package to install and reboot before upgrade or fixture qualification')
    parser.add_argument('--area')
    parser.add_argument('--test')
    parser.add_argument('--id', help='comma-separated persistent numeric system case IDs')
    parser.add_argument('--completed-cases')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--skip-backing-verification', action='store_true',
                        help='compatibility option; VM verification is always metadata-only')
    parser.add_argument('--qualification-failure', action='store_true',
                        help='inject the fixed harness fault after the allowlisted case succeeds')
    parser.add_argument('--check-tools', action='store_true')
    args = parser.parse_args(argv)
    if not args.list:
        baseline.guest_contract.vm_config.selected()
    source = None
    lease = None
    suite = None
    directory = None
    manifest = None
    passed = False
    host_before = None
    category = 'runner-failed'
    selection = None
    selected_inputs_sha256 = None
    ledger = RunLedger()
    try:
        require(sum(argument == '--id' or argument.startswith('--id=')
                    for argument in argv) <= 1, 'selection:repeated-numeric-id-option')
        if args.list:
            selection = resolve_selection(args.area, args.test,
                                          recording_ids=args.id,
                                          qualification_failure=args.qualification_failure,
                                          fresh_install=args.previous_artifacts is not None,
                                          target_package_format=(configured.require_package_format()
                                                                 if configured is not None else None))
            print_selection(selection)
            return 0
        if not args.check_tools:
            require(os.geteuid() == os.getegid() == 0,
                    'guard:root; run from a root shell on the VM host')
        selection = resolve_selection(args.area, args.test,
                                      recording_ids=args.id,
                                      qualification_failure=args.qualification_failure,
                                      fresh_install=args.previous_artifacts is not None,
                                      target_package_format=configured.require_package_format())
        require(not any(item.case_id == PREVIOUS_POLICY_CASE for item in selection.executions)
                or args.previous_artifacts is not None,
                'selection:previous-policy-requires-previous-artifacts')
        require(not any(item.case_id == TRUSTED_FIXTURES_CASE for item in selection.executions)
                or args.previous_artifacts is not None,
                'selection:trusted-fixtures-requires-previous-artifacts')
        require(Path.cwd() == ROOT == baseline.guest_contract.CHECKOUT, 'guard:checkout')
        if args.completed_cases is not None:
            from tools.test_checkpoint import completed_cases
            selection = resume_selection(selection, completed_cases(args.completed_cases),
                                         fresh_install=args.previous_artifacts is not None)
        log(f'selection:scope={selection.scope} phases={len(selection.phases)} '
            f'executions={len(selection.executions)}')
        for name in HOST_EXECUTABLES:
            require(shutil.which(name) is not None,
                    f'tools:missing:{name}; run ./setup.sh')
        api, guestfs = importlib.import_module('libvirt'), importlib.import_module('guestfs')
        if args.check_tools:
            log('tools:available')
            return 0
        announce_selection(selection)
        with ledger.measure('preparation'):
            assets = artifact_source(args.artifacts)
            previous_assets = artifact_source(args.previous_artifacts) if args.previous_artifacts else None
        os.umask(0o077)
        from tools.test_retention import allocate
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-system-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        commands = Commands()
        commands.directory = private
        with ledger.measure('preparation'):
            manifest = stage_assets(assets, directory / 'input', commands)
            if previous_assets is not None:
                genuine = any(item.case_id in (PREVIOUS_POLICY_CASE, TRUSTED_FIXTURES_CASE)
                              for item in selection.executions)
                stage_previous_assets(previous_assets,
                    directory / 'input/previous' if genuine else directory / 'previous',
                    commands, manifest, genuine=genuine)
            host_before = host_fingerprint(commands)
            selected_inputs_sha256 = stage_selected_inputs(selection, directory / 'input')
            # Include the exact test/helper bytes as well as package and fixtures.
            inventory = {str(p.relative_to(directory / 'input')): baseline.digest(p)
                         for p in sorted((directory / 'input').rglob('*'))
                         if p.is_file() and p.name != 'transfer-sha256.json'}
            (directory / 'input/transfer-sha256.json').write_bytes(baseline.encode(inventory))
        api.virEventRegisterDefaultImpl()
        def events():
            while True:
                api.virEventRunDefaultImpl()
        threading.Thread(target=events, daemon=True, name='libvirt-events').start()
        source = baseline.LibvirtSource(api)
        from system_snapshots import create_suite, run_attempts
        suite = create_suite(source, guestfs, commands)
        _, _, lease = suite.acquire(ledger)
        # SIGTERM follows the same finally/lease cleanup as an interactive interruption.
        def interrupted(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupted)
        run_attempts(suite, directory, selection, manifest, selected_inputs_sha256, ledger,
                     fresh_install=args.previous_artifacts is not None)
        ledger.pass_outcome('infrastructure')
        passed = True
        category = 'all-checks-passed'
    except (Exception, KeyboardInterrupt) as error:
        # A remote pytest exits through ssh's generic CommandError boundary.
        # Retain the first classified runner failure instead of replacing it
        # with that transport wrapper in the aggregate result.
        category = record_caught_failure(ledger, error)
        # Keep unexpected host failures diagnosable without exposing exception
        # text, paths, command output, credentials, or other user data.
        if category == 'unexpected-failure-or-interruption':
            log(f'exception-type={type(error).__name__}')
        log(category)
    finally:
        if suite is not None:
            try:
                with ledger.measure('cleanup'):
                    suite.close()
            except (Exception, KeyboardInterrupt) as error:
                cleanup_category = error_category(error)
                ledger.fail_outcome('cleanup', cleanup_category)
                if passed:
                    category = cleanup_category
                passed = False
            finally:
                if suite.source is not None:
                    source = None  # Suite.close owns closure, including failed audits.
        if host_before is not None:
            try:
                with ledger.measure('cleanup'):
                    require(host_fingerprint(commands) == host_before, 'host:product-state-changed')
            except Exception:
                cleanup_category = 'host:product-state-changed-or-unverifiable'
                ledger.fail_outcome('cleanup', cleanup_category)
                if passed:
                    category = cleanup_category
                passed = False
        if source:
            try:
                with ledger.measure('cleanup'):
                    source.close()
            except Exception as error:
                cleanup_category = error_category(error)
                ledger.fail_outcome('cleanup', cleanup_category)
                if passed:
                    category = cleanup_category
                passed = False
        if (directory and manifest and lease and lease.state and selection and
                selected_inputs_sha256):
            passed, category = evidence(
                directory, manifest, lease, passed, category, selection,
                selected_inputs_sha256, ledger)
            log('evidence:' + str(directory / 'evidence'))
    return 0 if passed else 1


if __name__ == '__main__':
    # Shared snapshot helpers import this controller by its module name.
    sys.modules['system_runner'] = sys.modules[__name__]
    raise SystemExit(main())
