"""Reusable public-result checks, run before a journey acknowledges input."""

from private_artifacts import require
from ui_observations import AppRowsObservation


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
