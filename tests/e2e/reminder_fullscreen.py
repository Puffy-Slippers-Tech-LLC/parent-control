"""311a: saved fullscreen reminder preference and discarded changes."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, overlay_entry, prefixed_stages
from overlay_reminders import DEFAULTS, OverlayReminderJourney
from private_artifacts import require


REMINDER_STAGES = {
    'defaults-open': 'defaults', 'fullscreen-disabled': 'fullscreen-false',
    'saved': 'save', 'saved-read': 'read', 'fullscreen-enabled-draft': 'fullscreen-true',
    'cancelled': 'cancel', 'cancel-read': 'read', 'preferences-close': 'cancel',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'policy-before': 'ui:overlay-language-policy',
    'logout-ready': 'ui:desktop', 'logout': 'system:parent-logout',
    'gdm-logged-out': 'ui:gdm-returned',
    **prefixed_stages('fresh', fresh_desktop('child')),
    **overlay_entry('direct', 'command', form_operation='overlay-language-initial'),
    'initial-save': 'ui:overlay-language-save', 'initial-form': 'ui:overlay-language-form-en',
    **{stage: 'ui:overlay-reminder-' + action for stage, action in REMINDER_STAGES.items()},
    'final-form': 'ui:overlay-language-form-en',
    'cancel': 'ui:overlay-qualification-cancel', 'returned': 'ui:overlay-desktop',
    'child-logout': 'system:child-logout', 'child-logged-out': 'ui:gdm-returned',
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('return', parent_management()),
    'policy-after': 'ui:overlay-language-policy',
}
LOGIN_STAGES = set(fresh_desktop('parent')) | {
    prefix + stage for prefix, account in (('fresh-', 'child'), ('return-', 'parent'))
    for stage in fresh_desktop(account)}
PLAN = JourneyPlan(prefix='reminder-fullscreen', worker_mode='reminder_fullscreen_preference',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage.startswith('direct-')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return-parent': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    assertions_after={stage: stage + '-verified' for stage in (
        *REMINDER_STAGES, 'initial-form', 'final-form', 'policy-before', 'policy-after')})


class ReminderFullscreenJourney(OverlayReminderJourney):
    """Reuse request/policy preservation; compare the caller's saved boolean."""
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.original_preferences = None

    def check_settings(self, stage, observed):
        operation = self.plan.screen_tags.get(stage, '')[3:]
        if not operation.startswith('overlay-reminder-'):
            return super().check_settings(stage, observed)
        InstalledJourney.check_settings(self, stage, observed)
        require(stage not in self.reminder_captures, 'fullscreen-reminders:capture-replay')
        if operation not in ('overlay-reminder-save', 'overlay-reminder-cancel'):
            value = observed['ui']['reminders']
            projection = {key: value[key] for key in ('records', 'language', 'fullscreen_enabled')}
            if stage == 'defaults-open':
                require(projection == {'records': DEFAULTS, 'language': 'en',
                                       'fullscreen_enabled': True},
                        'fullscreen-reminders:declared-defaults')
                self.original_preferences = deepcopy(projection)
            require(self.original_preferences is not None and projection == self.original_preferences,
                    'fullscreen-reminders:preference-preservation')
            expected = stage in ('defaults-open', 'fullscreen-enabled-draft')
            require(value['show_in_fullscreen'] is expected,
                    'fullscreen-reminders:saved-boolean')
        self.reminder_captures.add(stage)
