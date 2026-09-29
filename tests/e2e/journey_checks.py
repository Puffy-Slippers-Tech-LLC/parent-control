"""Reusable public-result checks, run before a journey acknowledges input."""

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
