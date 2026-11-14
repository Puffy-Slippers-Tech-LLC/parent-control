"""Case 253: Jordan's launcher access follows Jamie's approvals across reboot."""
from copy import deepcopy
import time

from accessible_ui import (LUNAR_POLICY_APP, MINECRAFT_POLICY_APP,
                           NAMED_CHILD_OPERATIONS, OVERLAY_BOUND_OPERATIONS)
from calendar_fixture import preset_ordinary_daytime
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (allowance_selection, app_policy_entry, desktop_entry,
                            desktop_return, overlay_entry, parent_management,
                            parent_selection, prefixed_stages)
from lunar_profile import LunarProfile
from minecraft_access import MinecraftAccessJourney, allowed_work, launcher
from native_fixtures import fixture_actions
from private_artifacts import require
from request_flow import overlay_approved_request, prepared_request
from ui_observations import SettingsObservation


ENTRIES = {}
REQUESTS = {}


def enter(prefix, account, entry):
    stages = desktop_entry(account, source='gdm', entry=entry)
    ENTRIES[prefix] = (account, stages)
    return prefixed_stages(prefix, stages)


def hidden_lunar(prefix):
    return prefixed_stages(prefix, {
        'observer-ready': 'ui:lunar-observer-ready',
        'present': 'ui:lunar-snapshot', 'quit': 'ui:lunar-quit', 'closed': 'ui:lunar-closed'})


def launchers(prefix):
    return {
        **prefixed_stages(prefix + '-lunar', {
            'launch': 'ui:lunar-launch', 'opened': 'ui:lunar-opened',
            'quit': 'ui:lunar-quit', 'closed': 'ui:lunar-closed'}),
        **launcher(prefix + '-minecraft'),
    }


def denied(prefix):
    return prefixed_stages(prefix, {
        'observer-ready': 'ui:lunar-observer-ready',
        'lunar-before': 'ui:lunar-closed',
        'lunar-denied': 'ui:lunar-command-blocked', 'lunar-absent': 'ui:lunar-closed',
        'minecraft-denied': 'ui:minecraft-command-blocked',
        'minecraft-absent': 'ui:minecraft-closed',
        **allowed_work('work'),
    })


def approval(prefix, soft):
    choices = dict(child='existing-fixture-child', approver='fixture-parent',
                   duration_seconds=900, allow_soft=soft)
    stages = prefixed_stages(prefix, {
        **overlay_entry('request', 'command', form_operation='request-overlay-jordan-ready'),
        **prepared_request(prefix='new', entry='open', initial='observed',
                           surface='overlay', **choices),
        **overlay_approved_request(exit='automatic', **choices),
    })
    REQUESTS.update({stage: ('other-child', 'parent', 900, soft)
                     for stage, tag in stages.items()
                     if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})
    return stages


def parent_visit(prefix, entry):
    return {
        **desktop_return(prefix + '-child-leave', account='other-child'),
        **enter(prefix + '-parent', 'parent', entry),
        **prefixed_stages(prefix + '-view', parent_management(child='existing')
                         if entry == 'fresh' else
                         parent_selection(child='existing', screen_limits=True)),
    }


def child_return(prefix):
    return {**desktop_return(prefix + '-parent-leave', account='parent'),
            **enter(prefix + '-child', 'other-child', 'retained')}


def reboot(prefix):
    return {prefix + '-reboot': 'system:standard-desktop-identity',
            prefix + '-greeter': 'ui:gdm-list',
            **enter(prefix + '-login', 'other-child', 'fresh')}


def policy_choices(prefix, choice):
    return {stage: tag for app in ('lunar', 'minecraft') for stage, tag in {
        **{f'{prefix}-{app}-search-{action}': f'ui:text-catalogue-{app}-{action}'
           for action in ('focus', 'selected', 'read')},
        f'{prefix}-{app}-save': f'ui:access-{app}-{choice}',
        f'{prefix}-{app}-row': f'ui:access-{app}-row',
    }.items()} | {f'{prefix}-clear-{action}': f'ui:text-catalogue-clear-{action}'
                 for action in ('focus', 'selected', 'read')}


PARTS = {
    'step-1': {
        **app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                           initial_rows=False),
        'screen-page': 'ui:access-screen',
        **allowance_selection('daily', (120,)),
        'daily-settings': 'ui:existing-returned',
        'allowed-apps': 'ui:existing-apps',
        **policy_choices('allowed', 'allowed'),
        'allowed-policy': 'ui:revoke-saved-balances',
        'parent-logout': 'system:parent-logout',
        **enter('initial-child', 'other-child', 'fresh'),
        # The supplied hidden autostart must quit before an explicit command.
        **hidden_lunar('initial-hidden'),
        'minecraft-observer': 'ui:minecraft-observer-ready',
        **launchers('allowed'), **reboot('allowed'), **hidden_lunar('allowed-hidden'),
    },
    'step-2': {
        **parent_visit('soft', 'fresh'),
        'soft-apps': 'ui:existing-apps', **policy_choices('soft', 'conditional'),
        'soft-policy': 'ui:revoke-saved-balances',
        **child_return('soft'), **denied('ungranted'),
    },
    'step-3': {
        **approval('time-only', False),
        **parent_visit('time-only-before', 'retained'),
        'time-only-before-policy': 'ui:revoke-saved-balances',
        **child_return('time-only-before'), **reboot('time-only'),
        **denied('time-only'),
        **parent_visit('time-only-after', 'fresh'),
        'time-only-after-policy': 'ui:revoke-saved-balances',
        **child_return('time-only-after'),
    },
    'step-4': {**approval('included', True), **launchers('included')},
    'step-5': {
        **approval('replacement', False),
        **parent_visit('replacement-before', 'retained'),
        'replacement-before-policy': 'ui:revoke-saved-balances',
        **child_return('replacement-before'), **reboot('replacement'),
        **denied('replacement'),
        **parent_visit('replacement-after', 'fresh'),
        'replacement-after-policy': 'ui:revoke-saved-balances',
        **child_return('replacement-after'),
        'child-logout': 'system:standard-logout',
    },
}
SCREENS = {stage: tag for part in PARTS.values() for stage, tag in part.items()}
LOGIN_STAGES = {prefix + '-' + stage for prefix, (_account, stages) in ENTRIES.items()
                for stage, tag in stages.items() if tag.startswith('ui:')}
