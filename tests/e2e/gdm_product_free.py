"""GDM01/02/08/09 qualification on case 1's product-free baseline."""

from installed_journey import InstalledJourney, JourneyPlan


PLAN = JourneyPlan(
    prefix='gdm-product-free', worker_mode='gdm_product_free',
    screen_tags={
        'initial-list': 'ui:gdm-product-free-list',
        'initial-focused': 'ui:gdm-product-free-focused',
        'initial-prompt': 'ui:gdm-product-free-select-parent',
        'initial-returned': 'ui:gdm-product-free-returned',
        'repeated-list': 'ui:gdm-product-free-list',
        'repeated-focused': 'ui:gdm-product-free-focused',
        'repeated-prompt': 'ui:gdm-product-free-select-parent',
        'repeated-returned': 'ui:gdm-product-free-returned',
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


class GdmProductFreeJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
