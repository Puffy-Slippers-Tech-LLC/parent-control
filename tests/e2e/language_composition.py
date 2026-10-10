"""Reusable public language checks and run-owned offline history actions.

Recipes own literals, comparison endpoints and elapsed budgets. The guarded
recorder and shared Internet owner retain transport, evidence and cleanup.
"""
from copy import deepcopy
from functools import partial

from installed_journey import InstalledJourney
from private_artifacts import require
from vm_internet import InternetIsolation, restore
from vm_internet_qualification import internet_result
from watch_activity import operation


class PublicLanguageJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, actions=None, checks=None):
        super().__init__(context, progress, plan, actions=actions)
        self.checks = dict(checks or {})
        require(set(self.checks) <= set(plan.screen_tags)
                and all(callable(check) for check in self.checks.values()), 'language:checks')
        self.public_captures = {}
        self.checked_stages = set()

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.checks:
            require(stage not in self.checked_stages, 'language:check-replay')
            self.checks[stage](self, observed)
            self.checked_stages.add(stage)


def language_journey(*, checks):
    return partial(PublicLanguageJourney, checks=dict(checks))


def public_language_value(key, expected, *, capture=None, same=None):
    """Literal public comparison with optional immutable caller-named endpoints."""
    require(key in ('language', 'language_form', 'dialog_presentation', 'feedback'), 'language:public-key')
    require(not (capture and same), 'language:public-endpoints')
    return partial(_public_value, key=key, expected=deepcopy(expected), capture=capture, same=same)


def _public_value(journey, observed, *, key, expected, capture, same):
    value = observed['ui'].get(key)
    require(value == expected, journey.plan.prefix + ':public-' + key)
    if same:
        require(same in journey.public_captures, 'language:missing-public-capture')
        require(value == journey.public_captures[same], 'language:public-preservation')
    if capture:
        require(capture not in journey.public_captures, 'language:capture-replay')
        journey.public_captures[capture] = deepcopy(value)


def language_policy(expected, *, capture=None, same=None, max_elapsed_seconds,
                    labels=(), absent_labels=(), app_names_capture=None, app_names_same=None):
    require(bool(capture) != bool(same) and type(max_elapsed_seconds) is int
            and 0 < max_elapsed_seconds <= 3600, 'language:policy-plan')
    require(not (app_names_capture and app_names_same)
            and all(endpoint is None or isinstance(endpoint, str) and endpoint
                    and endpoint not in (capture, same)
                    for endpoint in (app_names_capture, app_names_same)),
            'language:app-name-plan')
    return partial(_language_policy, expected=deepcopy(expected), capture=capture,
                   same=same, max_elapsed_seconds=max_elapsed_seconds,
                   labels=tuple(labels), absent_labels=tuple(absent_labels),
                   app_names_capture=app_names_capture, app_names_same=app_names_same)


def _language_policy(journey, observed, *, expected, capture, same, max_elapsed_seconds,
                     labels, absent_labels, app_names_capture, app_names_same):
    value = observed['ui']['language_state']
    require(all(value.get(key) == item for key, item in expected.items()),
            journey.plan.prefix + ':policy-values')
    require(set(labels) <= set(value['management_labels'])
            and not set(absent_labels) & set(value['management_labels']), 'language:management-labels')
    saved = {key: value[key] for key in ('child', 'account_name', 'limit_enabled',
        'allowance_minutes', 'rows', 'app_names')}
    balances = value['balances']
    require(balances['child'] == value['child'] and balances['one_time']['seconds'] == 0
            and balances['daily']['seconds'] == balances['total']['seconds']
            and 0 < balances['daily']['seconds'] <= value['allowance_minutes'] * 60,
            journey.plan.prefix + ':zero-grant-daily')
    if capture:
        require(capture not in journey.public_captures, 'language:capture-replay')
        journey.public_captures[capture] = deepcopy((saved, balances))
    else:
        require(same in journey.public_captures, 'language:missing-policy')
        prior, baseline = journey.public_captures[same]
        # App IDs and rules remain exact across languages. Desktop-entry names
        # follow Parent's language (ONPC-CORE-APPS-002); callers may declare a
        # separate immutable name endpoint for each language in their history.
        keys = saved.keys() - {'app_names'} if app_names_capture or app_names_same else saved.keys()
        require(all(saved[key] == prior[key] for key in keys),
                journey.plan.prefix + ':policy-preservation')
        elapsed = (balances['observed_monotonic_ns'] - baseline['observed_monotonic_ns']) / 1e9
        decrease = baseline['daily']['seconds'] - balances['daily']['seconds']
        require(0 <= elapsed <= max_elapsed_seconds and -2 <= decrease <= elapsed + 2,
                journey.plan.prefix + ':balance-preservation')
    if app_names_capture:
        require(app_names_capture not in journey.public_captures, 'language:capture-replay')
        journey.public_captures[app_names_capture] = deepcopy(value['app_names'])
    elif app_names_same:
        require(app_names_same in journey.public_captures, 'language:missing-app-names')
        require(value['app_names'] == journey.public_captures[app_names_same],
                journey.plan.prefix + ':app-name-preservation')


def enter_offline(journey, guard):
    with operation('Confirming Internet isolation before changing personal languages'):
        require(not hasattr(journey, 'online_before'), 'language:offline-replay')
        guard()
        journey.online_before = internet_result(journey.transport)
        # A live path proves the subsequent isolation; unrelated provider
        # outages do not prevent testing local language and policy behavior.
        require(any(probe['reachable'] for probe in journey.online_before['probes']), 'language:online-entry')
        InternetIsolation(journey.context.lease).enter(journey.transport)
        guard()
        offline = internet_result(journey.transport)
        require(offline['ipv6_default_route'] == journey.online_before['ipv6_default_route']
                and not any(probe['reachable'] for probe in offline['probes']), 'language:offline-result')
        return {'online_entry': journey.online_before, 'offline': offline}


def leave_offline(journey, guard):
    with operation('Restoring Internet and independently confirming recovery'):
        require(hasattr(journey, 'online_before') and not hasattr(journey, 'online_after'),
                'language:recovery-entry')
        guard()
        restore(journey.context.lease)
        guard()
        journey.online_after = internet_result(journey.transport)
        # The probe reader validates the fixed endpoint order for this route
        # state. Restore every working path; an unavailable path may recover.
        require(journey.online_after['ipv6_default_route'] == journey.online_before['ipv6_default_route']
                and all(not before['reachable'] or after['reachable']
                        for before, after in zip(journey.online_before['probes'],
                                                 journey.online_after['probes'], strict=True)),
                'language:online-recovery')
        return {'online_recovery': journey.online_after}


def offline_language_actions():
    # Partial/failure recovery belongs to the lease's existing Internet journal.
    return {'language-offline': enter_offline, 'language-online': leave_offline}
