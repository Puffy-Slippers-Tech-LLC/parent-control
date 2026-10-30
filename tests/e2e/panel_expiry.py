"""Case 262: language changes retain Riley's original time, work and expiry."""

from dataclasses import asdict

from accessible_ui import countdown_seconds
from countdown import CountdownSample
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (daily_time_profile, fresh_desktop, language_selection,
                            native_activity_entry, overlay_entry, prefixed_stages)
from journey_checks import CountdownActivityJourney, DailyTimeProfileJourney
from overlay_language import OverlayLanguageJourney
from private_artifacts import require
from ui_observations import SettingsObservation


SETUP = {
    **fresh_desktop('parent'),
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=10),
}
ENGLISH = {
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
    **overlay_entry('direct', 'command', form_operation='overlay-language-initial'),
    'initial-save': 'ui:overlay-language-save', 'initial-form': 'ui:overlay-language-form-en',
    'initial-cancel': 'ui:overlay-qualification-cancel', 'initial-returned': 'ui:overlay-desktop',
    'initial-countdown': 'ui:child-countdown-present',
}
HEBREW = {
    **overlay_entry('hebrew-entry', 'command', form_operation='overlay-language-form-en'),
    **language_selection('hebrew', 'he', surface='overlay'),
    'hebrew-save': 'ui:overlay-language-save', 'hebrew-form': 'ui:overlay-language-form-he',
    'hebrew-cancel': 'ui:overlay-qualification-cancel', 'hebrew-returned': 'ui:overlay-desktop',
    'hebrew-activity': 'ui:overlay-native-activity',
    'panel-hebrew': 'ui:child-countdown-present',
}
RESTORED = {
    **overlay_entry('english-entry', 'command', form_operation='overlay-language-form-he'),
    **language_selection('english', 'en', surface='overlay'),
    'english-save': 'ui:overlay-language-save', 'english-form': 'ui:overlay-language-form-en',
    'english-cancel': 'ui:overlay-qualification-cancel', 'english-returned': 'ui:overlay-desktop',
    'english-activity': 'ui:overlay-native-activity',
    'panel-restored': 'ui:child-countdown-present',
}
TIME_STAGES = ('minute-progression', 'final-second-transition', 'second-progression',
               'independent-second-progression', 'natural-expiry')
EXPIRY = {
    **{stage: 'ui:child-countdown-present' for stage in TIME_STAGES},
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
    'return-greeter': 'system:child-return-greeter', 'returned-gdm': 'ui:gdm-returned',
    'parent-greeter': 'ui:gdm-list', 'parent-focused-return': 'ui:gdm-focused',
    'parent-qualified-return': 'ui:gdm-parent-recipient',
    'parent-rechecked-return': 'ui:gdm-parent-recipient-rechecked',
    'parent-desktop-return': 'ui:desktop', 'policy-after': 'ui:overlay-language-policy',
}
# Capture policy before leaving Parent, without interrupting the child's history.
SETUP = {stage: tag for stage, tag in SETUP.items() if stage not in (
    'repeat-desktop', 'switch-user', 'gdm-switched')} | {
    'policy-before': 'ui:overlay-language-policy', 'repeat-desktop': 'ui:desktop',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned'}
SCREENS = {**SETUP, **ENGLISH, **HEBREW, **RESTORED, **EXPIRY}
PLAN = JourneyPlan(prefix='panel-expiry', worker_mode='panel_language_expiry', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', SETUP), ('step-2', ENGLISH), ('step-3', HEBREW),
            ('step-4', RESTORED), ('step-5', EXPIRY)) for stage in screens},
        'installed-greeter': 'start'},
    advance_after={'gdm-switched': 'step-2', 'initial-countdown': 'step-3',
                   'panel-hebrew': 'step-4', 'panel-restored': 'step-5'},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
        or stage.startswith(('fresh-', 'direct-', 'hebrew-entry-', 'english-entry-'))
        or stage in ('initial-countdown', 'panel-hebrew', 'panel-restored', *TIME_STAGES,
            'lock-input-ready', 'lock-result', 'parent-greeter', 'parent-focused-return',
            'parent-qualified-return', 'parent-rechecked-return', 'parent-desktop-return')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return-parent': ('parent', 'parent-qualified-return', 'parent-rechecked-return')},
    settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('10 minutes',))},
    balance_checks={'profile-configured': 600},
    stage_actions={'desktop': 'native-verify', 'minute-progression': 'minute-progress',
                   'final-second-transition': 'final-transition',
                   'second-progression': 'second-progress',
                   'independent-second-progression': 'second-progress',
                   'natural-expiry': 'natural-expiry'},
    activity_entries={'natural-expiry': 'activity-capture'},
    activity_checks={stage: ('activity-capture', 'same')
                     for stage in ('hebrew-activity', 'english-activity')},
    assertions_after={
        'policy-before': 'original-daily-only-policy', 'activity-capture': 'original-child-work',
        'initial-countdown': 'original-english-time', 'hebrew-form': 'hebrew-request-preserved',
        'hebrew-activity': 'hebrew-original-work', 'panel-hebrew': 'hebrew-time-without-reset',
        'english-form': 'english-request-restored', 'english-activity': 'english-original-work',
        'panel-restored': 'english-time-without-reset', 'minute-progression': 'minute-progression',
        'independent-second-progression': 'final-second-progression',
        'natural-expiry': 'natural-enforced-lock', 'lock-result': 'lock-owns-normal-input',
        'policy-after': 'unchanged-policy-zero-time'},
)


class PanelExpiryJourney(CountdownActivityJourney, DailyTimeProfileJourney, OverlayLanguageJourney):
    policy_minutes = 10
    minute_edge_limit = 9

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
            time_stages=('initial-countdown', *TIME_STAGES),
            no_grant_checks=('profile-before',), actions=actions)
        self.panel_samples = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'policy-after':
            require(observed['ui']['language_policy']['balances'] == {
                'daily': 0, 'one_time': 0, 'total': 0}, 'panel-expiry:terminal-zero-time')
        if stage not in ('initial-countdown', 'panel-hebrew', 'panel-restored'):
            return
        current = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
        prefix = 'בקשת זמן, ' if stage == 'panel-hebrew' else 'Request time, '
        panel = current.countdown
        require(panel.request_text.startswith(prefix), 'panel-expiry:public-language')
        low, high = countdown_seconds(panel.request_text.removeprefix(prefix))
        require(low - 1 <= panel.seconds <= high + 1 and panel.seconds > 0,
                'panel-expiry:public-label-balance')
        if self.panel_samples:
            previous = next(reversed(self.panel_samples.values()))
            elapsed = current.elapsed_since(previous, max_elapsed_seconds=180)
            used = previous.countdown.seconds - panel.seconds
            require(elapsed[0] - 2 <= used <= elapsed[1] + 2,
                    'panel-expiry:language-reset-or-extra-use')
            observed['comparison'] = {'before': asdict(previous), 'after': asdict(current),
                'elapsed_interval_seconds': list(elapsed), 'tolerance_seconds': 2}
        require(stage not in self.panel_samples, 'panel-expiry:replayed-panel')
        self.panel_samples[stage] = current
        if stage == 'panel-restored':
            # TIME02 starts from this history's final language observation.
            self.samples['returned-countdown'] = current


def execute(recorder, context):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-061/panel-expiry'
    record_installed_journey(recorder, context, PLAN, timeout=1200, journey_type=PanelExpiryJourney)


E2E_CASES = {'panel-expiry': execute}
