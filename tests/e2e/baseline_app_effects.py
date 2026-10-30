"""C04p's finite native grant/use/revocation history; no scenario completion."""
import json
import re
import sys

from accessible_ui import (MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS,
                           NATIVE_EXECUTION_ERRNOS)
from feedback_composition import text_fragment
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, native_usable_app,
                            parent_management, prefixed_stages, retained_parent_entry)
from kiosk_approved_flow import obtain_time
from native_fixtures import fixture_actions
from policy_edits import policy_edit
from private_artifacts import require
from request_composition import GrantAppEffectsJourney
from ui_observations import SettingsObservation


CHOICES = dict(child='fixture-child', approver='fixture-parent',
               duration_seconds=600, allow_soft=True)
EDITS = (
    ('A', 'match-precise', 'allowed', 'allowed'),
    ('H', 'match-hard-precise', 'permanent', 'hard'),
    ('S', 'match-soft-wildcard', 'conditional', 'soft'),
    ('H', 'match-hard-precise', 'allowed', 'restore-hard'),
    ('S', 'match-soft-wildcard', 'allowed', 'restore-soft'),
)
POLICIES = {prefix: policy_edit(MATCH_APPS[role], draft, access, prefix)
            for role, draft, access, prefix in EDITS}
RULES = {'A': MATCH_RULES[0], 'H': MATCH_RULES[3], 'S': MATCH_RULES[4]}
CHILD_ENTRY = prefixed_stages('child-entry', desktop_entry('child', source='gdm', entry='fresh'))
PARENT_RETURN = prefixed_stages('parent-return', desktop_entry('parent', source='gdm', entry='retained'))
RESTORE_RETURN = prefixed_stages('restore-return', desktop_entry('parent', source='gdm', entry='retained'))

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'saved-settings': 'ui:parent-selected',
    'apps-page': 'ui:parent-apps-page',
    **POLICIES['allowed'], **POLICIES['hard'], **POLICIES['soft'],
    **text_fragment('catalogue-clear', 'setup-clear'),
    'saved-policy': 'ui:revoke-saved-balances',
    'switch-ready': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **obtain_time(initial='default', **CHOICES, exit='automatic'),
    **CHILD_ENTRY,
    'child-countdown': 'ui:child-countdown-present',
    **prefixed_stages('allowed-use', native_usable_app('command', child='child', role='A')),
    **prefixed_stages('soft-use', native_usable_app('command', child='child', role='S')),
    'soft-close': 'ui:overlay-native-soft-close',
    'soft-closed': 'ui:overlay-native-soft-closed',
    'allowed-close': 'ui:overlay-native-allowed-close',
    'allowed-closed': 'ui:overlay-native-allowed-closed',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'remaining-countdown': 'ui:child-countdown-present',
    'child-switch-ready': 'ui:fresh-child-desktop',
    'child-switch': 'system:child-switch-user', 'child-greeter': 'ui:gdm-returned',
    **PARENT_RETURN,
    **prefixed_stages('supplied', retained_parent_entry(source='same-user')),
    'granted-policy': 'ui:revoke-saved-balances',
    'revoke-open': 'ui:revoke-open', 'revoke-warning': 'ui:revoke-warning',
    'revoke-confirm': 'ui:revoke-confirm',
    'revoked-policy': 'ui:revoke-cleared-balances',
    'parent-switch-ready': 'ui:desktop', 'parent-switch': 'system:parent-switch-user',
    'revoked-greeter': 'ui:gdm-returned',
    'enter-locked': 'system:child-enter-locked',
    'curtain': 'ui:child-lock-curtain', 'reveal-ready': 'ui:child-lock-reveal-ready',
    'time-denied': 'ui:child-lock-time-denied',
    'soft-denied': 'ui:overlay-native-soft-locked-command-blocked',
    'return-greeter': 'system:child-return-greeter', 'denied-returned': 'ui:gdm-returned',
    **RESTORE_RETURN,
    **prefixed_stages('restored', retained_parent_entry(source='same-user')),
    'restore-apps': 'ui:parent-apps-page',
    **POLICIES['restore-hard'], **POLICIES['restore-soft'],
    **text_fragment('catalogue-clear', 'restore-clear'),
    'restore-screen': 'ui:parent-screen-page',
    'restore-disabled': 'ui:parent-toggle-disabled',
    'restore-saved': 'ui:parent-save-disabled',
    'restore-settings': 'ui:parent-toggle-disabled-settings',
    'restore-balance': 'ui:time-explanation-reach-read',
}
_login = set(CHILD_ENTRY) | set(PARENT_RETURN) | set(RESTORE_RETURN)
_matches, _accesses = {}, {}
for role, _draft, access, prefix in EDITS:
    for suffix in ('open', 'old', 'match', 'final-match'):
        _matches[prefix + '-' + suffix] = (MATCH_APPS[role], RULES[role])
    _accesses[prefix + '-access'] = (MATCH_APPS[role], access)
