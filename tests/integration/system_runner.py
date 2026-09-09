#!/usr/bin/python3
"""Run installed-system pytest on the fixed VM, resetting its retained snapshot.

Root host controller. No product installation command executes on the host.
All VM/storage operations are injectable; imports have no machine side effects.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
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

import prepare_host as baseline

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = '/var/tmp/onpc-system-input'
TAG = 'onpc-system-run:'
QUALIFICATION_CASE = 'test_method_role_matrix[ListManagedUsers-parent1]'
QUALIFICATION_FAILURE = 'harness:qualification-failure'
PHASE_ORDER = ('installed', 'rebooted', 'authorization', 'enforcement')
AREA_SOURCES = {
    'package': ROOT / 'tests/system/test_install_smoke.py',
    'authorization': ROOT / 'tests/system/test_authorization.py',
    'enforcement': ROOT / 'tests/system/test_enforcement.py',
}
COMMON_SELECTED_INPUTS = (
    ('tests/integration/system_guest.py', 'system_guest.py'),
    ('tests/integration/owned_commands.py', 'owned_commands.py'),
    ('tests/integration/guest/redact.py', 'guest/redact.py'),
    ('tests/system/pytest.ini', 'pytest.ini'),
)
AREA_SELECTED_HELPERS = {
    'package': (),
    'authorization': (('tests/integration/system_caller.py', 'system_caller.py'),
                      ('tests/integration/system_assertions.py', 'system_assertions.py'),
                      ('tests/integration/system_accounts.py', 'system_accounts.py'),
                      ('tests/integration/system_remote_accounts.py', 'system_remote_accounts.py')),
    'enforcement': (('tests/integration/system_caller.py', 'system_caller.py'),
                    ('tests/integration/system_assertions.py', 'system_assertions.py'),
                    ('tests/integration/system_enforcement.py', 'system_enforcement.py')),
}
PHASE_DEPENDENCIES = {
    'installed': (),
    'rebooted': ('installed',),
    'authorization': ('installed', 'rebooted'),
    'enforcement': ('installed', 'rebooted'),
}
PHASE_PREREQUISITES = {
    'installed': ('accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap', 'package-install'),
    'rebooted': ('installed-phase', 'guest-reboot', 'boot-readiness'),
    'authorization': ('rebooted-phase', 'authorization-accounts'),
    'enforcement': ('rebooted-phase', 'native-enforcement-fixture'),
}
require = baseline.require
Error = baseline.CaptureError

from owned_commands import Commands, CommandError


def log(stage):
    print(f'check-system: [{stage}]', file=sys.stderr, flush=True)


STAGE_NAMES = ('preparation', 'bootstrap', 'install', 'reboot', 'test',
               'collection', 'cleanup')
OUTCOME_NAMES = ('product', 'infrastructure', 'collection', 'cleanup')
HOST_EXECUTABLES = ('ssh', 'qemu-img', 'ssh-keygen', 'virt-customize',
                    'dpkg-deb', 'dpkg-query')


def error_category(error):
    """Return only the runner's fixed public failure categories."""
    if isinstance(error, (Error, CommandError)):
        return str(error)
    return 'unexpected-failure-or-interruption'


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
    return cases


def case_phases(area, case_id):
    if area in ('authorization', 'enforcement'):
        return (area,)
    package = {
        'test_installed_package': ('installed', 'rebooted'),
        'test_first_install_requests_reboot': ('installed',),
        'test_reboot_applies_installation': ('rebooted',),
    }
    require(case_id in package, 'selection:unregistered-package-case')
    return package[case_id]


