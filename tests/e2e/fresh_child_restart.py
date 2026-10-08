"""Case 258: fresh-install Child App notice, reopening, reboot and usable request."""

from installed_journey import JourneyPlan
from journey_blocks import custom_child_selection, fresh_desktop, package_installation, prefixed_stages, restart_reentry
from journey_checks import restart_instructions
from package_install import check_install_result
from package_journey import record_package_journey
from ui_observations import SettingsObservation


INSTALL = package_installation()
CHILD = prefixed_stages('child', fresh_desktop('child'))
NOTICE = {
    'parent-logout': 'system:parent-logout', **CHILD,
    'overlay-launch': 'ui:child-command-launch',
    'overlay-notice': 'ui:restart-overlay-read',
    **restart_reentry('overlay'),
}
PARENT_RETURN = prefixed_stages('return', fresh_desktop('parent'))
CHILD_RETURN = prefixed_stages('child-return', fresh_desktop('child'))
POSTBOOT = {
    'reboot-requested': 'ui:restart-overlay-read',
    'reboot-greeter': 'ui:gdm-list', **PARENT_RETURN,
    'usable-parent-launch': 'ui:parent-command-launch',
    'usable-parent': 'ui:restart-parent-usable',
    **custom_child_selection('postboot-riley', 'child'),
    'postboot-riley-configured': 'ui:time-explanation-setup-thirty-read',
    'return-parent-logout': 'system:parent-logout', **CHILD_RETURN,
    'usable-overlay-launch': 'ui:child-command-launch',
    'usable-overlay': 'ui:restart-overlay-usable',
}
PLAN = JourneyPlan(
    prefix='fresh-child-restart', worker_mode='fresh_child_restart',
    screen_tags={**INSTALL, **NOTICE, **POSTBOOT},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in INSTALL}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in NOTICE},
            **{stage: 'step-3' for stage in POSTBOOT}},
    advance_after={'installed-greeter': 'step-1', 'package-result': 'step-2',
                   'overlay-reentry': 'step-3'},
    stage_actions={'package-submitted': 'install-package'},
    invocations=(*CHILD, *PARENT_RETURN, *CHILD_RETURN),
    challenges={
        'child': ('child', 'child-child-recipient-qualified', 'child-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
        'child-return': ('child', 'child-return-child-recipient-qualified', 'child-return-child-recipient-rechecked'),
    },
    reboot_transition=('reboot-requested', 'reboot-greeter'),
    modal_reboots={'reboot-requested': 'overlay'},
    child_bindings={'postboot-riley-configured': 'child'},
    settings_checks={'postboot-riley-selected': SettingsObservation('fixture-child', False, ('0 minutes',))},
    assertions_after={
        'package-result': 'installation-notice',
        'overlay-notice': 'child-installation-modal',
        'overlay-desktop': 'close-without-reboot',
        'overlay-reentry': 'reopened-installation-modal',
        'reboot-greeter': 'new-boot-usable-greeter',
        'postboot-riley-configured': 'public-child-setup',
        'child-return-desktop': 'fresh-child-desktop',
        'usable-overlay': 'usable-child-request-without-modal',
    })

INSTRUCTIONS = restart_instructions('overlay', {
    'update-required-message': 'Restart the computer for Oh No! Parent Control to work properly.',
    'update-required-close': 'Close', 'update-required-reboot': 'Reboot now',
})
CHECKS = {'package-result': check_install_result,
          'overlay-notice': INSTRUCTIONS, 'overlay-reentry': INSTRUCTIONS,
          'reboot-requested': INSTRUCTIONS}


def execute(recorder, context):
    record_package_journey(recorder, context, PLAN, checks=CHECKS, timeout=1800)


E2E_CASES = {'child': execute}
