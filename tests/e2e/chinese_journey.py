"""Compose qualified Chinese package/presentation/authentication comparisons.

Consumers supply finite stages and public checks. The existing recorder,
asset transfer, commands, UI adapters and worker retain all resource ownership.
"""
from functools import partial

from asset_transfer import AssetTransfer
from chinese_current_install import ChineseInstallJourney
from chinese_native_auth import ChineseApprovalMixin
from private_artifacts import require


class ChineseRequestInstallJourney(ChineseApprovalMixin, ChineseInstallJourney):
    def __init__(self, context, progress, plan, *, actions=None, checks=None):
        require(not context.installed_snapshot and context.verified.upgrade_inputs is None,
                'chinese-journey:current-product-free-required')
        self.checks = dict(checks or {})
        require(set(self.checks) <= set(plan.screen_tags)
                and all(callable(check) for check in self.checks.values()), 'chinese-journey:checks')
        self.public_captures = {}
        self.checked_stages = set()
        context.asset_transfer = AssetTransfer(context.verified)
        context.asset_transfer.provision(context.lease, context.guestfs)
        context.product_free = True
        super().__init__(context, progress, plan, actions=actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.checks:
            require(stage not in self.checked_stages, 'chinese-journey:check-replay')
            self.checks[stage](self, observed)
            self.checked_stages.add(stage)


def chinese_journey(*, checks):
    """Bind caller-owned comparison endpoints to the shared recorder constructor."""
    return partial(ChineseRequestInstallJourney, checks=dict(checks))
