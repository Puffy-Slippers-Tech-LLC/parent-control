"""GDM01/02/03/04/08/09 qualification for one prepared Parent prompt."""

from installed_journey import InstalledJourney, JourneyPlan


PLAN = JourneyPlan(
    prefix='gdm-recipient', worker_mode='gdm_recipient',
    screen_tags={
        'wrong-list': 'ui:gdm-other-list',
        'wrong-focused': 'ui:gdm-other-focused',
        'wrong-recipient-refused': 'ui:gdm-wrong-recipient-refused',
        'wrong-returned': 'ui:gdm-navigation-returned',
        'intended-list': 'ui:gdm-list',
        'intended-focused': 'ui:gdm-focused',
        'recipient-qualified': 'ui:gdm-parent-recipient',
        'recipient-rechecked': 'ui:gdm-parent-recipient-rechecked',
        'intended-prompt': 'ui:gdm-select-parent',
        'intended-returned': 'ui:gdm-navigation-returned',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup',
        'wrong-list': 'start', 'wrong-focused': 'start',
        'wrong-recipient-refused': 'step-1', 'wrong-returned': 'step-2',
        'intended-list': 'step-3', 'intended-focused': 'step-3',
        'recipient-qualified': 'step-3',
        'recipient-rechecked': 'step-3', 'intended-prompt': 'step-3',
        'intended-returned': 'step-4',
    },
    advance_after={
        'wrong-focused': 'step-1',
        'wrong-recipient-refused': 'step-2',
        'wrong-returned': 'step-3',
        'intended-prompt': 'step-4',
    },
)


class GdmRecipientJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
