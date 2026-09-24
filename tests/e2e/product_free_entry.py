"""005a: product-free graphical entry and a verified administrator command context."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
import session_control


SCREENS = {
    'wrong-entry': 'ui:gdm-product-free-list',
    **fresh_desktop('parent'),
    'command-context': 'system:parent-command-context',
}
SCREENS['installed-greeter'] = 'ui:gdm-product-free-list'
SCREENS['parent-focused'] = 'ui:gdm-product-free-focused'
SCREENS['desktop'] = 'ui:fresh-parent-desktop'
PLAN = JourneyPlan(
    prefix='product-free-entry', worker_mode='product_free_entry', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'wrong-entry': 'start',
            'command-context': 'step-2'},
    advance_after={'desktop': 'step-2'},
    stage_actions={'wrong-entry': 'refuse-command'},
    assertions_after={'wrong-entry': 'wrong-entry-refused', 'desktop': 'fresh-desktop',
                      'command-context': 'administrator-package-context'},
)


def refuse_command(journey, guard):
    guard()
    result = session_control.observe(journey.transport, 'parent-command-refused')
    guard()
    return result


class ProductFreeEntryJourney(InstalledJourney):
    def __init__(self, context, progress):
        require(getattr(context, 'product_free', False) is True
                and getattr(context, 'asset_transfer', None) is not None,
                'product-free-entry:setup-required')
        super().__init__(context, progress, PLAN, actions={'refuse-command': refuse_command})

    def check_settings(self, stage, observed):
        if stage in ('installed-greeter', 'desktop'):
            operation = ('gdm-product-free-provider' if stage == 'installed-greeter'
                         else 'parent-desktop-provider')
            observed['provider'] = self.ui.observe(operation)['provider']
        if stage == 'command-context':
            self.context.verified.recheck()
            require(observed['system']['package_sha256'] ==
                    self.context.verified.inputs['package_sha256'],
                    'product-free-entry:package-changed')
