"""Finite shortcut results, ordinary controls and fresh usable station return."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, prefixed_stages, station_entry
from private_artifacts import require
from public_desktop_selection import parent_settings


ROUTES = ('overview', 'grid', 'run', 'terminal')
SCREENS = {
    **parent_settings('shortcut-setup', True),
    **prefixed_stages('ordinary', fresh_desktop('other-child')),
}
for route in ROUTES:
    SCREENS.update({f'standard-shortcut-{route}-{phase}':
                    f'ui:standard-shortcut-{route}-{phase}'
                    for phase in ('ready', 'read', 'close-ready', 'closed')})
SCREENS.update({
    'ordinary-logout': 'system:standard-logout',
    'ordinary-returned': 'ui:gdm-returned',
    **station_entry(),
    'shortcut-child': 'ui:kiosk-child-select',
    'shortcut-approver': 'ui:kiosk-approver-select',
    'shortcut-usable': 'ui:kiosk-enabled-form',
})
for route in ROUTES:
    SCREENS.update({f'kiosk-shortcut-{route}-{phase}':
                    f'ui:kiosk-shortcut-{route}-{phase}'
                    for phase in ('ready', 'read')})
    SCREENS[f'usable-after-{route}'] = 'ui:kiosk-enabled-form'
SCREENS.update({
    'shortcut-cancel': 'ui:kiosk-request-cancel',
    'shortcut-returned': 'ui:gdm-station-returned',
    **station_entry('renewed-'),
    'fresh-usable': 'ui:kiosk-enabled-form',
    'fresh-cancel': 'ui:kiosk-request-cancel',
    'fresh-returned': 'ui:gdm-station-returned',
    **parent_settings('shortcut-restore', False),
})
PLAN = JourneyPlan(
    prefix='station-shortcuts', worker_mode='station_shortcuts', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS},
            'shortcut-setup-installed-greeter': 'start'},
    invocations=tuple(stage for stage, tag in SCREENS.items() if tag.startswith('ui:')),
    challenges={
        'shortcut-setup': ('parent', 'shortcut-setup-recipient-qualified',
                           'shortcut-setup-recipient-rechecked'),
        'ordinary': ('other-child', 'ordinary-standard-recipient-qualified',
                     'ordinary-standard-recipient-rechecked'),
        'shortcut-restore': ('parent', 'shortcut-restore-recipient-qualified',
                             'shortcut-restore-recipient-rechecked'),
    },
    settings_checks={'shortcut-restore-restored': 'shortcut-setup-parent-selected'},
)


class StationShortcutsJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.shortcut_results = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'shortcut-setup-parent-selected':
            require(observed['ui']['settings']['limit_enabled'] is False,
                    'station-shortcuts:initial-disabled-child')
        if stage.endswith('-read') and '-shortcut-' in stage:
            self.shortcut_results[stage] = observed['ui']['shortcut']
        if stage == 'shortcut-restore-returned':
            # Defer applicability verdict until public restoration and fresh
            # usable entry have completed; an absent positive is inconclusive.
            require(len(self.shortcut_results) == 8, 'station-shortcuts:missing-results')
            for route in ROUTES:
                positive = self.shortcut_results[f'standard-shortcut-{route}-read']
                require(positive['outcome'] == {
                    'overview': 'overview', 'grid': 'app-grid',
                    'run': 'run', 'terminal': 'terminal'}[route],
                        'station-shortcuts:ordinary-control-inconclusive:' + route)
                station = self.shortcut_results[f'kiosk-shortcut-{route}-read']
                require(station['usable_request'] is True,
                        'station-shortcuts:request-unusable:' + route)