def resolve_selection(area=None, test=None, *, inventories=None, qualification_failure=False):
    """Resolve an exact selection and all test-phase prerequisites on the host."""
    require(area is None or area != '', 'selection:empty-area')
    require(test is None or test != '', 'selection:empty-test')
    require(area is None or area in AREA_SOURCES, 'selection:unknown-area')
    require(test is None or area is not None, 'selection:test-requires-area')
    require(not qualification_failure or (area == 'authorization' and test == QUALIFICATION_CASE),
            'qualification:requires-allowlisted-case')
    if inventories is None:
        inventories = {name: collect_area_cases(name) for name in AREA_SOURCES}
    else:
        inventories = {name: tuple(cases) for name, cases in inventories.items()}
    require(set(inventories) == set(AREA_SOURCES), 'selection:incomplete-registry')
    for name, cases in inventories.items():
        require(cases and len(cases) == len(set(cases)), f'selection:invalid-registry:{name}')

    if test is not None and test not in inventories[area]:
        incompatible = any(test in cases for name, cases in inventories.items() if name != area)
        require(not incompatible, 'selection:incompatible-test')
        raise Error('selection:unknown-test')

    chosen_areas = tuple(AREA_SOURCES) if area is None else (area,)
    chosen = {name: inventories[name] for name in chosen_areas}
    if test is not None:
        chosen[area] = (test,)

    terminal_phases = {phase for name, cases in chosen.items() for case in cases
                       for phase in case_phases(name, case)}
    phases = tuple(phase for phase in PHASE_ORDER if phase in terminal_phases or
                   any(phase in PHASE_DEPENDENCIES[item] for item in terminal_phases))

    executions = []
    for phase in phases:
        if phase in terminal_phases:
            for name, cases in chosen.items():
                for case in cases:
                    if phase in case_phases(name, case):
                        executions.append(CaseExecution(phase, name, case, False))
        if phase not in terminal_phases:
            for case in inventories['package']:
                if phase in case_phases('package', case):
                    executions.append(CaseExecution(phase, 'package', case, True))

    prerequisites = []
    for phase in phases:
        for item in PHASE_PREREQUISITES[phase]:
            if item not in prerequisites:
                prerequisites.append(item)
    if test and (test in ('test_authenticated_request_rejects_deleted_target',
                         'test_requester_disconnect_during_approval',
                         'test_administrator_eligibility_predicates') or
                 test.startswith('test_authenticated_request_revalidates_live_state[') or
                 test.startswith('test_request_rejects_locked_approver_during_authentication[') or
                 test.startswith('test_real_selected_parent_authentication[')):
        prerequisites.append('fixture-passwords')
    available = {name: inventories[name] for name in chosen_areas}
    if any(item.case_id == 'test_remote_accounts_are_excluded' for item in executions):
        prerequisites.append('remote-ldap-nss-fixtures')
    return Selection(area, test, 'full' if area is None else 'partial', phases,
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
    print(f'  expected-executions: {len(selection.executions)}', file=stream)
    for execution in selection.executions:
        kind = 'prerequisite' if execution.prerequisite else 'selected'
        print(f'    {execution.phase}::{execution.case_id} [{kind}]', file=stream)
    print('  available-selectors:', file=stream)
    for name, cases in selection.available.items():
        print(f'    {name}:', file=stream)
        for case in cases:
            print(f'      {case}', file=stream)


def isolated_xml(xml, expected_uuid, run, *, graphics_type='spice'):
    """Use only the fixed guest disk; remove every host-sharing interface."""
    baseline.domain_layout(xml, expected_uuid)
    root = ET.fromstring(xml)
    require(not root.findall('{http://libvirt.org/schemas/domain/qemu/1.0}commandline'), 'guard:qemu-override')
    devices = root.find('devices')
    for name in ('filesystem', 'redirdev', 'channel', 'graphics', 'audio', 'sound', 'rng'):
        for node in devices.findall(name):
            devices.remove(node)
    require(graphics_type in ('spice', 'vnc'), 'guard:graphics-type')
    # Neither display listens on a host port/socket. Graphical workers obtain
    # VNC through libvirt's public openGraphicsFD API under the same lease.
    graphics = ET.SubElement(devices, 'graphics', type=graphics_type)
    ET.SubElement(graphics, 'listen', type='none')
    if graphics_type == 'spice':
        graphics.set('autoport', 'yes')
        ET.SubElement(graphics, 'clipboard', copypaste='no')
        ET.SubElement(graphics, 'filetransfer', enable='no')
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
    require(len(displays) == 1, 'guard:graphics-count')
    display = displays[0]
    require(display.get('type') == 'vnc' and
            set(display.attrib) <= {'type', 'port', 'autoport'} and
            display.get('port', '-1') == '-1' and
            display.get('autoport', 'no') == 'no', 'guard:graphics-endpoint')
    require(len(display) == 1 and display[0].tag == 'listen' and
            display[0].attrib == {'type': 'none'} and len(display[0]) == 0,
            'guard:graphics-listener')


class SourceView:
    """Retain Task 12's exact disk checks while allowing our removed file share."""

    def __init__(self, source):
        self.source = source
        self.original_shares = None
        self.run = None
        self.domain_id = None
        self.graphics_type = 'spice'

    def snapshot(self):
        layout, off = self.source.snapshot()
        if self.run is not None:
            domain = self.source.connection.lookupByName(baseline.DOMAIN)
            root = ET.fromstring(domain.XMLDesc(0))
            require(root.findtext('description') == TAG + self.run, 'guard:run-identity')
            if self.graphics_type == 'vnc':
                validate_private_vnc(root)
            require(not layout['source_shares'] and not root.findall('devices/filesystem') and
                    not root.findall('devices/hostdev') and not root.findall('devices/channel') and
                    not root.findall('devices/redirdev'), 'guard:host-sharing')
            if not off:
                require(self.domain_id is not None and domain.ID() == self.domain_id, 'guard:domain-replaced')
            layout['source_shares'] = self.original_shares
        return layout, off

    def baseline(self):
        return self.source.baseline()


class Lease:
    """Serializes prep-host/system runners; durable state refuses interrupted ownership."""

    def __init__(self, source, commands, inspect, *, directory=baseline.BASELINES,
                 anchor=baseline.ANCHOR, ledger=None, graphics_type='spice', finalize=None):
        self.source, self.commands, self.inspect = source, commands, inspect
        self.view = SourceView(source)
        self.view.graphics_type = graphics_type
        self.capture = baseline.Capture(self.view, commands, inspect, directory=directory, anchor=anchor)
        self.directory = directory
        self.journal = directory / 'system-run.json'
        self.fd = None
        self.state = None
        self.original_xml = None
        self.original_id = None
        self.mutated = False
        self.ledger = ledger
        # Trusted read/report callback, after the sole cleanup attempt and while
        # the lease is held. It must never restore or release this lease itself.
        self.finalize = finalize

    def save(self, phase):
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

    def __enter__(self):
        try:
            self.capture.directory_identity = self.capture.private_directory()
            self.fd = os.open(self.directory / '.lock', os.O_RDWR | os.O_NOFOLLOW)
            baseline.identity(self.directory / '.lock', private=True, mode=0o600)
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Error('state:busy-controller') from error
            self.commands.lock_fd = self.fd
            self.capture.state = self.capture.read_state()
            require(self.capture.state['phase'] == 'finalized', 'baseline:not-finalized')
            log('stage:baseline-verification')
            # Proof validation can dominate preparation. Include it on refusal
            # and interruption too, before any VM mutation is permitted.
            with self.ledger.measure('preparation') if self.ledger else nullcontext():
                require(self.capture.verify_snapshot() == self.capture.state['proof'], 'baseline:changed')
            if self.journal.exists():
                baseline.identity(self.journal, private=True, mode=0o600)
                previous = baseline.parse_json(self.journal.read_bytes())
                require(previous.get('phase') == 'complete', 'state:interrupted-run; preserve state for recovery')
            self.original_xml = self.source.domain.XMLDesc(self.source.api.VIR_DOMAIN_XML_INACTIVE)
            self.original_id = self.source.domain.ID()
            require(not self.source.domain.autostart(), 'guard:autostart')
            run = uuid.uuid4().hex
            # Validate isolation before creating state or shutting down a VM.
            self.test_xml = isolated_xml(self.original_xml, self.source.uuid, run,
                                         graphics_type=self.view.graphics_type)
            self.state = {'schema_version': 1, 'run': run, 'phase': 'validated',
                          'domain_uuid': self.source.uuid, 'domain_id': None,
                          'original_xml': self.original_xml,
                          'baseline_sha256': hashlib.sha256(baseline.encode(self.capture.state)).hexdigest()}
            self.save('validated')
            return self
        except BaseException:
            self.release()
            raise

    def guard(self, *, off=False):
        self.capture.revalidate(off=off)
        require(self.source.baseline() == self.snapshot_xml, 'baseline:snapshot-metadata-changed')

    def prepare(self):
        self.snapshot_xml = self.source.baseline()
        # The initial shutdown is explicitly authorized for this fixed source VM.
        self.save('shutdown-requested')
        self.source.shutdown(self.capture.revalidate, requested=False)
        self.guard(off=True)
        self.save('restore-requested')
        self.mutated = True
        self.restore()
        require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                             self.capture.state['script_digest']) == self.capture.state['guest'], 'baseline:guest-changed')
        self.source.connection.defineXML(self.test_xml)
        self.view.original_shares = self.capture.state['source']['layout']['source_shares']
        self.view.run = self.state['run']
        self.guard(off=True)
        self.save('isolated')

    def restore(self):
        # snapshot revert defaults to its saved shutoff state; never pass RUNNING.
        self.capture.revalidate(off=True)
        snap = self.source.domain.snapshotLookupByName(baseline.SNAPSHOT, 0)
        require(snap.getXMLDesc(0) == self.snapshot_xml, 'baseline:snapshot-metadata-changed')
        self.source.domain.revertToSnapshot(snap, 0)
        self.view.run = None
        self.view.domain_id = None
        self.capture.revalidate(off=True)

    def start(self):
        self.guard(off=True)
        self.save('start-requested')
        self.source.domain.create()
        self.view.domain_id = self.source.domain.ID()
        require(self.view.domain_id >= 0, 'start:identity-unavailable')
        self.state['domain_id'] = self.view.domain_id
        self.guard()
        self.save('running')

    def stop(self):
        """Stop the recorded instance without restoring between backend callbacks."""
        self.guard()
        if not self.view.snapshot()[1]:
            # Only the domain instance started and identity-recorded by this run.
            require(self.view.domain_id is not None, 'cleanup:unowned-domain')
            try:
                self.source.shutdown(self.guard, requested=False)
            except Error as error:
                if str(error) != 'shutdown:timeout':
                    raise
                self.guard()
                self.source.domain.destroyFlags(0)
        self.guard(off=True)

    def finish(self):
        if not self.mutated:
            self.save('complete')
            return
        self.save('cleanup-requested')
        self.stop()
        self.restore()
        log('stage:restored-baseline-verification')
        require(self.capture.verify_snapshot() == self.capture.state['proof'], 'cleanup:baseline-changed')
        require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                             self.capture.state['script_digest']) == self.capture.state['guest'], 'cleanup:guest-changed')
        # Revert restores the snapshot's XML; restore the validated pre-run config.
        self.source.connection.defineXML(self.original_xml)
        self.capture.revalidate(off=True)
        self.save('complete')

    def release(self):
        self.commands.lock_fd = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def recover_graphical_cleanup(self):
        """Resume only a recorded, still-running VNC cleanup after connection loss.

        No start, preparation, new baseline or journal replacement is allowed.
        Replaced/off domains and other incomplete phases require separate review.
        """
        require(self.fd is None and self.view.graphics_type == 'vnc', 'recovery:invalid-lease')
        try:
            self.capture.directory_identity = self.capture.private_directory()
            self.fd = os.open(self.directory / '.lock', os.O_RDWR | os.O_NOFOLLOW)
            baseline.identity(self.directory / '.lock', private=True, mode=0o600)
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Error('state:busy-controller') from error
            self.commands.lock_fd = self.fd
            self.capture.state = self.capture.read_state()
            require(self.capture.state['phase'] == 'finalized', 'baseline:not-finalized')
            baseline.identity(self.journal, private=True, mode=0o600)
            state = baseline.parse_json(self.journal.read_bytes())
            require(isinstance(state, dict) and set(state) == {
                'schema_version', 'run', 'phase', 'domain_uuid', 'domain_id',
                'original_xml', 'baseline_sha256'} and state['schema_version'] == 1 and
                state['phase'] == 'cleanup-requested' and
                isinstance(state['run'], str) and re.fullmatch(r'[0-9a-f]{32}', state['run']) and
                type(state['domain_id']) is int and state['domain_id'] >= 0 and
                state['domain_uuid'] == self.source.uuid and
                state['baseline_sha256'] == hashlib.sha256(baseline.encode(self.capture.state)).hexdigest(),
                'recovery:journal-identity')
            require(not self.source.domain.autostart() and
                    self.source.domain.ID() == state['domain_id'], 'recovery:domain-replaced-or-off')
            self.original_xml = state['original_xml']
            require(baseline.domain_layout(self.original_xml, self.source.uuid) ==
                    self.capture.state['source']['layout'], 'recovery:original-layout')
            isolated_xml(self.original_xml, self.source.uuid, state['run'], graphics_type='vnc')
            self.state = state
            self.view.original_shares = self.capture.state['source']['layout']['source_shares']
            self.view.run = state['run']
            self.view.domain_id = state['domain_id']
            self.snapshot_xml = self.source.baseline()
            self.guard()
            require(self.capture.verify_snapshot() == self.capture.state['proof'], 'recovery:baseline-changed')
            self.mutated = True
            log('recovery:recorded-graphical-cleanup')
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
    shutil.copyfile(package, destination / 'package.deb')
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
    # receives an exact run digest in addition to Task 13A's stable payload digest.
    inventory = {str(p.relative_to(destination)): baseline.digest(p)
                 for p in sorted(destination.rglob('*')) if p.is_file()}
    (destination / 'transfer-sha256.json').write_bytes(baseline.encode(inventory))
    return manifest


