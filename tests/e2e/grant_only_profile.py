"""Two-minute FLOW13 and independently restored explicit revoke-first entry."""

from copy import deepcopy
import time

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import grant_only_time_profile, revocation_entry, fresh_desktop
from journey_checks import check_balances, require_zero_grant
from private_artifacts import EvidenceError, require
from request_flow import CHOICES


def plan(*, revoke_first):
    screens = {
        **(revocation_entry(**CHOICES) if revoke_first else {}),
        **grant_only_time_profile(source='desktop' if revoke_first else 'gdm',
            entry='same-user' if revoke_first else 'fresh',
            window='retained' if revoke_first else 'new', initial_enabled=revoke_first,
            revoke_first=revoke_first, duration_seconds=120,
            request_initial='selected' if revoke_first else 'default'),
    }
    logins = {'': 'parent-login', 'profile-return-': 'profile-return'}
    if revoke_first:
        logins['return-'] = 'return'
    login_stages = {prefix + stage for prefix in logins for stage in fresh_desktop('parent')}
    return JourneyPlan(
        prefix='grant-only-profile',
        worker_mode='grant_only_revoke' if revoke_first else 'grant_only_profile', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
                **{stage: 'step-1' for stage in screens if stage != 'installed-greeter'}},
        invocations=tuple(stage for stage in screens if stage in login_stages),
        challenges={identity: ('parent', prefix + 'recipient-qualified', prefix + 'recipient-rechecked')
                    for prefix, identity in logins.items()},
        assertions_after={'profile-balance': 'zero-daily-positive-two-minute-grant'},
    )


PLAN = plan(revoke_first=False)
REVOKE_PLAN = plan(revoke_first=True)


class GrantOnlyProfileJourney(InstalledJourney):
    def __init__(self, context, progress, *, revoke_first=False):
        super().__init__(context, progress, REVOKE_PLAN if revoke_first else PLAN)
        self.revoke_first = revoke_first
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
                                         'allowance': ['0 minutes']}, 'time-profile:saved-zero-daily')
            require(self.approval_started is not None, 'time-profile:missing-approval')
            elapsed = (time.monotonic_ns() - self.approval_started) / 1_000_000_000
            daily, grant, total = (balances[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(balances[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            require(daily == 0 and 0 < grant <= 120 and grant > 120 - elapsed - precision - 2
                    and abs(total - grant) < precision, 'time-profile:grant-only-balances')
            observed['comparison'] = {'zero_daily_positive_grant': True, 'duration_seconds': 120}
