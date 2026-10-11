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


def reproduce_transfer_refusal(lease):
    """Retain the shared transfer history before the overlay's wrong-surface read."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from choices_overlay_to_kiosk import ChoicesOverlayToKioskJourney, PLAN
    return reproduce_denial(lease, ChoicesOverlayToKioskJourney, PLAN,
                            'riley-refused', 'transfer-refusal')


def reproduce_riley_native_grid(lease):
    """Retain Riley's second grid entry after the actual first launch/use/close."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from riley_native_grid import RileyNativeGridJourney, PLAN
    from tools.test_storage import named_input
    assets = named_input(vm_source=True, fixture_source=True)
    if not assets.is_dir():
        print('riley-native-grid-diagnosis: prepare fixture inputs with '
              'tools/run-tests artifacts prepare --for-vm --vm NAME --output ' + str(assets),
              flush=True)
    return reproduce_denial(lease, RileyNativeGridJourney, PLAN,
                            'repeat-refusals', 'riley-native-grid',
                            assets=assets, boundary_operation='overlay-native-grid-refusals')


def probe_riley_native_grid(lease):
    """Exercise the shared refusal observer on the retained Riley session bus."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Probing Riley second native grid refusal'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-riley-native-grid-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('riley-native-grid-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('overlay-native-grid-refusals')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('riley-native-grid-probe: guarded refusal passed', flush=True)


def reproduce_remembered_return(lease):
    """Retain the historical return scene, separate from current case 58."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from remembered_choices import DIAGNOSTIC_PLAN as PLAN
    from request_composition import KioskRequestJourney
    return reproduce_denial(lease, KioskRequestJourney, PLAN,
                            'jordan-return-entry-desktop', 'remembered-return',
                            boundary_operation='standard-desktop')


def probe_remembered_return(lease):
    """Read the same desktop adapter on the retained Jordan session's bus."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Reading the retained Jordan desktop'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-remembered-return-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('remembered-return-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('standard-desktop')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('remembered-return-probe: guarded desktop read passed', flush=True)


def repeat_remembered_return(lease):
    """Repeat only the Riley/station/Jordan return in the already reproduced scene."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from remembered_choices import DIAGNOSTIC_PLAN as PLAN
    from installed_journey import JourneyPlan
    from request_composition import KioskRequestJourney
    screens = {'repeat-desktop': 'ui:standard-desktop',
               'switch-user': 'system:standard-switch-user', 'gdm-switched': 'ui:gdm-returned'}
    screens.update({stage: tag for stage, tag in PLAN.screen_tags.items()
                    if stage.startswith('riley-return-')})
    screens.update({'riley-return-exit': 'ui:kiosk-request-cancel',
                    'riley-return-greeter': 'ui:gdm-station-returned'})
    screens.update({stage: tag for stage, tag in PLAN.screen_tags.items()
                    if stage.startswith('jordan-return-entry-')})
    plan = JourneyPlan(prefix='remembered-return', worker_mode='remembered_return_diagnosis',
        screen_tags=screens, phases={}, invocations=tuple(stage for stage in screens
                                                         if stage in PLAN.invocations),
        challenges={name: binding for name, binding in PLAN.challenges.items()
                    if name in ('riley-return-entry', 'jordan-return-entry')},
        request_transfer_checks={'riley-return-transfer-read': 'riley-return-source'})
    return reproduce_denial(lease, KioskRequestJourney, plan,
                            'jordan-return-entry-desktop', 'remembered-return',
                            boundary_operation='standard-desktop')


def enter_remembered_return(lease):
    """A new guarded Jordan challenge from the owned reproduced greeter scene."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from remembered_choices import DIAGNOSTIC_PLAN as PLAN
    from installed_journey import JourneyPlan
    from request_composition import KioskRequestJourney
    screens = {stage: tag for stage, tag in PLAN.screen_tags.items()
               if stage.startswith('jordan-return-entry-')}
    plan = JourneyPlan(prefix='remembered-return', worker_mode='remembered_return_entry_diagnosis',
        screen_tags=screens, phases={}, invocations=tuple(stage for stage in screens
                                                         if stage in PLAN.invocations),
        challenges={'jordan-return-entry': PLAN.challenges['jordan-return-entry']})
    return reproduce_denial(lease, KioskRequestJourney, plan,
                            'jordan-return-entry-desktop', 'remembered-return',
                            boundary_operation='standard-desktop')


def probe_transfer_refusal(lease):
    """Run the original read-only refusal in the retained child's actual session."""
    sys.path.insert(0, str(system.ROOT / 'tests/e2e'))
    from ui_observations import UiObservations
    from qualification_storage import recovery_session, allocate
    with operation('Reading the retained overlay wrong-surface refusal'), recovery_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-transfer-refusal-probe-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        lease.commands.directory = private
        print('transfer-refusal-probe: evidence=' + str(directory), flush=True)
        observed = UiObservations(connect(lease)).observe('transfer-overlay-riley-refused')
        (directory / 'observed.json').write_text(json.dumps(observed))
        lease.guard()
        print('transfer-refusal-probe: guarded refusal read passed', flush=True)


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


def reproduce_denial(lease, journey_type, plan, boundary, surface, *, boundary_operation=None,
                     assets=None):
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
        context = SimpleNamespace(directory=directory, lease=lease)
        expected_inputs = {}
        if assets is not None:
            from provenance import VerifiedInputs, preflight_source
            staged = directory / 'input'
            system.stage_assets(system.artifact_source(assets), staged, lease.commands)
            staged.chmod(0o700)
            preflight_source(staged)
            context.verified = VerifiedInputs(lease=lease, assets=staged)
            expected_inputs = context.verified.source_files

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

        journey = Reproduction(context, progress,
                               **({'plan': plan} if plan is not None else {}))

        def validate():
            validate_boundary(journey, directory, boundary)

        def observe(guard):
            if (directory / (boundary + '.request.json')).exists():
                guard()
                validate()
                if boundary_operation is not None:
                    from ui_observations import UiObservations
                    try:
                        observed = UiObservations(transport).observe(boundary_operation)
                    except Exception as error:
                        observed = {'outcome': 'refused', 'error_type': type(error).__name__}
                    (directory / 'boundary-observation.json').write_text(json.dumps(observed))
                    guard()
                return True
            journey.step(guard)
            return False

        result = e2e_worker.run_distribution(directory, lease, system.RunLedger(),
            expected_inputs=expected_inputs, observe=lambda: None, validate=validate,
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
