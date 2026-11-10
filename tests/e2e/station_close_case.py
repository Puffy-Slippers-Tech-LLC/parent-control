"""Case 175: close pending station approval, then approve a fresh request."""
from copy import deepcopy

from access_choices import AccessChoiceJourney
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop,
                            native_blocked_app, native_usable_app, parent_management,
                            parent_selection, prefixed_stages, retained_parent_entry,
                            station_entry)
from kiosk_approved_flow import approved_request
from named_app_set import APPS, named_app_set, saved_rows
from native_fixtures import fixture_actions
from private_artifacts import require
from request_composition import CancelledRequestJourney
from request_flow import CHOICES, prepared_request


def peer_read(prefix):
    return {**prefixed_stages(prefix, parent_selection(child='existing', screen_limits=True)),
            prefix + '-settings': 'ui:existing-returned',
            prefix + '-balance': 'ui:time-explanation-refresh-read',
            prefix + '-apps-page': 'ui:existing-apps',
            prefix + '-apps': 'ui:existing-parent-app-rows'}


RETURN = {**desktop_entry('parent', source='gdm', entry='retained'),
          **retained_parent_entry(source='same-user', desktop_observation=False)}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(child='existing'),
    'peer-allowance': 'ui:time-explanation-setup-thirty-read',
    'peer-settings': 'ui:existing-returned',
    'peer-apps-page': 'ui:existing-apps', 'peer-apps': 'ui:existing-parent-app-rows',
    **prefixed_stages('selected', parent_selection(child='child', screen_limits=True)),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    **named_app_set(source='desktop', entry='same-user', window='retained',
                    child='child', apps=APPS, prefix='rules'),
    **station_entry(),
    'peer-choices-before': 'ui:transfer-kiosk-jordan-select-default',
    **prepared_request(prefix='open', entry='open', initial='observed', **CHOICES),
    **prefixed_stages('interruption', approved_request(**CHOICES, exit='close')),
    **station_entry('cancel-'),
    'reopened-form': 'ui:kiosk-valid-fraction-soft-read',
    'peer-choices-returned': 'ui:remembered-second-reverse-kiosk-jordan-select-default',
    'selected-restored': 'ui:kiosk-flow-child-select',
    'cancel': 'ui:kiosk-request-cancel', 'cancel-returned': 'ui:gdm-station-returned',
    **prefixed_stages('return', RETURN),
    'balance-returned': 'ui:time-explanation-refresh-read',
    'returned-apps': 'ui:parent-apps-page', **saved_rows(APPS, 'returned'),
    **peer_read('peer-returned'),
    **prefixed_stages('selected-returned', parent_selection(child='child', screen_limits=True)),
    **desktop_return('cancelled-parent', account='parent'),
    **prefixed_stages('cancelled-child', desktop_entry('child', source='gdm', entry='fresh')),
    **prefixed_stages('cancelled-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('cancelled-soft', native_blocked_app('S', child='child')),
    **prefixed_stages('preapproval', retained_parent_entry(source='child-desktop')),
    'preapproval-balance': 'ui:time-explanation-refresh-read',
    **desktop_return('recovery-parent', account='parent'),
    **prefixed_stages('recovery', station_entry()),
    'recovery-form': 'ui:kiosk-request-estimate',
    **approved_request(**CHOICES, exit='automatic', explicit=True),
    **prefixed_stages('approved-child', desktop_entry('child', source='gdm', entry='retained')),
    'countdown': 'ui:child-countdown-present',
    **prefixed_stages('approved-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('approved-soft', native_usable_app('command', child='child', role='S')),
    'soft-close': 'ui:overlay-native-soft-close', 'soft-closed': 'ui:overlay-native-soft-closed',
    **prefixed_stages('final', retained_parent_entry(source='child-desktop')),
    'approved-balance': 'ui:time-explanation-refresh-read',
    **peer_read('peer-final'),
}
STEP2 = tuple(SCREENS).index('interruption-approval-open')
STEP3 = tuple(SCREENS).index('cancel-station-list')
LOGINS = {'return': ('parent', 'return-'), 'cancelled-child': ('child', 'cancelled-child-'),
          'preapproval': ('parent', 'preapproval-'), 'approved-child': ('child', 'approved-child-'),
          'final': ('parent', 'final-')}
LOGIN_STAGES = {*fresh_desktop('parent'),
                *(prefix + stage for account, prefix in LOGINS.values()
                  for stage in fresh_desktop(account))}
PLAN = JourneyPlan(
    prefix='station-close-case', worker_mode='station_close_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if index < STEP2 else 'step-2' if index < STEP3 else 'step-3'
               for index, stage in enumerate(SCREENS)}, 'installed-greeter': 'start'},
    advance_after={'open-estimate': 'step-2', 'interruption-new-returned': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        **{name: (account, prefix + ('child-recipient-qualified' if account == 'child' else 'recipient-qualified'),
                  prefix + ('child-recipient-rechecked' if account == 'child' else 'recipient-rechecked'))
           for name, (account, prefix) in LOGINS.items()}},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' if stage.startswith('peer-') else 'child'
                    for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    balance_checks={'peer-allowance': 1800, 'allowance-configured': 1800},
    match_checks={prefix + '-' + role.lower() + '-match': (MATCH_APPS[role], rule)
                  for prefix in ('rules-saved', 'returned')
                  for role, rule in (('A', MATCH_RULES[0]), ('H', MATCH_RULES[3]), ('S', MATCH_RULES[4]))},
    access_checks={prefix + '-' + role.lower() + '-access': (MATCH_APPS[role], choice)
                   for prefix in ('rules-saved', 'returned')
                   for role, choice in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    kiosk_request=('child', 'parent', 75, True),
    request_checks={stage: ('open-estimate', 'station-close:choices-changed', 'preserved_cancelled_choices')
                    for stage in ('reopened-form', 'recovery-form')},
    countdown_checks={'countdown': ('recovery-form', 'estimate', 1, 300)},
    assertions_after={'peer-final-apps': 'visible-result'},
)


