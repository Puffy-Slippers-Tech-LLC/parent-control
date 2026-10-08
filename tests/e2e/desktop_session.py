"""DESK03/04 qualification: shared system switching and logout commands."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, lock_challenge, lock_recipient

ENTRY = fresh_desktop('parent')
ENTRY_PHASES = {
    'ready': 'setup', 'setup-detached': 'setup',
    **{stage: 'start' if stage == 'installed-greeter' else 'step-1' for stage in ENTRY},
}


def _plan(prefix, worker_mode, extra, extra_phase):
    screens = {**ENTRY, **extra}
    return JourneyPlan(
        prefix=prefix, worker_mode=worker_mode, screen_tags=screens,
        phases={**ENTRY_PHASES, **{stage: extra_phase for stage in extra}},
        advance_after={'desktop': extra_phase},
    )


LOGOUT_PLAN = _plan(
    'desktop-logout', 'desktop_session_logout',
    {'logout': 'system:parent-logout',
     'gdm-logged-out': 'ui:gdm-returned'},
    'step-2')
SWITCH_PLAN = _plan(
    'desktop-switch', 'desktop_session_switch',
    {'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned'},
    'step-2')


def lock_plan(supplied=False):
    return _plan('lock-supplied' if supplied else 'lock-command',
        'lock_surface_supplied' if supplied else 'lock_surface_command',
        {'unlocked-refused': 'ui:parent-lock-unlocked-refused',
         'lock-ready': 'ui:desktop',
         **({} if supplied else {'lock': 'system:parent-lock'}),
         **lock_challenge(),
         'lock-refusals': 'ui:parent-lock-refusals',
         'independent-challenge': 'ui:parent-lock-challenge'}, 'step-2')


LOCK_PLAN = lock_plan()
SUPPLIED_LOCK_PLAN = lock_plan(supplied=True)
LOCK_RECIPIENT_PLAN = _plan('lock-recipient', 'lock_recipient', {
    'unlocked-refused': 'ui:parent-lock-unlocked-refused',
    'lock-ready': 'ui:desktop',
    'lock': 'system:parent-lock',
    **lock_challenge(),
    'lock-recipient-refusals': 'ui:parent-lock-recipient-refusals',
    'independent-challenge': 'ui:parent-lock-challenge',
    **lock_recipient(),
    'final-challenge': 'ui:parent-lock-challenge',
}, 'step-2')


class DesktopSessionJourney(InstalledJourney):
    """Installed envelope for one session-control attempt; review cannot pass it."""

    def __init__(self, context, progress, plan):
        super().__init__(context, progress, plan)
