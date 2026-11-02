"""Guarded public input for the installed login/unlock recovery history."""

import json

from desktop_session import run_attached
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import desktop_entry, native_activity_entry, native_activity_resume, prefixed_stages
from private_artifacts import require


SCREENS = {
    **prefixed_stages('login', desktop_entry('child', source='gdm', entry='fresh')),
    **native_activity_entry('activity', child='child'),
    'lock-ready': 'ui:fresh-child-desktop',
    'lock': 'system:child-lock',
    **prefixed_stages('unlock', desktop_entry('child', source='locked', entry='lock')),
    **native_activity_resume('resume', child='child'),
    'original-work': 'ui:overlay-native-activity',
}
PLAN = JourneyPlan(
    prefix='extension-login', worker_mode='extension_login', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', **{stage: 'step-1' for stage in SCREENS}},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if tag.startswith('ui:') and (stage.startswith('login-') or stage == 'original-work')),
    challenges={'login': ('child', 'login-child-recipient-qualified',
                           'login-child-recipient-rechecked')},
    stage_actions={'login-desktop': 'login-complete', 'lock': 'unlock-fault'},
    activity_entries={'unlock-entry-guard': 'activity-capture'},
    activity_checks={'resume-opened': ('activity-capture', 'same'),
                     'original-work': ('activity-capture', 'same')},
)


def history_command(transport, name):
    import system_runner
    raw = transport.call(['env', 'ONPC_EXPECTED_RUN=' + transport.config['run'],
        'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
        system_runner.PAYLOAD + '/system_extension_login.py', name], timeout=180)
    require(type(raw) is bytes and 0 < len(raw) < 1024, 'extension-login:history-response')
    value = json.loads(raw)
    expected = {'prepared': True} if name == 'host-ready' else (
        {'restored': True} if name == 'restore' else {'completed': name})
    require(value == expected, 'extension-login:history-response')
    return value


class LoginRecoveryJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None, transport=None):
        if actions is None:
            actions = {name: self.action(name) for name in ('login-complete', 'unlock-fault')}
        super().__init__(context, progress, plan, actions=actions, transport=transport)

    @staticmethod
    def action(name):
        def perform(journey, guard):
            guard()
            result = history_command(journey.transport, name)
            guard()
            return result
        return perform


def run_login_recovery(directory, lease, transport, ledger, *, expected_inputs, progress, context):
    # host-ready persists the helper identity before any permission mutation.
    # Even a refused/uncertain worker is followed by the same guarded restore.
    try:
        history_command(transport, 'host-ready')
        result = run_attached(directory, lease, transport, ledger, PLAN,
            expected_inputs=expected_inputs, progress=progress, context=context,
            journey_type=LoginRecoveryJourney, timeout=1800)
        history_command(transport, 'host-complete')
        return result
    finally:
        history_command(transport, 'restore')
