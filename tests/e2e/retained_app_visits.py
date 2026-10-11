"""047a: distinct Parent/child activity capture and legitimate retained visits."""
from installed_journey import JourneyPlan
from journey_blocks import (fresh_desktop, parent_management,
                            prefixed_stages, retained_app_activities, retained_app_visit)
from journey_checks import RetainedDesktopJourney
from native_fixtures import fixture_actions


USERS = (('jamie', 'parent', 'retained'), ('riley', 'child', 'fresh'))
PREPARATION = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'setup-switch-ready': 'ui:desktop', 'setup-switch': 'system:parent-switch-user',
    'setup-greeter': 'ui:gdm-returned',
    **retained_app_activities(USERS),
}
VISITS = {
    **retained_app_visit('parent-return', account='parent', source='gdm'),
    'parent-usable-activity': 'ui:parent-native-activity',
    **retained_app_visit('child-return', account='child', source='desktop', source_account='parent'),
    'child-usable-activity': 'ui:overlay-native-activity',
    'wrong-mode-refused': 'system:child-entry-refusals',
    **retained_app_visit('independent-return', account='parent', source='desktop', source_account='child'),
    'independent-usable-activity': 'ui:parent-native-activity',
}
SCREENS = {**PREPARATION, **VISITS}
ACTIVITY_CHECKS = {stage: (capture, 'same') for stage, capture in (
    ('parent-return-activity-opened', 'jamie-activity-capture'),
    ('parent-usable-activity', 'jamie-activity-capture'),
    ('child-return-activity-opened', 'riley-activity-capture'),
    ('child-usable-activity', 'riley-activity-capture'),
    ('independent-return-activity-opened', 'jamie-activity-capture'),
    ('independent-usable-activity', 'jamie-activity-capture'))}
ACTIVITY_ENTRIES = {'parent-return-entry-guard': 'jamie-activity-capture',
                    'child-return-source-desktop': 'riley-activity-capture',
                    'independent-return-source-desktop': 'jamie-activity-capture'}
CHALLENGES = {'initial': ('parent', 'recipient-qualified', 'recipient-rechecked'),
    **{prefix: (account, prefix + '-' + recipient + 'qualified', prefix + '-' + recipient + 'rechecked')
       for prefix, account, recipient in (('jamie', 'parent', 'recipient-'),
            ('riley', 'child', 'child-recipient-'), ('parent-return', 'parent', 'recipient-'),
            ('child-return', 'child', 'child-recipient-'), ('independent-return', 'parent', 'recipient-'))}}
LOGIN_STAGES = {**fresh_desktop('parent'),
    **{stage: tag for prefix, account in (('jamie', 'parent'), ('riley', 'child'),
             ('parent-return', 'parent'), ('child-return', 'child'), ('independent-return', 'parent'))
       for stage, tag in prefixed_stages(prefix, fresh_desktop(account)).items()}}

PLAN = JourneyPlan(
    prefix='retained-app-visits', worker_mode='retained_app_visits', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in PREPARATION if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in VISITS}},
    advance_after={'riley-greeter': 'step-2'},
    stage_actions={'desktop': 'native-verify'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges=CHALLENGES, activity_checks=ACTIVITY_CHECKS, activity_entries=ACTIVITY_ENTRIES,
    balance_checks={'allowance-configured': 900},
    assertions_after={stage: 'same-' + stage for stage in ACTIVITY_CHECKS},
)


class RetainedAppVisitsJourney(RetainedDesktopJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=fixture_actions(include_refusal=False)
                         if actions is None else actions,
                         parent_expected={}, parent_checks={}, window_checks={},
                         session_checks={'parent-return-entry-guard': 'jamie-desktop-identity',
                                         'child-return-entry-guard': 'riley-desktop-identity',
                                         'independent-return-entry-guard': 'jamie-desktop-identity'})
