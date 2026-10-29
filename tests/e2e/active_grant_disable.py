"""C04j3: genuine grant, Parent disable and retained usable child work."""
from copy import deepcopy
import sys

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

    def collect_failure(self):
        """Distinguish save and refresh failures before restoring this guest."""
        if self.transport is None or self.failure_collected:
            return
        try:
            self.context.lease.guard()
            # Engineering evidence only. Reuse the installed collector and
            # schema validator; never return raw journals, names or exceptions.
            source = '''import hashlib, json, sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
assert hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest() == sys.argv[1]
sys.path[:0] = ['/usr/lib/oh-no-parent-control', '/usr/lib/oh-no-parent-control/broker']
from oh_no_parent_control.diagnostics import collect_logs
from common.oh_no_parent_control_ui.diagnostic_report import read_report
with ZipFile(BytesIO(collect_logs())) as archive:
    logs, info = read_report(archive)
since = (datetime.now(timezone.utc) - timedelta(seconds=180)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
records = sorted((record for rows in logs.values() for record in rows
    if record['component'] in ('parent', 'broker', 'child')
    and record.get('timestamp', '') >= since),
    key=lambda record: (record['timestamp'], record['sequence']))
total = len(records)
# Routine status polls and child restart events can fill the tail after the
# failed verification. Keep the original readbacks and delayed observations,
# not just the later rollback and error-report activity.
records = [record for record in records
    if record['component'] in ('parent', 'broker') and (
        record['level'] in ('WARNING', 'ERROR', 'CRITICAL')
        or record['event'].startswith('extension-manager.') and record['event'] not in (
            'extension-manager.001', 'extension-manager.003', 'extension-manager.command'))]
relevant = len(records)
records = records[-160:]
while len(json.dumps(records).encode()) > 65536:
    records.pop(0)
print(json.dumps({'event': 'active-grant-disable-failure-logs',
    'window_seconds': 180, 'counts': info['counts'],
    'omitted_records': total - len(records),
    'omitted_relevant_records': relevant - len(records), 'records': records}), flush=True)
'''
            self.transport.call(['/usr/bin/python3', '-I', '-c', source, self.boot],
                                timeout=20)
        except Exception:
            # Diagnostic failure must retain the original failure and must not
            # prevent the existing collection or owned cleanup.
            print('active-grant-disable:product-logs-unavailable', file=sys.stderr, flush=True)
        finally:
            super().collect_failure()

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
