"""DESK03/04 qualification: shared system switching and logout commands."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop

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


class DesktopSessionJourney(InstalledJourney):
    """Installed envelope for one session-control attempt; review cannot pass it."""

    def __init__(self, context, progress, plan):
        super().__init__(context, progress, plan)
