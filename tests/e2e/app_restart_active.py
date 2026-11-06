"""Active-grant persistence across app reopening, sign-out and reboot."""
from copy import deepcopy
from dataclasses import replace
import time

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS, countdown_seconds
from countdown import CountdownObservation
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop, native_activity_entry,
                            native_activity_resume, native_blocked_app, native_usable_app,
                            parent_reopen, parent_selection, prefixed_stages, station_entry)
from kiosk_approved_flow import obtain_time
from named_app_set import APPS, named_app_set
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney
from private_artifacts import require
from real_interval import interval_action
from ui_observations import RequestObservation


LOGINS = {}


def enter(prefix, role, entry):
    LOGINS[prefix] = role
    return prefixed_stages(prefix, desktop_entry(role, source='gdm', entry=entry))


def overlay(prefix, child, *, prepare=False):
    return {prefix + '-' + action: f'ui:remembered-overlay-{child}-{action}'
            for action in ('launch', *(('approver', 'custom', 'text', 'apps') if prepare else ()),
                           'read', 'cancel', 'returned')}


CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
               duration_seconds=1200, allow_soft=True)
SETUP = {
    **named_app_set(source='gdm', entry='fresh', window='new', child='existing',
                    apps=APPS, prefix='rules'),
    **enter('setup-return', 'parent', 'retained'),
    **prefixed_stages('riley-setup', parent_selection(screen_limits=True)),
    'riley-time': 'ui:time-explanation-setup-thirty-read',
    **prefixed_stages('jordan-setup', parent_selection(child='existing', screen_limits=True)),
    'no-grant': 'ui:revoke-balances',
    'jordan-time': 'ui:time-explanation-setup-zero-read',
    **desktop_return('setup-leave', account='parent'),
    **prefixed_stages('seed-station', station_entry()),
    'seed-riley-select': 'ui:remembered-kiosk-riley-select-default',
    'seed-riley-parent': 'ui:remembered-kiosk-riley-approver',
    'seed-station-cancel': 'ui:kiosk-request-cancel',
    'seed-station-returned': 'ui:gdm-station-returned',
    **enter('seed-riley', 'child', 'fresh'),
    **overlay('seed-riley-form', 'riley', prepare=True),
    **desktop_return('seed-riley-leave', account='child'),
    **prefixed_stages('request', obtain_time(initial='observed', **CHOICES, exit='automatic')),
    **enter('issued-return', 'parent', 'retained'),
    'issued-policy': 'ui:revoke-saved-balances',
    **desktop_return('issued-leave', account='parent'),
    **enter('original-entry', 'other-child', 'fresh'),
    'original-countdown': 'ui:child-countdown-present',
    **native_activity_entry('original', child='other-child', binding='policy'),
    'jordan-launch': 'ui:remembered-overlay-jordan-launch',
    # A first overlay already has Sam selected. Approval changed the shared
    # duration to twenty minutes; restore it before the persistence capture.
    **{f'jordan-{action}': f'ui:remembered-overlay-jordan-{action}'
       for action in ('custom', 'text', 'apps', 'read', 'cancel', 'returned')},
    **desktop_return('original-leave', account='other-child'),
    **prefixed_stages('capture-station', station_entry()),
    'capture-jordan': 'ui:remembered-kiosk-jordan-read',
    'capture-riley-select': 'ui:remembered-kiosk-riley-select',
    'capture-riley': 'ui:remembered-kiosk-riley-read',
    'capture-cancel': 'ui:kiosk-request-cancel',
    'capture-returned': 'ui:gdm-station-returned',
    **enter('before-parent', 'parent', 'retained'),
    'before-policy': 'ui:revoke-saved-balances',
}
BOUNDARY = {
    **prefixed_stages('reopen', parent_reopen()),
    'boundary-wait': 'ui:desktop',
}
RETURN = {
    **prefixed_stages('returned-jordan', parent_selection(child='existing', screen_limits=True)),
    'returned-policy': 'ui:revoke-saved-balances',
    **prefixed_stages('returned-riley', parent_selection(screen_limits=True)),
    'returned-riley-settings': 'ui:retained-parent-read',
    **prefixed_stages('final-jordan', parent_selection(child='existing', screen_limits=True)),
    **desktop_return('returned-parent-leave', account='parent'),
    **prefixed_stages('returned-station', station_entry()),
    'returned-riley': 'ui:remembered-kiosk-riley-read',
    'returned-jordan-select': 'ui:remembered-kiosk-jordan-select',
    'returned-jordan': 'ui:remembered-kiosk-jordan-read',
    'returned-cancel': 'ui:kiosk-request-cancel',
    'returned-greeter': 'ui:gdm-station-returned',
    **enter('returned-riley-entry', 'child', 'retained'),
    **overlay('returned-riley-form', 'riley'),
    **desktop_return('returned-riley-leave', account='child'),
    **enter('final-parent', 'parent', 'retained'),
    'final-policy': 'ui:revoke-saved-balances',
    **desktop_return('final-parent-leave', account='parent'),
    **enter('returned-jordan-entry', 'other-child', 'retained'),
    **overlay('returned-jordan-form', 'jordan'),
    **{stage: 'ui:native-policy-activity' if stage == 'resume-opened' else tag
       for stage, tag in native_activity_resume('resume', child='other-child').items()},
    'original-close': 'ui:native-close', 'original-closed': 'ui:native-closed',
    **prefixed_stages('hard', native_blocked_app('H')),
    **prefixed_stages('soft', native_usable_app('command', role='unmatched-soft')),
    'final-countdown': 'ui:child-countdown-present',
}
SCREENS = {**SETUP, **BOUNDARY, **RETURN}
LOGIN_STAGES = {prefix + '-' + stage for prefix, role in LOGINS.items()
                for stage in fresh_desktop(role)}
