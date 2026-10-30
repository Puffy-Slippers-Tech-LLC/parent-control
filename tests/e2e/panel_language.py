"""One overlay language Save, independently observed on the same child panel."""

from dataclasses import asdict
import math
import re

from accessible_ui import countdown_seconds
from countdown import CountdownObservation, check_countdown_balance
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, overlay_entry, language_selection
from overlay_language import OverlayLanguageJourney
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'policy-before': 'ui:overlay-language-policy',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **overlay_entry('direct', 'command', form_operation='overlay-language-initial'),
    'initial-save': 'ui:overlay-language-save', 'initial-form': 'ui:overlay-language-form-en',
    'initial-cancel': 'ui:overlay-qualification-cancel', 'initial-returned': 'ui:overlay-desktop',
    'panel-before': 'ui:child-countdown-present',
    **overlay_entry('renewed', 'command', form_operation='overlay-language-form-en'),
    **language_selection('hebrew', 'he', surface='overlay'),
    'hebrew-save': 'ui:overlay-language-save', 'hebrew-form': 'ui:overlay-language-form-he',
    'cancel': 'ui:overlay-qualification-cancel', 'returned': 'ui:overlay-desktop',
    'panel-after': 'ui:child-countdown-present',
    'child-switch-user': 'system:child-switch-user', 'child-gdm-switched': 'ui:gdm-returned',
    'return-greeter': 'ui:gdm-list', 'return-focused': 'ui:gdm-focused',
    'return-qualified': 'ui:gdm-parent-recipient', 'return-rechecked': 'ui:gdm-parent-recipient-rechecked',
    'return-desktop': 'ui:desktop', 'policy-after': 'ui:overlay-language-policy',
}
PLAN = JourneyPlan(prefix='panel-language', worker_mode='panel_language_refresh', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
        or stage.startswith(('fresh-', 'direct-', 'renewed-', 'return-'))
        or stage in ('panel-before', 'panel-after')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return-parent': ('parent', 'return-qualified', 'return-rechecked')},
    assertions_after={stage: stage + '-verified' for stage in
        ('policy-before', 'initial-form', 'panel-before', 'hebrew-choose',
         'hebrew-form', 'returned', 'panel-after', 'policy-after')})


class PanelLanguageJourney(OverlayLanguageJourney):
    def __init__(self, context, progress, *, actions=None):
        super().__init__(context, progress, PLAN, actions=actions)
        self.panel_before = None
        self.balance_before = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            self.balance_before = observed['ui']['time_explanation']
        if stage not in ('panel-before', 'panel-after'):
            return
        panel = CountdownObservation.from_value(observed['ui']['countdown'], present=True)
        prefix = 'Request time, ' if stage == 'panel-before' else 'בקשת זמן, '
        require(panel.request_text.startswith(prefix), 'panel-language:public-meaning')
        label = panel.request_text.removeprefix(prefix)
        low, high = countdown_seconds(label)
        require(low - 1 <= panel.seconds <= high + 1, 'panel-language:label-balance')
        require(re.fullmatch(r'[0-9:]+', label) is not None, 'panel-language:label-text')
        if stage == 'panel-before':
            balance = self.balance_before
            require(balance is not None, 'panel-language:missing-balance')
            observed['comparison'] = check_countdown_balance(panel,
                seconds=balance['total']['seconds'],
                precision_seconds=balance['total']['precision_seconds'],
                observed_monotonic_ns=balance['observed_monotonic_ns'], max_elapsed_seconds=300)
            self.panel_before = panel
            return
        before = self.panel_before
        require(before is not None, 'panel-language:missing-before')
        elapsed = (panel.observed_monotonic_ns - before.observed_monotonic_ns) / 1_000_000_000
        require(0 < elapsed <= 180, 'panel-language:elapsed-bound')
        # Canonical seconds have one tick of read/update tolerance. Language Save
        # must not replenish time; only the real elapsed interval can consume it.
        require(before.seconds - math.ceil(elapsed) - 1 <= panel.seconds <= before.seconds + 1,
                'panel-language:time-preservation')
        observed['comparison'] = {'before': asdict(before), 'after': asdict(panel),
                                  'elapsed_seconds': elapsed, 'tolerance_seconds': 1}