class StationCloseCaseJourney(CancelledRequestJourney, AccessChoiceJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions, session_checks={},
                         balance_check=('allowance-configured', 'balance-returned', 1200))
        self.peer = {}
        self.approval_estimate = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        ui = observed.get('ui', {})
        for suffix in ('settings', 'apps', 'balance'):
            initial = 'peer-allowance' if suffix == 'balance' else 'peer-' + suffix
            key = 'time_explanation' if suffix == 'balance' else suffix
            if stage == initial:
                self.peer[suffix] = deepcopy(ui[key])
            elif stage in ('peer-returned-' + suffix, 'peer-final-' + suffix):
                before, after = self.peer[suffix], ui[key]
                if suffix == 'balance':
                    elapsed = (after['observed_monotonic_ns'] - before['observed_monotonic_ns']) / 1e9
                    require(after['child'] == before['child'] and 0 <= elapsed <= 2400
                            and after['one_time']['seconds'] == 0, 'station-close:peer-grant')
                    for field in ('daily', 'total'):
                        precision = before[field]['precision_seconds'] + after[field]['precision_seconds']
                        require(max(0, before[field]['seconds'] - elapsed) - precision
                                <= after[field]['seconds'] <= before[field]['seconds'] + precision,
                                'station-close:peer-balance')
                else:
                    require(after == before, 'station-close:peer-' + suffix)
                observed.setdefault('comparison', {})['preserved_peer_' + suffix] = True
        if stage in ('peer-choices-before', 'peer-choices-returned'):
            # Approver selection is local to the station; these shared choices
            # belong to Jordan and must survive Riley's cancelled request.
            choice = {key: value for key, value in ui['request'].items() if key != 'approver'}
            require(choice['child'] == 'existing-fixture-child' and choice['allow_soft'] is False,
                    'station-close:peer-request')
            if stage == 'peer-choices-before':
                self.peer['request'] = deepcopy(choice)
            else:
                require(choice == self.peer['request'], 'station-close:peer-choices')
                observed.setdefault('comparison', {})['preserved_peer_choices'] = True
        if stage == 'recovery-form':
            self.approval_estimate = deepcopy(ui['valid_choice'])
        if stage == 'approved-balance':
            before, after = self.approval_estimate, ui['time_explanation']
            require(before is not None and after['child'] == before['request']['child'],
                    'station-close:approval-owner')
            elapsed = (after['observed_monotonic_ns'] - before['observed_monotonic_ns']) / 1e9
            precision = after['one_time']['precision_seconds'] + before['estimate']['precision_seconds']
            require(0 <= elapsed <= 600 and after['one_time']['seconds'] > 0
                    and before['estimate']['seconds'] - elapsed - precision
                    <= after['one_time']['seconds'] <= before['estimate']['seconds'] + precision,
                    'station-close:actual-time-addition')
            observed.setdefault('comparison', {})['fresh_approval_added_time'] = True


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-039/kiosk-close'
    record_installed_journey(recorder, context, PLAN, timeout=3000,
        actions=fixture_actions(include_refusal=False), journey_type=StationCloseCaseJourney)


E2E_CASES = {'kiosk-close': execute}
