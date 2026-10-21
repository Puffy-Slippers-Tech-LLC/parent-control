"""REQUEST01/03 qualification: enter and read the disabled-child station."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import station_entry
import json
import re
import system_runner as system
import time
import watch_activity
from private_artifacts import require
from ui_observations import UiObservations


PLAN = JourneyPlan(
    prefix='kiosk-entry', worker_mode='kiosk_entry',
    screen_tags={
        **station_entry(),
        'request-form': 'ui:kiosk-request-form',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        'station-list': 'start',
        'station-focused': 'step-1', 'station-branch': 'step-2', 'request-form': 'step-2',
    },
    advance_after={'station-list': 'step-1', 'station-focused': 'step-2'},
)


def confinement_census(transport, lease):
    """Observe session identity separately from the public form result.

    This engineering observation grants no confinement or renewed installed
    qualification; the current public entry operation needs live qualification.
    """
    lease.guard()
    result = transport.call(['env', 'ONPC_EXPECTED_RUN=' + lease.state['run'],
        'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
        system.PAYLOAD + '/system_kiosk_confinement.py', 'census'], timeout=45)
    return json.loads(result)


def enter_station(lease, ui, observe, *, on_input=None):
    """Enter once from a fresh, boot-bound public account/focus observation."""
    require(on_input is None or callable(on_input), 'kiosk-activation:timing-callback')
    observe('gdm-station-list')
    boot = ui.boot_proof
    require(type(boot) is str and re.fullmatch(r'[0-9a-f]{64}', boot),
            'kiosk-activation:boot-proof')
    ui.boot_guard = boot
    checked = time.monotonic()
    recipient = observe('gdm-station-focused')
    require(recipient == {'operation': 'gdm-station-focused',
            'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'},
            'kiosk-activation:recipient')
    with watch_activity.operation('Entering the freshly focused request station'):
        lease.guard()
        require(0 <= time.monotonic() - checked < 30,
                'kiosk-activation:stale-recipient')
        started = time.monotonic_ns()
        try:
            lease.source.domain.sendKey(
                lease.source.api.VIR_KEYCODE_SET_LINUX, 100, [28], 1, 0)
            submitted = time.monotonic_ns()
        finally:
            # An uncertain Enter is never replayed, including guard failure.
            lease.guard()
    if on_input is not None:
        on_input(started, submitted)
    return started


def observe_activation(transport, lease, phase):
    """Observe real GDM entry in the caller's uninterrupted install history.

    The caller owns installation, boot, transport and lease lifetime. This leaf
    never restores snapshots or resets fixtures, and never retries native input.
    """
    require(phase in ('installed', 'rebooted'), 'kiosk-activation:phase')
    with watch_activity.operation('Checking real kiosk activation: ' + phase):
        ui = UiObservations(transport)
        ui.boot_guard = ''
        observations = []

        def observe(operation):
            lease.guard()
            value = ui.observe(operation)
            observations.append(value)
            return value

        enter_station(lease, ui, observe)
        boot = ui.boot_proof

        if phase == 'installed':
            observe('station-initial-entry')
            observe('restart-kiosk-read')
        else:
            observe('station-default-entry')
            observe('kiosk-request-form')
            observe('restart-kiosk-missing-refused')
        census = confinement_census(transport, lease)

        if phase == 'installed':
            observe('restart-kiosk-close')
            observe('restart-kiosk-closed')
            observe('restart-kiosk-exit')
        else:
            observe('kiosk-request-cancel')
        observe('gdm-station-returned')
        return {'phase': phase, 'boot_sha256': boot, 'public_observations': observations,
                'engineering_confinement': census}


class KioskEntryJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'request-form':
            # This qualification also supplies an engineering census. Customer
            # scenario classes retain only their public workflow assertions.
            observed['engineering_confinement'] = confinement_census(
                self.transport, self.context.lease)