PLAN = JourneyPlan(
    prefix='app-restart-active', worker_mode='app_restart_active', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
        **{stage: 'step-2' for stage in BOUNDARY},
        **{stage: 'step-3' if index <= list(RETURN).index('returned-policy') else 'step-4'
           for index, stage in enumerate(RETURN)}},
    advance_after={'before-policy': 'step-2', 'boundary-wait': 'step-3',
                   'returned-policy': 'step-4'},
    stage_actions={'desktop': 'native-verify', 'boundary-wait': 'real-interval'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS
                    and not stage.startswith(('riley-', 'returned-riley-'))},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (role, prefix + '-' +
        ('recipient-qualified' if role == 'parent' else
         'child-recipient-qualified' if role == 'child' else 'standard-recipient-qualified'),
        prefix + '-' + ('recipient-rechecked' if role == 'parent' else
         'child-recipient-rechecked' if role == 'child' else 'standard-recipient-rechecked'))
        for prefix, role in LOGINS.items()},
    kiosk_request=('other-child', 'parent', 1200, True),
    match_checks={f'rules-saved-{role.lower()}-match': (MATCH_APPS[role], rule)
                  for role, rule in (('A', MATCH_RULES[0]), ('H', MATCH_RULES[3]), ('S', MATCH_RULES[4]))},
    access_checks={f'rules-saved-{role.lower()}-access': (MATCH_APPS[role], access)
                   for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
    activity_entries={'returned-jordan-entry-entry-guard': 'original-capture'},
    activity_checks={'resume-opened': ('original-capture', 'same')},
    assertions_after={'final-countdown': 'visible-result'},
)

FORM_COMPARISONS = {
    'returned-riley': 'capture-riley', 'returned-jordan': 'capture-jordan',
    'returned-riley-form-read': 'seed-riley-form-read',
    'returned-jordan-form-read': 'jordan-read',
}


# Both active lifecycle branches share their finite preparation and untouched
# form comparisons. Sign-out invalidates child windows and uses fresh launches.
SIGN_OUT_SETUP = {}
for stage, tag in SETUP.items():
    SIGN_OUT_SETUP[stage] = tag
    if stage == 'riley-time':
        SIGN_OUT_SETUP['riley-policy-before'] = 'ui:revoke-saved-balances'
    elif stage == 'seed-riley-form-returned':
        SIGN_OUT_SETUP.update({
            'riley-animation-set': 'ui:child-countdown-animation-off',
            'riley-animation-read': 'ui:child-countdown-animation-read',
            **prefixed_stages('riley-before-app', native_usable_app('command', child='child', role='A')),
        })
    elif stage == 'seed-riley-leave-gdm-switched':
        SIGN_OUT_SETUP.update({
            **enter('riley-policy-entry', 'parent', 'retained'),
            **prefixed_stages('riley-policy-select', parent_selection(screen_limits=True)),
            'riley-policy-after': 'ui:revoke-saved-balances',
            **prefixed_stages('riley-policy-finish', parent_selection(child='existing', screen_limits=True)),
            **desktop_return('riley-policy-leave', account='parent'),
        })
    elif stage == 'original-countdown':
        SIGN_OUT_SETUP.update({
            'jordan-animation-set': 'ui:child-countdown-animation-on',
            'jordan-animation-read': 'ui:child-countdown-animation-read',
        })
