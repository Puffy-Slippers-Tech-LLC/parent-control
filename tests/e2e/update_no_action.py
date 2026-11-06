"""LIFE04/05: a genuine no-action update keeps the parent's child settings usable."""
from copy import deepcopy
from dataclasses import replace

from journey_blocks import parent_management
from package_command import NOTICE, OLD_INSTALL, PackageCommand
from package_install import submit_release
from package_upgrade import PLAN as UPGRADE_PLAN, PackageUpgradeJourney, upgrade_actions
from private_artifacts import require

tags = {stage: tag for stage, tag in UPGRADE_PLAN.screen_tags.items()
        if stage not in ('upgrade-context', 'upgrade-submitted', 'upgrade-result', 'upgrade-reread')}
tags.update({**parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'settings-before': 'ui:retained-parent-read',
    'upgrade-context': UPGRADE_PLAN.screen_tags['upgrade-context'],
    **{stage: UPGRADE_PLAN.screen_tags[stage] for stage in ('upgrade-submitted', 'upgrade-result')},
    'upgrade-reread': 'ui:retained-parent-read'})
PLAN = replace(UPGRADE_PLAN, prefix='update-no-action', worker_mode='update_no_action',
    screen_tags=tags,
    phases={**UPGRADE_PLAN.phases, **{stage: 'step-4' for stage in tags
                                    if stage not in UPGRADE_PLAN.phases}},
    assertions_after={**UPGRADE_PLAN.assertions_after,
        'settings-before': 'saved-child-allowance-before-update',
        'upgrade-result': 'real-update-completed-with-no-activation',
        'upgrade-reread': 'same-usable-parent-window-and-child-settings'})


def install_old(journey, guard):
    command = PackageCommand(journey.transport, journey.context.verified)
    journey.release_entry = command.read_identity()
    require(journey.release_entry['version'] is None, 'update-no-action:product-free-required')
    return submit_release(journey, guard, OLD_INSTALL, 'previous_package')


class UpdateNoActionJourney(PackageUpgradeJourney):
    def __init__(self, context, progress, plan=PLAN, *, activation='none'):
        actions = {**upgrade_actions(), 'install-previous': install_old}
        super().__init__(context, progress, plan, actions=actions, activation=activation)
        self.activation = activation
        self.parent_before = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'package-result':
            # This exact fresh install requests reboot. Follow that actual
            # public notice before the older release's activation transition.
            require(observed['package']['notice'] == NOTICE,
                    'update-no-action:old-install-activation-notice')
        if stage not in ('settings-before', 'upgrade-reread'):
            return
        value = observed['ui']['retained_parent']
        require(value['page'] == 'screen-limits' and value['settings'] == {
            'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['30 minutes']},
            'update-no-action:child-settings')
        if stage == 'settings-before':
            require(self.parent_before is None, 'update-no-action:repeated-capture')
            self.parent_before = deepcopy(value)
        else:
            require(self.parent_before is not None and value == self.parent_before,
                    'update-no-action:parent-window-or-settings-changed')
            require(observed['package']['notice'] is None,
                    'update-no-action:unexpected-activation-notice')
            observed['comparison'] = {'same_usable_window': True, 'saved_allowance_unchanged': True,
                                      'activation': self.activation}
