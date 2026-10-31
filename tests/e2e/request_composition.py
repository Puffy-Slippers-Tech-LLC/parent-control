"""Shared public balance and request-preservation checks for kiosk compositions.

Recipes declare comparison endpoints; this module owns no qualification plan.
The unused-child estimate applies to these fresh fixture entries only.
"""
from copy import deepcopy

from accessible_ui import countdown_seconds

from countdown import CountdownObservation, check_countdown_balance
from installed_journey import InstalledJourney
from journey_checks import check_balances
from private_artifacts import require
from ui_observations import RequestObservation
from access_choices import AccessChoiceJourney


def _estimate_read_bounds(choice, error='grant-effects:negative-read-bounds'):
    """Bracket a calculation forced through the ordinary public change handler."""
    bounds = choice.get('estimate_read_bounds')
    require(type(bounds) is list and len(bounds) == 2
            and all(type(value) is int for value in bounds),
            error)
    start, end = bounds
    require(type(choice.get('observed_monotonic_ns')) is int
            and 0 < start <= end and end == choice['observed_monotonic_ns']
            and end - start <= 45_000_000_000,
            error)
    return start, end


class KioskRequestJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.balance = None
        self.requests = {}
        self.transfer_requests = {}
        self.countdown_baselines = {}
        self.countdowns = {}

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
        self.check_transferred_request(stage, observed)
        self.check_countdown(stage, observed)

    def check_countdown(self, stage, observed):
        checks = self.plan.countdown_checks
        if stage in {binding[0] for binding in checks.values()}:
            require(stage not in self.countdown_baselines, 'countdown:capture-replay')
            choice = observed.get('ui', {}).get('valid_choice')
            require(isinstance(choice, dict) and choice['estimate']['kind'] == 'fixed',
                    'countdown:missing-estimate')
            self.countdown_baselines[stage] = (choice['estimate']['seconds'],
                                             choice['observed_monotonic_ns'])
        if stage in checks:
            before, seconds, precision, elapsed = checks[stage]
            require(before in self.countdown_baselines, 'countdown:missing-estimate')
            require(stage not in self.countdowns, 'countdown:comparison-replay')
            estimated, timestamp = self.countdown_baselines[before]
            require(seconds == 'estimate' or estimated == seconds, 'countdown:expected-estimate')
            current = CountdownObservation.from_value(observed['ui']['countdown'], present=True,
                child='existing-fixture-child' if (self.plan.overlay_request or self.plan.kiosk_request
                    or ('child',))[0] == 'other-child' else 'fixture-child')
            comparison = check_countdown_balance(current,
                seconds=estimated, precision_seconds=precision,
                observed_monotonic_ns=timestamp, max_elapsed_seconds=elapsed)
            observed.setdefault('comparison', {}).update(comparison)
            self.countdowns[stage] = current

    def check_estimate(self, observed):
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is None:
            return
        require(self.balance is not None, 'kiosk-valid:missing-balance')
        require(choice['request']['child'] == self.balance['child'], 'kiosk-valid:wrong-child-balance')
        elapsed = (choice['observed_monotonic_ns'] - self.balance['observed_monotonic_ns']) / 1e9
        require(0 <= elapsed <= 600, 'kiosk-valid:elapsed-bound')
        if choice['estimate']['kind'] == 'fixed':
            daily, grant = (self.balance[key]['seconds'] for key in ('daily', 'one_time'))
            requested = choice['request']['duration_seconds']
            actual = choice['estimate']['seconds']
            precision = max(self.balance[key]['precision_seconds'] for key in ('daily', 'one_time'))
            require(max(0, max(daily, grant) - elapsed) + requested - precision <= actual
                    <= max(daily, grant) + requested + precision, 'kiosk-valid:estimate-bounds')
            if choice['request'].get('surface', 'kiosk') == 'kiosk':
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

    def check_transferred_request(self, stage, observed):
        """Compare immutable child-owned choices, allowing local selector differences."""
        checks = self.plan.request_transfer_checks
        if stage not in checks and stage not in checks.values():
            return
        operation = self.plan.screen_tags[stage].removeprefix('ui:')
        value = observed.get('ui', {})
        request = RequestObservation.from_request(value.get('request',
            value.get('valid_choice', {}).get('request')), operation=operation)
        require(stage not in self.transfer_requests, 'request-transfer:replay')
        if stage in checks:
            before = self.transfer_requests.get(checks[stage])
            require(before is not None, 'request-transfer:missing-source')
            require((before.surface, request.surface) in (
                        ('child-overlay', 'kiosk'), ('kiosk', 'child-overlay')),
                    'request-transfer:direction')
            require(all(getattr(before, field) == getattr(request, field) for field in
                        ('child', 'duration_seconds', 'custom_text', 'allow_soft')),
                    'request-transfer:changed-child-choices')
            observed.setdefault('comparison', {})['shared_child_choices_local_approver'] = True
        self.transfer_requests[stage] = request