SIGN_OUT_BOUNDARY = {
    **desktop_return('boundary-parent-leave', account='parent'),
    **enter('boundary-jordan-entry', 'other-child', 'retained'),
    **desktop_return('boundary-jordan', account='other-child', action='logout'),
    **enter('boundary-riley-entry', 'child', 'retained'),
    **desktop_return('boundary-riley', account='child', action='logout'),
    **enter('boundary-parent-entry', 'parent', 'retained'),
}
SIGN_OUT_RETURN = {}
for stage, tag in RETURN.items():
    if stage in ('original-close', 'original-closed') or stage.startswith('resume-'):
        continue
    if stage.startswith(('returned-riley-entry-', 'returned-jordan-entry-')) and tag.endswith('-entry-retained'):
        tag = tag.removesuffix('retained') + 'fresh'
    SIGN_OUT_RETURN[stage] = ('ui:revoke-saved-balances'
                              if stage == 'returned-riley-settings' else tag)
    if stage == 'returned-riley-entry-desktop':
        SIGN_OUT_RETURN['returned-riley-animation'] = 'ui:child-countdown-animation-read'
    elif stage == 'returned-riley-form-returned':
        SIGN_OUT_RETURN.update(prefixed_stages('riley-after-app',
            native_usable_app('command', child='child', role='A')))
    elif stage == 'returned-jordan-entry-desktop':
        SIGN_OUT_RETURN['returned-jordan-animation'] = 'ui:child-countdown-animation-read'
    elif stage == 'returned-jordan-form-returned':
        SIGN_OUT_RETURN.update(prefixed_stages('new-allowed', native_usable_app('command')))
SIGN_OUT_SCREENS = {**SIGN_OUT_SETUP, **SIGN_OUT_BOUNDARY, **SIGN_OUT_RETURN}
SIGN_OUT_PLAN = replace(PLAN, prefix='sign-out-in-active', worker_mode='sign_out_in_active',
    screen_tags=SIGN_OUT_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SIGN_OUT_SETUP}, 'installed-greeter': 'start',
        **{stage: 'step-2' for stage in SIGN_OUT_BOUNDARY},
        **{stage: 'step-3' if index <= list(SIGN_OUT_RETURN).index('returned-policy') else 'step-4'
           for index, stage in enumerate(SIGN_OUT_RETURN)}},
    advance_after={'before-policy': 'step-2', 'boundary-parent-entry-desktop': 'step-3',
                   'returned-policy': 'step-4'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: ('child' if stage.startswith(('riley-', 'returned-riley-')) else 'existing')
                    for stage, tag in SIGN_OUT_SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    invocations=tuple(stage for stage in SIGN_OUT_SCREENS if stage in {
        prefix + '-' + leaf for prefix, role in LOGINS.items() for leaf in fresh_desktop(role)}),
    challenges={prefix: (role, prefix + '-' +
        ('recipient-qualified' if role == 'parent' else
         'child-recipient-qualified' if role == 'child' else 'standard-recipient-qualified'),
        prefix + '-' + ('recipient-rechecked' if role == 'parent' else
         'child-recipient-rechecked' if role == 'child' else 'standard-recipient-rechecked'))
        for prefix, role in LOGINS.items()},
    activity_entries={}, activity_checks={},
)

