"""C04j3: genuine grant, Parent disable and retained usable child work."""
from copy import deepcopy

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from feedback_composition import text_fragment
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry,
                            native_activity_resume, parent_management,
                            prefixed_stages, retained_parent_entry)
from kiosk_approved_flow import obtain_time
from native_fixtures import fixture_actions
from policy_edits import policy_edit
from private_artifacts import require
from request_composition import GrantAppEffectsJourney
from ui_observations import SettingsObservation


ENTRIES = {
    'child-entry': prefixed_stages('child-entry', desktop_entry('child', source='gdm', entry='fresh')),
    'parent-return': prefixed_stages('parent-return', desktop_entry('parent', source='gdm', entry='retained')),
    'child-return': prefixed_stages('child-return', desktop_entry('child', source='gdm', entry='retained')),
}
POLICIES = {
    'hard': policy_edit(MATCH_APPS['H'], 'match-hard-precise', 'permanent', 'hard', setup=True),
    'soft': policy_edit(MATCH_APPS['S'], 'match-soft-wildcard', 'conditional', 'soft', setup=True),
}
PREPARATION = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'apps-page': 'ui:parent-apps-page',
    **POLICIES['hard'], **POLICIES['soft'],
    **text_fragment('catalogue-clear', 'setup-clear'),
    'saved-policy': 'ui:revoke-saved-balances',
    'setup-switch': 'system:parent-switch-user', 'setup-greeter': 'ui:gdm-returned',
    **obtain_time(initial='default', child='fixture-child', approver='fixture-parent',
                  duration_seconds=600, allow_soft=True, exit='automatic'),
    **ENTRIES['child-entry'],
    'child-countdown': 'ui:child-countdown-present',
    **native_activity_entry('activity', desktop_observation=False),
}
PUBLIC_DISABLE = {
    'child-switch': 'system:child-switch-user', 'child-greeter': 'ui:gdm-returned',
    **ENTRIES['parent-return'],
    **prefixed_stages('supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'granted-policy': 'ui:revoke-saved-balances',
    'disabled': 'ui:parent-toggle-disabled',
    'disabled-saved': 'ui:parent-save-disabled',
    'disabled-policy': 'ui:revoke-cleared-balances',
    'parent-switch': 'system:parent-switch-user', 'disabled-greeter': 'ui:gdm-returned',
    **ENTRIES['child-return'],
    **native_activity_resume('resumed', child='child'),
}
_login = {stage for fragment in ENTRIES.values() for stage in fragment}


def disable_plan(binding):
    require(binding in ('engineering', 'public'), 'disable:qualification-binding')
    engineering = binding == 'engineering'
    screens = {**PREPARATION, **({} if engineering else PUBLIC_DISABLE)}
    entries = ('child-entry',) if engineering else tuple(ENTRIES)
    return JourneyPlan(
        prefix='active-grant-disable-' + binding,
        worker_mode='active_grant_disable_engineering' if engineering else 'active_grant_disable',
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
                **{stage: 'step-1' for stage in screens if stage != 'installed-greeter'}},
        stage_actions={'desktop': 'native-verify',
                       **({'activity-capture': 'disable-engineering'} if engineering else {})},
        child_bindings={stage: 'child' for stage, tag in screens.items()
                        if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
        invocations=tuple(stage for stage in screens if stage in _login and screens[stage].startswith('ui:')),
        challenges={prefix: (account, prefix + recipient + 'qualified', prefix + recipient + 'rechecked')
                    for prefix, account, recipient in (
                        ('child-entry', 'child', '-child-recipient-'),
                        ('parent-return', 'parent', '-recipient-'),
                        ('child-return', 'child', '-child-recipient-')) if prefix in entries},
        settings_checks={'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',))},
        balance_checks={'allowance-configured': 0},
        countdown_checks={'child-countdown': ('new-estimate', 600, 60, 180)},
        activity_checks={} if engineering else {'resumed-opened': ('activity-capture', 'same')},
        activity_entries={} if engineering else {'child-return-entry-guard': 'activity-capture'},
        assertions_after={} if engineering else {
            'granted-policy': 'genuine-live-grant-with-zero-daily',
            'disabled-policy': 'saved-disabled-cleared-grant-and-preserved-app-policy',
            'resumed-submitted': 'original-child-work-retained-and-usable'},
    )


PLAN = disable_plan('public')
ENGINEERING_PLAN = disable_plan('engineering')


class ActiveGrantDisableJourney(GrantAppEffectsJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        if actions is None:
            actions = fixture_actions(include_refusal=False)
            if plan is ENGINEERING_PLAN:
                from active_grant_disable_engineering import qualify
                actions['disable-engineering'] = qualify
        super().__init__(context, progress, plan, actions=actions,
            settings={'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
            app_rules={MATCH_APPS[role]: (access, MATCH_RULES[index])
                       for role, index, access in (('A', 0, 'allowed'),
                           ('H', 3, 'permanent'), ('S', 4, 'conditional'))},
            approval_stage='new-estimate', policy_reads={'saved-policy': (None, 'zero'),
                **({'granted-policy': ('saved-policy', 'positive')}
                   if plan is not ENGINEERING_PLAN else {})})
        self.disabled_seen = False

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage != 'disabled-policy':
            return
        require(not self.disabled_seen and 'granted-policy' in self.effects_seen,
                'disable:missing-grant-or-replayed-result')
        value = observed['ui']['revoke_cancel']
        before = self.effects_seen['granted-policy']
        expected = deepcopy(before['settings'])
        expected['limit_enabled'] = False
        require(value['settings'] == expected and all(value[key] == before[key]
                for key in ('apps', 'rules')), 'disable:changed-app-policy-or-settings')
        balances = value['balances']
        require(balances['child'] == 'fixture-child' and all(
            balances[key]['seconds'] == 0 for key in ('daily', 'one_time', 'total')),
            'disable:uncleared-native-time')
        observed.setdefault('comparison', {}).update(saved_disabled=True,
            cleared_daily_and_grant=True, unchanged_apps_and_patterns=True)
        self.disabled_seen = True
