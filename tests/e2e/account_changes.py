"""One removal, with independent Parent and remembered-station recovery."""

from copy import deepcopy

from account_fixture import SpareChildrenFixture
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import desktop_entry, fresh_desktop, prefixed_stages, station_entry
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


class AccountChangeJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        self.parent_window = None
        self.riley_request = None

        def compare(stage, observed):
            value = observed.get('ui', {}).get('account_change')
            if value is not None and 'settings' in value:
                if self.parent_window is None:
                    self.parent_window = deepcopy(value['window'])
                require(value['window'] == self.parent_window, 'remove-selected:parent-window-replaced')
                role = 'riley' if stage in ('riley-selected', 'riley-allowance', 'parent-fallback') else 'jordan'
                initial = stage in ('jordan-selected', 'riley-selected')
                require(value['settings'] == {
                    'child': 'spare-' + role, 'limit_enabled': not initial,
                    'allowance': ['0 minutes' if initial else '15 minutes' if role == 'riley'
                                  else '30 minutes']}, 'remove-selected:saved-settings')
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


E2E_CASES = {'remove-selected': execute}
