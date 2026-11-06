"""LIFE04/05: real extension update and renewal of the affected child session.

Only Riley has limits enabled and a running child extension in this slice.
Jordan and the station have no running affected session. Complete case 137
owns its broader rule/grant/request history.
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
import session_control

ENTRIES = {'before-child': ('child', 'fresh'), 'update-parent': ('parent', 'retained'),
           'renew-child': ('child', 'retained'), 'after-child': ('child', 'fresh'),
           'final-parent': ('parent', 'retained')}


def entry(prefix):
    account, mode = ENTRIES[prefix]
    return prefixed_stages(prefix, desktop_entry(account, source='gdm', entry=mode))


SCREENS = {
    **package_installation(),
    'reboot-requested': 'system:parent-command-context', **reboot_desktop(),
    **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'settings-before': 'ui:retained-parent-read',
    **desktop_return('initial-leave', account='parent'),
    **entry('before-child'),
    'animation-configured': 'ui:child-countdown-animation-off',
    'animation-before': 'ui:child-countdown-animation-read',
    **desktop_return('child-leave', account='child'),
    **entry('update-parent'),
    **{stage: 'system:parent-command-context'
       for stage in ('upgrade-context', 'upgrade-submitted', 'upgrade-result')},
    **desktop_return('updated-leave', account='parent'),
    **entry('renew-child'),
    'renewal-desktop': 'ui:fresh-child-desktop',
    'renewal-logout': 'system:child-logout', 'renewal-greeter': 'ui:gdm-returned',
    **entry('after-child'),
    'animation-after': 'ui:child-countdown-animation-read',
    'usable-countdown': 'ui:child-countdown-present',
    **desktop_return('renewed-leave', account='child'),
    **entry('final-parent'),
    'settings-after': 'ui:retained-parent-read',
}
LOGIN_STAGES = set(reboot_desktop()) | {
    prefix + '-' + stage for prefix, (account, _) in ENTRIES.items()
    for stage in fresh_desktop(account)}
PLAN = JourneyPlan(
    prefix='activation-session', worker_mode='activation_session', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'package-submitted': 'install-previous', 'upgrade-context': 'upgrade-entry',
                   'upgrade-submitted': 'upgrade-current'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={'after-reboot': ('parent', 'reboot-recipient-qualified', 'reboot-recipient-rechecked'),
        **{prefix: (account, prefix + '-' + recipient + 'qualified',
                    prefix + '-' + recipient + 'rechecked')
           for prefix, (account, _) in ENTRIES.items()
           for recipient in ('child-recipient-' if account == 'child' else 'recipient-',)}},
    reboot_transition=('reboot-requested', 'reboot-installed-greeter'),
    assertions_after={'upgrade-result': 'real-update-completed-without-restart-notice',
                      'animation-after': 'renewed-child-saved-preference',
                      'usable-countdown': 'renewed-child-usable-panel',
                      'settings-after': 'parent-saved-allowance-preserved'},
)


class ActivationSessionJourney(PackageUpgradeJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, activation='session-renewal', actions={
            'install-previous': install_previous_release, 'upgrade-entry': activated_entry,
            'upgrade-current': upgrade_current})
        self.parent_before = self.animation_before = None
        self.parent_session_before = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'package-result':
            require(observed['package']['notice'] == NOTICE, 'activation-session:old-install-notice')
        if stage == 'upgrade-result':
            require(observed['package']['notice'] is None,
                    'activation-session:unexpected-restart-notice')
        if stage in ('animation-before', 'animation-after'):
            value = observed['ui']['panel_animation']
            require(value['child'] == 'fixture-child' and value['animation'] is False,
                    'activation-session:saved-child-preference')
            if stage == 'animation-before':
                self.animation_before = deepcopy(value)
            else:
                require(self.animation_before is not None and value['observed_monotonic_ns']
                        > self.animation_before['observed_monotonic_ns'],
                        'activation-session:fresh-child-read')
        if stage in ('settings-before', 'settings-after'):
            value = observed['ui']['retained_parent']
            require(value['page'] == 'screen-limits' and value['settings'] == {
                'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['30 minutes']},
                'activation-session:saved-allowance')
            identity = session_control.observe(self.transport, 'parent-desktop-identity')
            if stage == 'settings-before':
                self.parent_before = deepcopy(value)
                self.parent_session_before = identity['session_sha256']
            else:
                require(self.parent_before is not None and value == self.parent_before,
                        'activation-session:parent-state-changed')
                # Package readback was already bound before leaving Parent.
                # Use the shared desktop proof and this checkpoint's boot read,
                # without repeating unrelated account-language preservation.
                require(observed['boot_sha256'] == self.activated_entry['boot']
                        and identity['session_sha256'] == self.parent_session_before,
                        'activation-session:unrequested-restart')
