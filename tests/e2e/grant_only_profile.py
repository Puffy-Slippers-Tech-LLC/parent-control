"""FLOW13 grant-only/combined and independently restored revoke-first entry."""

from copy import deepcopy
import time

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import grant_only_time_profile, revocation_entry, fresh_desktop
from journey_checks import check_balances, require_zero_grant
from private_artifacts import EvidenceError, require
from request_flow import CHOICES


def plan(*, revoke_first, daily_minutes=0):
    screens = {
        **(revocation_entry(**CHOICES) if revoke_first else {}),
        **grant_only_time_profile(source='desktop' if revoke_first else 'gdm',
            entry='same-user' if revoke_first else 'fresh',
            window='retained' if revoke_first else 'new', initial_enabled=revoke_first,
            revoke_first=revoke_first, duration_seconds=1200,
            request_initial='selected' if revoke_first else 'default', daily_minutes=daily_minutes),
    }
    logins = {'': 'parent-login', 'profile-return-': 'profile-return'}
    if revoke_first:
        logins['return-'] = 'return'
    login_stages = {prefix + stage for prefix in logins for stage in fresh_desktop('parent')}
    return JourneyPlan(
        prefix='time-profiles-grant' if daily_minutes else 'grant-only-profile',
        worker_mode='time_profiles_grant' if daily_minutes else
                    'grant_only_revoke' if revoke_first else 'grant_only_profile', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
                **{stage: 'step-1' for stage in screens if stage != 'installed-greeter'}},
        invocations=tuple(stage for stage in screens if stage in login_stages),
        challenges={identity: ('parent', prefix + 'recipient-qualified', prefix + 'recipient-rechecked')
                    for prefix, identity in logins.items()},
        assertions_after={'profile-balance': 'positive-daily-grant-dominant' if daily_minutes else
                          'zero-daily-positive-grant'},
    )


PLAN = plan(revoke_first=False)
REVOKE_PLAN = plan(revoke_first=True)
COMBINED_PLAN = plan(revoke_first=False, daily_minutes=4)


class GrantOnlyProfileJourney(InstalledJourney):
    def __init__(self, context, progress, plan=None, *, revoke_first=False, daily_minutes=0,
                 grant_seconds=1200, actions=None):
        super().__init__(context, progress, plan if plan is not None else
                         COMBINED_PLAN if daily_minutes else REVOKE_PLAN if revoke_first else PLAN,
                         actions=actions)
        self.revoke_first = revoke_first
        self.daily_minutes = daily_minutes
        require(type(grant_seconds) is int and grant_seconds in (120, 180, 240, 600, 1200),
                'time-profile:grant-duration')
        self.grant_seconds = grant_seconds
        self.daily_before_approval = None
        self.windows = {}
        self.approval_started = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            check_balances(self, observed, 900)
        if stage in ('before-window', 'profile-window'):
            self.windows[stage] = deepcopy(observed['ui']['retained_parent'])
        for later, earlier in (('supplied-parent-retained', 'before-window'),
                               ('profile-result-parent-retained', 'profile-window')):
            if stage == later:
                require(observed['ui']['retained_parent'] == self.windows[earlier],
                        'time-profile:retained-parent')
        if stage == 'profile-request-approval-open':
            self.approval_started = time.monotonic_ns()
        if stage == 'profile-zero':
            check_balances(self, observed, 0)
        if stage == 'profile-daily':
            # An allowance is a daily total, not a new bank. Carry the actual
            # displayed remainder (and its precision) into the grant comparison.
            balances = observed['ui']['time_explanation']
            require_zero_grant(balances)
            daily = balances['daily']
            require(0 < daily['seconds'] <= self.daily_minutes * 60
                    and abs(balances['total']['seconds'] - daily['seconds'])
                        < max(balances['total']['precision_seconds'], daily['precision_seconds']),
                    'time-profile:positive-daily-before-approval')
            self.daily_before_approval = deepcopy(daily)
            observed['comparison'] = {'positive_daily_zero_grant': True,
                                      'daily_seconds': daily['seconds']}
        if stage not in ('profile-before', 'profile-cleared', 'profile-balance'):
            return
        value = observed['ui']['revoke_cancel']
        balances = value['balances']
        if stage == 'profile-before' and self.revoke_first:
            require(balances['one_time']['seconds'] > 0, 'time-profile:missing-existing-grant')
            # Exercise the same undeclared-grant gate against this actual public
            # observation before the explicitly declared Confirm branch runs.
            try:
                require_zero_grant(balances)
            except EvidenceError as error:
                require(str(error) == 'time-profile:unexpected-grant', 'time-profile:refusal')
            else:
                require(False, 'time-profile:undeclared-grant-accepted')
            observed['comparison'] = {'undeclared_existing_grant_refused': True}
        elif stage != 'profile-balance':
            require_zero_grant(balances)
            observed['comparison'] = {'zero_grant_before_edits': True,
                                      'explicit_revoke': self.revoke_first}
        else:
            require(value['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                         'allowance': [f'{self.daily_minutes} minutes']},
                    'time-profile:saved-daily-allowance')
            require(self.approval_started is not None, 'time-profile:missing-approval')
            elapsed = (time.monotonic_ns() - self.approval_started) / 1_000_000_000
            daily, grant, total = (balances[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(balances[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            if self.daily_minutes:
                require(self.daily_before_approval is not None, 'time-profile:missing-daily-baseline')
                baseline = self.daily_before_approval
                margin = precision + baseline['precision_seconds'] + 2
                # G replaces max(D,G) plus the addition and keeps elapsing while
                # the parent returns. Total is max(D,G), never their sum.
                expected = baseline['seconds'] + self.grant_seconds
                require(grant > daily > 0 and grant - daily > precision
                        and abs(daily - baseline['seconds']) < margin
                        and expected - elapsed - margin < grant <= expected + margin
                        and abs(total - grant) < precision, 'time-profile:combined-balances')
                observed['comparison'] = {'positive_daily_grant_dominant': True,
                    'daily_before_approval_seconds': baseline['seconds'],
                    'additional_seconds': self.grant_seconds, 'elapsed_seconds': elapsed,
                    'rounding_margin_seconds': margin}
            else:
                require(daily == 0 and 0 < grant <= self.grant_seconds
                        and grant > self.grant_seconds - elapsed - precision - 2
                        and abs(total - grant) < precision, 'time-profile:grant-only-balances')
                observed['comparison'] = {'zero_daily_positive_grant': True,
                                          'duration_seconds': self.grant_seconds}
