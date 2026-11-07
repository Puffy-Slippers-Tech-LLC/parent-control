"""Cases 231/232: three approvals replace the child's temporary native app access."""
from accessible_ui import (KIOSK_BOUND_OPERATIONS, MATCH_APPS, NAMED_CHILD_OPERATIONS,
                           OVERLAY_BOUND_OPERATIONS)
from access_choices import AccessChoiceJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry, desktop_return,
                            fresh_desktop, native_blocked_app, native_usable_app, prefixed_stages,
                            station_entry)
from native_fixtures import fixture_actions
from private_artifacts import require
from request_composition import KioskRequestJourney
from request_flow import approval_and_return
from ui_observations import SettingsObservation


ROWS = (('allowed', 'A', 'allowed'), ('hard', 'H', 'permanent'),
        ('soft', 'S', 'conditional'))
REQUESTS = {'first': ('other-child', 'parent', 30, False),
            'included': ('other-child', 'other-parent', 30, True),
            'replacement': ('other-child', 'parent', 30, False)}


def temporary_access_plan(surface):
    require(surface in ('overlay', 'kiosk'), 'temporary-access:surface')
    screens = app_policy_entry(child='existing', initial_rows=False,
                               allowance='time-explanation-setup-thirty-read')
    access = {}
    for name, role, choice in ROWS:
        operation = 'access-' + (name + '-' if role != 'A' else '')
        screens.update({name + '-save': 'ui:' + operation + choice,
                        name + '-row': 'ui:' + operation + 'row'})
        access[name + '-row'] = (MATCH_APPS[role], choice)
    screens.update({
        **desktop_return('leave-parent', account='parent'),
        **prefixed_stages('initial', desktop_entry('other-child', source='gdm', entry='fresh')),
        **prefixed_stages('allowed', native_usable_app('grid')),
        'allowed-capture': 'ui:native-policy-activity',
        **prefixed_stages('initial-hard', native_blocked_app('H', route='grid')),
        **prefixed_stages('initial-soft', native_blocked_app('S', route='grid'))})
    step2 = len(screens)
    activities, countdowns, bindings, entries = {}, {}, {}, {}
    logins = {'initial': ('other-child', 'initial-'), 'final': ('parent', 'final-')}
    for name, (child, approver, seconds, soft) in REQUESTS.items():
        entry = ({**desktop_return('leave-child', account=child), **station_entry()}
                 if surface == 'kiosk' else {'independent-launch': 'ui:child-command-launch'})
        group = {
            **entry,
            **approval_and_return(prefix='open', entry='open', child='existing-fixture-child',
                approver='fixture-parent' if approver == 'parent' else 'other-fixture-parent',
                duration_seconds=seconds, allow_soft=soft, surface=surface,
                child_entry='retained' if surface == 'kiosk' else 'fresh'),
            **({'soft-closed': 'ui:native-policy-soft-closed'} if name == 'replacement' else {}),
            'allowed-preserved': 'ui:native-policy-activity',
            'allowed-submit': 'ui:native-resubmit',
            'allowed-submitted': 'ui:native-submitted',
            'allowed-original': 'ui:native-policy-activity',
            **prefixed_stages('hard', native_blocked_app('H', route='grid')),
            **({**prefixed_stages('soft', native_usable_app('grid', role='S')),
                'soft-capture': 'ui:native-policy-soft-activity'} if soft else
               prefixed_stages('soft', native_blocked_app('S', route='grid'))),
        }
        screens.update(prefixed_stages(name, group))
        bound_operations = KIOSK_BOUND_OPERATIONS if surface == 'kiosk' else OVERLAY_BOUND_OPERATIONS
        bindings.update({name + '-' + stage: REQUESTS[name] for stage, tag in group.items()
                         if tag.removeprefix('ui:') in bound_operations})
        activities.update({name + '-' + stage: ('allowed-capture', 'same')
                           for stage in ('allowed-preserved', 'allowed-original')})
        countdowns[name + '-countdown'] = (name + '-open-estimate', 'estimate', 1, 300)
        if surface == 'kiosk':
            entries[name + '-retained-entry-guard'] = 'allowed-capture'
            logins[name + '-retained'] = (child, name + '-retained-')
    activities['replacement-soft-closed'] = ('included-soft-capture', 'closed')
    activities['included-soft-capture'] = ('allowed-capture', 'separate')
    step3 = len(screens)
    screens.update({**prefixed_stages('final', desktop_entry('parent', source='desktop', entry='retained',
                                                          source_account='other-child')),
                    'final-apps': 'ui:existing-apps'})
    for name, role, choice in ROWS:
        screens['final-' + name + '-row'] = 'ui:access-' + (name + '-' if role != 'A' else '') + 'row'
        access['final-' + name + '-row'] = (MATCH_APPS[role], choice)
    login_stages = {prefix + stage for account, prefix in logins.values() for stage in fresh_desktop(account)}
    return JourneyPlan(
        prefix='native-grid-kiosk-temporary-access' if surface == 'kiosk' else 'native-grid-temporary-access',
        worker_mode='native_grid_kiosk_temporary_access' if surface == 'kiosk' else 'native_grid_temporary_access',
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
        overlay_request=REQUESTS['first'] if surface == 'overlay' else None,
        overlay_requests=bindings if surface == 'overlay' else {},
        kiosk_request=REQUESTS['first'] if surface == 'kiosk' else None,
        kiosk_requests=bindings if surface == 'kiosk' else {},
        countdown_checks=countdowns, activity_checks=activities, activity_entries=entries,
        invocations=tuple(stage for stage in screens if stage in login_stages),
        challenges={name: (account, prefix + ('recipient-qualified' if account == 'parent'
                                            else 'standard-recipient-qualified'),
                          prefix + ('recipient-rechecked' if account == 'parent'
                                    else 'standard-recipient-rechecked'))
                    for name, (account, prefix) in logins.items()},
        assertions_after={'final-soft-row': 'visible-result'})


PLAN = temporary_access_plan('overlay')
KIOSK_PLAN = temporary_access_plan('kiosk')


class TemporaryAccessJourney(KioskRequestJourney, AccessChoiceJourney):
    def check_estimate(self, observed):
        # Each request's current public estimate accounts for earlier grants/use.
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is not None:
            require(choice['request']['child'] == 'existing-fixture-child'
                    and choice['request']['duration_seconds'] == 30
                    and choice['estimate']['kind'] == 'fixed'
                    and choice['estimate']['seconds'] >= 900,
                    'temporary-access:request-margin')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
        actions=fixture_actions(include_refusal=False), journey_type=TemporaryAccessJourney)


def execute_kiosk(recorder, context):
    record_installed_journey(recorder, context, KIOSK_PLAN, timeout=1800,
        actions=fixture_actions(include_refusal=False), journey_type=TemporaryAccessJourney)


E2E_CASES = {'native-grid-child-overlay': execute, 'native-grid-kiosk': execute_kiosk}
