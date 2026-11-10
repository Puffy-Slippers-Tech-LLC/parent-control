"""Case 264: saved presets and custom units survive editing and station reentry."""
from copy import deepcopy

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, prefixed_stages, station_entry
from request_composition import KioskRequestJourney
from request_flow import prepared_request
from private_artifacts import require


SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'policy-before': 'ui:overlay-language-policy',
    'parent-logout': 'system:parent-logout', 'parent-logged-out': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
        child='fixture-child', approver='fixture-parent', duration_seconds=75,
        allow_soft=True, compact=True),
    'presets-shipped': 'ui:kiosk-presets-shipped-read',
}
EDIT = {
    'preset-added': 'ui:kiosk-presets-add-ten',
    'preset-reopened': 'ui:kiosk-presets-added-read',
    'preset-selected': 'ui:kiosk-saved-preset-select',
    'preset-deleted': 'ui:kiosk-presets-delete-ten',
    'deleted-custom': 'ui:kiosk-deleted-preset-read',
    'hours-selected': 'ui:kiosk-custom-hours-select',
    'hours-read': 'ui:kiosk-custom-hours-read',
    'presets-restored': 'ui:kiosk-presets-restored-read',
    'minutes-restored': 'ui:kiosk-custom-minutes-restore',
    'minutes-read': 'ui:kiosk-custom-minutes-read',
    'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned',
}
RETURN = {
    **station_entry('cancel-'),
    'reentered-minutes': 'ui:kiosk-custom-minutes-read',
    'reentered-presets': 'ui:kiosk-presets-restored-read',
    'final-cancel': 'ui:kiosk-request-cancel', 'final-returned': 'ui:gdm-station-returned',
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('return', parent_management()),
    'policy-after': 'ui:overlay-language-policy',
    'final-parent-logout': 'system:parent-logout', 'final-greeter': 'ui:gdm-returned',
}
SCREENS = {**SETUP, **EDIT, **RETURN}
PLAN = JourneyPlan(prefix='request-presets', worker_mode='request_presets', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
        **{stage: 'step-2' for stage in EDIT}, **{stage: 'step-3' for stage in RETURN}},
    advance_after={'presets-shipped': 'step-2', 'returned': 'step-3'},
    balance_checks={'allowance-configured': 0},
    invocations=tuple([*fresh_desktop('parent'),
                       *prefixed_stages('return', fresh_desktop('parent'))]),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'return-parent': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    request_checks={'reentered-minutes': ('minutes-read', 'request-presets:reentry-choices',
                                         'saved_choices_after_cancel')},
    assertions_after={'preset-reopened': 'saved-preset', 'deleted-custom': 'selected-deletion',
        'hours-read': 'custom-hours', 'reentered-presets': 'restored-after-reentry',
        'final-greeter': 'unchanged-policy'})


class RequestPresetsJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.shipped_presets = None
        self.original_policy = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        value = observed.get('ui', {})
        if 'presets' in value:
            presets = value['presets']['values']
            if stage == 'presets-shipped':
                require(self.shipped_presets is None and
                        presets == [300, 900, 1800, 3600, 7200, 14400],
                        'request-presets:shipped-list')
                self.shipped_presets = presets[:]
            else:
                require(self.shipped_presets is not None, 'request-presets:missing-original')
                expected = (sorted([*self.shipped_presets, 600]) if stage == 'preset-reopened'
                            else self.shipped_presets)
                require(presets == expected, 'request-presets:saved-list')
                observed.setdefault('comparison', {})['saved_presets_and_offered_choices'] = True
        if 'language_policy' in value:
            policy = value['language_policy']
            require(policy['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                    'allowance': ['0 minutes']} and
                    policy['balances'] == {'daily': 0, 'one_time': 0, 'total': 0},
                    'request-presets:zero-time-policy')
            if stage == 'policy-before':
                require(self.original_policy is None, 'request-presets:policy-replay')
                self.original_policy = deepcopy(policy)
            else:
                require(stage == 'policy-after' and self.original_policy == policy,
                        'request-presets:changed-policy')
                observed.setdefault('comparison', {})['unchanged_policy_and_zero_grant'] = True


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=RequestPresetsJourney)


E2E_CASES = {'saved-presets': execute}
