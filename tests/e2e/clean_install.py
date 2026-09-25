"""Case 2: one product-free installation, reboot, defaults and station exit."""

from installed_journey import JourneyPlan
from journey_blocks import parent_management, product_free_desktop, reboot_desktop, station_entry
from journey_checks import allowed_app_rows, installed_accounts
from package_install import check_install_result
from package_journey import record_package_journey
from ui_observations import SettingsObservation


INSTALL = product_free_desktop()
INSTALL.update({'package-submitted': 'system:parent-command-context',
                'package-result': 'system:parent-command-context'})
MANAGE = {
    **parent_management(),
    'apps-page': 'ui:parent-apps-page',
    'app-rows': 'ui:parent-app-rows',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry('cancel-'),
    'cancel-request-form': 'ui:kiosk-request-form',
    'cancel-action': 'ui:kiosk-request-cancel',
    'cancel-returned': 'ui:gdm-station-returned',
}
REBOOT = reboot_desktop()
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
    invocations=tuple(REBOOT),
    challenges={'after-reboot': ('parent', 'reboot-recipient-qualified',
                                'reboot-recipient-rechecked')},
    reboot_transition=('reboot-requested', 'reboot-installed-greeter'),
)


CHECKS = {'package-result': check_install_result,
          'reboot-installed-greeter': installed_accounts,
          'app-rows': allowed_app_rows}


def execute(recorder, context):
    record_package_journey(recorder, context, PLAN, checks=CHECKS)


E2E_CASES = {'clean': execute}
