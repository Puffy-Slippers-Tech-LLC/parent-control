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


# The dedicated credential check retains prompt dismissal and actual login.
# Reuse the semantic GDM adapter and the shared two-observation secret gate.
CREDENTIAL_SCREENS = {
    'initial-list': 'ui:gdm-product-free-list',
    'initial-focused': 'ui:gdm-product-free-focused',
    'initial-prompt': 'ui:gdm-product-free-select-parent',
    'initial-returned': 'ui:gdm-product-free-returned',
    'login-list': 'ui:gdm-product-free-list',
    'login-focused': 'ui:gdm-product-free-focused',
    'recipient-qualified': 'ui:gdm-parent-recipient',
    'recipient-rechecked': 'ui:gdm-parent-recipient-rechecked',
    'authenticated': 'ui:desktop',
}
CREDENTIAL_PLAN = JourneyPlan(
    prefix='gdm-credentials', worker_mode='gdm_credentials',
    screen_tags=CREDENTIAL_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in CREDENTIAL_SCREENS}},
    invocations=tuple(CREDENTIAL_SCREENS),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked')},
)


class GdmCredentialJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, CREDENTIAL_PLAN)
