"""FIX03 qualification and complete multiple/ineligible account cases."""

from account_fixture import station_fixture_actions
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, station_entry


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry': 'ui:parent-kiosk-refused',
    'mate-wrong-entry': 'ui:parent-mate-refused',
    'limit-enabled': 'ui:parent-toggle-enabled',
    'save-enabled': 'ui:parent-save-enabled',
    'existing-child-picker-opened': 'ui:existing-child-picker-opened',
    'existing-child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'existing-returned': 'ui:discovery-ready',
    'other-enabled': 'ui:multiple-other-enable',
    'other-saved': 'ui:multiple-other-saved',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    'first-child': 'ui:multiple-first-child',
    'first-parent': 'ui:multiple-first-parent',
    'first-first-cancel': 'ui:multiple-first-first-cancel',
    'other-parent': 'ui:multiple-other-parent',
    'other-child': 'ui:multiple-other-child',
    'other-other-cancel': 'ui:multiple-other-other-cancel',
    'cancel': 'ui:kiosk-request-cancel',
    'returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='kiosk-multiple', worker_mode='kiosk_multiple', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in (
                'switch-user', 'gdm-switched', *station_entry(),
                'first-child', 'first-parent', 'first-first-cancel', 'other-parent',
                'other-child', 'other-other-cancel', 'cancel', 'returned')}},
    advance_after={'other-saved': 'step-2'},
)


class KioskMultipleJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)


INELIGIBLE_PLAN = JourneyPlan(
    prefix=PLAN.prefix, worker_mode=PLAN.worker_mode, screen_tags=PLAN.screen_tags,
    phases=PLAN.phases, advance_after=PLAN.advance_after,
    stage_actions={'setup-detached': 'prepare-ineligible-approver'})


class KioskIneligibleJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, INELIGIBLE_PLAN,
                         actions=station_fixture_actions(context, 'ineligible-approver'))


CASE_SCREENS = {}
for stage, tag in SCREENS.items():
    if stage in ('wrong-entry', 'mate-wrong-entry'):
        continue
    if stage == 'cancel':
        CASE_SCREENS['preserved'] = 'ui:multiple-preserved'
    CASE_SCREENS[stage] = tag

CASE_PLAN = JourneyPlan(
    prefix='kiosk-multiple', worker_mode='multiple_case', screen_tags=CASE_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in CASE_SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in (
                'first-child', 'first-parent')},
            **{stage: 'step-3' for stage in (
                'first-first-cancel', 'other-parent', 'other-child', 'other-other-cancel',
                'preserved', 'cancel', 'returned')}},
    advance_after={'installed-greeter': 'step-1', 'station-branch': 'step-2',
                   'first-parent': 'step-3'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, CASE_PLAN, timeout=1800)


INELIGIBLE_CASE_PLAN = JourneyPlan(
    prefix=CASE_PLAN.prefix, worker_mode=CASE_PLAN.worker_mode,
    screen_tags=CASE_PLAN.screen_tags, phases=CASE_PLAN.phases,
    advance_after=CASE_PLAN.advance_after,
    stage_actions={'setup-detached': 'prepare-ineligible-approver'})


def execute_ineligible(recorder, context):
    record_installed_journey(
        recorder, context, INELIGIBLE_CASE_PLAN, timeout=1800,
        actions=station_fixture_actions(context, 'ineligible-approver'))


E2E_CASES = {'multiple': execute, 'ineligible-parent': execute_ineligible}
