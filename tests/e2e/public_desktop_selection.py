"""Finite public GDM desktop choices and their actual launch results."""

import hashlib
import json
from pathlib import Path

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry
from private_artifacts import require
import public_desktop_observation as launch
import session_control
from ui_observations import UiObservations
import watch_activity


def parent_settings(prefix, enabled):
    return {
        **{f'{prefix}-{stage}': tag for stage, tag in fresh_desktop('parent').items()},
        **{f'{prefix}-{stage}': tag for stage, tag in parent_management().items()},
        f'{prefix}-toggle': 'ui:parent-toggle-' + ('enabled' if enabled else 'disabled'),
        f'{prefix}-saved': 'ui:parent-save-' + ('enabled' if enabled else 'disabled'),
        **({f'{prefix}-restored': 'ui:parent-selected'} if not enabled else {}),
        f'{prefix}-logout': 'system:parent-logout',
        f'{prefix}-returned': 'ui:gdm-returned',
    }


SCREENS = {
    **parent_settings('public-setup', True),
    'public-standard-list': 'ui:gdm-standard-list',
    'public-standard-focused': 'ui:gdm-standard-focused',
    'public-standard-open': 'ui:gdm-standard-session-open',
    'public-standard-selected': 'ui:gdm-standard-session-select-full',
    'public-standard-recipient-qualified': 'ui:gdm-standard-recipient',
    'public-standard-recipient-rechecked': 'ui:gdm-standard-recipient-rechecked',
    'public-standard-desktop': 'ui:standard-desktop',
    'public-standard-launch': 'ui:public-standard-launch',
    'public-standard-logout': 'system:standard-logout',
    'public-standard-returned': 'ui:gdm-returned',
}
for _attempt in ('direct', 'carry'):
    if _attempt == 'carry':
        SCREENS.update({
            'public-cancel-list': 'ui:gdm-standard-list',
            'public-cancel-focused': 'ui:gdm-standard-focused',
            'public-cancel-open': 'ui:gdm-standard-session-open',
            'public-cancel-selected': 'ui:gdm-standard-session-select-full',
            'public-cancel-prompt': 'ui:gdm-standard-session-cancel',
            'public-cancel-returned': 'ui:gdm-returned',
        })
    SCREENS.update({
        f'public-{_attempt}-list': 'ui:gdm-station-list',
        f'public-{_attempt}-focused': 'ui:gdm-station-focused',
        f'public-{_attempt}-open': 'ui:gdm-station-session-open',
        f'public-{_attempt}-selected': f'ui:public-{_attempt}-select',
        f'public-{_attempt}-launch': f'ui:public-{_attempt}-launch',
        f'public-{_attempt}-child': f'ui:public-{_attempt}-child',
        f'public-{_attempt}-approver': f'ui:public-{_attempt}-approver',
        f'public-{_attempt}-result': f'ui:public-{_attempt}-result',
        f'public-{_attempt}-exit': f'ui:public-{_attempt}-exit',
        f'public-{_attempt}-returned': 'ui:gdm-station-returned',
    })
SCREENS['public-routing-restored'] = 'ui:public-routing-restored'
for _prefix in ('public-restored', 'public-fresh'):
    SCREENS.update({f'{_prefix}-{stage}': tag for stage, tag in station_entry().items()})
    SCREENS.update({
        f'{_prefix}-child': f'ui:{_prefix}-child',
        f'{_prefix}-approver': f'ui:{_prefix}-approver',
        f'{_prefix}-usable': 'ui:kiosk-enabled-form',
        f'{_prefix}-cancel': 'ui:kiosk-request-cancel',
        f'{_prefix}-returned': 'ui:gdm-station-returned',
    })
SCREENS.update(parent_settings('public-policy-restore', False))

PLAN = JourneyPlan(
    prefix='public-desktop-selection', worker_mode='public_desktop_selection',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'public-setup-installed-greeter': 'start'},
    invocations=tuple(stage for stage, tag in SCREENS.items() if tag.startswith('ui:')),
    challenges={
        'public-setup': ('parent', 'public-setup-recipient-qualified',
                         'public-setup-recipient-rechecked'),
        'standard-login': ('other-child', 'public-standard-recipient-qualified',
                           'public-standard-recipient-rechecked'),
        'public-policy-restore': ('parent', 'public-policy-restore-recipient-qualified',
                                 'public-policy-restore-recipient-rechecked'),
    },
    settings_checks={'public-policy-restore-restored': 'public-setup-parent-selected'},
)


