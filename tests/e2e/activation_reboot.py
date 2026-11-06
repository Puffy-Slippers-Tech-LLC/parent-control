"""LIFE04/05: real reboot update, saved Parent allowance and child preference.

The unchanged station update/reentry binding has its own qualification. This
slice adds the affected Parent and child panel observations, without replaying
the station's approval history or case 138's remembered-request tour.
"""
from copy import deepcopy

from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop,
                            package_installation, parent_management, prefixed_stages,
                            reboot_desktop)
from package_command import NOTICE
from package_upgrade import (PackageUpgradeJourney, activated_entry,
                             install_previous_release, upgrade_current)
from private_artifacts import require

ENTRIES = {'before-child': ('child', 'fresh'), 'update-parent': ('parent', 'retained'),
           'after-child': ('child', 'fresh')}
RETURN = prefixed_stages('updated', reboot_desktop())
SCREENS = {
    **package_installation(),
    'reboot-requested': 'system:parent-command-context', **reboot_desktop(),
    **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'settings-before': 'ui:retained-parent-read',
    **desktop_return('initial-leave', account='parent'),
    **prefixed_stages('before-child', desktop_entry('child', source='gdm', entry='fresh')),
    'animation-configured': 'ui:child-countdown-animation-off',
    'animation-before': 'ui:child-countdown-animation-read',
    **desktop_return('child-leave', account='child'),
    **prefixed_stages('update-parent', desktop_entry('parent', source='gdm', entry='retained')),
    **{stage: 'system:parent-command-context'
       for stage in ('upgrade-context', 'upgrade-submitted', 'upgrade-result')},
    'updated-reboot-requested': 'system:parent-command-context', **RETURN,
    **prefixed_stages('updated', parent_management()),
    'settings-after': 'ui:retained-parent-read',
    **desktop_return('updated-leave', account='parent'),
    **prefixed_stages('after-child', desktop_entry('child', source='gdm', entry='fresh')),
    'animation-after': 'ui:child-countdown-animation-read',
    'usable-countdown': 'ui:child-countdown-present',
}
LOGIN_STAGES = set(reboot_desktop()) | set(RETURN) | {
    prefix + '-' + stage for prefix, (account, _) in ENTRIES.items()
    for stage in fresh_desktop(account)}
PLAN = JourneyPlan(
    prefix='activation-reboot', worker_mode='activation_reboot', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'package-submitted': 'install-previous', 'upgrade-context': 'upgrade-entry',
                   'upgrade-submitted': 'upgrade-current'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={
        'after-reboot': ('parent', 'reboot-recipient-qualified', 'reboot-recipient-rechecked'),
        'after-update': ('parent', 'updated-reboot-recipient-qualified', 'updated-reboot-recipient-rechecked'),
        **{prefix: (account, prefix + '-' + recipient + 'qualified',
                    prefix + '-' + recipient + 'rechecked')
           for prefix, (account, _) in ENTRIES.items()
           for recipient in ('child-recipient-' if account == 'child' else 'recipient-',)}},
    reboot_transition=('reboot-requested', 'reboot-installed-greeter'),
    additional_reboot_transitions=(('updated-reboot-requested', 'updated-reboot-installed-greeter'),),
    assertions_after={'upgrade-result': 'real-update-completed-with-reboot-notice',
                      'updated-reboot-installed-greeter': 'update-changed-boot-usable-gdm',
                      'settings-after': 'rebooted-parent-saved-allowance',
                      'animation-after': 'rebooted-child-saved-preference',
                      'usable-countdown': 'rebooted-child-usable-panel'},
)


class ActivationRebootJourney(PackageUpgradeJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions={
            'install-previous': install_previous_release, 'upgrade-entry': activated_entry,
            'upgrade-current': upgrade_current})
        self.parent_before = self.animation_before = None
        self.animation_boot = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('package-result', 'upgrade-result'):
            require(observed['package']['notice'] == NOTICE, 'activation-reboot:required-notice')
        if stage in ('settings-before', 'settings-after'):
            value = observed['ui']['retained_parent']
            require(value['page'] == 'screen-limits' and value['settings'] == {
                'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['30 minutes']},
                'activation-reboot:saved-allowance')
            if stage == 'settings-before':
                self.parent_before = deepcopy(value['settings'])
            else:
                require(self.parent_before == value['settings']
                        and self.additional_reboots_observed == {1}
                        and observed['boot_sha256'] != self.activated_entry['boot'],
                        'activation-reboot:parent-after-update-reboot')
        if stage in ('animation-before', 'animation-after'):
            value = observed['ui']['panel_animation']
            require(value['child'] == 'fixture-child' and value['animation'] is False,
                    'activation-reboot:saved-child-preference')
            if stage == 'animation-before':
                self.animation_before = deepcopy(value)
                self.animation_boot = observed['boot_sha256']
            else:
                # Guest monotonic time resets at reboot. Freshness comes from
                # the guarded new-boot observation, never cross-boot ordering.
                require(self.animation_before is not None
                        and value['animation'] == self.animation_before['animation']
                        and self.additional_reboots_observed == {1}
                        and observed['boot_sha256'] != self.animation_boot,
                        'activation-reboot:fresh-child-read')
