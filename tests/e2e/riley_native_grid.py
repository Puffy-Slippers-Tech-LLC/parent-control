"""047g: Riley's same-target native grid launch and independently observed use."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, native_usable_app, prefixed_stages
from native_fixtures import fixture_actions
from request_composition import KioskRequestJourney


ENTRY = {**native_usable_app('grid', child='child'),
         'close': 'ui:overlay-native-close', 'closed': 'ui:overlay-native-closed'}
CHILD_SCREENS = {
    **prefixed_stages('fresh', fresh_desktop('child')),
    **prefixed_stages('first', ENTRY),
    'repeat-desktop': 'ui:overlay-native-desktop',
    'repeat-search-ready': 'ui:overlay-native-search-ready',
    'repeat-search-focused': 'ui:overlay-native-search-focused',
    'repeat-search-entered': 'ui:overlay-native-search-entered',
    'repeat-refusals': 'ui:overlay-native-grid-refusals',
    **prefixed_stages('repeat', {stage: tag for stage, tag in ENTRY.items()
        if stage in ('app-grid', 'opened', 'submit', 'submitted', 'close', 'closed')}),
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'wrong-account-refused': 'ui:overlay-wrong-account-refused',
    'repeat-parent-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **CHILD_SCREENS,
}
PLAN = JourneyPlan(
    prefix='riley-native-grid', worker_mode='riley_native_grid', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in CHILD_SCREENS}},
    advance_after={'gdm-switched': 'step-2'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=(*fresh_desktop('parent'), *prefixed_stages('fresh', fresh_desktop('child'))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 900},
)


class RileyNativeGridJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions(profile='riley-grid') if actions is None else actions)
