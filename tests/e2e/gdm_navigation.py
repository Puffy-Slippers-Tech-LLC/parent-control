"""GDM01/02 qualification for ordinary account selection and Escape return."""

from installed_journey import InstalledJourney, JourneyPlan


PLAN = JourneyPlan(
    prefix='gdm-navigation', worker_mode='gdm_navigation',
    screen_tags={
        'initial-list': 'ui:gdm-list',
        'initial-focused': 'ui:gdm-focused',
        'initial-prompt': 'ui:gdm-select-parent',
        'initial-returned': 'ui:gdm-navigation-returned',
        'repeated-list': 'ui:gdm-list',
        'repeated-focused': 'ui:gdm-focused',
        'repeated-prompt': 'ui:gdm-select-parent',
        'repeated-returned': 'ui:gdm-navigation-returned',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        'initial-list': 'start', 'initial-focused': 'start',
        'initial-prompt': 'step-1', 'initial-returned': 'step-2',
        'repeated-list': 'step-2', 'repeated-focused': 'step-2',
        'repeated-prompt': 'step-3', 'repeated-returned': 'step-4',
    },
    advance_after={
        'initial-focused': 'step-1', 'initial-prompt': 'step-2',
        'repeated-focused': 'step-3', 'repeated-prompt': 'step-4',
    },
)


class GdmNavigationJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
