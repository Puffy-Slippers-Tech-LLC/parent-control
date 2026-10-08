"""Case 257: genuine installation, Parent Close/re-entry and one modal reboot."""

from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, package_installation, prefixed_stages
from journey_checks import restart_instructions
from package_install import check_install_result
from package_journey import record_package_journey


INSTALL = package_installation()
NOTICE = {
    'parent-launch': 'ui:parent-command-launch',
    'parent-notice': 'ui:restart-parent-read',
    'parent-close': 'ui:restart-parent-close',
    'parent-closed': 'ui:restart-parent-closed',
    'parent-relaunch': 'ui:parent-command-launch',
    'parent-reentry': 'ui:restart-parent-read',
}
RETURN = prefixed_stages('return', fresh_desktop('parent'))
POSTBOOT = {
    'reboot-requested': 'ui:restart-parent-read',
    'reboot-greeter': 'ui:gdm-list', **RETURN,
    'usable-parent-launch': 'ui:parent-command-launch',
    'usable-parent': 'ui:restart-parent-usable',
}
PLAN = JourneyPlan(
    prefix='fresh-parent-restart', worker_mode='fresh_parent_restart',
    screen_tags={**INSTALL, **NOTICE, **POSTBOOT},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in INSTALL}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in NOTICE},
            **{stage: 'step-3' for stage in POSTBOOT}},
    advance_after={'installed-greeter': 'step-1', 'package-result': 'step-2',
                   'parent-reentry': 'step-3'},
    stage_actions={'package-submitted': 'install-package'},
    invocations=tuple(RETURN),
    challenges={'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
    modal_reboots={'reboot-requested': 'parent'},
    assertions_after={
        'package-result': 'installation-notice',
        'parent-notice': 'parent-installation-modal',
        'parent-closed': 'close-without-reboot',
        'parent-reentry': 'reopened-installation-modal',
        'reboot-greeter': 'new-boot-usable-greeter',
        'return-desktop': 'fresh-administrator-desktop',
        'usable-parent': 'usable-parent-without-modal',
    })

# Literal customer expectations are independent of the shared adapter's oracle.
INSTRUCTIONS = restart_instructions('parent', {
    'update-required-message': 'Restart the computer for Oh No! Parent Control to work properly.',
    'update-required-close': 'Close', 'update-required-reboot': 'Reboot now',
})
CHECKS = {'package-result': check_install_result,
          'parent-notice': INSTRUCTIONS, 'parent-reentry': INSTRUCTIONS,
          'reboot-requested': INSTRUCTIONS}


def execute(recorder, context):
    record_package_journey(recorder, context, PLAN, checks=CHECKS, timeout=1800)


E2E_CASES = {'parent': execute}
