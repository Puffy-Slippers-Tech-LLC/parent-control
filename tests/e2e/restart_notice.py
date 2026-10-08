"""301: genuine first-install restart modal bindings; no complete-case credit."""

from installed_journey import JourneyPlan
from journey_blocks import custom_child_selection, fresh_desktop, prefixed_stages, package_installation, restart_kiosk_usability, restart_reentry, station_entry
from package_install import PackageInstallJourney, submit_install
from product_free_entry import ProductFreeEntryJourney, refuse_command
from private_artifacts import require
from ui_observations import SettingsObservation


CHILD = prefixed_stages('child', fresh_desktop('child'))
PARENT_RETURN = prefixed_stages('return', fresh_desktop('parent'))
CHILD_RETURN = prefixed_stages('child-return', fresh_desktop('child'))
# Fresh installation deliberately leaves both children disabled. Establish the
# request prerequisite through Parent only after every same-boot notice and the
# independently verified reboot, preserving enabled Request usability checks.
POSTBOOT_POLICY = {
    **custom_child_selection('postboot-riley', 'child'),
    'postboot-riley-configured': 'ui:time-explanation-setup-thirty-read',
    **custom_child_selection('postboot-jamie', 'existing'),
    'postboot-jamie-configured': 'ui:time-explanation-setup-thirty-read',
}
SCREENS = {
    'wrong-entry': 'ui:gdm-product-free-list', **package_installation(),
    'parent-launch': 'ui:parent-command-launch',
    'parent-notice': 'ui:restart-parent-read',
    'parent-wrong-owner': 'ui:restart-parent-wrong-owner',
    **restart_reentry('parent'),
    'parent-second-close': 'ui:restart-parent-close', 'parent-second-closed': 'ui:restart-parent-closed',
    'parent-logout': 'system:parent-logout', **CHILD,
    'overlay-launch': 'ui:child-command-launch', 'overlay-notice': 'ui:restart-overlay-read',
    **restart_reentry('overlay'),
    'overlay-second-close': 'ui:restart-overlay-close', 'overlay-second-closed': 'ui:restart-overlay-closed',
    'overlay-second-exit': 'ui:restart-overlay-exit', 'overlay-second-desktop': 'ui:overlay-desktop',
    'child-logout': 'system:child-logout', **station_entry('initial-'),
    'kiosk-notice': 'ui:restart-kiosk-read', **restart_reentry('kiosk'),
    'reboot-requested': 'ui:restart-kiosk-read', 'reboot-greeter': 'ui:gdm-list',
    **PARENT_RETURN, 'usable-parent-launch': 'ui:parent-command-launch',
    'usable-parent': 'ui:restart-parent-usable', 'missing-notice-refused': 'ui:restart-parent-missing-refused',
    **POSTBOOT_POLICY,
    'return-parent-logout': 'system:parent-logout', **CHILD_RETURN,
    'usable-overlay-launch': 'ui:child-command-launch', 'usable-overlay': 'ui:restart-overlay-usable',
    'return-child-logout': 'system:child-logout', **station_entry(),
    **restart_kiosk_usability(),
}
PLAN = JourneyPlan(prefix='restart-notice', worker_mode='restart_notice', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'wrong-entry': 'start'},
    stage_actions={'wrong-entry': 'refuse-command', 'package-submitted': 'install-package'},
    invocations=(*CHILD, *PARENT_RETURN, *CHILD_RETURN),
    challenges={'child': ('child', 'child-child-recipient-qualified', 'child-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
        'child-return': ('child', 'child-return-child-recipient-qualified', 'child-return-child-recipient-rechecked')},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
    modal_reboots={'reboot-requested': 'kiosk'},
    child_bindings={'postboot-riley-configured': 'child', 'postboot-jamie-configured': 'existing'},
    settings_checks={
        'postboot-riley-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'postboot-jamie-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',))},
    assertions_after={stage: stage + '-verified' for stage in (
        'package-result', 'parent-notice', 'parent-reentry', 'parent-closed',
        'overlay-notice', 'overlay-reentry', 'overlay-closed', 'kiosk-notice', 'kiosk-reentry',
        'kiosk-closed', 'reboot-greeter', 'usable-parent', 'usable-overlay', 'usable-kiosk')})

# Independent finite qualification expectations, not the adapter's oracle.
NOTICE = {'update-required-message': 'Restart the computer for Oh No! Parent Control to work properly.',
          'update-required-close': 'Close', 'update-required-reboot': 'Reboot now'}


class RestartNoticeJourney(PackageInstallJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        ProductFreeEntryJourney.__init__(self, context, progress, plan,
            actions={'refuse-command': refuse_command, 'install-package': submit_install}
            if actions is None else actions)
        self.package = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if self.plan.screen_tags.get(stage) in (
                'ui:restart-parent-read', 'ui:restart-overlay-read', 'ui:restart-kiosk-read'):
            require(observed.get('ui', {}).get('restart', {}).get('texts') == NOTICE,
                    'restart-notice:installed-instructions')
