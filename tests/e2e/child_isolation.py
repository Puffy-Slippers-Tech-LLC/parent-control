"""Finite U02 healthy, unavailable and restored child request history."""
from copy import deepcopy
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import (custom_child_selection, desktop_entry, fresh_desktop,
                            parent_management, prefixed_stages, station_entry)
from private_artifacts import require
from request_composition import _estimate_read_bounds
from request_flow import CHOICES, prepared_request


SCREENS = {**fresh_desktop('parent'), **parent_management(),
           'healthy-allowance': 'ui:time-explanation-positive-read',
           **custom_child_selection('setup-jordan', 'existing'),
           'unavailable-allowance': 'ui:time-explanation-positive-read',
           'setup-switch': 'system:parent-switch-user', 'setup-greeter': 'ui:gdm-returned'}
ENTRIES = {}
for phase, child in (('healthy', 'child'), ('unavailable', 'existing'), ('restored', 'existing')):
    request = {**station_entry()}
    if phase == 'healthy':
        request.update(prepared_request(prefix='new', entry='open', initial='default',
                                       compact=True, **CHOICES))
        # Both children are enabled here. The ordinary single-child flow's
        # initial form binding expects the default Jordan account disabled.
        request['new-form'] = 'ui:multiple-preserved'
    elif phase == 'unavailable':
        request.update({'new-child': 'ui:multiple-isolation-child',
                        'new-duration': 'ui:jordan-custom-open',
                        **{'new-text-' + action: 'ui:text-jordan-kiosk-fraction-' + action
                           for action in ('focus', 'selected', 'read')},
                        'new-apps': 'ui:jordan-fraction-soft-select',
                        'new-estimate': 'ui:jordan-fraction-soft-read'})
    else:
        request['new-estimate'] = 'ui:jordan-fraction-estimate-refresh'
    mate = 'kiosk' if phase == 'healthy' else 'jordan'
    result = ('refused', 'submit-unavailable') if phase == 'unavailable' else ('success', 'submit-success')
    request.update({'approval-' + stage: f'ui:{mate}-mate-' + operation
                    for stage, operation in (('open', 'open'), ('qualified', 'qualified'),
                                             ('rechecked', 'rechecked'), result)})
    request['new-returned'] = 'ui:gdm-station-returned'
    SCREENS.update(prefixed_stages(phase, request))
    entry = prefixed_stages(phase + '-parent', desktop_entry('parent', source='gdm', entry='retained'))
    ENTRIES[phase] = entry
    SCREENS.update(entry)
    if phase == 'restored':
        # Force a normal status reload; Parent's unchanged selection can retain
        # the previous grant display until its periodic refresh.
        SCREENS.update(custom_child_selection('restored-selected-away', 'child'))
    SCREENS.update(custom_child_selection(phase + '-selected', child))
    SCREENS[phase + '-balance'] = 'ui:time-explanation-reach-read'
    SCREENS[phase + '-switch'] = 'system:parent-switch-user'
    SCREENS[phase + '-greeter'] = 'ui:gdm-returned'
SCREENS.update(prefixed_stages('reentry', {**station_entry(),
    'usable': 'ui:jordan-fraction-soft-read', 'exit': 'ui:kiosk-request-cancel',
    'returned': 'ui:gdm-station-returned'}))

PLAN = JourneyPlan(prefix='child-isolation', worker_mode='child_isolation', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'}},
    invocations=tuple(stage for entry in ENTRIES.values() for stage, tag in entry.items()
                      if tag.startswith('ui:')),
    challenges={phase + '-parent': ('parent', phase + '-parent-recipient-qualified',
                                   phase + '-parent-recipient-rechecked') for phase in ENTRIES},
    child_bindings={'unavailable-allowance': 'existing',
                    'unavailable-balance': 'existing', 'restored-balance': 'existing'},
    assertions_after={'healthy-balance': 'healthy-child-genuine-time-access',
                      'unavailable-balance': 'unavailable-child-safe-refusal-without-new-grant',
                      'restored-balance': 'restored-child-genuine-time-access',
                      'reentry-usable': 'fresh-passwordless-usable-request'})


class ChildIsolationJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.estimates = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'unavailable-allowance':
            require(observed['ui']['time_explanation']['one_time']['seconds'] == 0,
                    'child-isolation:initial-grant-not-empty')
        for phase, child in (('healthy', 'fixture-child'),
                             ('unavailable', 'existing-fixture-child'),
                             ('restored', 'existing-fixture-child')):
            if stage == phase + '-new-estimate':
                choice = observed['ui']['valid_choice']
                require(choice['request']['child'] == child
                        and choice['estimate']['kind'] == 'fixed', 'child-isolation:request-child')
                if phase != 'restored':
                    require(choice['estimate']['seconds'] == 975, 'child-isolation:initial-estimate')
                else:
                    _estimate_read_bounds(choice, 'child-isolation:estimate-read-bounds')
                self.estimates[phase] = deepcopy(choice)
            if stage == phase + '-balance':
                value = observed['ui']['time_explanation']
                require(value['child'] == child and phase in self.estimates, 'child-isolation:balance-child')
                estimate = self.estimates[phase]
                if phase == 'unavailable':
                    require(value['one_time']['seconds'] == 0
                            and abs(value['daily']['seconds'] - 900) < value['daily']['precision_seconds']
                            and abs(value['total']['seconds'] - value['daily']['seconds'])
                            < max(value[key]['precision_seconds'] for key in ('total', 'daily')),
                            'child-isolation:refusal-changed-time-access')
                    observed.setdefault('comparison', {})['no_new_grant'] = True
                    continue
                elapsed = (value['observed_monotonic_ns'] - estimate['observed_monotonic_ns']) / 1e9
                if phase == 'restored':
                    start, end = _estimate_read_bounds(estimate, 'child-isolation:estimate-read-bounds')
                    require(value['observed_monotonic_ns'] >= end
                            and estimate['estimate']['precision_seconds'] == 1,
                            'child-isolation:estimate-read-bounds')
                    elapsed = (value['observed_monotonic_ns'] - start) / 1e9
                grant = value['one_time']['seconds']
                precision = value['one_time']['precision_seconds']
                require(0 <= elapsed <= 600 and grant > 0
                        and estimate['estimate']['seconds'] - elapsed - precision <= grant
                        <= estimate['estimate']['seconds'] + precision,
                        'child-isolation:independent-grant')
                require(abs(value['daily']['seconds'] - 900) < value['daily']['precision_seconds']
                        and abs(value['total']['seconds'] - max(value['daily']['seconds'], grant))
                        < max(value[key]['precision_seconds'] for key in ('total', 'daily', 'one_time')),
                        'child-isolation:independent-time-access')
                observed.setdefault('comparison', {})['independent_genuine_time_access'] = True
