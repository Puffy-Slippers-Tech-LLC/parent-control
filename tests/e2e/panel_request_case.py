"""Case 30: panel approval excludes soft apps; a later request authenticates anew."""
from copy import deepcopy

from access_choices import AccessChoiceJourney
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, grant_only_time_profile,
                            native_usable_app, prefixed_stages)
from named_app_set import APPS, named_app_set
from native_fixtures import fixture_actions
from private_artifacts import require
from real_interval import interval_action
from request_composition import KioskRequestJourney
from request_flow import approval_and_return, overlay_authentication, prepared_request


CHOICES = dict(child='fixture-child', approver='fixture-parent',
               duration_seconds=30, allow_soft=False)
RETURN = prefixed_stages('rules-return', desktop_entry('parent', source='gdm', entry='retained'))
CHILD = prefixed_stages('child-entry', desktop_entry('child', source='gdm', entry='fresh'))
SCREENS = {
    **named_app_set(source='gdm', entry='fresh', window='new', child='child',
                    apps=APPS, prefix='rules'),
    **RETURN,
    **grant_only_time_profile(source='desktop', entry='same-user', window='retained',
        initial_enabled=False, revoke_first=False, duration_seconds=1200,
        request_initial='default', daily_minutes=30),
    **CHILD,
    **prefixed_stages('soft-use', native_usable_app('command', child='child', role='S')),
    'soft-capture': 'ui:overlay-native-policy-soft-activity',
    'panel-ready': 'ui:overlay-panel-ready', 'panel-launch': 'ui:overlay-panel-launch',
    **approval_and_return(prefix='open', entry='open', **CHOICES),
    'soft-closed': 'ui:overlay-native-policy-soft-closed',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'soft-denied': 'ui:overlay-native-soft-command-blocked',
    'cooldown': 'ui:fresh-child-desktop',
    **prefixed_stages('later', {
        **prepared_request(prefix='new', entry='new', initial='observed', surface='overlay', **CHOICES),
        **overlay_authentication(result='cancel', prefix='shell'),
        'preserved': 'ui:overlay-request-estimate',
        'cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop',
    }),
}
LOGINS = {'rules-return-': ('parent', 'rules-return'),
          'profile-return-': ('parent', 'profile-return'), 'child-entry-': ('child', 'child-entry')}
LOGIN_STAGES = {prefix + stage for prefix, (role, _challenge) in LOGINS.items()
                for stage in fresh_desktop(role)}
STEP2 = tuple(SCREENS).index('open-choices')
STEP3 = tuple(SCREENS).index('approval-qualified')
PLAN = JourneyPlan(
    prefix='panel-request-case', worker_mode='panel_request_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if index < STEP2 else 'step-2' if index < STEP3 else 'step-3'
               for index, stage in enumerate(SCREENS)}, 'installed-greeter': 'start'},
    advance_after={'panel-launch': 'step-2', 'approval-open': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={identity: (role, prefix + ('recipient-qualified' if role == 'parent' else 'child-recipient-qualified'),
                          prefix + ('recipient-rechecked' if role == 'parent' else 'child-recipient-rechecked'))
                for prefix, (role, identity) in LOGINS.items()},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    stage_actions={'desktop': 'native-verify', 'cooldown': 'cooldown'},
    balance_checks={'profile-daily': 1800},
    match_checks={'rules-saved-' + role.lower() + '-match': (MATCH_APPS[role], rule)
                  for role, rule in (('A', MATCH_RULES[0]), ('H', MATCH_RULES[3]), ('S', MATCH_RULES[4]))},
    access_checks={'rules-saved-' + role.lower() + '-access': (MATCH_APPS[role], access)
                   for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    overlay_request=('child', 'parent', 30, False),
    countdown_checks={'countdown': ('open-estimate', 'estimate', 1, 180)},
    activity_checks={'soft-closed': ('soft-capture', 'closed')},
    request_checks={'later-preserved': ('later-new-estimate', 'panel-request:cancel-changed-form',
                                        'preserved_choices')},
    assertions_after={'later-returned': 'visible-result'},
)


class PanelRequestJourney(GrantOnlyProfileJourney, KioskRequestJourney, AccessChoiceJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, daily_minutes=30, actions=actions)

    def check_estimate(self, observed):
        # The first approval compares the independent Parent balance and child
        # countdown. Later readbacks prove preserved choices after Cancel;
        # the pre-approval Parent balance no longer describes that new grant.
        if not self.countdowns:
            super().check_estimate(observed)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-balance':
            self.balance = deepcopy(observed['ui']['revoke_cancel']['balances'])
        if stage == 'open-estimate':
            require(observed['ui']['valid_choice']['estimate']['seconds'] >= 900,
                    'panel-request:approval-margin')


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-012/excluded-first'
    record_installed_journey(recorder, context, PLAN, timeout=2400,
        journey_type=PanelRequestJourney,
        actions={**fixture_actions(include_refusal=False),
                 'cooldown': interval_action(5)})


E2E_CASES = {'excluded-first': execute}
