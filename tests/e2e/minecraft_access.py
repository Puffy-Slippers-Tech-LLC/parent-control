"""Minecraft access follows the parent's saved Soft choice and real approval."""
from accessible_ui import MINECRAFT_POLICY_APP, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan
from journey_blocks import (app_policy_entry, desktop_entry, native_usable_app,
                            overlay_entry, prefixed_stages)
from policy_edits import AppPolicyJourney
from private_artifacts import require
from request_flow import overlay_approved_request, prepared_request
from ui_observations import SettingsObservation


def launcher(prefix):
    return prefixed_stages(prefix, {
        'launch': 'ui:minecraft-launch', 'opened': 'ui:minecraft-opened',
        'minecraft-close-ready': 'ui:minecraft-close-ready',
        'minecraft-closed': 'ui:minecraft-closed'})


def allowed_work(prefix):
    return prefixed_stages(prefix, {
        **native_usable_app('command', role='N'),
        'close': 'ui:native-nonmatching-close', 'closed': 'ui:native-nonmatching-closed'})


ENTRIES = {
    'initial': desktop_entry('other-child', source='gdm', entry='fresh'),
    'parent-return': desktop_entry('parent', source='desktop', entry='retained',
                                   source_account='other-child'),
    'child-return': desktop_entry('other-child', source='desktop', entry='retained',
                                  source_account='parent'),
}
# App access is the result; countdown arithmetic has its own qualification.
CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
               duration_seconds=900, allow_soft=True)
SCREENS = {
    **app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                       initial_rows=False),
    **{'minecraft-search-' + action: 'ui:text-catalogue-minecraft-' + action
       for action in ('focus', 'selected', 'read')},
    'allowed-save': 'ui:access-minecraft-allowed',
    'allowed-row': 'ui:access-minecraft-row',
    'parent-switch': 'system:parent-switch-user', 'parent-greeter': 'ui:gdm-returned',
    **prefixed_stages('initial', ENTRIES['initial']),
    'observer-ready': 'ui:minecraft-observer-ready',
    **allowed_work('initial-work'), **launcher('allowed'),
    **prefixed_stages('parent-return', ENTRIES['parent-return']),
    'soft-save': 'ui:access-minecraft-conditional',
    'soft-row': 'ui:access-minecraft-row',
    **prefixed_stages('child-return', ENTRIES['child-return']),
    'denied': 'ui:minecraft-command-blocked', 'denied-absent': 'ui:minecraft-closed',
    **allowed_work('denied-work'),
    **prefixed_stages('approved', {
        **overlay_entry('request', 'command', form_operation='request-overlay-jordan-ready'),
        **prepared_request(prefix='new', entry='open', initial='observed',
                           surface='overlay', **CHOICES),
        **overlay_approved_request(exit='automatic', **CHOICES)}),
    **launcher('approved'),
    'child-logout': 'system:standard-logout',
}
PLAN = JourneyPlan(
    prefix='minecraft-access', worker_mode='minecraft_access', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'setup-detached': 'daytime-clock', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    access_checks={'allowed-row': (MINECRAFT_POLICY_APP, 'allowed'),
                   'soft-row': (MINECRAFT_POLICY_APP, 'conditional')},
    overlay_request=('other-child', 'parent', 900, True),
    invocations=tuple(prefix + '-' + stage for prefix, stages in ENTRIES.items()
                      for stage, tag in stages.items() if tag.startswith('ui:')
                      and stage not in ('source-desktop', 'source-greeter')) + (
                          'approved-request-launch', 'approved-request-form'),
    challenges={prefix: (account, prefix + '-' + role + 'recipient-qualified',
                         prefix + '-' + role + 'recipient-rechecked')
                for prefix, account, role in (('initial', 'other-child', 'standard-'),
                                              ('parent-return', 'parent', ''),
                                              ('child-return', 'other-child', 'standard-'))},
)


class MinecraftAccessJourney(AppPolicyJourney):
    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage.endswith('-minecraft-close-ready'):
            opened_stage = stage.removesuffix('minecraft-close-ready') + 'opened'
            opened = next(step for step in self.steps if step['stage'] == opened_stage)
            require(observed['ui']['minecraft'] == opened['ui']['minecraft'],
                    'minecraft-access:close-owner-changed')