PLAN = JourneyPlan(
    prefix='baseline-app-effects', worker_mode='baseline_app_effects', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('fixture-child', True, ('0 minutes',)),
        'restore-settings': SettingsObservation('fixture-child', False, ('0 minutes',))},
    balance_checks={'allowance-configured': 0, 'restore-balance': 0},
    match_checks=_matches, access_checks=_accesses,
    countdown_checks={stage: ('new-estimate', 600, 60, 180)
                      for stage in ('child-countdown', 'remaining-countdown')},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if stage in _login and tag.startswith('ui:')),
    challenges={
        'child-entry': ('child', 'child-entry-child-recipient-qualified',
                        'child-entry-child-recipient-rechecked'),
        'parent-return': ('parent', 'parent-return-recipient-qualified',
                          'parent-return-recipient-rechecked'),
        'restore-return': ('parent', 'restore-return-recipient-qualified',
                           'restore-return-recipient-rechecked')},
    assertions_after={
        'saved-policy': 'zero-time-and-saved-native-policy',
        'remaining-countdown': 'positive-grant-allowed-soft-use-and-hard-denial',
        'granted-policy': 'independent-positive-grant-and-unchanged-rules',
        'revoked-policy': 'confirmed-zero-grant-and-unchanged-rules',
        'soft-denied': 'time-restriction-and-attributed-soft-execution-denial',
        'restore-balance': 'public-policy-and-time-restoration'},
)


class BaselineAppEffectsJourney(GrantAppEffectsJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
            actions=fixture_actions() if actions is None else actions,
            settings={'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
            app_rules={MATCH_APPS[role]: (access, RULES[role])
                       for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
            approval_stage='new-estimate', policy_reads={
                'saved-policy': (None, 'zero'),
                'granted-policy': ('saved-policy', 'positive'),
                'revoked-policy': ('saved-policy', 'zero')})

    def collect_failure(self):
        """Keep private logs and a bounded native launch diagnostic."""
        if self.transport is None or getattr(self, 'effects_failure_logs_collected', False):
            return
        self.effects_failure_logs_collected = True
        try:
            # The unprivileged launch observer can see no user-journal entries
            # even after systemd reports EXEC failure. Read the fixed fixture
            # namespace through the existing root transport before restoration.
            # Keep structured unit/executable/errno fields for attribution;
            # these diagnostics never substitute for the denial assertion.
            self.context.lease.guard()
            diagnostic = {'event': 'baseline-native-exec-journal',
                          'status': 'unavailable', 'entries': 0, 'exec_errors': []}
            try:
                raw = self.transport.call([
                    'journalctl', '--boot', '--no-pager', '--lines=64', '--output=json',
                    r'--grep=onpc-test-native-[0-9a-f]{32}\.service',
                ], timeout=20)
                if type(raw) is not bytes:
                    diagnostic['status'] = 'invalid'
                elif len(raw) > 131072 or len(raw.splitlines()) > 64:
                    diagnostic['status'] = 'oversized'
                else:
                    entries = [json.loads(line) for line in raw.splitlines()]
                    if any(type(entry) is not dict for entry in entries):
                        raise ValueError('invalid journal record')
                    diagnostic.update(status='read', entries=len(entries))
                    for entry in entries:
                        unit = entry.get('USER_UNIT') or entry.get('_SYSTEMD_USER_UNIT')
                        executable = entry.get('EXECUTABLE')
                        if (type(unit) is not str or re.fullmatch(
                                r'onpc-test-native-[0-9a-f]{32}\.service', unit) is None
                                or executable not in (
                                    '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
                                    '/opt/onpc-test-fixtures/Applications/Path With Spaces.AppImage',
                                    '/opt/onpc-test-fixtures/Applications/Versioned/Lunar Client-3.7.17.AppImage')):
                            continue
                        message = entry.get('MESSAGE')
                        prefix = unit + ': Failed at step EXEC spawning ' + executable + ': '
                        if type(message) is str and message.startswith(prefix):
                            errno = entry.get('ERRNO')
                            diagnostic['exec_errors'].append(
                                NATIVE_EXECUTION_ERRNOS.get(errno, 'other')
                                if type(errno) is str else 'other')
            except ValueError:
                diagnostic.update(status='invalid', exec_errors=[])
            except Exception:
                pass  # Keep the original failure and continue collecting product events.
            # Only fixed labels and bounded counts enter retained runner output;
            # raw journal messages remain in the private command transcript.
            print(json.dumps(diagnostic, sort_keys=True), file=sys.stderr, flush=True)
            # The shared journal collection does not include structured product
            # events. Read them before restoration removes this attempt's state;
            # a visible error report alone cannot identify the failed operation.
            self.context.lease.guard()
            raw = self.transport.call(['date', '-u', '+%F'], timeout=20)
            require(type(raw) is bytes and re.fullmatch(rb'\d{4}-\d{2}-\d{2}\n', raw),
                    'baseline-app-effects:diagnostic-date')
            day = raw.decode('ascii').strip()
            for component in ('broker', 'parent'):
                self.context.lease.guard()
                root = '/var/log/oh-no-parent-control/' + component + '/' + day
                self.transport.call(['tail', '-c', '32768', '--',
                                     root + '.events', root + '.incident.events'],
                                    timeout=20, check=False)
        finally:
            super().collect_failure()