class PublicDesktopSelectionUi(UiObservations):
    """Finite qualification branches; shared adapters retain all input guards."""

    def __init__(self, transport, lease, original, **kwargs):
        super().__init__(transport, **kwargs)
        self.lease, self.original = lease, original
        self.public_choices = {}
        self.launches = {}
        self.request_prepared = False

    def observe(self, operation, **kwargs):
        if not operation.startswith('public-'):
            result = (self.observe_gdm_chooser(operation, self.lease) if operation in (
                'gdm-standard-session-open', 'gdm-standard-session-select-full',
                'gdm-standard-session-cancel', 'gdm-station-session-open',
                'gdm-station-session-select-full') else super().observe(operation, **kwargs))
            if operation == 'gdm-station-session-open':
                self.public_choices['station'] = result['session_choice']
            return result
        self.lease.guard()
        self.boot_proof = None
        boot = hashlib.sha256(self.transport.call(
            ['cat', '/proc/sys/kernel/random/boot_id'], timeout=15)).hexdigest()
        require(boot == self.boot_guard, 'public-desktop:boot-changed')
        self.boot_proof = boot
        value = {'operation': operation, 'outcome': 'passed',
                 'interface': 'ApplicationUI+external-provider'}
        if operation == 'public-routing-restored':
            value['restoration'] = launch.restore_routing(
                self.transport, self.lease, self.original, self.launches)
            return value
        if operation == 'public-standard-launch':
            actual = launch.observe(self.transport, self.lease, binding='standard')
            self.launches['standard'] = actual
            value['launch'] = actual
            return value
        _, attempt, action = operation.split('-')
        require(attempt in ('direct', 'carry', 'restored', 'fresh'), 'public-desktop:attempt')
        if action == 'select':
            choice = self.public_choices['station']
            if choice['disposition'] == 'chooser-opened':
                value['public_choice'] = self.observe(
                    'gdm-station-session-select-full')['session_choice']
            else:
                require(choice['disposition'] == 'no-public-chooser',
                        'public-desktop:unresolved-choice')
                value['public_choice'] = choice
            self.public_choices[attempt] = value['public_choice']
        elif action == 'launch':
            actual = launch.observe(self.transport, self.lease, binding='station')
            self.launches['station'] = actual
            value['launch'] = actual
        elif action in ('child', 'approver', 'result'):
            actual = self.launches['station']
            compositor = Path(actual['compositor']['executable']).name
            require(compositor in ('gnome-shell', 'gnome-kiosk'),
                    'public-desktop:unresolved-compositor')
            full = attempt in ('direct', 'carry') and compositor == 'gnome-shell'
            if action == 'result':
                value['public_result'] = super().observe(
                    'gdm-station-full-desktop' if full else 'kiosk-enabled-form')
                value['result'] = 'full-desktop-gap' if full else 'request-only'
                value['launch'] = actual
                value['public_choice'] = self.public_choices[attempt]
                self.public_choices[attempt + '-result'] = value['result']
            elif full:
                value['disposition'] = 'not-applicable-full-desktop'
            elif self.request_prepared:
                # The first request saved Riley/Jamie. Reentry reads those
                # exact usable choices below; replaying the initial child
                # selection would wrongly expect its original Casey default.
                value['disposition'] = 'choices-already-prepared'
            else:
                value['request_choice'] = super().observe('kiosk-' + action + '-select')
                if action == 'approver':
                    self.request_prepared = True
        elif action == 'exit':
            if self.public_choices[attempt + '-result'] == 'request-only':
                value['exit'] = super().observe('kiosk-request-cancel')
            else:
                actual = self.launches['station']
                # Shared supported logout command, pinned to the actual owned
                # session. Never terminate another session or replay input.
                with watch_activity.operation('Logging out the observed station desktop'):
                    raw = self.transport.call(
                        ['/usr/bin/python3', '-I', '-', 'maintenance-logout',
                         str(actual['uid']), actual['session']['id']],
                        input=Path(session_control.__file__).read_bytes(), timeout=120)
                value['exit'] = json.loads(raw)
                require(value['exit'] == {
                    'operation': 'maintenance-logout', 'outcome': 'passed',
                    'source_retained': False, 'other_desktops_retained': True},
                    'public-desktop:logout-result')
        else:
            require(False, 'public-desktop:operation')
        self.lease.guard()
        return value


class PublicDesktopSelectionJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.full_choice = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'setup-detached':
            original = launch.capture_routing(self.transport, self.context.lease)
            observed['original_routing'] = original
            self.ui = PublicDesktopSelectionUi(
                self.transport, self.context.lease, original, progress=self.watch_progress)
            self.ui.trace_sink = self.retain_trace_sample
        elif stage == 'public-standard-selected':
            self.full_choice = observed['ui']['session_choice']['choice']
            require(self.full_choice in ('ubuntu', 'gnome'), 'public-desktop:positive-choice')
        elif stage == 'public-cancel-selected':
            require(observed['ui']['session_choice']['choice'] == self.full_choice,
                    'public-desktop:cancel-same-choice')
        elif stage == 'public-standard-launch':
            actual = observed['ui']['launch']
            require(Path(actual['compositor']['executable']).name == 'gnome-shell',
                    'public-desktop:positive-full-desktop')
            require(actual['selected_desktop']['id'] == self.full_choice,
                    'public-desktop:positive-selected-id')
        elif stage in ('public-direct-selected', 'public-carry-selected'):
            choice = observed['ui']['public_choice']
            require(choice['disposition'] == 'no-public-chooser'
                    or choice['choice'] == self.full_choice,
                    'public-desktop:station-same-choice')
        elif stage == 'public-setup-parent-selected':
            require(observed['ui']['settings']['limit_enabled'] is False,
                    'public-desktop:initial-disabled-child')

    def validate(self):
        matched = super().validate()
        # Keep exposed-desktop observations and finish safe exit, routing/policy
        # restoration and usable reentry before rejecting either attempt.
        results = {step['stage']: step['ui']['result'] for step in self.steps
                   if step['stage'] in ('public-direct-result', 'public-carry-result')}
        for stage in ('public-direct-result', 'public-carry-result'):
            require(results[stage] == 'request-only', 'public-desktop:' + stage + ':request-only')
        return matched