PLAN = JourneyPlan(
    prefix='lunar-access', worker_mode='lunar_access', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, part in PARTS.items() for stage in part},
            'installed-greeter': 'start'},
    advance_after={list(PARTS['step-' + str(index)])[-1]: 'step-' + str(index + 1)
                   for index in range(1, 5)},
    stage_actions={'setup-detached': 'launcher-prepare', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',)),
        'daily-settings': SettingsObservation('existing-fixture-child', True, ('2 hours',))},
    access_checks={f'{prefix}-{app}-row': (target, choice)
                   for prefix, choice in (('allowed', 'allowed'), ('soft', 'conditional'))
                   for app, target in (('lunar', LUNAR_POLICY_APP),
                                       ('minecraft', MINECRAFT_POLICY_APP))},
    overlay_request=('other-child', 'parent', 900, False), overlay_requests=REQUESTS,
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES or
                      stage in {prefix + '-request-' + leaf
                                for prefix in ('time-only', 'included', 'replacement')
                                for leaf in ('launch', 'form')}),
    challenges={prefix: (account, prefix + '-' + role + 'recipient-qualified',
                         prefix + '-' + role + 'recipient-rechecked')
                for prefix, (account, _stages) in ENTRIES.items()
                for role in ('standard-' if account == 'other-child' else '',)},
    reboot_transition=('allowed-reboot', 'allowed-greeter'),
    additional_reboot_transitions=(('time-only-reboot', 'time-only-greeter'),
                                   ('replacement-reboot', 'replacement-greeter')),
    assertions_after={'allowed-hidden-closed': 'allowed-route-control',
                      'ungranted-work-closed': 'ungranted-soft-denial',
                      'time-only-after-child-desktop': 'time-only-boot-denial',
                      'included-minecraft-minecraft-closed': 'explicit-soft-approval',
                      'replacement-after-child-desktop': 'replacement-boot-denial'},
)


class LunarAccessJourney(MinecraftAccessJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.profile = None
        self.saved_policy = None
        self.grants = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage.endswith('-policy'):
            policy = observed['ui']['revoke_cancel']
            require(policy['settings'] == {'child': 'existing-fixture-child',
                    'limit_enabled': True, 'allowance': ['2 hours']}, 'lunar-access:settings')
            rows = {row[0]: row[1:] for row in policy['apps']}
            choice = 'allowed' if stage == 'allowed-policy' else 'conditional'
            require(rows.get(LUNAR_POLICY_APP) == [choice, 'pattern']
                    and rows.get(MINECRAFT_POLICY_APP) == [choice, 'precise'],
                    'lunar-access:saved-choices')
            require(self.profile is not None and dict(policy['rules']).get(LUNAR_POLICY_APP)
                    == self.profile['targets']['version_pattern'], 'lunar-access:version-pattern')
            saved = {key: deepcopy(policy[key]) for key in ('settings', 'apps', 'rules')}
            if stage == 'soft-policy':
                self.saved_policy = saved
            elif stage != 'allowed-policy':
                require(self.saved_policy == saved, 'lunar-access:saved-policy-changed')
            balances = policy['balances']
            require(balances['daily']['seconds'] > 600, 'lunar-access:daily-margin')
            if stage in ('allowed-policy', 'soft-policy'):
                require(balances['one_time']['seconds'] == 0, 'lunar-access:unexpected-grant')
            else:
                name, when = stage.removesuffix('-policy').rsplit('-', 1)
                bounds = tuple(self.ui.read_bounds)
                grant = balances['one_time']
                require(grant['seconds'] > (600 if when == 'before' else 0),
                        'lunar-access:active-grant')
                if when == 'before':
                    require(name not in self.grants, 'lunar-access:grant-replay')
                    self.grants[name] = (deepcopy(grant), bounds)
                else:
                    before, earlier = self.grants[name]
                    low = (bounds[0] - earlier[1]) / 1e9
                    high = (bounds[1] - earlier[0]) / 1e9
                    tolerance = before['precision_seconds'] + grant['precision_seconds'] + 2
                    require(0 < low <= high
                            and before['seconds'] - high - tolerance < grant['seconds']
                            < before['seconds'] - low + tolerance,
                            'lunar-access:original-grant-deadline')
                    observed.setdefault('comparison', {})['original_positive_grant'] = True
        if stage in ('time-only-reboot', 'replacement-reboot'):
            before, bounds = self.grants[stage.removesuffix('-reboot')]
            require(before['seconds'] - (time.monotonic_ns() - bounds[0]) / 1e9
                    - before['precision_seconds'] > 600, 'lunar-access:reboot-grant-margin')


def prepare(journey, guard):
    guard()
    journey.profile = LunarProfile(journey.transport, journey.context.verified).verify()
    guard()
    return {'profile': journey.profile, 'daytime': preset_ordinary_daytime(journey, guard)}


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
        journey_type=LunarAccessJourney,
        actions={**fixture_actions(include_refusal=False), 'launcher-prepare': prepare})


E2E_CASES = {'appimagelauncher-login-autostart': execute}
