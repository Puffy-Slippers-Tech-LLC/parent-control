"""247/248: two homework/game cycles with retained or fresh child departures."""
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from accessible_ui import (GDM_DENIAL_OPERATIONS, KIOSK_BOUND_OPERATIONS, MATCH_APPS, MATCH_RULES, PRESET_LABELS,
                           NAMED_CHILD_OPERATIONS, OVERLAY_BOUND_OPERATIONS,
                           countdown_seconds)
from child_saved_work import work_document_actions
from calendar_fixture import preset_ordinary_daytime
from countdown import CountdownSample
from feedback_composition import text_fragment
from game_permission import APPS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (allowance_selection, app_policy_entry, custom_allowance,
                            desktop_entry, fresh_desktop, game_usable_app, overlay_entry,
                            parent_reopen, parent_selection, prefixed_stages, rejected_gdm_return,
                            station_entry)
from named_app_set import saved_rows
from natural_expiry_observation import await_natural_expiry
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney, policy_edit
from private_artifacts import require
from request_composition import _estimate_read_bounds
from request_flow import RequestFlowJourney, approval_and_return
from ui_observations import SettingsObservation


def build_plan(*, fresh=False):
    """Keep both histories in one composition, declaring each work lifetime."""
    # The declarations below are local to this binding, including remembered
    # choices and immutable activity comparisons.
    screens = app_policy_entry(child='existing', allowance=None, initial_rows=False)
    del screens['apps-page']
    screens.update({'initial-balance': 'ui:time-explanation-setup-zero-read',
                    'initial-settings': 'ui:existing-returned', 'apps-page': 'ui:existing-apps'})
    logins = set(fresh_desktop('parent'))
    challenges = {'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked')}
    texts, saves, activities, entries, overlays, kiosks, countdowns, requests = ({} for _ in range(8))
    settings = {'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
                'initial-settings': SettingsObservation('existing-fixture-child', True, ('0 minutes',))}
    for index, (app, draft, access) in enumerate(APPS):
        screens.update(policy_edit(app, draft, access, 'policy-' + str(index), setup=True))
    screens.update({**text_fragment('catalogue-clear', 'clear'), **saved_rows(APPS, 'saved'),
                    'setup-leave': 'ui:desktop', 'setup-switch': 'system:parent-switch-user',
                    'setup-gdm': 'ui:gdm-returned'})

    def entry(prefix, account, retained=False, expected='success', capture=None):
        result = prefixed_stages(prefix, desktop_entry(account, source='gdm',
            entry='retained' if retained else 'fresh', expected=expected))
        if retained and account == 'other-child' and expected == 'success':
            result[prefix + '-desktop'] = 'system:standard-desktop-identity'
        logins.update(stage for stage in result if not stage.endswith('entry-guard'))
        role = 'recipient' if account == 'parent' else 'child-recipient' if account == 'child' else 'standard-recipient'
        challenges[prefix] = (account, prefix + '-' + role + '-qualified', prefix + '-' + role + '-rechecked')
        if capture is not None:
            entries[prefix + '-entry-guard'] = capture
        return result

    def leave(prefix, account):
        role = 'standard' if account == 'other-child' else account
        action = 'logout' if fresh and account == 'other-child' else 'switch-user'
        return {prefix + '-leave': 'system:' + role + '-desktop-identity',
                prefix + '-switch': 'system:' + role + '-' + action, prefix + '-gdm': 'ui:gdm-returned'}

    def work(prefix, actions, text, prior='No submitted draft', who='jordan', capture=None, result='same'):
        fragment = {prefix + '-' + action: 'ui:work-' + who + '-' +
                    ('activity' if action == 'capture' else action) for action in actions}
        texts.update({stage: (text, prior) for stage in fragment})
        if 'saved' in actions:
            saves[prefix + '-saved-bytes'] = (who, text)
        if capture is not None:
            activities[prefix + '-capture'] = (capture, result)
        return fragment

    def reopen_work(prefix, text, capture):
        return work(prefix, ('open', 'opened', 'submit', 'submitted', 'capture'), text,
                    capture=capture, result='replaced')

    local_parents = {'overlay': 'other-parent', 'kiosk': 'other-parent'}
    last_seconds, last_soft = 1800, False

    def approval(prefix, surface, parent, seconds, soft, capture, *, recovery=False):
        nonlocal last_seconds, last_soft
        before = ('other-child', local_parents[surface], last_seconds, last_soft)
        bound = ('other-child', parent, seconds, soft)
        request = dict(child='existing-fixture-child',
            approver='fixture-parent' if parent == 'parent' else 'other-fixture-parent',
            duration_seconds=seconds, allow_soft=soft)
        if surface == 'overlay':
            fragment = {**prefixed_stages(prefix, overlay_entry('request', 'panel',
                form_operation='request-overlay-jordan-ready')),
                prefix + '-remembered': 'ui:overlay-request-read',
                **prefixed_stages(prefix, approval_and_return(prefix='new', entry='open',
                    surface=surface, **request))}
            overlays.update({stage: bound for stage, tag in fragment.items()
                             if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})
            overlays[prefix + '-remembered'] = before
        else:
            retained = not fresh or recovery
            child_entry = 'retained' if retained else 'fresh'
            flow = approval_and_return(prefix='new', entry='open', surface='kiosk',
                                       child_entry=child_entry, **request)
            if retained:
                flow['retained-desktop'] = 'system:standard-desktop-identity'
            fragment = {**prefixed_stages(prefix, station_entry('cancel-')),
                prefix + '-remembered-child': 'ui:kiosk-request-child',
                prefix + '-remembered': 'ui:kiosk-request-read', **prefixed_stages(prefix, flow)}
            kiosks.update({stage: bound for stage, tag in fragment.items()
                           if tag.removeprefix('ui:') in KIOSK_BOUND_OPERATIONS})
            kiosks[prefix + '-remembered'] = before
            entry_prefix = prefix + '-' + child_entry
            logins.update(prefixed_stages(entry_prefix, fresh_desktop('other-child')))
            challenges[entry_prefix] = ('other-child', entry_prefix + '-standard-recipient-qualified',
                                       entry_prefix + '-standard-recipient-rechecked')
            if retained:
                entries[entry_prefix + '-entry-guard'] = capture
        countdowns[prefix + '-countdown'] = (prefix + '-new-estimate', 'estimate', 1, 300)
        requests[prefix] = (surface, bound)
        local_parents[surface] = parent
        last_seconds, last_soft = seconds, soft
        return fragment

    def parent_return(prefix):
        return {**entry(prefix, 'parent', True), prefix + '-retained': 'ui:retained-parent-read'}

    def riley_visit(prefix):
        return {**entry(prefix, 'child', True, capture='riley-work-capture'),
            **work(prefix + '-work', ('capture', 'resubmit', 'submitted'),
                   'Riley saved synthetic work', who='riley', capture='riley-work-capture')}

    screens.update({**entry('riley-initial', 'child'),
        **work('riley-work', ('open', 'opened', 'edit', 'save', 'saved', 'submit', 'submitted', 'capture'),
               'Riley saved synthetic work', who='riley'), **leave('riley-initial', 'child')})
    prior_work = 'No submitted draft'
    for cycle, mode in ((1, 'windowed'), (2, 'fullscreen')):
        root = 'cycle-' + str(cycle)
        homework, resumed = 'homework cycle ' + str(cycle), 'work again cycle ' + str(cycle)
        first_parent, second_parent = (('parent', 'other-parent') if cycle == 1 else ('other-parent', 'parent'))
        work_capture = root + '-homework-capture'
        screens.update({**parent_return(root + '-daily-parent'),
            **allowance_selection(root + '-daily', (60 * cycle,)),
            root + '-daily-settings': 'ui:existing-returned', root + '-daily-balance': 'ui:time-explanation-refresh-read',
            **leave(root + '-daily-parent', 'parent'),
            **entry(root + '-entry', 'other-child', cycle == 2 and not fresh,
                    capture='cycle-1-final-work-capture' if cycle == 2 and not fresh else None)})
        if fresh and cycle == 2:
            screens.update(reopen_work(root + '-reopened', prior_work, 'cycle-1-final-work-capture'))
        screens.update({**work(root + '-homework',
                (*(('open', 'opened') if cycle == 1 else ()), 'edit', 'save', 'saved', 'submit', 'submitted', 'capture'),
                homework, prior_work),
            root + '-daily-game-denied': 'ui:game-command-blocked', root + '-daily-hard-denied': 'ui:native-hard-command-blocked',
            root + '-earn-before': 'ui:child-countdown-present',
            **approval(root + '-earn', 'overlay', first_parent, 60, True, work_capture),
            **prefixed_stages(root + '-first-game', {**game_usable_app(level=1, mode=mode), 'capture': 'ui:game-policy-activity'}),
            **work(root + '-earned-work', ('capture',), homework, capture=work_capture),
            root + '-more-before': 'ui:child-countdown-present', **leave(root + '-more', 'other-child'),
            **parent_return(root + '-more-balance-parent'), root + '-more-balance': 'ui:time-explanation-refresh-read',
            **leave(root + '-more-balance-parent', 'parent'),
            **approval(root + '-more', 'kiosk', second_parent, 30, True, work_capture)})
        if fresh:
            screens.update({**reopen_work(root + '-more-reopened', homework, work_capture),
                **prefixed_stages(root + '-more-new-game', {**game_usable_app(level=1, mode=mode), 'capture': 'ui:game-policy-activity'})})
            work_capture = root + '-more-reopened-capture'
            game_capture = root + '-more-new-game-capture'
        else:
            screens.update({root + '-more-game': 'ui:game-policy-activity', root + '-more-move': 'ui:game-resume',
                            root + '-more-played': 'ui:game-resumed'})
            game_capture = root + '-first-game-capture'
            activities[root + '-more-game'] = (game_capture, 'same')
        screens.update({**work(root + '-more-work', ('capture',), homework, capture=work_capture),
            root + '-more-hard-denied': 'ui:native-hard-command-blocked', root + '-home-before': 'ui:child-countdown-present',
            **approval(root + '-home', 'overlay', first_parent, 30, False, work_capture),
            root + '-home-closed': 'ui:game-policy-closed', root + '-home-denied': 'ui:game-command-blocked',
            **work(root + '-again', ('edit', 'save', 'saved', 'submit', 'submitted', 'capture'), resumed, homework),
            root + '-break-before': 'ui:child-countdown-present', **leave(root + '-break', 'other-child'),
            **parent_return(root + '-break-balance-parent'), root + '-break-balance': 'ui:time-explanation-refresh-read',
            **leave(root + '-break-balance-parent', 'parent'),
            **approval(root + '-break', 'kiosk', second_parent, 30, True, root + '-again-capture')})
        activities[root + '-home-closed'] = (game_capture, 'closed')
        work_capture = root + '-again-capture'
        if fresh:
            screens.update(reopen_work(root + '-break-reopened', resumed, work_capture))
            work_capture = root + '-break-reopened-capture'
        screens.update(prefixed_stages(root + '-break-game', {**game_usable_app(level=1, mode=mode), 'capture': 'ui:game-policy-activity'}))
        settings[root + '-daily-settings'] = SettingsObservation('existing-fixture-child', True, (PRESET_LABELS[60 * cycle],))
        for name, minutes in (('positive', 60 * cycle + 1), ('zero', 0)):
            prefix = root + '-' + name
            screens.update({**leave(prefix, 'other-child'), **parent_return(prefix + '-parent'),
                **({root + '-original-grant': 'ui:time-explanation-refresh-read'} if name == 'positive' else {}),
                **(custom_allowance(prefix + '-daily', minutes) if minutes else allowance_selection(prefix + '-daily', (0,))),
                prefix + '-settings': 'ui:existing-returned', prefix + '-balance': 'ui:time-explanation-refresh-read',
                **leave(prefix + '-parent', 'parent'),
                **entry(prefix + '-child', 'other-child', not fresh, capture=work_capture if not fresh else None)})
            if fresh:
                screens.update(reopen_work(prefix + '-reopened', resumed, work_capture))
                work_capture = prefix + '-reopened-capture'
                screens[prefix + '-denied'] = 'ui:game-' + ('fullscreen-' if cycle == 2 else '') + 'command-blocked'
            else:
                screens.update({prefix + '-game': 'ui:game-policy-activity',
                    prefix + '-denied': 'ui:game-' + ('fullscreen-' if cycle == 2 else '') + 'secondary-command-blocked',
                    prefix + '-original': 'ui:game-policy-activity'})
                for suffix in ('game', 'original'):
                    activities[prefix + '-' + suffix] = (root + '-break-game-capture', 'same')
            screens.update({prefix + '-hard': 'ui:native-hard-command-blocked',
                **work(prefix + '-work', ('capture', 'resubmit', 'submitted'), resumed, capture=work_capture)})
            settings[prefix + '-settings'] = SettingsObservation('existing-fixture-child', True, (str(minutes) + ' minutes',))
        screens.update({**leave(root + '-off', 'other-child'), **parent_return(root + '-off-parent'),
            root + '-off-toggle': 'ui:parent-toggle-disabled', root + '-off-settings': 'ui:existing-returned',
            **leave(root + '-off-parent', 'parent'),
            **entry(root + '-off-child', 'other-child', not fresh, capture=work_capture if not fresh else None)})
        if fresh:
            screens.update(reopen_work(root + '-off-reopened', resumed, work_capture))
            work_capture = root + '-off-reopened-capture'
        screens.update({root + '-off-countdown': 'ui:child-countdown-absent', root + '-off-hard': 'ui:native-hard-command-blocked',
            root + '-off-game-denied': 'ui:game-' + ('command-blocked' if fresh else 'secondary-command-blocked')})
        if not fresh:
            screens.update({root + '-off-game-close': 'ui:game-close', root + '-off-game-closed': 'ui:game-closed'})
        screens.update({**leave(root + '-on', 'other-child'), **parent_return(root + '-on-parent'),
            root + '-on-toggle': 'ui:parent-toggle-enabled', root + '-on-settings': 'ui:existing-returned',
            root + '-on-balance': 'ui:time-explanation-refresh-read', **leave(root + '-on-parent', 'parent'),
            **entry(root + '-denied', 'other-child', not fresh, expected='time-denied'),
            **prefixed_stages(root + '-entry', rejected_gdm_return()),
            **approval(root + '-visit', 'kiosk', first_parent, 600, cycle == 1, work_capture)})
        if fresh:
            screens.update(reopen_work(root + '-visit-reopened', resumed, work_capture))
            work_capture = root + '-visit-reopened-capture'
        screens.update({**work(root + '-visit-work', ('capture', 'resubmit', 'submitted'), resumed, capture=work_capture),
            **(prefixed_stages(root + '-visit-game', {**game_usable_app(level=1, mode=mode), 'capture': 'ui:game-policy-activity'}) if cycle == 1 else
               {root + '-visit-game-denied': 'ui:game-fullscreen-command-blocked'}),
            root + '-natural-expiry': 'ui:work-jordan-activity', root + '-lock-input-ready': 'ui:child-natural-expiry-lock-ready',
            root + '-lock-result': 'ui:child-natural-expiry-lock-result', root + '-curtain': 'ui:child-lock-curtain',
            root + '-reveal-ready': 'ui:child-lock-reveal-ready', root + '-time-denied': 'ui:child-lock-time-denied',
            root + '-return-greeter': 'system:standard-return-greeter', root + '-denied-returned': 'ui:gdm-returned',
            **approval(root + '-recovery', 'kiosk', second_parent, 1200, cycle == 2, root + '-visit-work-capture', recovery=True),
            **work(root + '-recovered-work', ('capture', 'resubmit', 'submitted'), resumed, capture=root + '-visit-work-capture'),
            **({root + '-recovery-closed': 'ui:game-policy-closed', root + '-recovery-game-denied': 'ui:game-command-blocked'} if cycle == 1 else
               prefixed_stages(root + '-recovery-game', {**game_usable_app(level=1, mode=mode), 'capture': 'ui:game-policy-activity'})),
            root + '-recovery-hard': 'ui:native-hard-command-blocked',
            **work(root + '-final-work', ('capture',), resumed, capture=root + '-visit-work-capture'),
            **leave(root + '-revoke', 'other-child'), **parent_return(root + '-revoke-parent'),
            **{root + '-revoke-' + action: 'ui:revoke-' + operation for action, operation in
               (('open', 'open'), ('warning', 'warning'), ('confirm', 'confirm'))},
            root + '-revoked-settings': 'ui:existing-returned', root + '-revoked-balance': 'ui:time-explanation-refresh-read',
            **leave(root + '-revoke-parent', 'parent'), **entry(root + '-revoked', 'other-child', not fresh, expected='time-denied'),
            **prefixed_stages(root + '-revoked', rejected_gdm_return()), **riley_visit(root + '-riley'), **leave(root + '-riley', 'child')})
        texts[root + '-natural-expiry'] = (resumed, resumed)
        entries[root + '-natural-expiry'] = root + '-visit-work-capture'
        activities[root + '-natural-expiry'] = (root + '-visit-work-capture', 'same')
        if cycle == 1:
            activities[root + '-recovery-closed'] = (root + '-visit-game-capture', 'closed')
        settings[root + '-off-settings'] = SettingsObservation('existing-fixture-child', False, ('0 minutes',))
        for suffix in ('on-settings', 'revoked-settings'):
            settings[root + '-' + suffix] = SettingsObservation('existing-fixture-child', True, ('0 minutes',))
        prior_work = resumed
    screens.update({**parent_return('final-parent'), **prefixed_stages('reopen', parent_reopen()),
        **prefixed_stages('final', parent_selection(child='existing', screen_limits=True)),
        'final-settings': 'ui:existing-returned', 'final-balance': 'ui:time-explanation-refresh-read',
        'final-apps': 'ui:existing-apps', **saved_rows(APPS, 'final'),
        **leave('final-parent', 'parent'), **riley_visit('final-riley'), 'cleanup': 'system:child-desktop-identity'})
    settings['final-settings'] = SettingsObservation('existing-fixture-child', True, ('0 minutes',))
    visible_panels = {}
    for stage, tag in screens.items():
        reveal = stage.startswith('cycle-2-') and tag in ('ui:child-countdown-present', 'ui:child-countdown-absent')
        if reveal:
            visible_panels[stage + '-panel'] = 'system:standard-overview-open'
        visible_panels[stage] = tag
        if reveal:
            visible_panels[stage + '-game'] = 'system:standard-overview-close'
    screens = visible_panels
    plan = JourneyPlan(
        prefix='homework-game', worker_mode='homework_game_fresh' if fresh else 'homework_game', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if not stage.startswith(('cycle-', 'final-', 'reopen-')) else
                     'step-2' if stage.startswith('cycle-') else 'step-3' for stage in screens},
            'installed-greeter': 'start', 'cleanup': 'step-3'},
        stage_actions={'setup-detached': 'daytime-window', 'desktop': 'native-verify',
            'setup-switch': 'work-prepare', 'cleanup': 'work-cleanup',
            **{stage.removesuffix('-bytes'): stage for stage in saves},
            **{'cycle-' + str(cycle) + '-natural-expiry': 'natural-expiry' for cycle in (1, 2)}},
        child_bindings={stage: 'existing' for stage, tag in screens.items() if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
        settings_checks=settings,
        match_checks={prefix + '-' + role + '-match': (app, rule) for prefix in ('saved', 'final')
            for role, app, rule in (('a', MATCH_APPS['A'], MATCH_RULES[0]), ('h', MATCH_APPS['H'], MATCH_RULES[3]),
                                    ('game', MATCH_APPS['Game'], MATCH_RULES[-1]))},
        access_checks={prefix + '-' + role + '-access': (app, access) for prefix in ('saved', 'final')
            for role, (app, _draft, access) in zip(('a', 'h', 'game'), APPS)},
        invocations=tuple(stage for stage, tag in screens.items() if stage in logins
            or tag.removeprefix('ui:') in GDM_DENIAL_OPERATIONS or stage.endswith(
                ('request-panel', 'request-launch', 'request-form', 'natural-expiry', 'lock-input-ready', 'lock-result'))),
        challenges=challenges, work_texts=texts, activity_checks=activities, activity_entries=entries,
        overlay_request=('other-child', 'parent', 60, True), overlay_requests=overlays,
        kiosk_request=('other-child', 'parent', 60, True), kiosk_requests=kiosks,
        countdown_checks=countdowns, assertions_after={'cleanup': 'visible-result'})
    return plan, saves, requests


