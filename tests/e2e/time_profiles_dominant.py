"""FLOW13 daily dominance preserves the original grant through a policy save."""
from copy import deepcopy

from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan
from journey_blocks import daily_dominant_time_profile, fresh_desktop, prefixed_stages
from private_artifacts import require
from request_flow import prepared_request
from ui_observations import SettingsObservation


SCREENS = {
    **daily_dominant_time_profile(grant_seconds=600, daily_minutes=20),
    **prefixed_stages('request', prepared_request(prefix='new', entry='new',
        initial='observed', child='fixture-child', approver='fixture-parent',
        duration_seconds=75, allow_soft=False)),
    'request-cancel': 'ui:kiosk-request-cancel',
    'request-gdm': 'ui:gdm-station-returned',
}
LOGIN_STAGES = {prefix + stage for prefix in ('', 'profile-return-')
                for stage in fresh_desktop('parent')}
PLAN = JourneyPlan(
    prefix='time-profiles-dominant', worker_mode='time_profiles_dominant',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={name: ('parent', prefix + 'recipient-qualified', prefix + 'recipient-rechecked')
                for name, prefix in (('parent-login', ''), ('profile-return', 'profile-return-'))},
    kiosk_request=('child', 'parent', 75, False),
    settings_checks={'dominant-settings': SettingsObservation('fixture-child', True, ('20 minutes',))},
    assertions_after={'dominant-configured': 'daily-dominant-original-grant',
                      'request-new-estimate': 'daily-dominant-request-estimate'},
)


class DailyDominantProfileJourney(GrantOnlyProfileJourney):
    """Caller-owned operands and read brackets, never a renewed grant deadline."""
    def __init__(self, context, progress, plan=PLAN, *, grant_seconds=600,
                 daily_minutes=20, actions=None):
        require((grant_seconds, daily_minutes) in ((600, 20), (1200, 40)),
                'time-profile:daily-dominant-binding')
        super().__init__(context, progress, plan, grant_seconds=grant_seconds, actions=actions)
        self.dominant_minutes = daily_minutes
        self.original_grant = None
        self.parent_balance = None

    @staticmethod
    def elapsed(before, after):
        low, high = (after[0] - before[1]) / 1e9, (after[1] - before[0]) / 1e9
        require(0 <= low <= high <= 600, 'time-profile:daily-dominant-elapsed')
        return low, high

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        ui = observed.get('ui', {})
        if stage == 'profile-request-new-estimate':
            choice = ui['valid_choice']
            require(choice['request']['child'] == 'fixture-child'
                    and choice['request']['duration_seconds'] == self.grant_seconds
                    and choice['estimate']['kind'] == 'fixed'
                    and choice['estimate']['seconds'] == self.grant_seconds,
                    'time-profile:daily-dominant-setup-estimate')
        if stage == 'profile-balance':
            self.original_grant = (deepcopy(ui['revoke_cancel']['balances']), tuple(self.ui.read_bounds))
        if stage == 'dominant-configured':
            require(self.original_grant is not None, 'time-profile:missing-original-grant')
            before, bounds = self.original_grant
            balance = ui['time_explanation']
            low, high = self.elapsed(bounds, tuple(self.ui.read_bounds))
            daily, grant, total = (balance[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            margin = precision + before['one_time']['precision_seconds'] + 2
            require(balance['child'] == before['child'] == 'fixture-child'
                    and 0 < daily <= self.dominant_minutes * 60
                    and before['one_time']['seconds'] - high - margin <= grant
                        <= before['one_time']['seconds'] - low + margin
                    and grant - precision >= 300 and daily - grant - 2 * precision > 90
                    and abs(total - daily) <= precision,
                    'time-profile:daily-dominant-parent')
            self.parent_balance = (deepcopy(balance), tuple(self.ui.read_bounds))
            observed['comparison'] = {'daily_dominant_original_grant': True,
                'elapsed_interval_seconds': [low, high], 'rounding_margin_seconds': margin}

    def check_request_time(self, choice, bounds, *, additional_seconds):
        """Reuse at a consumer's estimate; elapsed use must not reverse D>G>0."""
        require(self.parent_balance is not None, 'time-profile:missing-dominant-parent')
        balance, earlier = self.parent_balance
        low, high = self.elapsed(earlier, bounds)
        daily, grant = (balance[key]['seconds'] for key in ('daily', 'one_time'))
        precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time')) + 2
        request = choice['request']
        require(request['child'] == balance['child']
                and request['duration_seconds'] == additional_seconds
                and choice['estimate']['kind'] == 'fixed', 'time-profile:dominant-request-binding')
        # The estimate is an independent later public endpoint. Its base is D
        # only if the original grant's upper bound remains below D's lower bound.
        grant_low, grant_high = grant - high - precision, grant - low + precision
        daily_low = daily - high - precision
        base = choice['estimate']['seconds'] - additional_seconds
        require(grant_low >= 300 and daily_low - grant_high > 90
                and daily_low <= base <= daily + precision
                and base - choice['estimate']['precision_seconds'] - grant_high > 90,
                'time-profile:daily-dominant-request')
        return {'daily_dominant_at_request': True, 'elapsed_interval_seconds': [low, high],
                'original_grant_lower_seconds': grant_low, 'original_grant_upper_seconds': grant_high,
                'estimate_base_seconds': base}

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'request-new-estimate':
            observed['comparison'] = self.check_request_time(
                observed['ui']['valid_choice'], tuple(self.ui.read_bounds), additional_seconds=75)