class GrantAppEffectsJourney(KioskRequestJourney, AccessChoiceJourney):
    """Public grant-only balances and immutable saved app-policy endpoints.

    Callers declare the finite policy oracle, approval capture and zero/positive
    read endpoints. This shares policy/choice/countdown checks without acquiring
    fixtures or supplying any part of a qualification's worker sequence.
    """

    def __init__(self, context, progress, plan, *, settings, app_rules,
                 approval_stage, policy_reads, actions=None, approval_stages=None,
                 negative_estimates=None, countdown_balances=()):
        super().__init__(context, progress, plan, actions=actions)
        stages = list(plan.screen_tags)
        require(approval_stage in stages and type(policy_reads) is dict
                and bool(policy_reads) and type(app_rules) is dict and bool(app_rules),
                'grant-effects:comparison-plan')
        require(all(stage in stages and plan.screen_tags[stage] in (
                    'ui:revoke-saved-balances', 'ui:revoke-cleared-balances')
                    and type(binding) is tuple and len(binding) == 2
                    and binding[1] in ('zero', 'positive')
                    and (binding[0] is None or binding[0] in policy_reads
                         and stages.index(binding[0]) < stages.index(stage))
                    for stage, binding in policy_reads.items()),
                'grant-effects:comparison-plan')
        self.effects_settings = deepcopy(settings)
        self.effects_rules = deepcopy(app_rules)
        self.effects_approval_stage = approval_stage
        self.effects_reads = dict(policy_reads)
        self.effects_seen = {}
        self.effects_estimate = None
        self.effects_approvals = dict(approval_stages or {})
        self.effects_negative_checks = dict(negative_estimates or {})
        require(all(stage in policy_reads and policy_reads[stage][1] == 'positive'
                    and capture in stages and stages.index(capture) < stages.index(stage)
                    and plan.screen_tags[capture] in (
                        'ui:kiosk-valid-fraction-soft-read', 'ui:kiosk-long-request-soft-read',
                        'ui:overlay-valid-fraction-soft-read',
                        'ui:overlay-fraction-estimate-refresh')
                    for stage, capture in self.effects_approvals.items()),
                'grant-effects:approval-plan')
        require(all(stage in stages and before in stages
                    and stages.index(before) < stages.index(stage)
                    and plan.screen_tags[stage] == plan.screen_tags[before]
                    == 'ui:overlay-fraction-estimate-refresh'
                    for stage, before in self.effects_negative_checks.items()),
                'grant-effects:negative-plan')
        self.effects_estimates = {}
        self.effects_negative_seen = {}
        require(type(countdown_balances) is tuple and len(set(countdown_balances)) == len(countdown_balances)
                and all(stage in plan.countdown_checks for stage in countdown_balances),
                'grant-effects:countdown-balance-plan')
        self.effects_countdown_balances = countdown_balances

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.effects_countdown_balances:
            current = self.countdowns[stage]
            low, high = countdown_seconds(current.text)
            require(low > 0 and self.balance is not None
                    and self.balance['daily']['seconds'] == 0,
                    'grant-effects:positive-countdown')
            self.balance = {'daily': {'seconds': 0, 'precision_seconds': 1},
                            'one_time': {'seconds': high, 'precision_seconds': high - low + 1},
                            'observed_monotonic_ns': current.observed_monotonic_ns}
            observed.setdefault('comparison', {})['public_grant_only_countdown_baseline'] = True
        if stage == self.effects_approval_stage:
            require(self.effects_estimate is None, 'grant-effects:estimate-replay')
            self.effects_estimate = deepcopy(observed['ui']['valid_choice'])
        if stage in self.effects_approvals.values():
            require(stage not in self.effects_estimates, 'grant-effects:estimate-replay')
            if self.plan.screen_tags[stage] == 'ui:overlay-fraction-estimate-refresh':
                _estimate_read_bounds(observed['ui']['valid_choice'],
                                      'grant-effects:approval-read-bounds')
            self.effects_estimates[stage] = deepcopy(observed['ui']['valid_choice'])
        if stage in self.effects_negative_checks or stage in self.effects_negative_checks.values():
            require(stage not in self.effects_negative_seen, 'grant-effects:negative-replay')
            current = observed['ui']['valid_choice']
            current_start, current_end = _estimate_read_bounds(current)
            if stage in self.effects_negative_checks:
                before = self.effects_negative_seen.get(self.effects_negative_checks[stage])
                require(before is not None, 'grant-effects:negative-missing')
                require(current['request'] == before['request'], 'grant-effects:negative-choices')
                old, new = before['estimate'], current['estimate']
                require(old['kind'] == new['kind'] == 'fixed'
                        and old['precision_seconds'] == new['precision_seconds'] == 1,
                        'grant-effects:negative-precision')
                before_start, before_end = _estimate_read_bounds(before)
                elapsed = (current_end - before_end) / 1e9
                minimum = (current_start - before_end) / 1e9
                maximum = (current_end - before_start) / 1e9
                requested = current['request']['duration_seconds']
                # Each estimate can have been calculated anywhere inside its
                # guest-clock bracket. Include both whole-second precisions,
                # while keeping the entire uncertainty narrower than one
                # requested grant: an accidental extra 75 s must remain
                # distinguishable from ordinary countdown.
                lower = old['seconds'] - maximum - 2
                upper = old['seconds'] - minimum + 2
                require(0 <= minimum <= elapsed <= 120 and minimum <= maximum
                        and requested == 75 and upper - lower < requested
                        and lower > requested and new['seconds'] > requested
                        and lower <= new['seconds'] <= upper,
                        'grant-effects:negative-added-time')
                observed.setdefault('comparison', {})['no_additional_grant_with_elapsed_bounds'] = True
            self.effects_negative_seen[stage] = deepcopy(current)
        if stage not in self.effects_reads:
            return
        require(stage not in self.effects_seen, 'grant-effects:read-replay')
        before, mode = self.effects_reads[stage]
        value = observed['ui']['revoke_cancel']
        require(value['settings'] == self.effects_settings, 'grant-effects:settings')
        rows = {row[0]: row[1] for row in value['apps']}
        rules = dict(value['rules'])
        require(all(rows.get(app) == access and rules.get(app) == rule
                    for app, (access, rule) in self.effects_rules.items()),
                'grant-effects:saved-rules')
        if before is not None:
            require(before in self.effects_seen, 'grant-effects:missing-policy')
            earlier = self.effects_seen[before]
            require(all(value[key] == earlier[key] for key in ('settings', 'apps', 'rules')),
                    'grant-effects:changed-policy')
        balances = value['balances']
        require(balances['child'] == self.effects_settings['child'], 'grant-effects:wrong-child')
        daily, grant, total = (balances[key]['seconds'] for key in ('daily', 'one_time', 'total'))
        require(daily == 0 and total == grant and
                (grant > 0 if mode == 'positive' else grant == 0),
                'grant-effects:grant-only-balance')
        if mode == 'positive':
            estimate = (self.effects_estimates.get(self.effects_approvals[stage])
                        if stage in self.effects_approvals else self.effects_estimate)
            require(estimate is not None, 'grant-effects:missing-approval')
            require(estimate['estimate']['kind'] == 'fixed', 'grant-effects:fixed-estimate')
            elapsed = (balances['observed_monotonic_ns'] - estimate['observed_monotonic_ns']) / 1e9
            precision = balances['one_time']['precision_seconds']
            expected = estimate['estimate']['seconds']
            capture = self.effects_approvals.get(stage, self.effects_approval_stage)
            if self.plan.screen_tags[capture] == 'ui:overlay-fraction-estimate-refresh':
                start, end = _estimate_read_bounds(estimate, 'grant-effects:approval-read-bounds')
                # The refreshed calculation happened inside this guest-clock
                # bracket, not at the later label read. Parent reloads status
                # before reading its balance; its final read is a conservative
                # endpoint for the largest possible countdown. Keep the old
                # upper bound (approval cannot add more than the estimate).
                elapsed = (balances['observed_monotonic_ns'] - start) / 1e9
                require(balances['observed_monotonic_ns'] >= end
                        and estimate['estimate']['precision_seconds'] == 1,
                        'grant-effects:approval-read-bounds')
            require(0 <= elapsed <= 600 and expected - elapsed - precision <= grant
                    <= expected + precision, 'grant-effects:elapsed-grant')
        observed.setdefault('comparison', {}).update(
            grant_only_balance=True, saved_app_rules=True,
            **({'unchanged_saved_policy': True} if before is not None else {}),
            **({'positive_grant_with_elapsed_bounds': True} if mode == 'positive' else
               {'zero_grant': True}))
        self.effects_seen[stage] = deepcopy(value)
        self.balance = deepcopy(balances)