def stage_selected_inputs(selection, destination):
    """Freeze and identify only the test/helper files needed by this selection."""
    selected_areas = {execution.area for execution in selection.executions}
    inputs = list(COMMON_SELECTED_INPUTS)
    if selection.qualification_failure:
        inputs.append(('tests/integration/system_qualification.py', 'system_qualification.py'))
    for area in AREA_SOURCES:
        if area not in selected_areas:
            continue
        inputs.append((str(AREA_SOURCES[area].relative_to(ROOT)), AREA_SOURCES[area].name))
        inputs.extend(AREA_SELECTED_HELPERS[area])
    # Areas share transport/assertion helpers. Coalesce identical declarations
    # in stable order, but still refuse two different sources for one target.
    inputs = list(dict.fromkeys(inputs))
    require(len({target for _, target in inputs}) == len(inputs),
            'selection:duplicate-input-target')

    files = {}
    for relative, target in inputs:
        source = ROOT / relative
        staged = destination / target
        staged.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, staged)
        files[target] = {'source': relative, 'sha256': baseline.digest(staged)}
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
    path = destination / 'selected-inputs.json'
    path.write_bytes(baseline.encode(identity))
    digest = baseline.digest(path)
    log(f'provenance:selected-inputs files={len(files)} sha256={digest}')
    return digest


