"""Case 259: genuine install, kiosk Close/reentry, reboot and usable request."""

from installed_journey import JourneyPlan
from journey_blocks import custom_child_selection, fresh_desktop, package_installation, prefixed_stages, restart_kiosk_usability, restart_reentry, station_entry
from journey_checks import restart_instructions
from package_install import check_install_result
from package_journey import record_package_journey
from ui_observations import SettingsObservation


INSTALL = package_installation()
NOTICE = {
    'parent-logout': 'system:parent-logout', **station_entry('initial-'),
    'kiosk-notice': 'ui:restart-kiosk-read', **restart_reentry('kiosk'),
}
PARENT_RETURN = prefixed_stages('return', fresh_desktop('parent'))
POSTBOOT = {
    'reboot-requested': 'ui:restart-kiosk-read',
    'reboot-greeter': 'ui:gdm-list', **PARENT_RETURN,
    'usable-parent-launch': 'ui:parent-command-launch',
    'usable-parent': 'ui:restart-parent-usable',
    **custom_child_selection('postboot-jordan', 'existing'),
    'postboot-jordan-configured': 'ui:time-explanation-setup-thirty-read',
    'return-parent-logout': 'system:parent-logout', **station_entry(),
    **restart_kiosk_usability(),
}
PLAN = JourneyPlan(
    prefix='fresh-kiosk-restart', worker_mode='fresh_kiosk_restart',
    screen_tags={**INSTALL, **NOTICE, **POSTBOOT},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in INSTALL}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in NOTICE},
            **{stage: 'step-3' for stage in POSTBOOT}},
    advance_after={'installed-greeter': 'step-1', 'package-result': 'step-2',
                   'kiosk-reentry': 'step-3'},
    stage_actions={'package-submitted': 'install-package'},
    invocations=tuple(PARENT_RETURN),
    challenges={'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
    modal_reboots={'reboot-requested': 'kiosk'},
    child_bindings={'postboot-jordan-configured': 'existing'},
    settings_checks={'postboot-jordan-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',))},
    assertions_after={
        'package-result': 'installation-notice',
        'kiosk-notice': 'kiosk-installation-modal',
        'kiosk-returned': 'close-without-reboot',
        'kiosk-reentry': 'reopened-installation-modal',
        'reboot-greeter': 'new-boot-usable-greeter',
        'postboot-jordan-configured': 'public-child-setup',
        'usable-kiosk': 'usable-kiosk-request-without-modal',
    })

INSTRUCTIONS = restart_instructions('kiosk', {
    'update-required-message': 'Restart the computer for Oh No! Parent Control to work properly.',
    'update-required-close': 'Close', 'update-required-reboot': 'Reboot now',
})
CHECKS = {'package-result': check_install_result,
          'kiosk-notice': INSTRUCTIONS, 'kiosk-reentry': INSTRUCTIONS,
          'reboot-requested': INSTRUCTIONS}


def execute(recorder, context):
    record_package_journey(recorder, context, PLAN, checks=CHECKS, timeout=1800)


E2E_CASES = {'kiosk': execute}
