"""Guarded spare-child removal and automatic account-selection recovery."""

from copy import deepcopy

from account_fixture import SpareChildrenFixture, SpareApproverFixture
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import desktop_entry, fresh_desktop, prefixed_stages, station_entry, parent_management
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch', 'parent-window': 'ui:parent-window',
    'jordan-selected': 'ui:spare-parent-jordan-select',
    'jordan-allowance': 'ui:spare-parent-jordan-allowance',
    'riley-selected': 'ui:spare-parent-riley-select',
    'riley-allowance': 'ui:spare-parent-riley-allowance',
    'jordan-retained': 'ui:spare-parent-jordan-return',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    'jordan-choices': 'ui:spare-kiosk-jordan-seed',
    'jordan-saved': 'ui:spare-kiosk-jordan-read',
    'riley-choices': 'ui:spare-kiosk-riley-seed',
    'riley-saved': 'ui:spare-kiosk-riley-read',
    'remember-jordan': 'ui:spare-kiosk-jordan-remember',
    'station-cancel': 'ui:kiosk-request-cancel', 'station-returned': 'ui:gdm-station-returned',
    **prefixed_stages('return', desktop_entry('parent', source='gdm', entry='retained')),
    'remove-requested': 'ui:spare-parent-jordan-read',
    'parent-fallback': 'ui:spare-parent-riley-fallback',
    'reopen-switch': 'system:parent-switch-user', 'reopen-greeter': 'ui:gdm-returned',
    **prefixed_stages('reopen', station_entry()),
    'station-fallback': 'ui:spare-kiosk-riley-fallback',
    'final-cancel': 'ui:kiosk-request-cancel', 'final-greeter': 'ui:gdm-station-returned',
}
LOGIN_STAGES = (*fresh_desktop('parent'),
                *prefixed_stages('return', fresh_desktop('parent')))
PLAN = JourneyPlan(
    prefix='remove-selected', worker_mode='remove_selected', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            'remove-requested': 'step-2',
            **{stage: 'step-3' for stage in tuple(SCREENS)[tuple(SCREENS).index('parent-fallback'):]}},
    advance_after={'installed-greeter': 'step-1', 'return-desktop': 'step-2',
                   'remove-requested': 'step-3'},
    stage_actions={'setup-detached': 'prepare-spare-children', 'remove-requested': 'remove-spare-child'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={'initial': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
)

LAST_CHILD_SCREENS = {
    **fresh_desktop('parent'),
    'parent-command': 'ui:parent-command-launch', 'parent-window': 'ui:parent-window',
    'jordan-only': 'ui:spare-parent-jordan-only',
    'parent-empty': 'ui:spare-parent-empty',
}
LAST_CHILD_PLAN = JourneyPlan(
    prefix='remove-last-child', worker_mode='remove_last_child', screen_tags=LAST_CHILD_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in LAST_CHILD_SCREENS},
            'installed-greeter': 'start', 'jordan-only': 'step-2', 'parent-empty': 'step-3'},
    advance_after={'installed-greeter': 'step-1', 'parent-window': 'step-2',
                   'jordan-only': 'step-3'},
    stage_actions={'setup-detached': 'prepare-spare-children', 'jordan-only': 'remove-spare-child'},
    invocations=tuple(fresh_desktop('parent')),
    challenges={'initial': ('parent', 'recipient-qualified', 'recipient-rechecked')},
)

APPROVER_SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'riley-allowance': 'ui:time-explanation-setup-thirty-read',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **prefixed_stages('seed', station_entry()),
    'station-seed': 'ui:approver-change-kiosk-seed',
    'station-cancel': 'ui:kiosk-request-cancel', 'station-returned': 'ui:gdm-station-returned',
    **prefixed_stages('child-entry', desktop_entry('child', source='gdm', entry='fresh')),
    'overlay-launch': 'ui:child-command-launch',
    'overlay-seed': 'ui:approver-change-overlay-seed',
    'overlay-cancel': 'ui:overlay-request-cancel',
    'forms-closed': 'ui:overlay-desktop',
    'overlay-reopen': 'ui:child-command-launch',
    'overlay-fallback': 'ui:approver-change-overlay-fallback',
    'overlay-final-cancel': 'ui:overlay-request-cancel',
    'child-returned': 'ui:overlay-desktop',
    'child-switch': 'system:child-switch-user', 'child-greeter': 'ui:gdm-returned',
    **prefixed_stages('reopen', station_entry()),
    'station-fallback': 'ui:approver-change-kiosk-fallback',
    'final-cancel': 'ui:kiosk-request-cancel', 'final-greeter': 'ui:gdm-station-returned',
}
APPROVER_LOGINS = (*fresh_desktop('parent'),
                   *prefixed_stages('child-entry', fresh_desktop('child')))
