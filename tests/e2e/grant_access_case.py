"""Cases 9–12: real extra time survives child visits and daily edits."""
from copy import deepcopy
import time

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from countdown import CountdownObservation, check_countdown_balance
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (allowance_selection, custom_allowance, desktop_entry,
                            fresh_desktop, native_blocked_app, native_usable_app,
                            native_activity_entry, native_activity_resume,
                            parent_management, prefixed_stages, rejected_gdm_return,
                            retained_parent_entry)
from kiosk_approved_flow import approved_request
from native_fixtures import fixture_actions
from journey_checks import RetainedDesktopJourney
from policy_edits import AppPolicyJourney, policy_edit
from private_artifacts import require
from request_flow import prepared_request
from ui_observations import SettingsObservation


CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
               duration_seconds=1200, allow_soft=True)
EDITS = (('A', 'match-precise', 'allowed', 'allowed'),
         ('H', 'match-hard-precise', 'permanent', 'hard'))


def setup(*, combined=False):
    return {
        **fresh_desktop('parent'), **parent_management(child='existing'),
        'initial-balance': 'ui:time-explanation-reach-read',
        'setup-enable': 'ui:parent-toggle-enabled',
        **(custom_allowance('setup-thirty', 30) if combined else
           allowance_selection('setup-zero', (0,))),
        'setup-settings': 'ui:retained-parent-read', 'apps-page': 'ui:existing-apps',
        **{stage: tag for role, draft, access, prefix in EDITS
           for stage, tag in policy_edit(MATCH_APPS[role], draft, access, prefix).items()},
        'policy-screen': 'ui:discovery-ready', 'setup-disable': 'ui:parent-toggle-disabled',
        'setup-off-settings': 'ui:retained-parent-read',
        'setup-off-balance': 'ui:time-explanation-reach-read',
    }


def visit(name, logins, denials, *, retained=False, denied=False, apps=False,
          resume_original=False):
    """Finite case ordering over the shared entry, app and logout operations."""
    expected = 'time-denied' if denied else 'success'
    logins[name + '-entry'] = ('other-child', name + '-entry-', expected)
    logins[name + '-return'] = ('parent', name + '-return-', 'success')
    screens = {
        **prefixed_stages(name + '-leave', {
            'desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
            'gdm-switched': 'ui:gdm-returned'}),
        **prefixed_stages(name + '-entry', desktop_entry('other-child', source='gdm',
            entry='retained' if retained else 'fresh', expected=expected)),
    }
    if denied:
        returned = prefixed_stages(name + '-denial', rejected_gdm_return())
        denials.update(returned)
        screens.update(returned)
    else:
        screens[name + '-countdown'] = ('ui:child-countdown-absent' if name == 'off'
                                       else 'ui:child-countdown-present')
        if apps:
            if resume_original:
                screens.update({
                    **native_activity_resume(name + '-original', child='other-child'),
                    name + '-original-close': 'ui:native-close',
                    name + '-original-closed': 'ui:native-closed'})
            screens.update(prefixed_stages(name + '-hard', native_blocked_app('H')))
            screens.update(prefixed_stages(name + '-allowed', {
                **native_usable_app('grid'), 'close': 'ui:native-close',
                'closed': 'ui:native-closed'}))
        screens.update(prefixed_stages(name + ('-child-leave' if retained else '-logout'), {
            'desktop': 'ui:standard-desktop',
            ('switch-user' if retained else 'logout'):
                'system:standard-switch-user' if retained else 'system:standard-logout',
            ('gdm-switched' if retained else 'gdm-logged-out'): 'ui:gdm-returned'}))
    screens.update({
        **prefixed_stages(name + '-return', desktop_entry('parent', source='gdm', entry='retained')),
        **prefixed_stages(name + '-supplied', retained_parent_entry(
            source='same-user', desktop_observation=False)),
        name + '-returned-balance': ('ui:time-explanation-refresh-read'
            if name in ('grant', 'positive', 'zero') else 'ui:time-explanation-reach-read'),
    })
    return screens


TRANSITIONS = (
        ('enabled', 'step-2', True, 0), ('grant', 'step-2', True, 0),
        ('positive', 'step-3', True, 30), ('zero', 'step-3', True, 0),
        ('off', 'step-4', False, 0), ('reenabled', 'step-4', True, 0))
COMBINED_TRANSITIONS = (
        ('enabled', 'step-2', True, 30), ('grant', 'step-2', True, 30),
        ('positive', 'step-3', True, 40), ('zero', 'step-3', True, 0),
        ('off', 'step-4', False, 0), ('reenabled', 'step-4', True, 0))


