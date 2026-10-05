"""Reusable public-result checks, run before a journey acknowledges input."""

from copy import deepcopy
from functools import partial

from private_artifacts import require
from ui_observations import AppRowsObservation


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
