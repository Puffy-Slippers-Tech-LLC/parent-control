"""Cases 243/246: three approvals replace Jordan's temporary Flatpak access."""
from accessible_ui import (FLATPAK_POLICY_APPS, KIOSK_BOUND_OPERATIONS,
                           NAMED_CHILD_OPERATIONS, OVERLAY_BOUND_OPERATIONS)
from flatpak_fixtures import fixture_actions
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry, desktop_return,
                            flatpak_blocked_app, fresh_desktop, native_usable_app,
                            prefixed_stages, station_entry)
from private_artifacts import require
from request_composition import KioskRequestJourney
from access_choices import AccessChoiceJourney
from request_flow import approval_and_return
from ui_observations import SettingsObservation


ROWS = (('allowed', 'A', 'allowed'), ('hard', 'H', 'permanent'),
        ('soft', 'S', 'conditional'))
REQUESTS = {'first': ('other-child', 'parent', 300, False),
            'included': ('other-child', 'other-parent', 300, True),
            'replacement': ('other-child', 'parent', 300, False)}


def temporary_access_plan(route, surface):
    require((route, surface) in (('command', 'kiosk'), ('grid', 'overlay')),
            'temporary-access:binding')
    screens = app_policy_entry(child='existing', initial_rows=False,
                               allowance='time-explanation-setup-thirty-read')
    access = {}
    for name, role, choice in ROWS:
        operation = 'access-flatpak-' + (name + '-' if role != 'A' else '')
        screens.update({name + '-save': 'ui:' + operation + choice,
                        name + '-row': 'ui:' + operation + 'row'})
        access[name + '-row'] = (FLATPAK_POLICY_APPS[role], choice)
    screens.update(desktop_return('leave-parent', account='parent'))
    screens.update({
        **prefixed_stages('initial', desktop_entry('other-child', source='gdm', entry='fresh')),
        **prefixed_stages('allowed', native_usable_app(route, role='A', kind='flatpak')),
        'allowed-capture': 'ui:flatpak-allowed-policy-activity',
        **flatpak_blocked_app('initial-hard', 'H', route),
        **flatpak_blocked_app('initial-soft', 'S', route)})
    activities, entries, countdowns, bindings = {}, {}, {}, {}
    logins = {'initial': ('other-child', 'initial-'), 'final': ('parent', 'final-')}
    step2 = len(screens)
    for name, (_child, approver, seconds, soft) in REQUESTS.items():
        entry = ({**desktop_return('leave-child', account='other-child'), **station_entry()}
                 if surface == 'kiosk' else {'independent-launch': 'ui:child-command-launch'})
        group = {
            **entry,
            **approval_and_return(prefix='open', entry='open', child='existing-fixture-child',
                approver='fixture-parent' if approver == 'parent' else 'other-fixture-parent',
                duration_seconds=seconds, allow_soft=soft, surface=surface,
                child_entry='retained' if surface == 'kiosk' else 'fresh'),
            **({'soft-closed': 'ui:flatpak-soft-policy-closed'} if name == 'replacement' else {}),
            'allowed-preserved': 'ui:flatpak-allowed-policy-activity',
            'allowed-submit': 'ui:flatpak-allowed-resubmit',
            'allowed-submitted': 'ui:flatpak-allowed-submitted',
            'allowed-original': 'ui:flatpak-allowed-policy-activity',
            **flatpak_blocked_app('hard', 'H', route),
            **({**prefixed_stages('soft', native_usable_app(route, role='S', kind='flatpak')),
                'soft-capture': 'ui:flatpak-soft-policy-activity'} if soft else
               flatpak_blocked_app('soft', 'S', route)),
        }
        screens.update(prefixed_stages(name, group))
        bound_operations = KIOSK_BOUND_OPERATIONS if surface == 'kiosk' else OVERLAY_BOUND_OPERATIONS
        bindings.update({name + '-' + stage: REQUESTS[name] for stage, tag in group.items()
                         if tag.removeprefix('ui:') in bound_operations})
        activities.update({name + '-' + stage: ('allowed-capture', 'same')
                           for stage in ('allowed-preserved', 'allowed-original')})
        if surface == 'kiosk':
            entries[name + '-retained-entry-guard'] = 'allowed-capture'
            logins[name + '-retained'] = ('other-child', name + '-retained-')
        countdowns[name + '-countdown'] = (name + '-open-estimate', 'estimate', 1, 300)
    activities['replacement-soft-closed'] = ('included-soft-capture', 'closed')
    activities['included-soft-capture'] = ('allowed-capture', 'separate')
    step3 = len(screens)
    screens.update({**prefixed_stages('final', desktop_entry('parent', source='desktop', entry='retained',
                                                          source_account='other-child')),
                    'final-apps': 'ui:existing-apps'})
    for name, role, choice in ROWS:
        screens['final-' + name + '-row'] = 'ui:access-flatpak-' + (name + '-' if role != 'A' else '') + 'row'
        access['final-' + name + '-row'] = (FLATPAK_POLICY_APPS[role], choice)
    login_stages = {prefix + stage for account, prefix in logins.values() for stage in fresh_desktop(account)}
    return JourneyPlan(
        prefix='flatpak-temporary-access' if surface == 'kiosk' else 'flatpak-grid-temporary-access',
        worker_mode='flatpak_temporary_access' if surface == 'kiosk' else 'flatpak_grid_temporary_access',
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' if index < step2 else 'step-2' if index < step3 else 'step-3'
                   for index, stage in enumerate(screens)}, 'installed-greeter': 'start'},
        advance_after={'initial-soft-denied': 'step-2', 'replacement-soft-denied': 'step-3'},
        stage_actions={'desktop': 'native-verify'},
        child_bindings={stage: 'existing' for stage, tag in screens.items()
                        if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
        settings_checks={
            'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
            'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
        balance_checks={'allowance-configured': 1800}, access_checks=access,
        kiosk_request=REQUESTS['first'] if surface == 'kiosk' else None,
        kiosk_requests=bindings if surface == 'kiosk' else {},
        overlay_request=REQUESTS['first'] if surface == 'overlay' else None,
        overlay_requests=bindings if surface == 'overlay' else {},
        countdown_checks=countdowns, activity_checks=activities, activity_entries=entries,
        invocations=tuple(stage for stage in screens if stage in login_stages),
        challenges={name: (account, prefix + ('recipient-qualified' if account == 'parent'
                                            else 'standard-recipient-qualified'),
                          prefix + ('recipient-rechecked' if account == 'parent'
                                    else 'standard-recipient-rechecked'))
                    for name, (account, prefix) in logins.items()},
        assertions_after={'final-soft-row': 'visible-result'},
    )


PLAN = temporary_access_plan('command', 'kiosk')
GRID_PLAN = temporary_access_plan('grid', 'overlay')


class TemporaryAccessJourney(KioskRequestJourney, AccessChoiceJourney):
    countdown_tolerance_seconds = 120

    def check_estimate(self, observed):
        # Child use and a running grant make each fresh estimate the operand.
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is not None:
            require(choice['request']['child'] == 'existing-fixture-child'
                    and choice['request']['duration_seconds'] == 300
                    and choice['estimate']['kind'] == 'fixed'
                    and choice['estimate']['seconds'] >= 300,
                    'temporary-access:request-margin')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
        actions=fixture_actions(include_refusal=False), journey_type=TemporaryAccessJourney)


def execute_grid(recorder, context):
    record_installed_journey(recorder, context, GRID_PLAN, timeout=1800,
        actions=fixture_actions(include_refusal=False), journey_type=TemporaryAccessJourney)


E2E_CASES = {'flatpak-command-kiosk': execute, 'flatpak-grid-child-overlay': execute_grid}
