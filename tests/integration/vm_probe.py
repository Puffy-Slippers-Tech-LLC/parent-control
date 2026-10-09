"""Root commands in an owned maintenance guest, using its saved SSH identity.

Only the guest command is arbitrary. The host controller, domain, snapshot
credentials, transport flags, locks and observation remain fixed and guarded.
"""

import re
import os
import stat
import sys
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import xml.etree.ElementTree as ET

import system_runner as system
from watch_activity import operation


def reproduce_gdm_denial(lease):
    """Run the real shared denial journey, retaining the scene after Escape.

    This fixed maintenance route supplies no acceptance result. The same owner
    must inspect with exec and finish with test-vm stop.
    """
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from fresh_child_denied import FreshChildDeniedJourney
    return reproduce_denial(lease, FreshChildDeniedJourney, None, 'denied-returned', 'gdm')


def reproduce_lock_denial(lease):
    """Retain the actual child's lock scene immediately after guarded reveal."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from desktop_session import RetainedDenialJourney, CHILD_DENIAL_PLAN
    return reproduce_denial(lease, RetainedDenialJourney, CHILD_DENIAL_PLAN, 'time-denied', 'lock')


def reproduce_retained_entry(lease):
    """Retain the two-child activity history before the restricted curtain read."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from retained_entry import RetainedEntryJourney, PLAN
    return reproduce_denial(lease, RetainedEntryJourney, PLAN,
                            'riley-restricted-curtain', 'retained-entry')


def reproduce_retained_focus(lease):
    """Engineering focus experiment in the unlocked retained child history."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from retained_entry import RetainedEntryJourney, PLAN
    return reproduce_denial(lease, RetainedEntryJourney, PLAN,
                            'riley-restricted-curtain', 'retained-focus', focus_experiment='telemetry')


def probe_lock_curtain(lease):
    """Read the same guarded child curtain in a retained maintenance scene."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Reading the locked child surface for engineering diagnosis'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-lock-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('lock-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('child-lock-curtain')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('lock-probe: guarded curtain read passed', flush=True)


