"""Case 110: save the retained parent draft across a real fixture update."""
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from asset_transfer import AssetTransfer
from feedback_composition import text_fragment
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry, parent_reopen,
                            parent_selection, prefixed_stages)
from package_command import PackageCommand
from policy_edits import AppPolicyJourney
from ui_observations import SettingsObservation


SETUP = app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                         initial_rows=False)
DRAFT = {'block-save': 'ui:access-update-permanent',
         'editor-open': 'ui:match-update-open', 'opened-rule': 'ui:match-update-read',
         **text_fragment('match-update-wildcard', 'draft'),
         'draft-before-update': 'ui:match-update-read'}
SAVE = {'draft-after-update': 'ui:match-update-read', 'save': 'ui:match-update-save'}
REFRESH = {**prefixed_stages('reopen', parent_reopen()),
           **prefixed_stages('jordan', parent_selection(child='existing', screen_limits=True)),
           'loaded-apps': 'ui:existing-apps', 'loaded-rule': 'ui:match-update-row',
           'loaded-access': 'ui:access-update-row'}
CHILD = desktop_entry('other-child', source='gdm', entry='fresh')
RESULT = {'parent-logout': 'system:parent-logout',
          **prefixed_stages('child-entry', CHILD),
          'updated-launch': 'ui:native-updated-command-blocked'}
SCREENS = {**SETUP, **DRAFT, **SAVE, **REFRESH, **RESULT}
APP = MATCH_APPS['Update']
PLAN = JourneyPlan(
    prefix='catalogue-update', worker_mode='catalogue_update_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in (*SETUP, *DRAFT)}, 'installed-greeter': 'start',
            'draft-before-update': 'step-2',
            **{stage: 'step-3' for stage in (*SAVE, *REFRESH, *RESULT)}},
    advance_after={'draft-read': 'step-2',
                   'draft-before-update': 'step-3'},
    stage_actions={'desktop': 'install-old', 'draft-before-update': 'update-new'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',)),
        'jordan-parent-selected': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    match_checks={'opened-rule': (APP, MATCH_RULES[-3]),
                  'draft-before-update': (APP, MATCH_RULES[-1]),
                  'draft-after-update': 'draft-before-update',
                  'loaded-rule': (APP, MATCH_RULES[-1])},
    access_checks={'loaded-access': (APP, 'permanent')},
    invocations=tuple('child-entry-' + stage for stage, tag in CHILD.items() if tag.startswith('ui:')),
    challenges={'child-entry': ('other-child', 'child-entry-standard-recipient-qualified',
                               'child-entry-standard-recipient-rechecked')},
)


class CatalogueUpdateJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        context.asset_transfer = AssetTransfer(context.verified)
        super().__init__(context, progress, plan, actions={
            'install-old': self.install_old, 'update-new': self.update_new})

    def change(self, binding, guard):
        guard()
        command = PackageCommand(self.transport, self.context.verified)
        command.submit_fixture(binding)
        guard()
        return command.read_fixture_result()

    def install_old(self, journey, guard):
        return self.change('install-catalogue-old', guard)

    def update_new(self, journey, guard):
        return self.change('update-catalogue-new', guard)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=CatalogueUpdateJourney)


E2E_CASES = {'update': execute}