PLAN, SAVES, REQUESTS = build_plan()
FRESH_PLAN, FRESH_SAVES, FRESH_REQUESTS = build_plan(fresh=True)


class HomeworkGameJourney(RequestFlowJourney, AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        self.fresh = plan is FRESH_PLAN
        self.request_bindings = FRESH_REQUESTS if self.fresh else REQUESTS
        super().__init__(context, progress, plan, actions={
            **fixture_actions(include_refusal=False, profile='game'),
            **work_document_actions(saves=FRESH_SAVES if self.fresh else SAVES), 'daytime-window': preset_ordinary_daytime,
            'natural-expiry': self.natural_expiry})
        self.before_requests = {}
        self.original_grants = {}
        self.expiry_countdowns = {}
        self.expiry_results = {}
        self.request_balances = {}

    def check_calendar(self, guard):
        guard()
        clock = self.vm.local_calendar()
        now = datetime.fromtimestamp(clock['epoch_ns'] / 1e9, ZoneInfo(clock['timezone']))
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), now.tzinfo)
        remaining = midnight.timestamp() - now.timestamp()
        require(remaining > 5400, 'homework-game:midnight-margin')
        return {'seconds_before_midnight': remaining}

    def check_estimate(self, observed):
        # Each request is checked against its immediately preceding public
        # countdown. Parent's earlier daily balance pauses while Jordan is away.
        pass

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        balance = observed.get('ui', {}).get('time_explanation')
        if balance is not None:
            require(balance['child'] == 'existing-fixture-child', 'homework-game:balance-child')
            daily, grant, total = (balance[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            require(abs(total - max(daily, grant)) <= precision, 'homework-game:larger-balance')
            if stage == 'initial-balance' or stage.endswith(('-on-balance', '-revoked-balance')) or stage == 'final-balance':
                require(daily == grant == total == 0, 'homework-game:cleared-time')
            if stage.endswith('-daily-balance'):
                require(daily >= 300 and grant == 0, 'homework-game:daily-only')
            if stage.endswith('-original-grant'):
                self.original_grants[stage[:7]] = deepcopy(balance)
            if stage.endswith(('-more-balance', '-break-balance')):
                self.request_balances[stage.removesuffix('-balance')] = deepcopy(balance)
            if stage.endswith(('-positive-balance', '-zero-balance')):
                before = self.original_grants[stage[:7]]
                elapsed = (balance['observed_monotonic_ns'] - before['observed_monotonic_ns']) / 1e9
                margin = precision + before['one_time']['precision_seconds'] + 2
                require(0 <= elapsed <= 600 and grant >= 300
                    and abs(grant - (before['one_time']['seconds'] - elapsed)) <= margin
                    and (daily == 0 if stage.endswith('-zero-balance') else daily > 0),
                    'homework-game:original-grant-preserved')
        if stage.endswith(('-earn-before', '-more-before', '-home-before', '-break-before')):
            self.before_requests[stage.removesuffix('-before')] = deepcopy(observed['ui']['countdown'])
        if stage == 'desktop':
            observed['calendar'] = self.check_calendar(lambda: self.context.lease.guard())
        if stage.endswith('-visit-countdown'):
            sample = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'],
                                             child='existing-fixture-child')
            require(countdown_seconds(sample.countdown.text)[0] >= 300, 'homework-game:visit-margin')
            self.expiry_countdowns[stage[:7]] = sample
        if stage.endswith('-time-denied'):
            require(observed['ui']['lock']['surface_id'] == self.expiry_results[stage[:7]]['lock']['surface_id'],
                    'homework-game:original-natural-lock')

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if not stage.endswith('-new-estimate'):
            return
        prefix = stage.removesuffix('-new-estimate')
        _surface, bound = self.request_bindings[prefix]
        choice = observed['ui']['valid_choice']
        requested = bound[2]
        require(choice['estimate']['kind'] == 'fixed', 'homework-game:fixed-estimate')
        if prefix.endswith(('-visit', '-recovery')):
            require(choice['estimate']['seconds'] == requested, 'homework-game:replacement-time')
        else:
            before = self.before_requests[prefix]
            elapsed = (choice['observed_monotonic_ns'] - before['observed_monotonic_ns']) / 1e9
            require(0 <= elapsed <= 600 and before['seconds'] >= 300, 'homework-game:request-margin')
            start, end = _estimate_read_bounds(choice, 'homework-game:estimate-read-bounds')
            require(before['observed_monotonic_ns'] <= start <= end,
                    'homework-game:request-margin')
            if _surface == 'overlay':
                # The public refresh calculates inside this guest-clock
                # bracket, before its final label and choice reads finish.
                low = before['seconds'] - elapsed
                high = before['seconds'] - (start - before['observed_monotonic_ns']) / 1e9
                margin = 2
            else:
                balance = self.request_balances[prefix]
                earliest = (start - balance['observed_monotonic_ns']) / 1e9
                latest = (end - balance['observed_monotonic_ns']) / 1e9
                require(0 <= earliest <= latest <= 300, 'homework-game:request-balance-age')
                low = max(balance['daily']['seconds'], max(0, balance['one_time']['seconds'] - latest))
                high = max(balance['daily']['seconds'], max(0, balance['one_time']['seconds'] - earliest))
                margin = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time')) + 2
            require(high - low + 2 * margin < requested
                    and low + requested - margin <= choice['estimate']['seconds']
                        <= high + requested + margin, 'homework-game:request-increment')
        observed.setdefault('comparison', {})['requested_time_added_to_current_balance'] = True

    def check_activity(self, stage, observed):
        super().check_activity(stage, observed)
        if self.fresh and stage.endswith('-more-new-game-capture'):
            current = self.activity_observations[stage]
            earlier = self.activity_observations[stage[:7] + '-first-game-capture']
            # Logout ends the old session. This case requires the same child
            # playing in a new session/window, unlike a same-session relaunch.
            require(current.owner is not None and earlier.owner is not None
                    and current.owner[0] == earlier.owner[0]
                    and current.owner[1] != earlier.owner[1],
                    'homework-game:fresh-game-session')
            require(current.binding == earlier.binding
                    and current.pid != earlier.pid and current.endpoint != earlier.endpoint
                    and current.state == earlier.state,
                    'homework-game:fresh-game-activity')
            observed['comparison'] = {'fresh_session': True, 'new_game_window': True,
                                      'activity_unchanged': True, 'outcome': 'passed'}
        if stage.endswith(('-again-capture', '-homework-capture')) and stage != 'cycle-1-homework-capture':
            current = self.activity_observations[stage]
            if self.fresh:
                earlier_stage = stage[:7] + ('-more-reopened-capture' if stage.endswith('-again-capture')
                                            else '-reopened-capture')
            else:
                earlier_stage = 'cycle-1-homework-capture'
            earlier = self.activity_observations[earlier_stage]
            require((current.pid, current.endpoint, current.owner) == (earlier.pid, earlier.endpoint, earlier.owner),
                    'homework-game:original-homework-window')

    @staticmethod
    def natural_expiry(journey, guard):
        cycle = 'cycle-' + str(len(journey.expiry_results) + 1)
        result = await_natural_expiry(journey, guard, journey.expiry_countdowns[cycle],
            journey.activity_observations[cycle + '-visit-work-capture'], maximum_seconds=600, child='existing')
        journey.expiry_results[cycle] = result
        return result


def execute(recorder, context):
    from e2e_fixture_preparation import GAME_SUBSETS
    context.fixture_subsets = GAME_SUBSETS
    context.fixture_caller = 'E2E-050/overlay-first-retained'
    record_installed_journey(recorder, context, PLAN, timeout=5400, journey_type=HomeworkGameJourney)


def execute_fresh(recorder, context):
    from e2e_fixture_preparation import GAME_SUBSETS
    context.fixture_subsets = GAME_SUBSETS
    context.fixture_caller = 'E2E-050/overlay-first-fresh'
    record_installed_journey(recorder, context, FRESH_PLAN, timeout=5400, journey_type=HomeworkGameJourney)


E2E_CASES = {'overlay-first-retained': execute, 'overlay-first-fresh': execute_fresh}
