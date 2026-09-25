"""Product-free package journeys within the shared recorder/ownership envelope.

Recipes supply ordered stages and public-result checks. This envelope owns
asset staging and the single install input; it introduces no VM lifecycle route.
"""

from functools import partial

from asset_transfer import AssetTransfer
from installed_journey import InstalledJourney, record_installed_journey
from package_install import check_install_result, submit_install
from private_artifacts import require


class PackageJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, actions=None, checks=None):
        require(actions is None and not context.installed_snapshot,
                plan.prefix + ':product-free-required')
        self.checks = dict(checks or {})
        require(set(self.checks) <= set(plan.screen_tags)
                and all(callable(check) for check in self.checks.values())
                and self.checks.get('package-result') is check_install_result
                and plan.stage_actions == {'package-submitted': 'install-package'}
                and plan.screen_tags.get('package-submitted') == 'system:parent-command-context'
                and plan.screen_tags.get('package-result') == 'system:parent-command-context'
                and list(plan.screen_tags).index('package-submitted')
                    < list(plan.screen_tags).index('package-result'),
                plan.prefix + ':package-plan')
        super().__init__(context, progress, plan, actions={'install-package': submit_install})
        context.asset_transfer = AssetTransfer(context.verified)
        context.asset_transfer.provision(context.lease, context.guestfs)
        context.product_free = True
        self.package = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.checks:
            self.checks[stage](self, observed)


def record_package_journey(recorder, context, plan, *, checks, timeout=1800):
    record_installed_journey(recorder, context, plan, timeout=timeout,
                            journey_type=partial(PackageJourney, checks=checks))
