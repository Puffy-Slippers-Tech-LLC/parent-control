"""Case 2: one product-free installation, reboot, defaults and station exit."""

from asset_transfer import AssetTransfer
from customer_reboot import RETURN
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import station_entry
from package_install import observe_install, submit_install
from private_artifacts import require
from product_free_entry import SCREENS
from ui_observations import AppRowsObservation, SettingsObservation


INSTALL = {stage: tag for stage, tag in SCREENS.items() if stage != 'wrong-entry'}
INSTALL.update({'package-submitted': 'system:parent-command-context',
                'package-result': 'system:parent-command-context'})
MANAGE = {
    'parent-command': 'ui:parent-command-launch',
    'parent-window': 'ui:parent-window',
    'child-picker-opened': 'ui:child-picker-opened',
    'child-choice-highlighted': 'ui:child-choice-highlighted',
    'parent-selected': 'ui:parent-selected',
    'apps-page': 'ui:parent-apps-page',
    'app-rows': 'ui:parent-app-rows',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry('cancel-'),
    'cancel-request-form': 'ui:kiosk-request-form',
    'cancel-action': 'ui:kiosk-request-cancel',
    'cancel-returned': 'ui:gdm-station-returned',
}
REBOOT = dict(RETURN)
PLAN = JourneyPlan(
    prefix='clean-install', worker_mode='clean_install',
    screen_tags={**INSTALL, 'reboot-requested': 'system:parent-command-context',
                 **REBOOT, **MANAGE},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in INSTALL}, 'installed-greeter': 'start',
            'reboot-requested': 'step-2', **{stage: 'step-2' for stage in REBOOT},
            **{stage: 'step-3' for stage in MANAGE}},
    advance_after={'installed-greeter': 'step-1', 'package-result': 'step-2',
                   'reboot-desktop': 'step-3'},
    stage_actions={'package-submitted': 'install-package'},
    assertions_after={'package-result': 'installation-notice',
                      'cancel-returned': 'visible-result'},
    settings_checks={'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',))},
    invocations=tuple(RETURN),
    challenges={'after-reboot': ('parent', 'reboot-recipient-qualified',
                                'reboot-recipient-rechecked')},
    reboot_transition=('reboot-requested', 'reboot-installed-greeter'),
)


class CleanInstallJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        require(plan is PLAN and actions is None and not context.installed_snapshot,
                'clean-install:product-free-required')
        super().__init__(context, progress, plan, actions={'install-package': submit_install})
        context.asset_transfer = AssetTransfer(context.verified)
        context.asset_transfer.provision(context.lease, context.guestfs)
        context.product_free = True
        self.package = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'package-result':
            observed['package'] = observe_install(self)
        if stage == 'reboot-installed-greeter':
            # One read, before the Parent challenge: no unrelated account input.
            observed['accounts'] = self.ui.observe('gdm-installed-accounts')
        if stage == 'app-rows':
            rows = AppRowsObservation.from_rows(observed['ui']['apps']['rows'])
            require(bool(rows.rows) and all(row[1] == 'allowed' for row in rows.rows),
                    'clean-install:initial-allowed')
            observed['comparison'] = {'initial_allowed': True, 'row_count': len(rows.rows)}


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, journey_type=CleanInstallJourney)


E2E_CASES = {'clean': execute}
