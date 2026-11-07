"""Cases 136–138: real updates preserve rules, choices and the original grant."""
from copy import deepcopy
from dataclasses import replace
import time

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from asset_transfer import AssetTransfer
from countdown import CountdownObservation, check_countdown_balance
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop,
                            native_blocked_app, native_usable_app, package_installation,
                            parent_management, parent_selection, prefixed_stages,
                            reboot_desktop, station_entry)
from kiosk_approved_flow import obtain_time
from named_app_set import APPS, named_app_set, saved_rows
from native_fixtures import NativeFixtures
from package_command import NOTICE
from package_upgrade import (PackageUpgradeJourney, activated_entry,
                             install_previous_release, upgrade_current)
from private_artifacts import require
import session_control
from system_fixture_preparation import renew_after_reboot
from ui_observations import RequestObservation


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
    'settings-after': 'ui:retained-parent-read',
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


def verify_native_after_reboot(journey, guard):
    guard()
    require(journey.reboot_observed, 'update-process:reboot-required')
    prepared = journey.context.verified.fixture_prepared
    renew_after_reboot(prepared)
    guard()
    return NativeFixtures(journey.transport, journey.context.verified).verify()


class ProcessUpdateJourney(PackageUpgradeJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None, activation='process-restart'):
        require(not context.installed_snapshot, 'update-process:product-free-required')
        context.product_free = True
        context.asset_transfer = AssetTransfer(context.verified)
        actions = {'native-verify': verify_native_after_reboot,
                   'install-previous': install_previous_release,
                   'upgrade-entry': activated_entry, 'upgrade-current': upgrade_current}
        super().__init__(context, progress, plan, actions=actions, activation=activation)
        self.parent_before = self.grant_before = self.approval_started = None
        self.parent_session_before = None
        self.saved_rules = {}
        self.activation = activation

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'package-result':
            require(observed['package']['notice'] == NOTICE, 'update-process:old-install-notice')
        if stage == 'upgrade-result':
            require(observed['package']['notice'] == (NOTICE if self.activation == 'reboot' else None),
                    'update-process:unexpected-restart-notice')
        if stage == 'request-approval-open':
            self.approval_started = time.monotonic_ns()
        if stage in ('settings-before', 'settings-after'):
            value = observed['ui']['retained_parent']
            require(value['page'] == 'screen-limits' and value['settings'] == {
                'child': CHOICES['child'], 'limit_enabled': True, 'allowance': ['0 minutes']},
                'update-process:saved-allowance')
            identity = session_control.observe(self.transport, 'parent-desktop-identity')
            if stage == 'settings-before':
                self.parent_before = deepcopy(value)
                self.parent_session_before = identity['session_sha256']
            else:
                require(value['settings'] == self.parent_before['settings'],
                        'update-process:saved-allowance-changed')
                if self.activation == 'reboot':
                    # Session numbers can repeat after boot. The verified boot
                    # change and freshly opened usable Parent prove renewal.
                    require(self.additional_reboots_observed == {1}
                            and observed['boot_sha256'] != self.activated_entry['boot'],
                            'update-reboot:fresh-parent-required')
                    observed['comparison'] = {'fresh_usable_parent': True, 'saved_allowance': True}
                    return
                require(value == self.parent_before,
                        'update-process:retained-parent-or-activation')
                # Package/account preservation is proved at upgrade-result.
                # After desktop transitions, prove the retained Parent directly,
                # as in the session-activation qualification. GDM's temporary
                # NSS greeter account can legitimately retire during sign-in.
                require(observed['boot_sha256'] == self.activated_entry['boot']
                        and identity['session_sha256'] == self.parent_session_before,
                        'update-process:unrequested-restart')
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


RENEWAL_ENTRIES = {'renew-child': ('other-child', 'retained'),
                   'renewed-child': ('other-child', 'fresh'),
                   'renewed-parent': ('parent', 'retained')}
RENEWAL = {
    **desktop_return('renewal-leave', account='parent'),
    **prefixed_stages('renew-child', desktop_entry('other-child', source='gdm', entry='retained')),
    'renewal-desktop': 'ui:standard-desktop',
    'renewal-logout': 'system:standard-logout',
    'renewal-greeter': 'ui:gdm-returned',
    **prefixed_stages('renewed-child', desktop_entry('other-child', source='gdm', entry='fresh')),
    **desktop_return('renewed-leave', account='other-child'),
    **prefixed_stages('renewed-parent', desktop_entry('parent', source='gdm', entry='retained')),
}
SESSION_SCREENS = {**SETUP, **UPDATE, **RENEWAL, **RESULT}
RENEWAL_LOGINS = {prefix + '-' + stage for prefix, (account, _) in RENEWAL_ENTRIES.items()
                  for stage in fresh_desktop(account)}