class RevocationJourney(KioskRequestJourney):
    """Fixed qualified grant/policy checks with caller-declared endpoints.

    Read checks declare (earlier invocation or None, cancel/confirm result).
    Window checks pair retained Parent observations; approval_stage captures the
    public estimate. Endpoint renaming does not qualify another account/profile.
    """

    def __init__(self, context, progress, plan, *, read_checks, window_checks,
                 approval_stage, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        require(all(stage in plan.screen_tags and mode in ('cancel', 'confirm')
                    and (before is None or before in plan.screen_tags
                         and plan.stages.index(before) < plan.stages.index(stage))
                    for stage, (before, mode) in read_checks.items()), 'revocation:read-plan')
        require(all(before in plan.screen_tags and stage in plan.screen_tags
                    and plan.screen_tags[before] == 'ui:retained-parent-leave'
                    and plan.screen_tags[stage] == 'ui:retained-parent-read'
                    and plan.stages.index(before) < plan.stages.index(stage)
                    for stage, before in window_checks.items()), 'revocation:window-plan')
        require(approval_stage is None or approval_stage in plan.screen_tags
                and plan.screen_tags[approval_stage] == 'ui:kiosk-valid-fraction-soft-read',
                'revocation:approval-plan')
        self.read_checks = dict(read_checks)
        self.window_checks = dict(window_checks)
        self.approval_stage = approval_stage
        self.revoke_reads = {}
        self.windows = {}
        self.grant_estimate = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.window_checks.values():
            require(stage not in self.windows, 'revoke-cancel:read-replay')
            self.windows[stage] = deepcopy(observed['ui']['retained_parent'])
        elif stage in self.window_checks:
            before = self.window_checks[stage]
            require(before in self.windows and
                    observed['ui']['retained_parent'] == self.windows[before],
                    'revoke-cancel:retained-parent')
        elif stage == self.approval_stage:
            self.grant_estimate = deepcopy(observed['ui']['valid_choice'])
        if stage not in self.read_checks:
            return
        capture, mode = self.read_checks[stage]
        require(stage not in self.revoke_reads, 'revoke-cancel:read-replay')
        value = observed['ui']['revoke_cancel']
        require(value['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                     'allowance': ['15 minutes']}, 'revoke-cancel:settings')
        balances = value['balances']
        start, end = value['read_bounds']
        require(type(start) is int and type(end) is int and 0 < start <= end,
                'revoke-cancel:read-bounds')
        daily, grant, total = (balances[key]['seconds'] for key in ('daily', 'one_time', 'total'))
        precision = max(balances[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
        require((abs(daily - 900) < precision if capture is None or mode == 'cancel' else daily >= 0)
                and (grant > 0 if capture is None or mode == 'cancel' else grant == 0)
                and abs(total - max(daily, grant)) < precision, 'revoke-cancel:real-grant')
        if capture is None:
            require(self.grant_estimate is not None, 'revoke-cancel:missing-approval')
            elapsed = (balances['observed_monotonic_ns'] -
                       self.grant_estimate['observed_monotonic_ns']) / 1e9
            expected = self.grant_estimate['estimate']['seconds']
            require(0 <= elapsed <= 600 and expected - elapsed - precision <= grant <= expected + precision,
                    'revoke-cancel:approved-balance')
        else:
            earlier = self.revoke_reads.get(capture)
            require(earlier is not None, 'revoke-cancel:missing-baseline')
            require(value['settings'] == earlier['settings'], 'revoke-cancel:changed-settings')
            if mode == 'confirm':
                require(value['apps'] == earlier['apps'] and value['rules'] == earlier['rules'],
                        'revocation:changed-app-rules')
            minimum = (start - earlier['read_bounds'][1]) / 1e9
            maximum = (end - earlier['read_bounds'][0]) / 1e9
            require(0 <= minimum <= maximum <= 120, 'revoke-cancel:elapsed-bound')
            for key in ('daily', 'one_time', 'total'):
                if mode == 'confirm' and key == 'one_time':
                    continue
                baseline_key = 'daily' if mode == 'confirm' and key == 'total' else key
                old, new = earlier['balances'][baseline_key], balances[key]
                tolerance = old['precision_seconds'] + new['precision_seconds']
                require(max(0, old['seconds'] - maximum) - tolerance <= new['seconds']
                        <= old['seconds'] + tolerance, 'revoke-cancel:changed-balance')
            observed.setdefault('comparison', {}).update(unchanged_settings=True)
            if mode == 'confirm':
                observed['comparison'].update(grant_cleared=True, unchanged_app_rules=True,
                                             unchanged_daily_with_elapsed_bounds=True)
            else:
                observed['comparison']['unchanged_balances_with_elapsed_bounds'] = True
        self.revoke_reads[stage] = deepcopy(value)
