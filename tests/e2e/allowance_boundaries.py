"""Task 040a's finite boundary slice, retaining ordinary commit regressions."""
from installed_journey import InstalledJourney, JourneyPlan
from allowance import SCREENS as ORDINARY_SCREENS
from allowance_values import ACCEPTED, INVALID

BOUNDARY_SCREENS = {}


def reload_stages(prefix):
    for suffix, operation in (
        ('away-open', 'existing-child-picker-opened'),
        ('away-focus', 'existing-child-choice-highlighted'),
        ('away-selected', 'existing-returned'),
        ('back-open', 'child-picker-opened'),
        ('back-focus', 'child-choice-highlighted'),
        ('back-selected', 'parent-selected'),
    ):
        BOUNDARY_SCREENS[prefix + '-' + suffix] = 'ui:' + operation


for value in ACCEPTED:
    prefix = 'boundary-' + str(value)
    BOUNDARY_SCREENS[prefix + '-open'] = 'ui:custom-' + str(value) + '-open'
    for action in ('focus', 'selected', 'read'):
        BOUNDARY_SCREENS[prefix + '-text-' + action] = 'ui:text-daily-' + str(value) + '-' + action
    BOUNDARY_SCREENS[prefix + '-saved'] = 'ui:custom-' + str(value) + '-saved'
    reload_stages(prefix)
    BOUNDARY_SCREENS[prefix + '-reopen'] = 'ui:custom-' + str(value) + '-reopen'

for binding in INVALID:
    prefix = 'invalid-' + binding
    BOUNDARY_SCREENS[prefix + '-baseline'] = 'ui:allowance-15-select'
    BOUNDARY_SCREENS[prefix + '-baseline-read'] = 'ui:allowance-15-read'
    BOUNDARY_SCREENS[prefix + '-open'] = 'ui:custom-15-open'
    for action in ('focus', 'selected', 'read'):
        BOUNDARY_SCREENS[prefix + '-text-' + action] = 'ui:text-daily-invalid-' + binding + '-' + action
    BOUNDARY_SCREENS[prefix + '-rejected'] = 'ui:custom-invalid-' + binding
    reload_stages(prefix)
    BOUNDARY_SCREENS[prefix + '-unchanged'] = 'ui:allowance-15-read'
    BOUNDARY_SCREENS[prefix + '-reopen'] = 'ui:custom-15-reopen'

SCREENS = {**ORDINARY_SCREENS, **BOUNDARY_SCREENS}

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