SESSION_PLAN = replace(PLAN, prefix='update-session-case', worker_mode='update_session_case',
    screen_tags=SESSION_SCREENS,
    phases={**PLAN.phases, **{stage: 'step-2' for stage in RENEWAL}},
    advance_after={'settings-before': 'step-2', 'renewed-parent-desktop': 'step-3'},
    invocations=tuple(stage for stage in SESSION_SCREENS
                      if stage in PLAN.invocations or stage in RENEWAL_LOGINS),
    challenges={**PLAN.challenges,
        **{prefix: (account, prefix + '-' + recipient + 'qualified',
                    prefix + '-' + recipient + 'rechecked')
           for prefix, (account, _) in RENEWAL_ENTRIES.items()
           for recipient in ('recipient-' if account == 'parent' else 'standard-recipient-',)}})


class SessionUpdateJourney(ProcessUpdateJourney):
    def __init__(self, context, progress, plan=SESSION_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions, activation='session-renewal')


def execute_session(recorder, context):
    # Only Jordan has enabled limits and a running affected child session.
    # The initial install/reboot precedes issuance of the real twenty-minute grant.
    record_installed_journey(recorder, context, SESSION_PLAN, timeout=2400,
                             journey_type=SessionUpdateJourney)


def remembered_overlay(prefix, child, *, prepare=False):
    return {prefix + '-' + action: f'ui:remembered-overlay-{child}-{action}'
            for action in ('launch', *(('approver', 'custom', 'text', 'apps') if prepare else ()),
                           'read', 'cancel', 'returned')}


# Prepare Riley before issuing Jordan's measured grant. Approval changes the
# shared request choices, so restore Jordan's intended values before capture.
REBOOT_SETUP = {}
for stage, tag in SETUP.items():
    REBOOT_SETUP[stage] = tag
    if stage == 'rules-gdm-switched':
        REBOOT_SETUP.update({
            **enter('seed-parent', 'parent', 'retained'),
            **prefixed_stages('riley-setup', parent_selection(screen_limits=True)),
            'riley-time': 'ui:time-explanation-setup-thirty-read',
            'riley-before': 'ui:retained-parent-read',
            **prefixed_stages('jordan-setup', parent_selection(child='existing', screen_limits=True)),
            **desktop_return('seed-leave', account='parent'),
            **prefixed_stages('seed-station', station_entry()),
            'seed-riley-select': 'ui:remembered-kiosk-riley-select-default',
            'seed-riley-parent': 'ui:remembered-kiosk-riley-approver',
            'seed-cancel': 'ui:kiosk-request-cancel', 'seed-returned': 'ui:gdm-station-returned',
            **enter('seed-riley', 'child', 'fresh'),
            **remembered_overlay('seed-riley-form', 'riley', prepare=True),
            **desktop_return('seed-riley-leave', account='child'),
        })
    elif stage == 'before-soft-command':
        REBOOT_SETUP.update({name: operation for name, operation in
            remembered_overlay('seed-jordan-form', 'jordan', prepare=True).items()
            if name != 'seed-jordan-form-approver'})
    elif stage == 'child-leave-gdm-switched':
        REBOOT_SETUP.update({
            **prefixed_stages('capture-station', station_entry()),
            'capture-jordan': 'ui:remembered-kiosk-jordan-read',
            'capture-riley-select': 'ui:remembered-kiosk-riley-select',
            'capture-riley': 'ui:remembered-kiosk-riley-read',
            'capture-cancel': 'ui:kiosk-request-cancel',
            'capture-returned': 'ui:gdm-station-returned',
        })

REBOOT_ACTIVATION = {
    **UPDATE, 'updated-reboot-requested': 'system:parent-command-context',
    **prefixed_stages('updated', reboot_desktop()),
    **prefixed_stages('updated', parent_management(child='existing')),
}
REBOOT_RESULT = {}
for stage, tag in RESULT.items():
    if stage in ('overlay-ready', 'kiosk-ready'):
        tag = ('ui:remembered-overlay-jordan-read' if stage == 'overlay-ready'
               else 'ui:remembered-kiosk-riley-read')
    if stage.startswith('after-child-') and tag.endswith('-entry-retained'):
        tag = tag.removesuffix('retained') + 'fresh'
    REBOOT_RESULT[stage] = tag
    if stage == 'settings-after':
        REBOOT_RESULT.update({
            **prefixed_stages('riley-return', parent_selection(screen_limits=True)),
            'riley-after': 'ui:retained-parent-read',
            **prefixed_stages('jordan-return', parent_selection(child='existing', screen_limits=True)),
        })
    elif stage == 'kiosk-ready':
        REBOOT_RESULT.update({
            'returned-jordan-select': 'ui:remembered-kiosk-jordan-select',
            'returned-jordan': 'ui:remembered-kiosk-jordan-read',
        })