def reproduce_denial(lease, journey_type, plan, boundary, surface, *, focus_experiment=False):
    """Shared maintenance envelope; fixed callers own the finite history/boundary."""
    from fixture_credentials import FixtureCredentials
    from observation_transport import ReadOnlyObservations
    import e2e_worker
    from qualification_storage import recovery_session, allocate

    with operation('Reproducing the child ' + surface + ' boundary for live diagnosis'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-' + surface + '-diagnosis-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        transport = connect(lease)
        credentials = FixtureCredentials()
        credentials.provision_online(lease, transport)

        class Reproduction(journey_type):
            def _step(self, guard):
                stage = self.plan.stages[len(self.steps)]
                if stage != 'setup-detached':
                    return super()._step(guard)
                # The maintenance snapshot already owns the installed package
                # and transport. All actual journey observations still use the
                # current shared source bundled by UiObservations.
                request = directory / 'setup-detached.request.json'
                if not request.exists():
                    return
                system.require(not request.is_symlink() and request.stat().st_size <= 1024
                    and json.loads(request.read_bytes()) ==
                    {'stage': stage, 'screenshot': None}, 'diagnosis:setup-request')
                guard()
                self.transport = transport
                self.vm = ReadOnlyObservations(transport)
                observed = {'stage': stage, 'outcome': 'diagnostic'}
                self.steps.append(observed)
                self.progress(stage, observed)
                pending = directory / 'setup-detached.reply.tmp'
                destination = directory / 'setup-detached.reply.json'
                system.require(not destination.exists(), 'diagnosis:reply-replay')
                with pending.open('x') as stream:
                    json.dump({'setup_complete': True}, stream)
                guard()
                pending.rename(destination)

        def progress(stage, observed):
            # Fixed stage names and the shared sanitized observation only.
            with (directory / 'observations.jsonl').open('a') as stream:
                stream.write(json.dumps({'stage': stage, 'observed': observed}) + '\n')
            print(surface + '-diagnosis: ' + stage, file=sys.stderr, flush=True)
            if focus_experiment and stage in (
                    'riley-again-activity', 'return-source-desktop', 'return-source-switch',
                    'return-parent-retained', 'zero-configured',
                    'riley-denied-child-recipient-rechecked', 'riley-denied-denied',
                    'denied-returned', 'enter-locked', 'riley-restricted-entry-guard'):
                guard = lambda: lease.guard()
                guard()
                with operation('Reading child focus across the retained-entry history'):
                    output = transport.call(['/usr/bin/python3', '-', 'telemetry'], timeout=45,
                        input=(system.ROOT / 'tests/e2e/lock_surface_probe.py').read_bytes())
                summaries = [json.loads(row)['probe_summary'] for row in output.splitlines()
                             if b'"probe_summary"' in row]
                system.require(len(summaries) == 1, 'diagnosis:focus-observation')
                print('retained-focus-timeline: ' + json.dumps(
                    {'stage': stage, 'summary': summaries[0]}, sort_keys=True), flush=True)
                guard()

        journey = Reproduction(SimpleNamespace(directory=directory, lease=lease), progress,
                               **({'plan': plan} if plan is not None else {}))

        def validate():
            validate_boundary(journey, directory, boundary)

        def observe(guard):
            if (directory / (boundary + '.request.json')).exists():
                guard()
                validate()
                return True
            journey.step(guard)
            return False

        result = e2e_worker.run_distribution(directory, lease, system.RunLedger(),
            expected_inputs={}, observe=lambda: None, validate=validate,
            guarded_observe=observe, credentials=credentials, maintenance=True, timeout=900)
        system.require(result['worker_stopped'] and result['callback_closed'],
                       'diagnosis:cleanup-incomplete')
        lease.guard()
        print(surface + '-diagnosis: scene retained; evidence=' + str(directory), flush=True)


def validate_boundary(journey, directory, boundary):
    """Retain only a complete verified prefix, never a failed or advanced scene."""
    system.require(not journey.failed and [s['stage'] for s in journey.steps]
                   == list(journey.plan.stages[:journey.plan.stages.index(boundary)]),
                   'diagnosis:incomplete-history')
    request = directory / (boundary + '.request.json')
    system.require(not request.is_symlink() and request.stat().st_size <= 1024
        and json.loads(request.read_bytes()) ==
        {'stage': boundary, 'screenshot': None}, 'diagnosis:boundary-request')


def connect(lease):
    """Bind a probe to the current owned online snapshot, without restoring it."""
    from online_snapshot import load, connect_saved_transport, validate_saved_snapshot
    lease.guard()
    snapshot = lease.source.domain.snapshotCurrent(0)
    name, xml = snapshot.getName(), snapshot.getXMLDesc(0)
    system.require(re.fullmatch(r'onpc-v[0-9]+(?:\.[0-9]+)*', name) is not None,
                   'vm-probe:online-appsnapshot-required')
    tree = ET.fromstring(xml)
    memory, domain = tree.find('memory'), tree.find('domain')
    system.require(tree.findtext('state') == 'running' and memory is not None and
                   memory.get('snapshot') == 'internal' and domain is not None,
                   'vm-probe:online-appsnapshot-required')
    record = load(lease.source, name, xml)
    system.require(record is not None, 'vm-probe:snapshot-credentials-missing')
    validate_saved_snapshot(lease, xml, record)
    hostname = system.address(lease.source)
    return connect_saved_transport(lease, lease.commands.directory, record, hostname)


def execute(lease, command, timeout, *, input_stream=False):
    """Probe the present instance; never boot, restore, rekey or correct time."""
    # The caller has resumed the shared maintenance lease. Existing detached
    # display observation stays attached throughout and outlives this command.
    with operation('Running a root command in the owned guest'):
        payload = None
        if input_stream:
            # The unprivileged launcher opened the source. Never open a host
            # pathname as root, or block reading an interactive/pipe descriptor.
            info = os.fstat(0)
            limit = 64 * 1024 * 1024
            system.require(stat.S_ISREG(info.st_mode) and info.st_size <= limit and
                           os.lseek(0, 0, os.SEEK_CUR) == 0, 'vm-probe:invalid-input')
            payload = sys.stdin.buffer.read(limit + 1)
            system.require(len(payload) == info.st_size, 'vm-probe:input-changed')
        transport = connect(lease)

        def output(data, stream):
            destination = sys.stdout.buffer if stream == 'stdout' else sys.stderr.buffer
            destination.write(data)
            destination.flush()

        transport.call(command, timeout=timeout, check=False, on_stream=output,
                       **({'input': payload} if input_stream else {}))
        # Guard probes can replace Commands.last_returncode; capture it first.
        status = transport.commands.last_returncode
        lease.guard()
        system.require(type(status) is int and 0 <= status <= 255, 'vm-probe:invalid-exit-status')
        return status
