"""Shared public balance and request-preservation checks for kiosk compositions.

Recipes declare comparison endpoints; this module owns no qualification plan.
The unused-child estimate applies to these fresh fixture entries only.
"""
from copy import deepcopy

from installed_journey import InstalledJourney
from journey_checks import check_balances
from private_artifacts import require


class KioskRequestJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.balance = None
        self.requests = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage)
        if stage in self.plan.balance_checks:
            check_balances(self, observed, self.plan.balance_checks[stage])
            self.balance = deepcopy(observed['ui']['time_explanation'])
        elif operation == 'ui:time-explanation-read':
            self.balance = deepcopy(observed['ui']['time_explanation'])
        self.check_estimate(observed)
        self.check_preserved_request(stage, observed)

    def check_estimate(self, observed):
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is None:
            return
        require(self.balance is not None, 'kiosk-valid:missing-balance')
        elapsed = (choice['observed_monotonic_ns'] - self.balance['observed_monotonic_ns']) / 1e9
        require(0 <= elapsed <= 600, 'kiosk-valid:elapsed-bound')
        if choice['estimate']['kind'] == 'fixed':
            daily, grant = (self.balance[key]['seconds'] for key in ('daily', 'one_time'))
            requested = choice['request']['duration_seconds']
            actual = choice['estimate']['seconds']
            precision = max(self.balance[key]['precision_seconds'] for key in ('daily', 'one_time'))
            require(max(0, max(daily, grant) - elapsed) + requested - precision <= actual
                    <= max(daily, grant) + requested + precision, 'kiosk-valid:estimate-bounds')
            require(abs(actual - (max(daily, grant) + requested)) <= precision,
                    'kiosk-valid:unused-child-estimate')
        observed['comparison'] = {'estimate_bounds': True, 'no_authentication': True}

    def check_preserved_request(self, stage, observed):
        checks = self.plan.request_checks
        if stage not in checks and stage not in {binding[0] for binding in checks.values()}:
            return
        request = observed.get('ui', {}).get('valid_choice', {}).get('request')
        require(isinstance(request, dict) and bool(request), 'request:missing-form')
        if stage in checks:
            before, error, result = checks[stage]
            require(before in self.requests and self.requests[before] == request, error)
            observed.setdefault('comparison', {})[result] = True
        require(stage not in self.requests, 'request:comparison-replay')
        self.requests[stage] = deepcopy(request)
