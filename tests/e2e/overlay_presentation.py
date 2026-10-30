"""Case 260: Riley's complete English/Hebrew/English approval and saved work."""
from copy import deepcopy
from functools import partial

from accessible_ui import countdown_seconds
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (fresh_desktop, parent_management, native_activity_entry,
                            overlay_entry, language_selection)
from language_composition import PublicLanguageJourney, public_language_value
from native_fixtures import fixture_actions
from private_artifacts import require
from request_composition import KioskRequestJourney
from request_flow import prepared_request, overlay_authentication


SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
}
REQUEST = {
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **native_activity_entry('activity'), **overlay_entry('direct', 'command'),
    **prepared_request(prefix='open', entry='open', initial='default',
        child='fixture-child', approver='fixture-parent', duration_seconds=75,
        allow_soft=True, surface='overlay'),
    'english-form': 'ui:language-history-overlay-en-jamie',
    **language_selection('hebrew', 'he', surface='overlay'),
    'hebrew-save': 'ui:overlay-language-save',
    'hebrew-form': 'ui:language-history-overlay-he-jamie',
    'translated-estimate': 'ui:overlay-hebrew-fraction-soft-read',
}
APPROVAL = {
    **overlay_authentication(result='approval', prefix='approval', language='he'),
    'returned': 'ui:overlay-desktop',
    'activity-returned': 'ui:overlay-native-activity',
    'approved-countdown': 'ui:child-countdown-present',
}
RESTORATION = {
    **overlay_entry('reopened', 'command', form_operation='language-history-overlay-he-jamie'),
    **language_selection('english', 'en', surface='overlay'),
    'english-save': 'ui:overlay-language-save',
    'restored-form': 'ui:language-history-overlay-en-jamie',
    'cancel': 'ui:overlay-qualification-cancel', 'cancel-returned': 'ui:overlay-desktop',
    'activity-restored': 'ui:overlay-native-activity',
    'restored-countdown': 'ui:child-countdown-present',
    'activity-close': 'ui:overlay-native-close', 'activity-closed': 'ui:overlay-native-closed',
}
SCREENS = {**SETUP, **REQUEST, **APPROVAL, **RESTORATION}
PLAN = JourneyPlan(
    # Reuse the qualified fixed Riley/Jamie/75-second credential namespace.
    prefix='overlay-approved-exit', worker_mode='overlay_language_history', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', SETUP), ('step-2', REQUEST), ('step-3', APPROVAL), ('step-4', RESTORATION))
           for stage in screens}, 'installed-greeter': 'start'},
    advance_after={'gdm-switched': 'step-2', 'translated-estimate': 'step-3',
                   'approved-countdown': 'step-4'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    invocations=(*fresh_desktop('parent'),
        *tuple('fresh-' + stage for stage in fresh_desktop('child')),
        'direct-launch', 'direct-form', 'reopened-launch', 'reopened-form'),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked')},
    balance_checks={'allowance-configured': 900},
    request_checks={'translated-estimate': ('open-estimate', 'overlay-history:changed-request',
                                           'preserved_choices')},
    activity_checks={stage: ('activity-capture', 'same')
                     for stage in ('activity-returned', 'activity-restored')},
    countdown_checks={stage: ('translated-estimate', 'estimate', 1, 300)
                      for stage in ('approved-countdown', 'restored-countdown')},
    assertions_after={
        'english-form': 'original-english-request', 'hebrew-form': 'hebrew-preserved-request',
        'approval-success': 'hebrew-approval-success', 'activity-returned': 'approved-original-activity',
        'approved-countdown': 'approved-time-increment', 'restored-form': 'english-preserved-request',
        'activity-restored': 'cancel-original-activity', 'restored-countdown': 'original-grant-deadline'},
)

IDS = ('kiosk-child-account-caption', 'kiosk-approver-account-caption',
       'kiosk-duration-label-1800', 'kiosk-request-submit', 'kiosk-request-cancel')
REQUEST_VALUES = {'surface': 'child-overlay', 'form_count': 1, 'child': 'fixture-child',
    'approver': 'fixture-parent', 'duration_seconds': 75, 'custom_text': '1.25', 'allow_soft': True,
    'child_selector_enabled': False, 'approver_selector_enabled': True, 'duration_enabled': True,
    'soft_choice_enabled': True, 'request_enabled': True, 'cancel_enabled': True, 'message': '', 'mute': None}
TEXT = {'en': ('Child', 'Approver', '30 minutes', 'Request access', 'Cancel request', 'REQUEST', 'CANCEL'),
        'he': ('ילד', 'מאשר', '30 דקות', 'בקשת גישה', 'ביטול הבקשה', 'בקשה', 'ביטול')}
CHECKS = {stage: public_language_value('language_form', {
    'request': REQUEST_VALUES, 'texts': dict(zip(IDS, TEXT[language][:5])),
    'labels': dict(zip(IDS[3:], TEXT[language][5:])), 'chooser_absent': True})
    for stage, language in (('english-form', 'en'), ('hebrew-form', 'he'),
                           ('reopened-form', 'he'), ('restored-form', 'en'))}


class OverlayLanguageHistoryJourney(PublicLanguageJourney, KioskRequestJourney):
    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in CHECKS:
            request = observed['ui']['language_form']['request']
            if stage == 'english-form':
                self.public_captures['original-request'] = deepcopy(request)
            else:
                require(request == self.public_captures['original-request'],
                        'overlay-history:changed-request')
        if stage == 'restored-countdown':
            before, after = (self.countdowns[key] for key in ('approved-countdown', 'restored-countdown'))
            elapsed = (after.observed_monotonic_ns - before.observed_monotonic_ns) / 1e9
            low, high = countdown_seconds(before.text)
            current_low, current_high = countdown_seconds(after.text)
            # The child remains active throughout. Preserve the original deadline,
            # allowing public minute rounding and two seconds of refresh latency.
            require(0 < elapsed <= 300 and current_low <= high - elapsed + 2
                    and current_high >= low - elapsed - 2, 'overlay-history:grant-reset')
            observed.setdefault('comparison', {})['original_grant_deadline'] = True


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-059/overlay-hebrew'
    record_installed_journey(recorder, context, PLAN, timeout=900, actions=fixture_actions(),
        journey_type=partial(OverlayLanguageHistoryJourney, checks=CHECKS))


E2E_CASES = {'overlay-hebrew': execute}