def ubuntu_archive_sources(contents):
    """Normalize only official Ubuntu URIs in Deb822 URIs fields.

    Preserve all other fields and bytes, including embedded signing keys and
    unrelated repositories. The fixed prepared Ubuntu guest uses Deb822.
    """
    lines = []
    uri_field = False
    for line in contents.splitlines(keepends=True):
        if line.strip() and not line.lstrip().startswith('#'):
            if not line[0].isspace():
                uri_field = line.lower().startswith('uris:')
            if uri_field:
                line = re.sub(
                    r'(?<!\S)https?://(?:(?:[a-z]{2}\.)?archive|security)\.ubuntu\.com/ubuntu/?(?=\s|$)',
                    'https://archive.ubuntu.com/ubuntu/', line)
        elif not line.strip():
            uri_field = False
        lines.append(line)
    return ''.join(lines)


@contextmanager
def mounted_guest(guestfs, lease, *, readonly=False):
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
        yield g
        if not readonly:
            g.sync()
    finally:
        g.close()
    lease.guard(off=True)


def bootstrap(commands, lease, directory, guestfs, *, observation_only=False):
    """Prepare SSH only on the reset, powered-off active disk via libguestfs."""
    lease.guard(off=True)
    disk = Path(lease.capture.state['source']['layout']['disk'])
    key = directory / 'ssh-key'
    commands.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'onpc-system-test', '-f', str(key)])
    lease.save('ssh-bootstrap')
    with mounted_guest(guestfs, lease) as g:
        sources_path = '/etc/apt/sources.list.d/ubuntu.sources'
        sources = g.read_file(sources_path).decode()
        normalized = ubuntu_archive_sources(sources)
        if normalized != sources:
            g.write(sources_path, normalized.encode())
        log('bootstrap:ubuntu-archive-https-ready')
        # The removed preparation-only share must not prevent boot via fstab.
        fstab = g.read_file('/etc/fstab').decode()
        lines = []
        for line in fstab.splitlines():
            fields = line.split()
            if fields and not fields[0].startswith('#') and len(fields) >= 3 and fields[2] in {'virtiofs', '9p'}:
                require(fields[1] == '/Data', 'bootstrap:unexpected-share')
                continue
            lines.append(line)
        g.write('/etc/fstab', ('\n'.join(lines) + '\n').encode())
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
            marker['package_sha256'] = baseline.digest(directory / 'input/package.deb')
        require(marker['machine_id'] != marker['host_machine_id'], 'bootstrap:host-identity')
        g.write('/etc/onpc-system-test.json', baseline.encode(marker))
        g.chown(0, 0, '/etc/onpc-system-test.json')
        g.chmod(0o600, '/etc/onpc-system-test.json')
    lease.guard(off=True)
    commands.run(['virt-customize', '--format', 'qcow2', '-a', str(disk),
                  '--install', ('openssh-server=1:10.2p1-2ubuntu3.6' if observation_only else
                                'openssh-server=1:10.2p1-2ubuntu3.6,python3-pytest=9.0.2-4'),
                  '--ssh-inject', f'root:file:{key}.pub',
                  '--run-command', 'systemctl enable ssh.service'], timeout=1800)
    with mounted_guest(guestfs, lease, readonly=True) as g:
        host_key = g.read_file('/etc/ssh/ssh_host_ed25519_key.pub').decode().split()
        require(len(host_key) >= 2 and host_key[0] == 'ssh-ed25519', 'bootstrap:ssh-host-key')
    return ' '.join(host_key[:2])