APPROVER_PLAN = JourneyPlan(
    prefix='ineligible-approver', worker_mode='ineligible_approver', screen_tags=APPROVER_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in APPROVER_SCREENS}, 'installed-greeter': 'start',
            'forms-closed': 'step-2',
            **{stage: 'step-3' for stage in tuple(APPROVER_SCREENS)[
                tuple(APPROVER_SCREENS).index('overlay-reopen'):]}},
    advance_after={'installed-greeter': 'step-1', 'overlay-cancel': 'step-2',
                   'forms-closed': 'step-3'},
    stage_actions={'setup-detached': 'prepare-spare-approver', 'forms-closed': 'demote-spare-approver'},
    invocations=tuple(stage for stage in APPROVER_SCREENS if stage in APPROVER_LOGINS),
    challenges={'initial': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'child-entry': ('child', 'child-entry-child-recipient-qualified',
                                'child-entry-child-recipient-rechecked')},
    child_bindings={'riley-allowance': 'child'},
)


class AccountChangeJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        self.parent_window = None
        self.riley_request = None

        def compare(stage, observed):
            value = observed.get('ui', {}).get('account_change')
            if value is not None and 'window' in value:
                if self.parent_window is None:
                    self.parent_window = deepcopy(value['window'])
                require(value['window'] == self.parent_window, plan.prefix + ':parent-window-replaced')
            if value is not None and 'settings' in value:
                role = 'riley' if stage in ('riley-selected', 'riley-allowance', 'parent-fallback') else 'jordan'
                initial = stage in ('jordan-selected', 'riley-selected', 'jordan-only')
                require(value['settings'] == {
                    'child': 'spare-' + role, 'limit_enabled': not initial,
                    'allowance': ['0 minutes' if initial else '15 minutes' if role == 'riley'
                                  else '30 minutes']}, plan.prefix + ':saved-settings')
            if stage == 'parent-empty':
                require(value is not None and value['empty'] is True,
                        'remove-last-child:missing-empty-result')
                observed['comparison'] = {'same_parent_window_empty': True}
            if stage == 'riley-saved':
                self.riley_request = deepcopy(value['request'])
            if stage == 'station-fallback':
                require(self.riley_request is not None and value['request'] == self.riley_request,
                        'remove-selected:station-borrowed-choices')
                observed['comparison'] = {'surviving_child_own_choices': True}
            progress(stage, observed)

        super().__init__(context, compare, plan, actions=actions)


def execute(recorder, context):
    fixture = SpareChildrenFixture(context)
    record_installed_journey(recorder, context, PLAN, timeout=2400,
        actions={'prepare-spare-children': fixture.prepare, 'remove-spare-child': fixture.remove},
        journey_type=AccountChangeJourney)


def execute_last_child(recorder, context):
    fixture = SpareChildrenFixture(context, count=1)
    record_installed_journey(recorder, context, LAST_CHILD_PLAN, timeout=1800,
        actions={'prepare-spare-children': fixture.prepare, 'remove-spare-child': fixture.remove},
        journey_type=AccountChangeJourney)


def execute_ineligible_approver(recorder, context):
    fixture = SpareApproverFixture(context)
    record_installed_journey(recorder, context, APPROVER_PLAN, timeout=2400,
        actions={'prepare-spare-approver': fixture.prepare, 'demote-spare-approver': fixture.demote})


E2E_CASES = {'remove-selected': execute, 'remove-last-child': execute_last_child,
             'ineligible-approver': execute_ineligible_approver}
