"""Case 136: a real process update preserves the child's rules and grant."""
from copy import deepcopy
import time

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from asset_transfer import AssetTransfer
from countdown import CountdownObservation, check_countdown_balance
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop,
                            native_blocked_app, native_usable_app, package_installation,
                            parent_management, prefixed_stages, reboot_desktop, station_entry)
from kiosk_approved_flow import obtain_time
from named_app_set import APPS, named_app_set, saved_rows
from native_fixtures import NativeFixtures
from package_command import NOTICE
from package_install import observe_release
from package_upgrade import PackageUpgradeJourney, upgrade_current
from private_artifacts import require
from update_no_action import install_old


CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
               duration_seconds=1200, allow_soft=False)
LOGINS = {}


def enter(prefix, account, entry):
    LOGINS[prefix] = account
    return prefixed_stages(prefix, desktop_entry(account, source='gdm', entry=entry))


def app_results(prefix):
    return prefixed_stages(prefix, {
        **prefixed_stages('allowed', {**native_usable_app('command'),
            'close': 'ui:native-close', 'closed': 'ui:native-closed'}),
        **prefixed_stages('hard', native_blocked_app('H')),
        **prefixed_stages('soft', native_blocked_app('S')),
    })


SETUP = {
    **package_installation(),
    'reboot-requested': 'system:parent-command-context', **reboot_desktop(),
    **parent_management(child='existing'),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    **named_app_set(source='desktop', entry='same-user', window='retained',
                    child='existing', apps=APPS, prefix='rules'),
    **prefixed_stages('request', obtain_time(initial='observed', **CHOICES, exit='automatic')),
    **enter('issued-parent', 'parent', 'retained'),
    'issued-screen': 'ui:discovery-ready',
    'issued-balance': 'ui:time-explanation-refresh-read',
    **desktop_return('issued-leave', account='parent'),
    **enter('before-child', 'other-child', 'fresh'),
    'before-countdown': 'ui:child-countdown-present', **app_results('before'),
    **desktop_return('child-leave', account='other-child'),
    **enter('before-parent', 'parent', 'retained'),
    'settings-before': 'ui:retained-parent-read',
}
UPDATE = {stage: 'system:parent-command-context'
          for stage in ('upgrade-context', 'upgrade-submitted', 'upgrade-result')}
RESULT = {
    'upgrade-reread': 'ui:retained-parent-read',
    'saved-apps': 'ui:existing-apps', **saved_rows(APPS, 'saved'),
    'saved-screen': 'ui:discovery-ready',
    'final-balance': 'ui:time-explanation-refresh-read',
    'about-information': 'ui:parent-about-information',
    'about-returned': 'ui:parent-dialog-about-en-closed',
    **desktop_return('updated-leave', account='parent'),
    **enter('after-child', 'other-child', 'retained'),
    'after-countdown': 'ui:child-countdown-present', **app_results('after'),
    'overlay-launch': 'ui:remembered-overlay-jordan-launch',
    'overlay-ready': 'ui:request-overlay-jordan-ready',
    'overlay-cancel': 'ui:remembered-overlay-jordan-cancel',
    'overlay-returned': 'ui:remembered-overlay-jordan-returned',
    **desktop_return('request-leave', account='other-child'),
    **station_entry('renewed-'),
    'kiosk-ready': 'ui:request-kiosk-jordan-ready',
    'kiosk-cancel': 'ui:kiosk-request-cancel',
    'kiosk-returned': 'ui:gdm-station-returned',
}
SCREENS = {**SETUP, **UPDATE, **RESULT}
LOGIN_STAGES = set(reboot_desktop()) | {
    prefix + '-' + stage for prefix, account in LOGINS.items()
    for stage in fresh_desktop(account)}
PLAN = JourneyPlan(
    prefix='update-process-case', worker_mode='update_process_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
        **{stage: 'step-2' for stage in UPDATE}, **{stage: 'step-3' for stage in RESULT}},
    advance_after={'settings-before': 'step-2', 'upgrade-result': 'step-3'},
    stage_actions={'package-submitted': 'install-previous', 'reboot-desktop': 'native-verify',
                   'upgrade-context': 'upgrade-entry', 'upgrade-submitted': 'upgrade-current'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={'after-reboot': ('parent', 'reboot-recipient-qualified', 'reboot-recipient-rechecked'),
        **{prefix: (account, prefix + '-' + recipient + 'qualified',
                    prefix + '-' + recipient + 'rechecked')
           for prefix, account in LOGINS.items()
           for recipient in ('recipient-' if account == 'parent' else 'standard-recipient-',)}},
    reboot_transition=('reboot-requested', 'reboot-installed-greeter'),
    kiosk_request=('other-child', 'parent', 1200, False),
    assertions_after={'kiosk-returned': 'visible-result'},
)


def activated_entry(journey, guard):
    guard()
    result, current = observe_release(journey.previous_package, 'previous',
                                     journey.release_entry, changed_boot=True)
    require(current['boot'] == journey.boot and journey.reboot_observed,
            'update-process:old-release-not-activated')
    journey.activated_entry = current
    guard()
    return result