REBOOT_RESULT.update({
    **enter('after-riley', 'child', 'fresh'),
    **remembered_overlay('returned-riley-form', 'riley'),
})
REBOOT_SCREENS = {**REBOOT_SETUP, **REBOOT_ACTIVATION, **REBOOT_RESULT}
REBOOT_LOGINS = set(reboot_desktop()) | set(prefixed_stages('updated', reboot_desktop())) | {
    prefix + '-' + stage for prefix, account in LOGINS.items() for stage in fresh_desktop(account)}
REBOOT_PLAN = replace(PLAN, prefix='update-reboot-case', worker_mode='update_reboot_case',
    screen_tags=REBOOT_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in REBOOT_SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REBOOT_ACTIVATION},
            **{stage: 'step-3' for stage in REBOOT_RESULT}},
    advance_after={'settings-before': 'step-2', 'updated-parent-selected': 'step-3'},
    stage_actions={**PLAN.stage_actions, 'updated-reboot-desktop': 'native-verify'},
    child_bindings={stage: ('child' if stage.startswith(('riley-', 'seed-riley-')) else 'existing')
                    for stage, tag in REBOOT_SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    invocations=tuple(stage for stage in REBOOT_SCREENS if stage in REBOOT_LOGINS),
    challenges={'after-reboot': PLAN.challenges['after-reboot'],
        'after-update': ('parent', 'updated-reboot-recipient-qualified', 'updated-reboot-recipient-rechecked'),
        **{prefix: (account, prefix + '-' + recipient + 'qualified', prefix + '-' + recipient + 'rechecked')
           for prefix, account in LOGINS.items() if prefix + '-entry-guard' in REBOOT_SCREENS
           for recipient in ('recipient-' if account == 'parent' else
                             'child-recipient-' if account == 'child' else 'standard-recipient-',)}},
    additional_reboot_transitions=(('updated-reboot-requested', 'updated-reboot-installed-greeter'),),
    assertions_after={'returned-riley-form-returned': 'visible-result'},
)
FORM_COMPARISONS = {'overlay-ready': 'seed-jordan-form-read',
                    'kiosk-ready': 'capture-riley', 'returned-jordan': 'capture-jordan',
                    'returned-riley-form-read': 'seed-riley-form-read'}


class RebootUpdateJourney(ProcessUpdateJourney):
    def __init__(self, context, progress, plan=REBOOT_PLAN, *, actions=None):
        super().__init__(context, progress, plan, activation='reboot')
        self.forms = {}
        self.riley_settings = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('riley-before', 'riley-after'):
            value = observed['ui']['retained_parent']['settings']
            require(value == {'child': 'fixture-child', 'limit_enabled': True,
                              'allowance': ['30 minutes']}, 'update-reboot:riley-allowance')
            if stage == 'riley-before':
                self.riley_settings = deepcopy(value)
            else:
                require(value == self.riley_settings, 'update-reboot:riley-allowance-changed')
        if stage in FORM_COMPARISONS or stage in FORM_COMPARISONS.values():
            value = RequestObservation.from_request(observed['ui']['request'],
                operation=self.plan.screen_tags[stage][3:])
            require(stage not in self.forms, 'update-reboot:form-replay')
            if stage in FORM_COMPARISONS:
                require(value == self.forms.get(FORM_COMPARISONS[stage]),
                        'update-reboot:remembered-choices-changed')
                observed.setdefault('comparison', {})['complete_remembered_choices'] = True
            self.forms[stage] = value
        if stage == 'settings-before':
            value, earlier = self.grant_before
            require(value['one_time']['seconds'] - (time.monotonic_ns() - earlier[0]) / 1e9 >= 300,
                    'update-reboot:insufficient-update-margin')
        if stage == 'final-balance':
            require(self.final_balance['one_time']['seconds'] >= 300,
                    'update-reboot:insufficient-tour-margin')


def execute_reboot(recorder, context):
    record_installed_journey(recorder, context, REBOOT_PLAN, timeout=3600,
                             journey_type=RebootUpdateJourney)


E2E_CASES = {'process': execute, 'session': execute_session, 'reboot': execute_reboot}