REBOOT_BOUNDARY = {
    # Installed persistence has no installer transfer. Bind the same unlocked
    # Parent desktop without requiring the package-only command context.
    'reboot-requested': 'system:parent-desktop-identity',
    'reboot-greeter': 'ui:gdm-list',
    **enter('boundary-parent-entry', 'parent', 'fresh'),
    'boundary-parent-launch-desktop': 'ui:desktop',
    'boundary-parent-launch-parent-command': 'ui:parent-command-launch',
    'boundary-parent-launch-parent-window': 'ui:parent-window',
}
REBOOT_SCREENS = {**SIGN_OUT_SETUP, **REBOOT_BOUNDARY, **SIGN_OUT_RETURN}
REBOOT_PLAN = replace(SIGN_OUT_PLAN, prefix='reboot-active', worker_mode='reboot_active',
    screen_tags=REBOOT_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SIGN_OUT_SETUP}, 'installed-greeter': 'start',
        **{stage: 'step-2' for stage in REBOOT_BOUNDARY},
        **{stage: 'step-3' if index <= list(SIGN_OUT_RETURN).index('returned-policy') else 'step-4'
           for index, stage in enumerate(SIGN_OUT_RETURN)}},
    advance_after={'before-policy': 'step-2',
                   'boundary-parent-launch-parent-window': 'step-3', 'returned-policy': 'step-4'},
    invocations=tuple(stage for stage in SIGN_OUT_PLAN.invocations if stage in REBOOT_SCREENS),
    challenges={prefix: binding for prefix, binding in SIGN_OUT_PLAN.challenges.items()
                if prefix + '-entry-guard' in REBOOT_SCREENS},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
)


class AppRestartActiveJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.approval_started = None
        self.policies = {}
        self.forms = {}
        self.original_balance = None
        self.final_balance = None
        self.riley_policy = None
        self.animations = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'no-grant':
            require(observed['ui']['revoke_cancel']['balances']['one_time']['seconds'] == 0,
                    'app-restart-active:unexpected-grant')
        if stage == 'request-approval-open':
            require(self.approval_started is None, 'app-restart-active:approval-replay')
            self.approval_started = time.monotonic_ns()
        if stage in ('issued-policy', 'before-policy', 'returned-policy', 'final-policy'):
            self.check_policy(stage, observed)
        fresh_sessions = self.plan.worker_mode in ('sign_out_in_active', 'reboot_active')
        if fresh_sessions and stage in (
                'riley-policy-before', 'riley-policy-after', 'returned-riley-settings'):
            self.check_riley_policy(stage, observed)
        elif stage == 'returned-riley-settings':
            require(observed['ui']['retained_parent']['settings'] == {
                'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['30 minutes']},
                'app-restart-active:riley-settings')
        if fresh_sessions and ('animation' in stage):
            value = observed['ui']['panel_animation']
            bounds = tuple(self.ui.read_bounds)
            jordan = 'jordan' in stage
            child = 'existing-fixture-child' if jordan else 'fixture-child'
            require(value['child'] == child and value['animation'] is jordan,
                    'sign-out-in-active:animation-choice')
            require(stage not in self.animations, 'sign-out-in-active:animation-replay')
            if not stage.endswith('-set'):
                _before, earlier = self.animations[('jordan' if jordan else 'riley') + '-animation-set']
                # Guest uptime restarts at reboot. The controller's read
                # brackets stay ordered across both lifecycle boundaries.
                require(bounds[0] > earlier[1],
                        'sign-out-in-active:independent-animation-read')
            self.animations[stage] = (deepcopy(value), bounds)
        if stage in FORM_COMPARISONS or stage in FORM_COMPARISONS.values():
            value = RequestObservation.from_request(observed['ui']['request'],
                operation=self.plan.screen_tags[stage][3:])
            require(stage not in self.forms, 'app-restart-active:form-replay')
            if stage in FORM_COMPARISONS:
                require(self.forms.get(FORM_COMPARISONS[stage]) == value,
                        'app-restart-active:remembered-form-changed')
                observed.setdefault('comparison', {})['complete_remembered_choices'] = True
            self.forms[stage] = value
        if stage in ('original-countdown', 'final-countdown'):
            countdown = CountdownObservation.from_value(observed['ui']['countdown'], present=True,
                                                        child='existing-fixture-child')
            require(countdown_seconds(countdown.text)[0] >= 300,
                    'app-restart-active:insufficient-active-margin')
            balance, _bounds = self.original_balance if stage == 'original-countdown' else self.final_balance
            from countdown import check_countdown_balance
            observed['comparison'] = check_countdown_balance(countdown,
                seconds=balance['one_time']['seconds'],
                precision_seconds=balance['one_time']['precision_seconds'],
                observed_monotonic_ns=balance['observed_monotonic_ns'], max_elapsed_seconds=300)

    def check_policy(self, stage, observed):
        value = observed['ui']['revoke_cancel']
        require(value['settings'] == {'child': 'existing-fixture-child',
            'limit_enabled': True, 'allowance': ['0 minutes']}, 'app-restart-active:saved-settings')
        # Exact rules are saved once through FLOW19. Compare the full immutable
        # public projection so later reads cannot hide another changed rule.
        saved = {key: deepcopy(value[key]) for key in ('settings', 'apps', 'rules')}
        if self.policies:
            require(saved == self.policies['issued-policy'], 'app-restart-active:saved-rules-changed')
        self.policies[stage] = saved
        balances, bounds = value['balances'], tuple(self.ui.read_bounds)
        grant = balances['one_time']['seconds']
        require(balances['daily']['seconds'] == 0 and grant >= 300
                and abs(balances['total']['seconds'] - grant) <= balances['total']['precision_seconds'],
                'app-restart-active:grant-only-active')
        if self.original_balance is None:
            require(self.approval_started is not None, 'app-restart-active:missing-approval')
            elapsed = (time.monotonic_ns() - self.approval_started) / 1e9
            require(0 < elapsed < 600 and 1200 - elapsed - balances['one_time']['precision_seconds'] - 2
                    < grant <= 1200, 'app-restart-active:issued-grant')
            self.original_balance = (deepcopy(balances), bounds)
        else:
            before, earlier = self.original_balance
            minimum, maximum = (bounds[0] - earlier[1]) / 1e9, (bounds[1] - earlier[0]) / 1e9
            tolerance = balances['one_time']['precision_seconds'] + before['one_time']['precision_seconds'] + 2
            require(0 < minimum <= maximum < 1200
                    and before['one_time']['seconds'] - maximum - tolerance < grant
                    < before['one_time']['seconds'] - minimum + tolerance,
                    'app-restart-active:original-grant-deadline')
            observed.setdefault('comparison', {})['original_positive_deadline'] = True
        if stage == 'final-policy':
            self.final_balance = (deepcopy(balances), bounds)

    def check_riley_policy(self, stage, observed):
        value = observed['ui']['revoke_cancel']
        require(value['settings'] == {'child': 'fixture-child',
            'limit_enabled': True, 'allowance': ['30 minutes']},
            'sign-out-in-active:riley-settings')
        saved = {key: deepcopy(value[key]) for key in ('settings', 'apps', 'rules')}
        balances, bounds = value['balances'], tuple(self.ui.read_bounds)
        require(balances['one_time']['seconds'] == 0 and balances['daily']['seconds'] >= 300
                and abs(balances['total']['seconds'] - balances['daily']['seconds'])
                    <= balances['total']['precision_seconds'], 'sign-out-in-active:riley-time')
        if stage == 'riley-policy-before':
            require(self.riley_policy is None, 'sign-out-in-active:riley-policy-replay')
            self.riley_policy = (saved, deepcopy(balances), bounds)
        else:
            require(self.riley_policy is not None, 'sign-out-in-active:riley-policy-missing')
            policy, before, earlier = self.riley_policy
            elapsed = (bounds[1] - earlier[0]) / 1e9
            tolerance = before['daily']['precision_seconds'] + balances['daily']['precision_seconds'] + 2
            require(saved == policy and 0 < elapsed < 1800
                    and before['daily']['seconds'] - elapsed - tolerance
                        < balances['daily']['seconds'] <= before['daily']['seconds'] + tolerance,
                    'sign-out-in-active:riley-policy-or-time-changed')
            observed.setdefault('comparison', {})['riley_policy_and_elapsed_time_preserved'] = True


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=3000,
        journey_type=AppRestartActiveJourney,
        actions={**fixture_actions(include_refusal=False), 'real-interval': interval_action(2)})


def execute_sign_out(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-022/sign-out-in-active'
    record_installed_journey(recorder, context, SIGN_OUT_PLAN, timeout=3600,
        journey_type=AppRestartActiveJourney, actions=fixture_actions(include_refusal=False))


def execute_reboot(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-022/reboot-active'
    record_installed_journey(recorder, context, REBOOT_PLAN, timeout=3600,
        journey_type=AppRestartActiveJourney, actions=fixture_actions(include_refusal=False))


E2E_CASES = {'app-restart-active': execute, 'sign-out-in-active': execute_sign_out,
             'reboot-active': execute_reboot}
