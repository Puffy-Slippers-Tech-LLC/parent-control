"""Installed custom-allowance boundaries with independent saved-value reloads."""
from installed_journey import InstalledJourney, JourneyPlan
from allowance_values import ACCEPTED, INVALID
from journey_blocks import allowance_selection, fresh_desktop, parent_management

def boundary_screens(accepted=ACCEPTED, invalid=tuple(INVALID)):
    """Share operation declarations; callers choose the size of their sample."""
    screens = {}

    def reload(prefix):
        for suffix, operation in (
            ('away-open', 'existing-child-picker-opened'),
            ('away-focus', 'existing-child-choice-highlighted'),
            ('away-selected', 'existing-returned'),
            ('back-open', 'child-picker-opened'),
            ('back-focus', 'child-choice-highlighted'),
            ('back-selected', 'parent-selected'),
        ):
            screens[prefix + '-' + suffix] = 'ui:' + operation

    for value in accepted:
        prefix = 'boundary-' + str(value)
        screens.update(allowance_selection(prefix + '-choice', ('custom',)))
        screens[prefix + '-open'] = 'ui:custom-' + str(value) + '-open'
        for action in ('focus', 'selected', 'read'):
            screens[prefix + '-text-' + action] = 'ui:text-daily-' + str(value) + '-' + action
        screens[prefix + '-saved'] = 'ui:custom-' + str(value) + '-saved'
        reload(prefix)
        if value in (0, 15):
            screens[prefix + '-reloaded-preset-read'] = 'ui:allowance-' + str(value) + '-read'
            screens.update(allowance_selection(prefix + '-reopen-choice', ('custom',)))
        screens[prefix + '-reopen'] = 'ui:custom-' + str(value) + '-reopen'

    for binding in invalid:
        prefix = 'invalid-' + binding
        screens.update(allowance_selection(prefix + '-baseline', (15,)))
        screens[prefix + '-baseline-read'] = 'ui:allowance-15-read'
        screens.update(allowance_selection(prefix + '-choice', ('custom',)))
        screens[prefix + '-open'] = 'ui:custom-15-open'
        for action in ('focus', 'selected', 'read'):
            screens[prefix + '-text-' + action] = 'ui:text-daily-invalid-' + binding + '-' + action
        screens[prefix + '-rejected'] = 'ui:custom-invalid-' + binding
        reload(prefix)
        screens[prefix + '-unchanged'] = 'ui:allowance-15-read'
        screens.update(allowance_selection(prefix + '-reopen-choice', ('custom',)))
        screens[prefix + '-reopen'] = 'ui:custom-15-reopen'
    return screens


BOUNDARY_SCREENS = boundary_screens()
# Ordinary commit routes have their own check_e2e_allowance qualification. Only
# enable editing here before exercising each accepted/rejected boundary.
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'parent-toggle-enabled': 'ui:parent-toggle-enabled',
    'parent-save-enabled': 'ui:parent-save-enabled',
    **BOUNDARY_SCREENS,
}

PLAN = JourneyPlan(
    prefix='allowance-boundaries', worker_mode='allowance_boundaries', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith(('boundary-', 'invalid-'))}},
    advance_after={'parent-save-enabled': 'step-2'},
)


class AllowanceBoundariesJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
