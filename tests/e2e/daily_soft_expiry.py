"""Daily access after expiry and the declared app-policy restoring action."""
from dataclasses import replace

from accessible_ui import NAMED_CHILD_OPERATIONS, countdown_seconds
from countdown import CountdownSample
from daily_soft_profile import PLAN as PROFILE_PLAN, SCREENS as PROFILE_SCREENS, DailySoftProfileJourney
from installed_journey import record_installed_journey
from journey_checks import require_zero_grant
from journey_blocks import (allowance_selection, desktop_entry, desktop_return, fresh_desktop, lock_challenge, lock_recipient,
                            native_activity_entry, native_activity_resume,
                            native_blocked_app, native_usable_app, prefixed_stages,
                            retained_app_activities, retained_app_visit, retained_parent_entry)
from native_fixtures import fixture_actions
from private_artifacts import require
from real_interval import interval_toward


PEER = retained_app_activities((('peer', 'other-child', 'fresh'),))
EXPIRY = {
    **native_activity_entry('allowed', child='child'),
    'expiry-wait-first': 'ui:child-countdown-present',
    'expiry-wait-last': 'ui:child-countdown-present',
    'expired-countdown': 'ui:child-countdown-present',
}
RESULTS = {
    **native_activity_resume('allowed-return', child='child'),
    **native_activity_resume('expired-soft', child='child', binding='policy-soft'),
    # Close normally after proving the old window usable, so the next launch
    # independently establishes new execution rather than activating that window.
    'expired-soft-close': 'ui:overlay-native-soft-close',
    'expired-soft-closed': 'ui:overlay-native-soft-closed',
    **prefixed_stages('new-soft', native_usable_app('command', child='child', role='S')),
    'final-child-countdown': 'ui:child-countdown-present',
    **retained_app_visit('peer-return', account='other-child', source='desktop', source_account='child'),
}
SCREENS = {**PEER, **PROFILE_SCREENS, **EXPIRY, **RESULTS}
PEER_LOGINS = {prefix + '-' + stage for prefix in ('peer', 'peer-return')
               for stage in fresh_desktop('other-child')}
PARENT_LOGIN = set(fresh_desktop('parent'))
PLAN = replace(PROFILE_PLAN,
    worker_mode='daily_soft_expiry', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, screens in (
                ('step-1', {**PEER, **PROFILE_SCREENS}), ('step-2', EXPIRY),
                ('step-3', RESULTS)) for stage in screens},
            'peer-entry-guard': 'start', 'peer-installed-greeter': 'start'},
    advance_after={'positive-child-witness': 'step-2', 'expired-countdown': 'step-3'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in set(PROFILE_PLAN.invocations) | PEER_LOGINS | PARENT_LOGIN),
    challenges={**PROFILE_PLAN.challenges,
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        **{prefix: ('other-child',
        prefix + '-standard-recipient-qualified', prefix + '-standard-recipient-rechecked')
        for prefix in ('peer', 'peer-return')}},
    activity_checks={**PROFILE_PLAN.activity_checks,
        'allowed-return-opened': ('allowed-capture', 'same'),
        'expired-soft-opened': ('soft-capture', 'same'),
        'peer-return-activity-opened': ('peer-activity-capture', 'same')},
    activity_entries={**PROFILE_PLAN.activity_entries,
        'peer-return-entry-guard': 'peer-activity-capture'},
    stage_actions={**PROFILE_PLAN.stage_actions,
        'expiry-wait-first': 'wait-original-expiry', 'expiry-wait-last': 'wait-original-expiry'},
    assertions_after={'peer-return-activity-submitted': 'visible-result'},
)