def verify_native_after_reboot(journey, guard):
    guard()
    require(journey.reboot_observed, 'update-process:reboot-required')
    prepared = journey.context.verified.fixture_prepared
    prepared['receipt'] = prepared['controller'].renew_after_reboot(prepared['receipt'])
    guard()
    return NativeFixtures(journey.transport, journey.context.verified).verify()


class ProcessUpdateJourney(PackageUpgradeJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        require(not context.installed_snapshot, 'update-process:product-free-required')
        context.product_free = True
        context.asset_transfer = AssetTransfer(context.verified)
        actions = {'native-verify': verify_native_after_reboot, 'install-previous': install_old,
                   'upgrade-entry': activated_entry, 'upgrade-current': upgrade_current}
        super().__init__(context, progress, plan, actions=actions, activation='process-restart')
        self.parent_before = self.grant_before = self.approval_started = None
        self.saved_rules = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'package-result':
            require(observed['package']['notice'] == NOTICE, 'update-process:old-install-notice')
        if stage == 'request-approval-open':
            self.approval_started = time.monotonic_ns()
        if stage in ('settings-before', 'upgrade-reread'):
            value = observed['ui']['retained_parent']
            require(value['page'] == 'screen-limits' and value['settings'] == {
                'child': CHOICES['child'], 'limit_enabled': True, 'allowance': ['0 minutes']},
                'update-process:saved-allowance')
            if stage == 'settings-before':
                self.parent_before = deepcopy(value)
            else:
                require(value == self.parent_before and observed['package']['notice'] is None,
                        'update-process:retained-parent-or-activation')
                observed['comparison'] = {'same_usable_parent': True, 'saved_allowance': True}
        for prefix in ('rules-saved', 'saved'):
            for role, rule, access in (('a', MATCH_RULES[0], 'allowed'),
                                       ('h', MATCH_RULES[3], 'permanent'),
                                       ('s', MATCH_RULES[4], 'conditional')):
                for kind, expected in (
                        ('match', {'app': MATCH_APPS[role.upper()], 'rule': rule}),
                        ('access', {'app': MATCH_APPS[role.upper()], 'choice': access})):
                    if stage == f'{prefix}-{role}-{kind}':
                        value = observed['ui'][kind]
                        require(value == expected, 'update-process:saved-app-rule')
                        key = (role, kind)
                        if prefix == 'rules-saved':
                            self.saved_rules[key] = deepcopy(value)
                        else:
                            require(value == self.saved_rules[key], 'update-process:app-rule-changed')
        if stage in ('issued-balance', 'final-balance'):
            value = observed['ui']['time_explanation']
            require(value['child'] == CHOICES['child'] and value['daily']['seconds'] == 0,
                    'update-process:grant-only-balance')
            grant = value['one_time']['seconds']
            bounds = tuple(self.ui.read_bounds)
            precision = value['one_time']['precision_seconds']
            require(abs(value['total']['seconds'] - grant) < value['total']['precision_seconds'],
                    'update-process:total-balance')
            if stage == 'issued-balance':
                require(self.approval_started is not None, 'update-process:missing-approval')
                elapsed = (time.monotonic_ns() - self.approval_started) / 1e9
                require(0 < elapsed < 600 and 1200 - elapsed - precision - 2 < grant <= 1200,
                        'update-process:issued-grant')
                self.grant_before = (deepcopy(value), bounds)
            else:
                before, earlier = self.grant_before
                minimum = (bounds[0] - earlier[1]) / 1e9
                maximum = (bounds[1] - earlier[0]) / 1e9
                margin = precision + before['one_time']['precision_seconds'] + 2
                require(0 < minimum <= maximum < 1200 and grant > 120
                        and grant < before['one_time']['seconds']
                        and before['one_time']['seconds'] - maximum - margin < grant
                        < before['one_time']['seconds'] - minimum + margin,
                        'update-process:original-grant-deadline')
                observed['comparison'] = {'original_grant_preserved': True,
                    'elapsed_seconds': [minimum, maximum], 'rounding_margin_seconds': margin}
                self.final_balance = deepcopy(value)
        if stage in ('before-countdown', 'after-countdown'):
            before = self.grant_before[0] if stage == 'before-countdown' else self.final_balance
            countdown = CountdownObservation.from_value(observed['ui']['countdown'],
                present=True, child=CHOICES['child'])
            observed['comparison'] = check_countdown_balance(countdown,
                seconds=before['total']['seconds'], precision_seconds=before['total']['precision_seconds'],
                observed_monotonic_ns=before['observed_monotonic_ns'], max_elapsed_seconds=300)


def execute(recorder, context):
    # Installation/reboot is outside the twenty-minute measured grant interval.
    # One finite worker budget includes installation, both visits and cleanup.
    record_installed_journey(recorder, context, PLAN, timeout=2400,
                             journey_type=ProcessUpdateJourney)


E2E_CASES = {'process': execute}
