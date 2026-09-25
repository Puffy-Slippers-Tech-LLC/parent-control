"""Task 040a's finite boundary slice, retaining ordinary commit regressions."""
from installed_journey import InstalledJourney, JourneyPlan
from allowance import SCREENS as ORDINARY_SCREENS
from allowance_values import ACCEPTED, INVALID

SCREENS = dict(ORDINARY_SCREENS)


def reload_stages(prefix):
    for suffix, operation in (
        ('away-open', 'existing-child-picker-opened'),
        ('away-focus', 'existing-child-choice-highlighted'),
        ('away-selected', 'existing-returned'),
        ('back-open', 'child-picker-opened'),
        ('back-focus', 'child-choice-highlighted'),
        ('back-selected', 'parent-selected'),
    ):
        SCREENS[prefix + '-' + suffix] = 'ui:' + operation


for value in ACCEPTED:
    prefix = 'boundary-' + str(value)
    SCREENS[prefix + '-open'] = 'ui:custom-' + str(value) + '-open'
    for action in ('focus', 'selected', 'read'):
        SCREENS[prefix + '-text-' + action] = 'ui:text-daily-' + str(value) + '-' + action
    SCREENS[prefix + '-saved'] = 'ui:custom-' + str(value) + '-saved'
    reload_stages(prefix)
    SCREENS[prefix + '-reopen'] = 'ui:custom-' + str(value) + '-reopen'

for binding in INVALID:
    prefix = 'invalid-' + binding
    SCREENS[prefix + '-baseline'] = 'ui:allowance-15-select'
    SCREENS[prefix + '-baseline-read'] = 'ui:allowance-15-read'
    SCREENS[prefix + '-open'] = 'ui:custom-15-open'
    for action in ('focus', 'selected', 'read'):
        SCREENS[prefix + '-text-' + action] = 'ui:text-daily-invalid-' + binding + '-' + action
    SCREENS[prefix + '-rejected'] = 'ui:custom-invalid-' + binding
    reload_stages(prefix)
    SCREENS[prefix + '-unchanged'] = 'ui:allowance-15-read'
    SCREENS[prefix + '-reopen'] = 'ui:custom-15-reopen'

PLAN = JourneyPlan(
    prefix='allowance-boundaries', worker_mode='allowance_boundaries', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith(('boundary-', 'invalid-'))}},
    advance_after={'custom-3-reopen': 'step-2'},
)


class AllowanceBoundariesJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
