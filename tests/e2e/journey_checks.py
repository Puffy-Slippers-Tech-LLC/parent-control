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


class RetainedSessionJourney(AllowanceJourney):
    """Compare caller-declared locked-session endpoints before durable replies."""

    def __init__(self, context, progress, plan, *, session_checks, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        stages = list(plan.screen_tags)
        require(type(session_checks) is dict and bool(session_checks)
                and all(earlier in stages and later in stages
                        and stages.index(earlier) < stages.index(later)
                        and plan.screen_tags[earlier] == plan.screen_tags[later]
                        == 'system:child-retained-locked'
                        for later, earlier in session_checks.items()),
                'retained-session:comparison-plan')
        self.session_checks = dict(session_checks)
        self.session_observations = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in self.session_checks and stage not in self.session_checks.values():
            return
        require(stage not in self.session_observations, 'retained-session:observation-replay')
        value = observed.get('system', {})
        import re
        identity = value.get('session_sha256')
        require(value.get('operation') == 'child-retained-locked'
                and value.get('outcome') == 'passed' and value.get('locked') is True
                and type(identity) is str and re.fullmatch(r'[0-9a-f]{64}', identity),
                'retained-session:observation')
        if stage in self.session_checks:
            earlier = self.session_checks[stage]
            require(earlier in self.session_observations, 'retained-session:missing-observation')
            require(identity == self.session_observations[earlier], 'retained-denial:session-replaced')
            observed['comparison'] = {'same_retained_locked_child': True}
        # Store the immutable public identity, never the decoder's mutable reply.
        self.session_observations[stage] = identity


class RetainedDesktopJourney(InstalledJourney):
    """Caller-declared Parent/window/session comparisons before durable replies."""

    def __init__(self, context, progress, plan, *, parent_expected, parent_checks,
                 window_checks, session_checks, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        stages = list(plan.screen_tags)
        parents = set(parent_expected) | set(parent_checks)
        require(bool(parent_expected) and not set(parent_expected) & set(parent_checks)
                and all(stage in stages and
                plan.screen_tags[stage] in ('ui:retained-parent-leave', 'ui:retained-parent-read')
                for stage in parents), 'retained-parent:comparison-plan')
        for checks in (parent_checks, window_checks, session_checks):
            for later, earlier in checks.items():
                require(earlier in stages and later in stages and
                        stages.index(earlier) < stages.index(later), 'retained-desktop:comparison-plan')
        require(all(earlier in parent_expected for earlier in parent_checks.values())
                and all(earlier in parent_expected and plan.screen_tags[later] in (
                    'ui:switch-parent-before', 'ui:switch-parent-ready', 'ui:switch-parent')
                    for later, earlier in window_checks.items()), 'retained-parent:comparison-plan')
        session_roles = {'system:parent-desktop-identity': 'parent',
                         'system:child-retained-locked': 'child',
                         **{'system:' + role + '-entry-' + mode: role
                            for role in ('parent', 'child', 'standard')
                            for mode in ('same', 'retained', 'lock', 'refusals')}}
        require(all(plan.screen_tags[stage] in session_roles for stage in
                    set(session_checks) | set(session_checks.values()))
                and all(session_roles[plan.screen_tags[later]] == session_roles[plan.screen_tags[earlier]]
                        for later, earlier in session_checks.items()), 'retained-session:comparison-plan')
        self.parent_expected = deepcopy(parent_expected)
        self.parent_checks = dict(parent_checks)
        self.window_checks = dict(window_checks)
        self.session_checks = dict(session_checks)
        self.parents = {}
        self.sessions = {}
        self.compared = set()

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in (set(self.parent_expected) | set(self.parent_checks) |
                     set(self.window_checks) | set(self.session_checks) | set(self.session_checks.values())):
            require(stage not in self.compared, 'retained-desktop:observation-replay')
            self.compared.add(stage)
        if stage in self.parent_expected:
            value = observed['ui']['retained_parent']
            require({key: value[key] for key in ('page', 'settings')} == self.parent_expected[stage],
                    'retained-parent:initial-settings')
            self.parents[stage] = deepcopy(value)
        elif stage in self.parent_checks:
            earlier = self.parent_checks[stage]
            require(earlier in self.parents and observed['ui']['retained_parent'] == self.parents[earlier],
                    'retained-parent:window-child-page-settings-changed')
            observed.setdefault('comparison', {})['same_parent_window_child_page_settings'] = True
        elif stage in self.window_checks:
            earlier = self.window_checks[stage]
            require(earlier in self.parents and observed['ui']['window'] == self.parents[earlier]['window'],
                    'retained-parent:foreground-window-replaced')
        if stage in self.session_checks or stage in self.session_checks.values():
            import re
            value = observed.get('system', {})
            identity = value.get('session_sha256')
            require(value.get('operation') == self.plan.screen_tags[stage][7:]
                    and value.get('outcome') == 'passed' and type(identity) is str
                    and re.fullmatch(r'[0-9a-f]{64}', identity), 'retained-session:observation')
            if stage in self.session_checks:
                earlier = self.session_checks[stage]
                require(earlier in self.sessions and identity == self.sessions[earlier],
                        'retained-desktop:session-replaced')
                result = ('same_parent_desktop' if value['operation'] == 'parent-desktop-identity' else
                          'same_retained_locked_child' if value['operation'] == 'child-retained-locked' else
                          'same_retained_child_desktop')
                observed.setdefault('comparison', {})[result] = True
            self.sessions[stage] = identity


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