# Expiry is witnessed on the original child desktop. Only the declared normal
# lock/unlock restores policy; no other desktop visit intervenes in app results.
UNLOCK = {
    **native_activity_resume('expired-soft', child='child', binding='policy-soft'),
    'lock-ready': 'ui:fresh-child-desktop',
    'lock': 'system:child-lock',
    **lock_challenge(account='child'),
    **lock_recipient(account='child'),
    'unlock-desktop': 'ui:fresh-child-desktop',
}
UNLOCK_RESULTS = {
    'restored-soft-closed': 'ui:overlay-native-policy-soft-closed',
    **prefixed_stages('blocked-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('blocked-soft', native_blocked_app('S', child='child')),
    **native_activity_resume('allowed-return', child='child'),
    'final-child-countdown': 'ui:child-countdown-present',
    **retained_app_visit('peer-return', account='other-child', source='desktop', source_account='child'),
}
UNLOCK_SCREENS = {**PEER, **PROFILE_SCREENS, **EXPIRY, **UNLOCK, **UNLOCK_RESULTS}
# Use the saved Allowed A executable, rather than the trusted activity helper,
# for this branch's original work. Its public capture/resume binding is shared.
UNLOCK_SCREENS['allowed-command'] = 'ui:overlay-native-command-launch'
UNLOCK_PLAN = replace(PLAN,
    worker_mode='daily_soft_unlock', screen_tags=UNLOCK_SCREENS,
    phases={**{stage: phase for stage, phase in PLAN.phases.items()
               if stage in UNLOCK_SCREENS or stage in ('ready', 'setup-detached')},
        **{stage: 'step-2' for stage in UNLOCK},
        **{stage: 'step-3' for stage in UNLOCK_RESULTS}},
    advance_after={'positive-child-witness': 'step-2', 'unlock-desktop': 'step-3'},
    activity_checks={**PLAN.activity_checks,
        'restored-soft-closed': ('soft-capture', 'closed')},
    activity_entries={**PLAN.activity_entries, 'lock-ready': 'allowed-capture'},
)


# Logout ends the original windows. Observe the same expiry before leaving,
# then require fresh entry and new launch results without a retained-work claim.
FRESH_LOGIN = {
    **native_activity_resume('expired-soft', child='child', binding='policy-soft'),
    **desktop_return('expired-child', account='child', action='logout'),
    **prefixed_stages('fresh-child', desktop_entry('child', source='gdm', entry='fresh')),
}
FRESH_LOGIN_RESULTS = {
    **prefixed_stages('blocked-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('blocked-soft', native_blocked_app('S', child='child')),
    **prefixed_stages('new-allowed', native_usable_app('command', child='child', role='A')),
    'final-child-countdown': 'ui:child-countdown-present',
    **retained_app_visit('peer-return', account='other-child', source='desktop', source_account='child'),
}
FRESH_LOGIN_SCREENS = {**PEER, **PROFILE_SCREENS, **EXPIRY, **FRESH_LOGIN, **FRESH_LOGIN_RESULTS}
FRESH_LOGIN_PLAN = replace(PLAN,
    worker_mode='daily_soft_fresh_login', screen_tags=FRESH_LOGIN_SCREENS,
    phases={**{stage: phase for stage, phase in PLAN.phases.items()
               if stage in FRESH_LOGIN_SCREENS or stage in ('ready', 'setup-detached')},
        **{stage: 'step-2' for stage in FRESH_LOGIN},
        **{stage: 'step-3' for stage in FRESH_LOGIN_RESULTS}},
    advance_after={'positive-child-witness': 'step-2', 'fresh-child-desktop': 'step-3'},
    invocations=tuple(stage for stage in FRESH_LOGIN_SCREENS
        if stage in PLAN.invocations or stage in {
            'fresh-child-' + leaf for leaf in fresh_desktop('child')}),
    challenges={**PLAN.challenges,
        'fresh-child': ('child', 'fresh-child-child-recipient-qualified',
                        'fresh-child-child-recipient-rechecked')},
    activity_checks={stage: binding for stage, binding in PLAN.activity_checks.items()
                     if stage in FRESH_LOGIN_SCREENS},
)


# Raising the allowance preserves the expired grant. The retained child's
# authenticated return reconciles that grant and closes matching blocked apps.
# Finish every child result before the final other-child continuity visit.
ALLOWANCE_ENTRIES = {
    'edit-parent': prefixed_stages('edit-parent', desktop_entry(
        'parent', source='desktop', entry='retained', source_account='child')),
    'restored-child': prefixed_stages('restored-child', desktop_entry(
        'child', source='desktop', entry='retained', source_account='parent')),
}
ALLOWANCE_EDIT = {
    **native_activity_resume('expired-soft', child='child', binding='policy-soft'),
    **ALLOWANCE_ENTRIES['edit-parent'],
    **prefixed_stages('edit', retained_parent_entry(source='same-user', desktop_observation=False)),
    **allowance_selection('raised', (15,)),
    **ALLOWANCE_ENTRIES['restored-child'],
}
ALLOWANCE_RESULTS = {
    'restored-soft-closed': 'ui:overlay-native-policy-soft-closed',
    **prefixed_stages('blocked-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('blocked-soft', native_blocked_app('S', child='child')),
    **native_activity_resume('allowed-return', child='child'),
    'final-child-countdown': 'ui:child-countdown-present',
    **retained_app_visit('peer-return', account='other-child', source='desktop', source_account='child'),
}
ALLOWANCE_SCREENS = {**PEER, **PROFILE_SCREENS, **EXPIRY, **ALLOWANCE_EDIT, **ALLOWANCE_RESULTS}
ALLOWANCE_PLAN = replace(PLAN,
    worker_mode='daily_soft_allowance_edit', screen_tags=ALLOWANCE_SCREENS,
    phases={**{stage: phase for stage, phase in PLAN.phases.items()
               if stage in ALLOWANCE_SCREENS or stage in ('ready', 'setup-detached')},
        **{stage: 'step-2' for stage in ALLOWANCE_EDIT},
        **{stage: 'step-3' for stage in ALLOWANCE_RESULTS}},
    advance_after={'positive-child-witness': 'step-2', 'restored-child-desktop': 'step-3'},
    invocations=tuple(stage for stage in ALLOWANCE_SCREENS
        if stage in PLAN.invocations or stage in {
            prefix + '-' + leaf for prefix, account in
            (('edit-parent', 'parent'), ('restored-child', 'child'))
            for leaf in fresh_desktop(account)}),
    challenges={**PLAN.challenges,
        'edit-parent': ('parent', 'edit-parent-recipient-qualified', 'edit-parent-recipient-rechecked'),
        'restored-child': ('child', 'restored-child-child-recipient-qualified',
                           'restored-child-child-recipient-rechecked')},
    child_bindings={stage: 'child' for stage, tag in ALLOWANCE_SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    activity_checks={**PLAN.activity_checks, 'restored-soft-closed': ('soft-capture', 'closed')},
    activity_entries={**PLAN.activity_entries, 'restored-child-source-desktop': 'soft-capture'},
)


# Both toggle saves clear the expired grant without closing existing Soft work.
# Prove that work first, then close it normally for an independent new launch.
TOGGLE = {
    **native_activity_resume('expired-soft', child='child', binding='policy-soft'),
    **ALLOWANCE_ENTRIES['edit-parent'],
    **prefixed_stages('edit', retained_parent_entry(source='same-user', desktop_observation=False)),
    'limit-off': 'ui:parent-toggle-disabled',
    'saved-off': 'ui:parent-save-disabled',
    'limit-on': 'ui:parent-toggle-enabled',
    'saved-on': 'ui:parent-save-enabled',
    'cleared-balance': 'ui:time-explanation-refresh-read',
    **ALLOWANCE_ENTRIES['restored-child'],
}
TOGGLE_RESULTS = {
    **native_activity_resume('restored-soft', child='child', binding='policy-soft'),
    'restored-soft-close': 'ui:overlay-native-soft-close',
    'restored-soft-closed': 'ui:overlay-native-soft-closed',
    **prefixed_stages('blocked-hard', native_blocked_app('H', child='child')),
    **prefixed_stages('blocked-soft', native_blocked_app('S', child='child')),
    **native_activity_resume('allowed-return', child='child'),
    'final-child-countdown': 'ui:child-countdown-present',
    **retained_app_visit('peer-return', account='other-child', source='desktop', source_account='child'),
}
TOGGLE_SCREENS = {**PEER, **PROFILE_SCREENS, **EXPIRY, **TOGGLE, **TOGGLE_RESULTS}
TOGGLE_PLAN = replace(ALLOWANCE_PLAN,
    worker_mode='daily_soft_toggle', screen_tags=TOGGLE_SCREENS,
    phases={**{stage: phase for stage, phase in PLAN.phases.items()
               if stage in TOGGLE_SCREENS or stage in ('ready', 'setup-detached')},
        **{stage: 'step-2' for stage in TOGGLE},
        **{stage: 'step-3' for stage in TOGGLE_RESULTS}},
    child_bindings={stage: 'child' for stage, tag in TOGGLE_SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    activity_checks={**PLAN.activity_checks, 'restored-soft-opened': ('soft-capture', 'same')},
)


# An unchanged Save leaves existing work alone and retains the expired grant.
# The child's later unlock reconciles that grant and closes blocked apps.
APP_SAVE = {
    **native_activity_resume('expired-soft', child='child', binding='policy-soft'),
    **ALLOWANCE_ENTRIES['edit-parent'],
    **prefixed_stages('edit', retained_parent_entry(source='same-user', desktop_observation=False)),
    'app-save-apps': 'ui:parent-apps-page',
    'app-save-open': 'ui:match-soft-open',
    'app-save-read': 'ui:match-soft-read',
    'app-save-save': 'ui:match-soft-save',
    'app-save-row': 'ui:match-soft-row',
    **ALLOWANCE_ENTRIES['restored-child'],
}
APP_SAVE_SCREENS = {**PEER, **PROFILE_SCREENS, **EXPIRY, **APP_SAVE, **ALLOWANCE_RESULTS}
APP_SAVE_PLAN = replace(ALLOWANCE_PLAN,
    worker_mode='daily_soft_app_save', screen_tags=APP_SAVE_SCREENS,
    phases={**{stage: phase for stage, phase in PLAN.phases.items()
               if stage in APP_SAVE_SCREENS or stage in ('ready', 'setup-detached')},
        **{stage: 'step-2' for stage in APP_SAVE},
        **{stage: 'step-3' for stage in ALLOWANCE_RESULTS}},
    child_bindings={stage: 'child' for stage, tag in APP_SAVE_SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    match_checks={**PLAN.match_checks,
        **{stage: 'apps-saved-s-match' for stage in
           ('app-save-open', 'app-save-read', 'app-save-row')}},
)


# Revoke clears the already-expired grant and closes blocked apps itself.
# The zero-duration record must not issue new permission on retained return.
REVOKE = {
    **native_activity_resume('expired-soft', child='child', binding='policy-soft'),
    **ALLOWANCE_ENTRIES['edit-parent'],
    **prefixed_stages('edit', retained_parent_entry(source='same-user', desktop_observation=False)),
    'revoke-before': 'ui:time-explanation-refresh-read',
    'revoke-open': 'ui:revoke-open',
    'revoke-confirm': 'ui:revoke-confirm',
    'revoke-cleared': 'ui:time-explanation-refresh-read',
    **ALLOWANCE_ENTRIES['restored-child'],
}
REVOKE_SCREENS = {**PEER, **PROFILE_SCREENS, **EXPIRY, **REVOKE, **ALLOWANCE_RESULTS}
REVOKE_PLAN = replace(ALLOWANCE_PLAN,
    worker_mode='daily_soft_revoke', screen_tags=REVOKE_SCREENS,
    phases={**{stage: phase for stage, phase in PLAN.phases.items()
               if stage in REVOKE_SCREENS or stage in ('ready', 'setup-detached')},
        **{stage: 'step-2' for stage in REVOKE},
        **{stage: 'step-3' for stage in ALLOWANCE_RESULTS}},
    child_bindings={stage: 'child' for stage, tag in REVOKE_SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
)


class DailySoftExpiryJourney(DailySoftProfileJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False, profile='activity'),
            'real-interval': self.wait_away, 'wait-original-expiry': self.wait_expiry})
        self.expiry_controller_ns = None
        self.expiry_guest_ns = None
        self.peer_session = None
        self.revoke_balance = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'peer-desktop-identity':
            self.peer_session = observed['system']['session_sha256']
        if stage == 'peer-return-entry-guard':
            require(self.peer_session is not None and
                    observed['system']['session_sha256'] == self.peer_session,
                    'daily-soft-expiry:peer-session-replaced')
        if stage == 'return-balance':
            balance = self.return_balance
            upper = balance['one_time']['seconds'] + balance['one_time']['precision_seconds'] + 2
            self.expiry_guest_ns = balance['observed_monotonic_ns'] + upper * 1_000_000_000
            # The controller bracket ends after the guest read. Starting the
            # same interval there is conservative even if its reply was delayed.
            self.expiry_controller_ns = self.ui.read_bounds[1] + upper * 1_000_000_000
        if stage == 'edit-parent-retained':
            # The intervening public balance refresh navigates to Screen Limits.
            # Preserve the captured window/settings, with that explicit page change.
            require(self.parent_window is not None
                    and observed['ui']['retained_parent'] == {
                        **self.parent_window, 'page': 'screen-limits'},
                    'daily-soft-expiry:retained-parent-before-allowance-edit')
        if stage == 'cleared-balance':
            balance = observed['ui']['time_explanation']
            require_zero_grant(balance)
            require(balance['daily']['seconds'] > 0, 'daily-soft-expiry:toggle-daily-access')
            observed['comparison'] = {'grant_cleared': True, 'daily_access_positive': True}
        if stage in ('revoke-before', 'revoke-cleared'):
            balance = observed['ui']['time_explanation']
            require_zero_grant(balance)
            require(balance['daily']['seconds'] > 0, 'daily-soft-expiry:revoke-daily-access')
            if stage == 'revoke-before':
                self.revoke_balance = balance
            else:
                require(self.revoke_balance is not None, 'daily-soft-expiry:missing-revoke-balance')
                before = self.revoke_balance
                require(balance['observed_monotonic_ns'] > before['observed_monotonic_ns']
                        and abs(balance['daily']['seconds'] - before['daily']['seconds'])
                            <= balance['daily']['precision_seconds'] + before['daily']['precision_seconds'],
                        'daily-soft-expiry:revoke-preserves-daily')
            observed['comparison'] = {'zero_grant': True, 'daily_access_positive': True,
                                      'revoked': stage == 'revoke-cleared'}
        if stage in ('expired-countdown', 'final-child-countdown'):
            sample = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            require(sample.boot_sha256 == self.return_boot
                    and self.expiry_guest_ns is not None
                    and sample.guest_read_bounds[0] > self.expiry_guest_ns
                    and countdown_seconds(sample.countdown.text)[0] > 0,
                    'daily-soft-expiry:original-expiry-with-positive-daily-access')
            observed['comparison'] = {'original_grant_expired': True, 'daily_access_positive': True}

    @staticmethod
    def wait_expiry(journey, guard):
        require(journey.expiry_controller_ns is not None, 'daily-soft-expiry:missing-original-deadline')
        return interval_toward(journey, guard, journey.expiry_controller_ns)


def execute(recorder, context):
    execute_branch(recorder, context, PLAN, 'none')


def execute_unlock(recorder, context):
    execute_branch(recorder, context, UNLOCK_PLAN, 'unlock')


def execute_fresh_login(recorder, context):
    execute_branch(recorder, context, FRESH_LOGIN_PLAN, 'fresh-login')


def execute_allowance_edit(recorder, context):
    execute_branch(recorder, context, ALLOWANCE_PLAN, 'allowance-edit')


def execute_toggle(recorder, context):
    execute_branch(recorder, context, TOGGLE_PLAN, 'toggle')


def execute_app_save(recorder, context):
    execute_branch(recorder, context, APP_SAVE_PLAN, 'app-save')


def execute_revoke(recorder, context):
    execute_branch(recorder, context, REVOKE_PLAN, 'revoke')


def execute_branch(recorder, context, plan, branch):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-038/' + branch
    record_installed_journey(recorder, context, plan, timeout=3000,
                             journey_type=DailySoftExpiryJourney)


E2E_CASES = {'none': execute, 'unlock': execute_unlock, 'fresh-login': execute_fresh_login,
             'allowance-edit': execute_allowance_edit, 'toggle': execute_toggle,
             'app-save': execute_app_save, 'revoke': execute_revoke}
