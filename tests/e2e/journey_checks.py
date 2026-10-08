"""Reusable public-result checks, run before a journey acknowledges input."""

from copy import deepcopy
from functools import partial

from private_artifacts import require
from ui_observations import AppRowsObservation
from installed_journey import InstalledJourney


def check_balances(journey, observed, expected_seconds=900):
    """Compare a fresh unused child's public daily, grant and total balances."""
    value = observed['ui']['time_explanation']
    require(all(abs(value[key]['seconds'] - expected) < value[key]['precision_seconds']
                for key, expected in zip(('daily', 'one_time', 'total'),
                                         (expected_seconds, 0, expected_seconds))),
            'time-explanation:ordinary-balances')
    earlier = getattr(journey, 'earlier_time_observation', None)
    if earlier is not None:
        require(value['observed_monotonic_ns'] > earlier, 'time-explanation:observation-order')
    journey.earlier_time_observation = value['observed_monotonic_ns']
    observed['comparison'] = {'ordinary_balances': True, 'independent_read': earlier is not None}


class AllowanceJourney(InstalledJourney):
    """Compare caller-declared saved balances before each keyboard reply."""

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.plan.balance_checks:
            check_balances(self, observed, self.plan.balance_checks[stage])


def allowed_app_rows(journey, observed):
    """Require a complete nonempty Allowed collection; return immutable rows."""
    rows = AppRowsObservation.from_rows(observed['ui']['apps']['rows'])
    require(bool(rows.rows) and all(row[1] == 'allowed' for row in rows.rows),
            journey.plan.prefix + ':initial-allowed')
    observed['comparison'] = {'initial_allowed': True, 'row_count': len(rows.rows)}
    return rows


def installed_accounts(journey, observed):
    """Independently read preserved personal accounts and the installed station."""
    observed['accounts'] = journey.ui.observe('gdm-installed-accounts')


def access_choice(app, choice):
    """Bind an independent exact app/access oracle to a public row read."""
    return partial(_access_choice, app=app, choice=choice)


def _access_choice(journey, observed, *, app, choice):
    require(observed['ui'].get('access') == {'app': app, 'choice': choice},
            journey.plan.prefix + ':app-rule')


def policy_projection(settings, *, row, capture=None, same=None, grant=None):
    """Compare saved public policy separately from naturally changing balances."""
    require(not (capture and same) and grant in (None, 'positive', 'zero'),
            'policy:comparison-plan')
    return partial(_policy_projection, settings=deepcopy(settings), row=tuple(row),
                   capture=capture, same=same, grant=grant)


def _policy_projection(journey, observed, *, settings, row, capture, same, grant):
    policy = observed['ui']['language_policy']
    require(policy['settings'] == settings and any(tuple(item[:2]) == row for item in policy['rows']),
            journey.plan.prefix + ':policy')
    saved = {key: policy[key] for key in ('settings', 'rows')}
    captures = journey.public_captures
    if same:
        require(same in captures and saved == captures[same], journey.plan.prefix + ':retained-policy')
    if grant is not None:
        require(policy['balances']['one_time'] > 0 if grant == 'positive' else
                policy['balances']['one_time'] == 0, journey.plan.prefix + ':grant')
    if capture:
        require(capture not in captures, 'policy:capture-replay')
        captures[capture] = deepcopy(saved)


def request_choices(expected, *, capture=None, same=None):
    """Compare caller-declared shared choices while preserving extra UI fields."""
    require(not (capture and same) and bool(expected), 'request:comparison-plan')
    return partial(_request_choices, expected=deepcopy(expected), capture=capture, same=same)


def _request_choices(journey, observed, *, expected, capture, same):
    request = observed['ui']['valid_choice']['request']
    choices = {key: request[key] for key in expected}
    require(choices == expected, journey.plan.prefix + ':request-choices')
    captures = journey.public_captures
    if same:
        require(same in captures and choices == captures[same], journey.plan.prefix + ':retained-request')
    if capture:
        require(capture not in captures, 'request:capture-replay')
        captures[capture] = deepcopy(choices)


def checked_language(expected):
    """Compare a complete literal public chooser result supplied by the recipe."""
    return partial(_checked_language, expected=deepcopy(expected))


def _checked_language(journey, observed, *, expected):
    require(observed['ui']['language'] == expected, journey.plan.prefix + ':checked-language')


def approval_estimate(*, capture=None, same=None):
    """Capture the public fixed request estimate, or compare its approved balance."""
    require(bool(capture) != bool(same), 'approval:estimate-plan')
    return partial(_approval_estimate, capture=capture, same=same)


def _approval_estimate(journey, observed, *, capture, same):
    captures = journey.public_captures
    if capture:
        value = observed['ui']['valid_choice']['estimate']
        require(value['kind'] == 'fixed' and value['seconds'] >= 75,
                journey.plan.prefix + ':approval-estimate')
        require(capture not in captures, 'approval:capture-replay')
        captures[capture] = deepcopy(value)
    else:
        require(same in captures, 'approval:missing-estimate')
        balances = observed['ui']['language_policy']['balances']
        require(balances['daily'] == 0 and balances['total'] == balances['one_time']
                and 0 < balances['one_time'] <= captures[same]['seconds'],
                journey.plan.prefix + ':approved-balance')


def restart_instructions(surface, texts):
    """Bind literal installation-neutral instructions to a fresh public modal."""
    require(surface in ('parent', 'overlay', 'kiosk') and type(texts) is dict
            and set(texts) == {'update-required-message', 'update-required-close', 'update-required-reboot'}
            and all(type(text) is str and bool(text) for text in texts.values()),
            'restart:comparison-plan')
    return partial(_restart_instructions, surface=surface, texts=deepcopy(texts))


def _restart_instructions(journey, observed, *, surface, texts):
    require(observed.get('ui', {}).get('restart') == {
        'surface': surface, 'texts': texts, 'modal': True, 'policy_blocked': True},
        journey.plan.prefix + ':installed-instructions')


def public_checks(*checks):
    """Run independent declared public comparisons before the durable reply."""
    require(bool(checks) and all(callable(check) for check in checks), 'journey:public-checks')
    return partial(_public_checks, checks=checks)


def _public_checks(journey, observed, *, checks):
    for check in checks:
        check(journey, observed)
