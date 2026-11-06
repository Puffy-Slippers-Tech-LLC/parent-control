"""Case 137: renew the child's session after updating, preserving rules and time."""
from dataclasses import replace

from installed_journey import record_installed_journey
from journey_blocks import desktop_entry, desktop_return, fresh_desktop, prefixed_stages
from update_process_case import PLAN as PROCESS_PLAN, SETUP, UPDATE, RESULT, ProcessUpdateJourney


ENTRIES = {'renew-child': ('other-child', 'retained'),
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
SCREENS = {**SETUP, **UPDATE, **RENEWAL, **RESULT}
EXTRA_LOGINS = {prefix + '-' + stage for prefix, (account, _) in ENTRIES.items()
                for stage in fresh_desktop(account)}
PLAN = replace(PROCESS_PLAN, prefix='update-session-case', worker_mode='update_session_case',
    screen_tags=SCREENS,
    phases={**PROCESS_PLAN.phases, **{stage: 'step-2' for stage in RENEWAL}},
    advance_after={'settings-before': 'step-2', 'renewed-parent-desktop': 'step-3'},
    invocations=tuple(stage for stage in SCREENS
                      if stage in PROCESS_PLAN.invocations or stage in EXTRA_LOGINS),
    challenges={**PROCESS_PLAN.challenges,
        **{prefix: (account, prefix + '-' + recipient + 'qualified',
                    prefix + '-' + recipient + 'rechecked')
           for prefix, (account, _) in ENTRIES.items()
           for recipient in ('recipient-' if account == 'parent' else 'standard-recipient-',)}})


class SessionUpdateJourney(ProcessUpdateJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions, activation='session-renewal')


def execute(recorder, context):
    # Only Jordan has enabled limits and a running affected child session.
    # The initial install/reboot precedes issuance of the real twenty-minute grant.
    record_installed_journey(recorder, context, PLAN, timeout=2400,
                             journey_type=SessionUpdateJourney)


E2E_CASES = {'session': execute}
