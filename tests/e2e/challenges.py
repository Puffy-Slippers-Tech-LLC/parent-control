"""Task 004: two distinct GDM challenges separated by an observed logout."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop

SCREEN_TAGS = {
    # Wrong-entry exercise belongs only to this harness qualification.
    'wrong-list': 'ui:gdm-other-list',
    'wrong-focused': 'ui:gdm-other-focused',
    'wrong-refused': 'ui:gdm-wrong-recipient-refused',
    'wrong-returned': 'ui:gdm-navigation-returned',
    **fresh_desktop('parent'),
    'logout': 'system:parent-logout',
    'gdm-logged-out': 'ui:gdm-returned',
    **{'second-' + stage: operation for stage, operation in fresh_desktop('parent').items()},
}
INVOCATIONS = tuple(stage for stage, tag in SCREEN_TAGS.items()
                    if tag.startswith('ui:') and stage != 'gdm-logged-out')
CHALLENGES = {
    'first-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
    'second-login': ('parent', 'second-recipient-qualified', 'second-recipient-rechecked'),
}
PLAN = JourneyPlan(
    prefix='challenges', worker_mode='challenges', screen_tags=SCREEN_TAGS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREEN_TAGS},
            'wrong-list': 'start',
            **{stage: 'step-2' for stage in SCREEN_TAGS if stage.startswith('second-')}},
    advance_after={'gdm-logged-out': 'step-2'},
    invocations=INVOCATIONS, challenges=CHALLENGES,
    assertions_after={'wrong-refused': 'wrong-entry-refused', 'desktop': 'first-login',
                      'gdm-logged-out': 'logout-complete', 'second-desktop': 'second-login'},
)


class ChallengesJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