def address(source, timeout=300):
    """Wait on libvirt's DHCP lease list with a bounded event-loop timer."""
    deadline = time.monotonic() + timeout
    event = threading.Event()
    timer = source.api.virEventAddTimeout(500, lambda *_: event.set(), None)
    try:
        while time.monotonic() < deadline:
            interfaces = source.domain.interfaceAddresses(source.api.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE, 0)
            addresses = [a['addr'] for item in interfaces.values() for a in item.get('addrs', [])
                         if a['type'] == source.api.VIR_IP_ADDR_TYPE_IPV4]
            if len(addresses) == 1:
                value = ipaddress.ip_address(addresses[0])
                require(value.is_private and not value.is_loopback, 'network:address')
                return str(value)
            event.wait(max(0, deadline - time.monotonic()))
            event.clear()
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
            f'PYTHONPATH={PAYLOAD}',
            'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-m', 'pytest',
            '-c', PAYLOAD + '/pytest.ini', '--noconftest', '--rootdir', PAYLOAD,
            '--junitxml', f'{PAYLOAD}/results/{phase}.xml', '-q',
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


def installed_run(vm, lease, directory, selection, ledger=None):
    ledger = ledger or RunLedger()
    run = lease.state['run']
    outcome = 'failed'
    qualification_pending = False
    try:
        with ledger.measure('bootstrap'):
            vm.ready()
            vm.copy(False, str(directory / 'input') + '/', PAYLOAD + '/')
        lease.save('package-install')
        with ledger.measure('install'):
            vm.call(guest_command(run, 'install'), timeout=2400)
        if 'installed' in selection.phases:
            lease.save('pytest-installed')
            with ledger.measure('test'):
                try:
                    vm.call(pytest_command(run, 'installed', selection), timeout=900)
                except CommandError as error:
                    domain = ('product' if getattr(vm.commands, 'last_returncode', None) == 1
                              else 'infrastructure')
                    ledger.fail_outcome(domain, 'pytest:failed:installed' if domain == 'product'
                                        else error_category(error))
                    raise
            # Preserve the successful first phase if a required reboot loses transport.
            with ledger.measure('collection'):
                vm.call(guest_command(run, 'collect', 'installed'), timeout=180)
                vm.copy(True, PAYLOAD + '/results/', str(directory / 'guest-results') + '/')
            ledger.pass_outcome('collection')
        if 'rebooted' in selection.phases:
            lease.save('reboot-requested')
            with ledger.measure('reboot'):
                vm.reboot()
            lease.save('pytest-rebooted')
            with ledger.measure('test'):
                try:
                    vm.call(pytest_command(run, 'rebooted', selection), timeout=900)
                except CommandError as error:
                    domain = ('product' if getattr(vm.commands, 'last_returncode', None) == 1
                              else 'infrastructure')
                    ledger.fail_outcome(domain, 'pytest:failed:rebooted' if domain == 'product'
                                        else error_category(error))
                    raise
        for phase in ('authorization', 'enforcement'):
            if phase not in selection.phases:
                continue
            lease.save('pytest-' + phase)
            with ledger.measure('test'):
                try:
                    vm.call(pytest_command(run, phase, selection), timeout=900)
                except CommandError as error:
                    domain = ('product' if getattr(vm.commands, 'last_returncode', None) == 1
                              else 'infrastructure')
                    qualification_pending = (selection.qualification_failure and
                                             phase == 'authorization' and domain == 'product')
                    if not qualification_pending:
                        ledger.fail_outcome(domain, 'pytest:failed:' + phase if domain == 'product'
                                            else error_category(error))
                    raise
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
             '/etc/oh-no-parent-control/config.json',
             '/usr/lib/systemd/system/oh-no-parent-control-broker.service',
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
            'transport': 'guarded-ssh-pytest', 'virtualization': 'libvirt-qemu-snapshot',
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
    directory.chmod(0o755)
    return passed, category


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, help='Task 13A artifact directory')
    parser.add_argument('--area')
    parser.add_argument('--test')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--qualification-failure', action='store_true',
                        help='inject the fixed harness fault after the allowlisted case succeeds')
    parser.add_argument('--check-tools', action='store_true')
    args = parser.parse_args(argv)
    source = None
    lease = None
    directory = None
    manifest = None
    passed = False
    host_before = None
    category = 'runner-failed'
    selection = None
    selected_inputs_sha256 = None
    ledger = RunLedger()
    try:
        if args.list:
            selection = resolve_selection(args.area, args.test,
                                          qualification_failure=args.qualification_failure)
            print_selection(selection)
            return 0
        require(Path.cwd() == ROOT == baseline.guest_contract.CHECKOUT, 'guard:checkout')
        if not args.check_tools:
            require(os.geteuid() == os.getegid() == 0,
                    'guard:root; run from a root shell on the VM host')
        selection = resolve_selection(args.area, args.test,
                                      qualification_failure=args.qualification_failure)
        log(f'selection:scope={selection.scope} phases={len(selection.phases)} '
            f'executions={len(selection.executions)}')
        for name in HOST_EXECUTABLES:
            require(shutil.which(name) is not None,
                    f'tools:missing:{name}; run ./setup.sh')
        api, guestfs = importlib.import_module('libvirt'), importlib.import_module('guestfs')
        if args.check_tools:
            log('tools:available')
            return 0
        with ledger.measure('preparation'):
            assets = artifact_source(args.artifacts)
        os.umask(0o077)
        directory = Path(tempfile.mkdtemp(prefix='onpc-system-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        commands = Commands()
        commands.directory = private
        with ledger.measure('preparation'):
            manifest = stage_assets(assets, directory / 'input', commands)
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
        lease = Lease(source, commands, lambda disk, digest: baseline.inspect_guest(guestfs, disk, digest),
                      ledger=ledger)
        # SIGTERM follows the same finally/lease cleanup as an interactive interruption.
        def interrupted(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupted)
        with lease:
            with ledger.measure('preparation'):
                lease.prepare()
            with ledger.measure('bootstrap'):
                host_key = bootstrap(commands, lease, directory, guestfs)
                lease.start()
                hostname = address(source)
            (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
            config = {
                'directory': str(directory), 'hostname': hostname, 'run': lease.state['run'],
                'domain_uuid': source.uuid, 'domain_id': lease.view.domain_id,
            }
            from vm_transport import Transport
            vm = Transport(config, commands, guard=lambda _: lease.guard())
            lease.guard()
            installed_run(vm, lease, directory, selection, ledger)
            try:
                result = json.loads((directory / 'guest-results/result.json').read_text())
                require(result['outcome'] == 'passed' and result['package_sha256'] ==
                        manifest['artifacts']['package']['sha256'] and
                        result['selected_inputs_sha256'] == selected_inputs_sha256,
                        'pytest:guest-evidence')
            except (OSError, json.JSONDecodeError, KeyError, TypeError, Error) as error:
                category = ('pytest:guest-evidence' if isinstance(error, Error)
                            else 'collection:missing-or-invalid-guest-result')
                ledger.fail_outcome('collection', category)
                raise Error(category) from error
            lease.guard()
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
    raise SystemExit(main())
