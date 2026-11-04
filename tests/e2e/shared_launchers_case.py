"""Case 187: either launcher's block governs their shared native app."""
from copy import deepcopy

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from feedback_composition import text_fragment
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, native_blocked_app, native_usable_app,
                            prefixed_stages, retained_parent_entry)
from policy_edits import policy_edit
from private_artifacts import require
from shared_target_launchers import PLAN as QUALIFIED_PLAN, SETUP, SharedTargetLaunchersJourney


# Keep both directions and each recovery in one attempt. Parent stays open;
# Jordan logs out between visits so no incidental retained-child branch is needed.
ROUNDS = (
    ('original-blocked', (('A', 'permanent'), ('Alias', 'allowed')), False),
    ('original-allowed', (('A', 'allowed'),), True),
    ('alias-blocked', (('Alias', 'permanent'),), False),
    ('alias-allowed', (('Alias', 'allowed'),), True),
)
SCREENS = {stage: tag for stage, tag in SETUP.items() if stage != 'parent-logout'}
SCREENS['retained-window'] = 'ui:retained-parent-leave'
SCREENS['parent-session'] = 'system:parent-desktop-identity'
PHASES = {stage: 'step-1' for stage in SCREENS}
ENTRIES = {}
MATCH_CHECKS = {}
ACCESS_CHECKS = {}
for name, edits, usable in ROUNDS:
    group = {}
    for role, choice in edits:
        prefix = name + '-' + role.lower()
        group.update(policy_edit(MATCH_APPS[role],
            'match-alias-precise' if role == 'Alias' else 'match-precise', choice, prefix))
        MATCH_CHECKS.update({prefix + '-' + suffix: (MATCH_APPS[role], MATCH_RULES[0])
                            for suffix in ('open', 'old', 'match', 'final-match')})
        ACCESS_CHECKS[prefix + '-access'] = (MATCH_APPS[role], choice)
    # Read both confirmed choices before every child visit, including the
    # unchanged Allowed entry that must not override the other launcher's block.
    group.update(text_fragment('catalogue-clear', name + '-clear'))
    group.update({name + '-original-choice': 'ui:access-row',
                  name + '-alias-choice': 'ui:access-alias-row'})
    ACCESS_CHECKS[name + '-original-choice'] = (
        MATCH_APPS['A'], 'permanent' if name == 'original-blocked' else 'allowed')
    ACCESS_CHECKS[name + '-alias-choice'] = (
        MATCH_APPS['Alias'], 'permanent' if name == 'alias-blocked' else 'allowed')
    group.update(prefixed_stages(name + '-leave', {
        'desktop': 'ui:desktop', 'switch': 'system:parent-switch-user',
        'greeter': 'ui:gdm-returned'}))
    entry = desktop_entry('other-child', source='gdm', entry='fresh')
    ENTRIES[name + '-entry'] = entry
    group.update(prefixed_stages(name + '-entry', entry))
    for role, label in (('A', 'original'), ('Alias', 'alias')):
        app = ({**native_usable_app('grid', role='Alias' if role == 'Alias' else None),
                'close': 'ui:native-close', 'closed': 'ui:native-closed'} if usable else
               native_blocked_app(role, route='grid'))
        group.update(prefixed_stages(name + '-' + label, app))
    group.update({name + '-logout': 'system:standard-logout',
                  name + '-greeter': 'ui:gdm-returned'})
    if name != 'alias-allowed':
        returned = desktop_entry('parent', source='gdm', entry='retained')
        ENTRIES[name + '-return'] = returned
        group.update(prefixed_stages(name + '-return', returned))
        group.update(prefixed_stages(name + '-supplied', retained_parent_entry(
            source='same-user', desktop_observation=False)))
        group[name + '-parent-session'] = 'system:parent-desktop-identity'
        group[name + '-apps-page'] = 'ui:existing-apps'
    SCREENS.update(group)
    PHASES.update({stage: 'step-2' for stage in group})

# The final policy edit precedes step-3; all final child results stay in step-3.
FINAL_ENTRY = 'alias-allowed-leave-desktop'
final_index = list(SCREENS).index(FINAL_ENTRY)
PHASES.update({stage: 'step-3' for stage in list(SCREENS)[final_index:]})
LOGIN_STAGES = {prefix + '-' + stage for prefix, screens in ENTRIES.items()
                for stage, tag in screens.items() if tag.startswith('ui:')}
PLAN = JourneyPlan(
    prefix='shared-launchers-case', worker_mode='shared_launchers_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', **PHASES, 'installed-greeter': 'start'},
    advance_after={'parent-session': 'step-2', 'alias-allowed-alias-choice': 'step-3'},
    stage_actions=QUALIFIED_PLAN.stage_actions,
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks=QUALIFIED_PLAN.settings_checks,
    balance_checks=QUALIFIED_PLAN.balance_checks,
    match_checks=MATCH_CHECKS, access_checks=ACCESS_CHECKS,
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (
        'parent' if prefix.endswith('-return') else 'other-child',
        prefix + ('-recipient-qualified' if prefix.endswith('-return') else '-standard-recipient-qualified'),
        prefix + ('-recipient-rechecked' if prefix.endswith('-return') else '-standard-recipient-rechecked'))
        for prefix in ENTRIES},
)


class SharedLaunchersCaseJourney(SharedTargetLaunchersJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.parent_window = None
        self.parent_session = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'retained-window' or stage.endswith('-supplied-parent-retained'):
            value = observed['ui']['retained_parent']
            require(value['page'] == 'app-limits' and value['settings'] == {
                'child': 'existing-fixture-child', 'limit_enabled': True,
                'allowance': ['30 minutes']}, 'shared-launchers:retained-settings')
            if self.parent_window is None:
                self.parent_window = deepcopy(value['window'])
            require(value['window'] == self.parent_window, 'shared-launchers:parent-window-replaced')
        if stage == 'parent-session' or stage.endswith('-parent-session'):
            value = observed['system']['session_sha256']
            if self.parent_session is None:
                self.parent_session = value
            require(value == self.parent_session, 'shared-launchers:parent-session-replaced')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=SharedLaunchersCaseJourney)


E2E_CASES = {'shared-launchers': execute}