def make_plan(*, retained=False, combined=False):
    screens = setup(combined=combined)
    daily_minutes = 30 if combined else 0
    original_visit = 'enabled' if combined else 'grant'
    saved = {'setup-settings': (True, daily_minutes),
             'setup-off-settings': (False, daily_minutes)}
    logins = {'initial': ('parent', '', 'success')}
    denials = set()
    if retained:
        screens.update({
            **prefixed_stages('prepare-leave', {
                'desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
                'gdm-switched': 'ui:gdm-returned'}),
            **prefixed_stages('prepare-entry', desktop_entry('other-child', source='gdm', entry='fresh')),
            **native_activity_entry('original', route='grid', child='other-child'),
            'original-session': 'system:standard-entry-same',
            **prefixed_stages('prepare-child-leave', {
                'desktop': 'ui:standard-desktop', 'switch-user': 'system:standard-switch-user',
                'gdm-switched': 'ui:gdm-returned'}),
            **prefixed_stages('prepare-return', desktop_entry('parent', source='gdm', entry='retained')),
            'prepared-parent-retained': 'ui:retained-parent-read',
        })
        logins.update({'prepare-entry': ('other-child', 'prepare-entry-', 'success'),
                       'prepare-return': ('parent', 'prepare-return-', 'success')})
        saved['prepared-parent-retained'] = (False, daily_minutes)
    phases = {stage: 'step-1' for stage in screens}
    for name, phase, enabled, minutes in (COMBINED_TRANSITIONS if combined else TRANSITIONS):
        if name == 'grant':
            logins['approval-return'] = ('parent', 'approval-return-', 'success')
            edits = {
                **prefixed_stages('approval-leave', {
                    'desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
                    'gdm-switched': 'ui:gdm-returned'}),
                **prefixed_stages('request', {
                    **prepared_request(prefix='new', entry='new', initial='observed', **CHOICES),
                    **approved_request(exit='automatic', explicit=True, **CHOICES)}),
                **prefixed_stages('approval-return', desktop_entry('parent', source='gdm', entry='retained')),
            }
        else:
            edits = (custom_allowance('positive', minutes) if name == 'positive' else
                     allowance_selection('zero', (0,)) if name == 'zero' else
                     {name + '-toggle': 'ui:parent-toggle-disabled' if name == 'off'
                                        else 'ui:parent-toggle-enabled'})
        group = {**edits, name + '-settings': 'ui:retained-parent-read',
                 name + '-balance': ('ui:time-explanation-refresh-read'
                     if name in ('grant', 'positive', 'zero') else 'ui:time-explanation-reach-read'),
                 **({} if combined and name == 'positive' else
                    visit(name, logins, denials, retained=retained,
                          denied=name == 'reenabled' or (name == 'enabled' and not combined),
                          apps=name in (original_visit, 'off'),
                          resume_original=retained and name == original_visit))}
        if combined and name == 'enabled':
            # Capture current daily time after the visit, before the real addition.
            group['enabled-returned-balance'] = 'ui:time-explanation-refresh-read'
        screens.update(group)
        phases.update({stage: phase for stage in group})
        saved[name + '-settings'] = (enabled, minutes)
        if name + '-supplied-parent-retained' in group:
            saved[name + '-supplied-parent-retained'] = (enabled, minutes)

    login_stages = {prefix + stage for role, prefix, expected in logins.values()
                    for stage in fresh_desktop(role, expected)}
    # All four bindings use the same qualified, fixed kiosk credential route.
    plan = JourneyPlan(
        prefix='grant-access-case',
        worker_mode=('combined_retained_access_case' if combined and retained else
                     'combined_access_case' if combined else
                     'grant_retained_access_case' if retained else 'grant_access_case'), screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup', **phases, 'installed-greeter': 'start'},
        advance_after={'installed-greeter': 'step-1',
                       ('prepared-parent-retained' if retained else 'setup-off-balance'): 'step-2',
                       'grant-returned-balance': 'step-3', 'zero-returned-balance': 'step-4'},
        stage_actions={'desktop': 'native-verify'},
        child_bindings={stage: 'existing' for stage, tag in screens.items()
                        if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
        settings_checks={
            'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
            'policy-screen': SettingsObservation('existing-fixture-child', True, (f'{daily_minutes} minutes',))},
        match_checks={prefix + '-' + suffix: (MATCH_APPS[role], MATCH_RULES[0 if role == 'A' else 3])
                      for role, _draft, _access, prefix in EDITS
                      for suffix in ('open', 'old', 'match', 'final-match')},
        access_checks={prefix + '-access': (MATCH_APPS[role], access)
                       for role, _draft, access, prefix in EDITS},
        invocations=tuple(stage for stage in screens if stage in login_stages | denials),
        challenges={key: (role, prefix + ('recipient-qualified' if role == 'parent'
                                          else 'standard-recipient-qualified'),
                               prefix + ('recipient-rechecked' if role == 'parent'
                                          else 'standard-recipient-rechecked'))
                    for key, (role, prefix, _expected) in logins.items()},
        activity_entries={original_visit + '-entry-entry-guard': 'original-capture'} if retained else {},
        activity_checks={original_visit + '-original-opened': ('original-capture', 'same')} if retained else {},
        kiosk_request=('other-child', 'parent', 1200, True),
    )
    return plan, saved


PLAN, SAVED = make_plan()
RETAINED_PLAN, RETAINED_SAVED = make_plan(retained=True)
COMBINED_PLAN, COMBINED_SAVED = make_plan(combined=True)
COMBINED_RETAINED_PLAN, COMBINED_RETAINED_SAVED = make_plan(retained=True, combined=True)


class GrantAccessJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
            actions=fixture_actions(include_refusal=False) if actions is None else actions)
        self.parent_window = None
        self.saved = {}
        self.balances = {}
        self.approval_started = None
        self.original_grant = None
        self.combined = plan in (COMBINED_PLAN, COMBINED_RETAINED_PLAN)
        self.before_approval = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        saved_states = (COMBINED_RETAINED_SAVED if self.plan is COMBINED_RETAINED_PLAN else
                        COMBINED_SAVED if self.combined else
                        RETAINED_SAVED if self.plan is RETAINED_PLAN else SAVED)
        if stage in saved_states:
            enabled, minutes = saved_states[stage]
            value = observed['ui']['retained_parent']
            require(value['page'] == 'screen-limits' and value['settings'] == {
                'child': 'existing-fixture-child', 'limit_enabled': enabled,
                'allowance': [f'{minutes} minutes']}, 'grant-access:saved-settings')
            if self.parent_window is None:
                self.parent_window = deepcopy(value['window'])
            require(value['window'] == self.parent_window, 'grant-access:parent-window-replaced')
            if '-supplied-' in stage:
                name = stage.split('-supplied-')[0]
                require(value == self.saved[name + '-settings'], 'grant-access:retained-settings-changed')
            self.saved[stage] = deepcopy(value)
        if stage == 'request-approval-open':
            self.approval_started = time.monotonic_ns()
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is not None:
            require(choice['request']['child'] == CHOICES['child']
                    and choice['estimate']['kind'] == 'fixed', 'grant-access:request-estimate')
            if self.combined:
                require(self.before_approval is not None, 'grant-access:missing-daily-baseline')
                daily_before = self.before_approval[0]['daily']
                require(abs(choice['estimate']['seconds'] - daily_before['seconds'] - 1200)
                        < choice['estimate']['precision_seconds'] + daily_before['precision_seconds'] + 2,
                        'grant-access:combined-request-estimate')
            else:
                require(choice['estimate']['seconds'] == 1200, 'grant-access:request-estimate')
        value = observed.get('ui', {}).get('time_explanation')
        if value is not None:
            require(value['child'] == CHOICES['child'], 'grant-access:balance-child')
            daily, grant, total = (value[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(value[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            if self.balances:
                require(value['observed_monotonic_ns'] > next(reversed(self.balances.values()))[
                    'observed_monotonic_ns'], 'grant-access:balance-order')
            if stage.startswith(('grant-', 'positive-', 'zero-')):
                require(self.approval_started is not None, 'grant-access:missing-approval')
                bounds = tuple(self.ui.read_bounds)
                if self.original_grant is None:
                    # Approval starts on the controller; public observations
                    # carry the guest's independent monotonic clock.
                    elapsed = (time.monotonic_ns() - self.approval_started) / 1e9
                    require(0 < elapsed < 600, 'grant-access:approval-budget')
                    if self.combined:
                        require(self.before_approval is not None, 'grant-access:missing-daily-baseline')
                        before, earlier = self.before_approval
                        maximum = (bounds[1] - earlier[0]) / 1e9
                        margin = precision + before['daily']['precision_seconds'] + 2
                        expected = before['daily']['seconds'] + 1200
                        require(0 < maximum < 600 and grant > daily > 900
                                and grant - daily > precision
                                and abs(daily - before['daily']['seconds']) < margin
                                and expected - maximum - margin < grant <= expected + margin,
                                'grant-access:combined-issued-grant')
                        observed['comparison'] = {'daily_before_approval_seconds': before['daily']['seconds'],
                            'additional_seconds': 1200, 'elapsed_upper_seconds': maximum,
                            'rounding_margin_seconds': margin}
                    else:
                        require(1200 - elapsed - precision - 2 < grant <= 1200,
                                'grant-access:issued-grant')
                    self.original_grant = (deepcopy(value), bounds)
                else:
                    before, earlier = self.original_grant
                    # Parent refreshes its displayed status every 30 seconds.
                    # Public reselection loads fresh status inside each read;
                    # bracket that load instead of treating its later snapshot
                    # timestamp as the instant the balance was calculated.
                    minimum = (bounds[0] - earlier[1]) / 1e9
                    maximum = (bounds[1] - earlier[0]) / 1e9
                    tolerance = precision + before['one_time']['precision_seconds'] + 2
                    require(0 < minimum <= maximum < 1200 and grant > (300 if self.combined else 60)
                            and before['one_time']['seconds'] - maximum - tolerance < grant
                            < before['one_time']['seconds'] - minimum + tolerance,
                            'grant-access:original-grant-deadline')
                    observed['comparison'] = {'original_grant_preserved': True,
                        'elapsed_seconds': [minimum, maximum],
                        'rounding_margin_seconds': tolerance}
                daily_limit = (2400 if self.combined else 1800) if stage.startswith('positive-') else (
                    1800 if self.combined and stage.startswith('grant-') else 0)
                require((0 < daily <= daily_limit) if daily_limit else daily == 0,
                        'grant-access:daily-balance')
                if self.combined and stage == 'positive-balance':
                    before, earlier = self.original_grant
                    elapsed = (self.ui.read_bounds[1] - earlier[0]) / 1e9
                    margin = precision + before['daily']['precision_seconds'] + 2
                    require(0 < elapsed < 300
                            and before['daily']['seconds'] + 600 - elapsed - margin < daily
                            <= before['daily']['seconds'] + 600 + margin,
                            'grant-access:increased-daily-balance')
            elif self.combined and stage.startswith('enabled-'):
                require(900 < daily <= 1800 and grant == 0, 'grant-access:daily-before-approval')
                if stage == 'enabled-returned-balance':
                    self.before_approval = (deepcopy(value), tuple(self.ui.read_bounds))
            else:
                require(daily == grant == total == 0, 'grant-access:cleared-time')
            require(abs(total - max(daily, grant)) < precision, 'grant-access:total-balance')
            self.balances[stage] = deepcopy(value)
        if stage in ('grant-countdown', 'positive-countdown', 'zero-countdown') or (
                self.combined and stage == 'enabled-countdown'):
            before = self.balances[stage.removesuffix('-countdown') + '-balance']
            countdown = CountdownObservation.from_value(observed['ui']['countdown'],
                present=True, child=CHOICES['child'])
            observed['comparison'] = check_countdown_balance(countdown,
                seconds=before['total']['seconds'], precision_seconds=before['total']['precision_seconds'],
                observed_monotonic_ns=before['observed_monotonic_ns'], max_elapsed_seconds=300)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800, journey_type=GrantAccessJourney)


class RetainedGrantAccessJourney(RetainedDesktopJourney, GrantAccessJourney):
    def __init__(self, context, progress, plan=RETAINED_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            parent_expected={}, parent_checks={}, window_checks={},
            session_checks={name + '-entry-entry-guard': 'original-session'
                            for name, _phase, _enabled, _minutes in (
                                COMBINED_TRANSITIONS if plan is COMBINED_RETAINED_PLAN else TRANSITIONS)
                            if name + '-entry-entry-guard' in plan.screen_tags})


def execute_retained(recorder, context):
    record_installed_journey(recorder, context, RETAINED_PLAN, timeout=1800,
                             journey_type=RetainedGrantAccessJourney)


def execute_combined(recorder, context):
    record_installed_journey(recorder, context, COMBINED_PLAN, timeout=1800,
                             journey_type=GrantAccessJourney)


def execute_combined_retained(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-005/combined-retained'
    record_installed_journey(recorder, context, COMBINED_RETAINED_PLAN, timeout=1800,
                             journey_type=RetainedGrantAccessJourney)


E2E_CASES = {'grant-only-new': execute, 'grant-only-retained': execute_retained,
             'combined-new': execute_combined, 'combined-retained': execute_combined_retained}
