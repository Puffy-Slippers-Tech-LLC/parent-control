"""247: two uninterrupted homework/game cycles, retaining both children's work."""
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


SCREENS = app_policy_entry(child='existing', allowance=None, initial_rows=False)
# Configure zero daily time through the ordinary enable/save path before rules.
del SCREENS['apps-page']
SCREENS.update({'initial-balance': 'ui:time-explanation-setup-zero-read',
                'initial-settings': 'ui:existing-returned', 'apps-page': 'ui:existing-apps'})
LOGINS = set(fresh_desktop('parent'))
CHALLENGES = {'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked')}
TEXTS, SAVES, ACTIVITIES, ENTRIES, OVERLAYS, KIOSKS, COUNTDOWNS = {}, {}, {}, {}, {}, {}, {}
SETTINGS = {'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
            'initial-settings': SettingsObservation('existing-fixture-child', True, ('0 minutes',))}
for index, (app, draft, access) in enumerate(APPS):
    SCREENS.update(policy_edit(app, draft, access, 'policy-' + str(index), setup=True))
SCREENS.update({**text_fragment('catalogue-clear', 'clear'), **saved_rows(APPS, 'saved'),
                'setup-leave': 'ui:desktop', 'setup-switch': 'system:parent-switch-user',
                'setup-gdm': 'ui:gdm-returned'})


def entry(prefix, account, retained=False, expected='success', capture=None):
    screens = prefixed_stages(prefix, desktop_entry(account, source='gdm',
        entry='retained' if retained else 'fresh', expected=expected))
    if retained and account == 'other-child' and expected == 'success':
        screens[prefix + '-desktop'] = 'system:standard-desktop-identity'
    LOGINS.update(stage for stage in screens if not stage.endswith('entry-guard'))
    role = 'recipient' if account == 'parent' else 'child-recipient' if account == 'child' else 'standard-recipient'
    CHALLENGES[prefix] = (account, prefix + '-' + role + '-qualified', prefix + '-' + role + '-rechecked')
    if capture is not None:
        ENTRIES[prefix + '-entry-guard'] = capture
    return screens


def leave(prefix, account):
    role = 'standard' if account == 'other-child' else account
    return {prefix + '-leave': 'system:' + role + '-desktop-identity',
            prefix + '-switch': 'system:' + role + '-switch-user', prefix + '-gdm': 'ui:gdm-returned'}


def work(prefix, actions, text, prior='No submitted draft', who='jordan', capture=None):
    screens = {prefix + '-' + action: 'ui:work-' + who + '-' +
               ('activity' if action == 'capture' else action) for action in actions}
    TEXTS.update({stage: (text, prior) for stage in screens})
    if 'saved' in actions:
        SAVES[prefix + '-saved-bytes'] = (who, text)
    if capture is not None:
        ACTIVITIES[prefix + '-capture'] = (capture, 'same')
    return screens


SCREENS.update({**entry('riley-initial', 'child'),
    **work('riley-work', ('open', 'opened', 'edit', 'save', 'saved', 'submit', 'submitted', 'capture'),
           'Riley saved synthetic work', who='riley'), **leave('riley-initial', 'child')})
LOCAL_PARENTS = {'overlay': 'other-parent', 'kiosk': 'other-parent'}
last_seconds, last_soft = 1800, False
REQUESTS = {}


def approval(prefix, surface, parent, seconds, soft, capture):
    """Compose qualified request/return leaves and an untouched REQUEST03 read."""
    global last_seconds, last_soft
    before = ('other-child', LOCAL_PARENTS[surface], last_seconds, last_soft)
    bound = ('other-child', parent, seconds, soft)
    request = dict(child='existing-fixture-child',
        approver='fixture-parent' if parent == 'parent' else 'other-fixture-parent',
        duration_seconds=seconds, allow_soft=soft)
    if surface == 'overlay':
        screens = {**prefixed_stages(prefix, overlay_entry('request', 'panel',
            form_operation='request-overlay-jordan-ready')),
            prefix + '-remembered': 'ui:overlay-request-read',
            **prefixed_stages(prefix, approval_and_return(prefix='new', entry='open',
                surface=surface, **request))}
        OVERLAYS.update({stage: bound for stage, tag in screens.items()
                        if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})
        OVERLAYS[prefix + '-remembered'] = before
    else:
        flow = approval_and_return(prefix='new', entry='open', surface='kiosk',
                                   child_entry='retained', **request)
        # Fullscreen return needs only the unlocked session and subsequent game.
        flow['retained-desktop'] = 'system:standard-desktop-identity'
        screens = {**prefixed_stages(prefix, station_entry('cancel-')),
            prefix + '-remembered-child': 'ui:kiosk-request-child',
            prefix + '-remembered': 'ui:kiosk-request-read', **prefixed_stages(prefix, flow)}
        KIOSKS.update({stage: bound for stage, tag in screens.items()
                       if tag.removeprefix('ui:') in KIOSK_BOUND_OPERATIONS})
        KIOSKS[prefix + '-remembered'] = before
        LOGINS.update(prefixed_stages(prefix + '-retained', fresh_desktop('other-child')))
        CHALLENGES[prefix + '-retained'] = ('other-child',
            prefix + '-retained-standard-recipient-qualified', prefix + '-retained-standard-recipient-rechecked')
        ENTRIES[prefix + '-retained-entry-guard'] = capture
    COUNTDOWNS[prefix + '-countdown'] = (prefix + '-new-estimate', 'estimate', 1, 300)
    REQUESTS[prefix] = (surface, bound)
    LOCAL_PARENTS[surface] = parent
    last_seconds, last_soft = seconds, soft
    return screens


def parent_return(prefix):
    return {**entry(prefix, 'parent', True), prefix + '-retained': 'ui:retained-parent-read'}


def riley_visit(prefix):
    return {**entry(prefix, 'child', True, capture='riley-work-capture'),
        **work(prefix + '-work', ('capture', 'resubmit', 'submitted'),
               'Riley saved synthetic work', who='riley', capture='riley-work-capture')}


prior_work = 'No submitted draft'
for cycle, mode in ((1, 'windowed'), (2, 'fullscreen')):
    root = 'cycle-' + str(cycle)
    homework, resumed = 'homework cycle ' + str(cycle), 'work again cycle ' + str(cycle)
    first_parent, second_parent = (('parent', 'other-parent') if cycle == 1
                                    else ('other-parent', 'parent'))
    work_capture = root + '-homework-capture'
    SCREENS.update({**parent_return(root + '-daily-parent'),
        **allowance_selection(root + '-daily', (60 * cycle,)),
        root + '-daily-settings': 'ui:existing-returned', root + '-daily-balance': 'ui:time-explanation-refresh-read',
        **leave(root + '-daily-parent', 'parent'),
        **entry(root + '-entry', 'other-child', cycle == 2,
                capture='cycle-1-final-work-capture' if cycle == 2 else None),
        **work(root + '-homework',
            (*(('open', 'opened') if cycle == 1 else ()), 'edit', 'save', 'saved', 'submit', 'submitted', 'capture'),
            homework, prior_work),
        root + '-daily-game-denied': 'ui:game-command-blocked',
        root + '-daily-hard-denied': 'ui:native-hard-command-blocked',
        root + '-earn-before': 'ui:child-countdown-present',
        **approval(root + '-earn', 'overlay', first_parent, 60, True, work_capture),
        **prefixed_stages(root + '-first-game', {**game_usable_app(level=1, mode=mode),
                                               'capture': 'ui:game-policy-activity'}),
        **work(root + '-earned-work', ('capture',), homework, capture=work_capture),
        root + '-more-before': 'ui:child-countdown-present', **leave(root + '-more', 'other-child'),
        **parent_return(root + '-more-balance-parent'),
        root + '-more-balance': 'ui:time-explanation-refresh-read',
        **leave(root + '-more-balance-parent', 'parent'),
        **approval(root + '-more', 'kiosk', second_parent, 30, True, work_capture),
        root + '-more-game': 'ui:game-policy-activity', root + '-more-move': 'ui:game-resume',
        root + '-more-played': 'ui:game-resumed',
        **work(root + '-more-work', ('capture',), homework, capture=work_capture),
        root + '-more-hard-denied': 'ui:native-hard-command-blocked',
        root + '-home-before': 'ui:child-countdown-present',
        **approval(root + '-home', 'overlay', first_parent, 30, False, work_capture),
        root + '-home-closed': 'ui:game-policy-closed', root + '-home-denied': 'ui:game-command-blocked',
        **work(root + '-again', ('edit', 'save', 'saved', 'submit', 'submitted', 'capture'), resumed, homework),
        root + '-break-before': 'ui:child-countdown-present', **leave(root + '-break', 'other-child'),
        **parent_return(root + '-break-balance-parent'),
        root + '-break-balance': 'ui:time-explanation-refresh-read',
        **leave(root + '-break-balance-parent', 'parent'),
        **approval(root + '-break', 'kiosk', second_parent, 30, True, root + '-again-capture'),
        **prefixed_stages(root + '-break-game', {**game_usable_app(level=1, mode=mode),
                                               'capture': 'ui:game-policy-activity'})})
    SETTINGS[root + '-daily-settings'] = SettingsObservation(
        'existing-fixture-child', True, (PRESET_LABELS[60 * cycle],))
    ACTIVITIES[root + '-more-game'] = (root + '-first-game-capture', 'same')
    ACTIVITIES[root + '-home-closed'] = (root + '-first-game-capture', 'closed')
    for name, minutes in (('positive', 60 * cycle + 1), ('zero', 0)):
        prefix = root + '-' + name
        SCREENS.update({**leave(prefix, 'other-child'), **parent_return(prefix + '-parent'),
            **({root + '-original-grant': 'ui:time-explanation-refresh-read'} if name == 'positive' else {}),
            **(custom_allowance(prefix + '-daily', minutes) if minutes else allowance_selection(prefix + '-daily', (0,))),
            prefix + '-settings': 'ui:existing-returned', prefix + '-balance': 'ui:time-explanation-refresh-read',
            **leave(prefix + '-parent', 'parent'),
            **entry(prefix + '-child', 'other-child', True, capture=root + '-again-capture'),
            prefix + '-game': 'ui:game-policy-activity',
            prefix + '-denied': 'ui:game-' + ('fullscreen-' if cycle == 2 else '') + 'secondary-command-blocked',
            prefix + '-original': 'ui:game-policy-activity', prefix + '-hard': 'ui:native-hard-command-blocked',
            **work(prefix + '-work', ('capture', 'resubmit', 'submitted'), resumed, capture=root + '-again-capture')})
        SETTINGS[prefix + '-settings'] = SettingsObservation('existing-fixture-child', True, (str(minutes) + ' minutes',))
        for suffix in ('game', 'original'):
            ACTIVITIES[prefix + '-' + suffix] = (root + '-break-game-capture', 'same')
    SCREENS.update({**leave(root + '-off', 'other-child'), **parent_return(root + '-off-parent'),
        root + '-off-toggle': 'ui:parent-toggle-disabled', root + '-off-settings': 'ui:existing-returned',
        **leave(root + '-off-parent', 'parent'),
        **entry(root + '-off-child', 'other-child', True, capture=root + '-again-capture'),
        root + '-off-countdown': 'ui:child-countdown-absent',
        root + '-off-hard': 'ui:native-hard-command-blocked',
        root + '-off-game-denied': 'ui:game-secondary-command-blocked',
        # Close the old game normally before preparing the next measured visit.
        root + '-off-game-close': 'ui:game-close', root + '-off-game-closed': 'ui:game-closed',
        **leave(root + '-on', 'other-child'), **parent_return(root + '-on-parent'),
        root + '-on-toggle': 'ui:parent-toggle-enabled', root + '-on-settings': 'ui:existing-returned',
        root + '-on-balance': 'ui:time-explanation-refresh-read', **leave(root + '-on-parent', 'parent'),
        **entry(root + '-denied', 'other-child', True, expected='time-denied'),
        **prefixed_stages(root + '-entry', rejected_gdm_return()),
        **approval(root + '-visit', 'kiosk', first_parent, 600, cycle == 1, root + '-again-capture'),
        **work(root + '-visit-work', ('capture', 'resubmit', 'submitted'), resumed, capture=root + '-again-capture'),
        **(prefixed_stages(root + '-visit-game', {**game_usable_app(level=1, mode=mode),
                                                'capture': 'ui:game-policy-activity'}) if cycle == 1 else
           {root + '-visit-game-denied': 'ui:game-fullscreen-command-blocked'}),
        root + '-natural-expiry': 'ui:work-jordan-activity',
        root + '-lock-input-ready': 'ui:child-natural-expiry-lock-ready',
        root + '-lock-result': 'ui:child-natural-expiry-lock-result',
        root + '-curtain': 'ui:child-lock-curtain', root + '-reveal-ready': 'ui:child-lock-reveal-ready',
        root + '-time-denied': 'ui:child-lock-time-denied',
        root + '-return-greeter': 'system:standard-return-greeter', root + '-denied-returned': 'ui:gdm-returned',
        **approval(root + '-recovery', 'kiosk', second_parent, 1200, cycle == 2, root + '-visit-work-capture'),
        **work(root + '-recovered-work', ('capture', 'resubmit', 'submitted'), resumed, capture=root + '-visit-work-capture'),
        **({root + '-recovery-closed': 'ui:game-policy-closed',
            root + '-recovery-game-denied': 'ui:game-command-blocked'} if cycle == 1 else
           prefixed_stages(root + '-recovery-game', {**game_usable_app(level=1, mode=mode),
                                                   'capture': 'ui:game-policy-activity'})),
        root + '-recovery-hard': 'ui:native-hard-command-blocked',
        **work(root + '-final-work', ('capture',), resumed, capture=root + '-visit-work-capture'),
        **leave(root + '-revoke', 'other-child'), **parent_return(root + '-revoke-parent'),
        **{root + '-revoke-' + action: 'ui:revoke-' + operation for action, operation in
           (('open', 'open'), ('warning', 'warning'), ('confirm', 'confirm'))},
        root + '-revoked-settings': 'ui:existing-returned', root + '-revoked-balance': 'ui:time-explanation-refresh-read',
        **leave(root + '-revoke-parent', 'parent'),
        **entry(root + '-revoked', 'other-child', True, expected='time-denied'),
        **prefixed_stages(root + '-revoked', rejected_gdm_return()),
        **riley_visit(root + '-riley'), **leave(root + '-riley', 'child')})
    TEXTS[root + '-natural-expiry'] = (resumed, resumed)
    ENTRIES[root + '-natural-expiry'] = root + '-visit-work-capture'
    ACTIVITIES[root + '-natural-expiry'] = (root + '-visit-work-capture', 'same')
    if cycle == 1:
        ACTIVITIES[root + '-recovery-closed'] = (root + '-visit-game-capture', 'closed')
    SETTINGS[root + '-off-settings'] = SettingsObservation('existing-fixture-child', False, ('0 minutes',))
    for suffix in ('on-settings', 'revoked-settings'):
        SETTINGS[root + '-' + suffix] = SettingsObservation('existing-fixture-child', True, ('0 minutes',))
    prior_work = resumed

SCREENS.update({**parent_return('final-parent'), **prefixed_stages('reopen', parent_reopen()),
    **prefixed_stages('final', parent_selection(child='existing', screen_limits=True)),
    'final-settings': 'ui:existing-returned', 'final-balance': 'ui:time-explanation-refresh-read',
    'final-apps': 'ui:existing-apps', **saved_rows(APPS, 'final'),
    **leave('final-parent', 'parent'), **riley_visit('final-riley'),
    'cleanup': 'system:child-desktop-identity'})
SETTINGS['final-settings'] = SettingsObservation('existing-fixture-child', True, ('0 minutes',))
# Fullscreen play hides the panel. Reuse the qualified overview transport for
# countdown observations, then return to the original game before progression.
VISIBLE_PANELS = {}
for stage, tag in SCREENS.items():
    reveal = stage.startswith('cycle-2-') and tag in ('ui:child-countdown-present', 'ui:child-countdown-absent')
    if reveal:
        VISIBLE_PANELS[stage + '-panel'] = 'system:standard-overview-open'
    VISIBLE_PANELS[stage] = tag
    if reveal:
        VISIBLE_PANELS[stage + '-game'] = 'system:standard-overview-close'
SCREENS = VISIBLE_PANELS
PLAN = JourneyPlan(
    prefix='homework-game', worker_mode='homework_game', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' if not stage.startswith(('cycle-', 'final-', 'reopen-')) else
                 'step-2' if stage.startswith('cycle-') else 'step-3' for stage in SCREENS},
        'installed-greeter': 'start', 'cleanup': 'step-3'},
    stage_actions={'setup-detached': 'daytime-window', 'desktop': 'native-verify',
        'setup-switch': 'work-prepare', 'cleanup': 'work-cleanup',
        **{stage.removesuffix('-bytes'): stage for stage in SAVES},
        **{'cycle-' + str(cycle) + '-natural-expiry': 'natural-expiry' for cycle in (1, 2)}},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    settings_checks=SETTINGS,
    match_checks={prefix + '-' + role + '-match': (app, rule) for prefix in ('saved', 'final')
        for role, app, rule in (('a', MATCH_APPS['A'], MATCH_RULES[0]),
            ('h', MATCH_APPS['H'], MATCH_RULES[3]), ('game', MATCH_APPS['Game'], MATCH_RULES[-1]))},
    access_checks={prefix + '-' + role + '-access': (app, access) for prefix in ('saved', 'final')
        for role, (app, _draft, access) in zip(('a', 'h', 'game'), APPS)},
    invocations=tuple(stage for stage, tag in SCREENS.items()
        if stage in LOGINS or tag.removeprefix('ui:') in GDM_DENIAL_OPERATIONS or stage.endswith(
        ('request-panel', 'request-launch', 'request-form', 'natural-expiry', 'lock-input-ready', 'lock-result'))),
    challenges=CHALLENGES, work_texts=TEXTS, activity_checks=ACTIVITIES, activity_entries=ENTRIES,
    overlay_request=('other-child', 'parent', 60, True), overlay_requests=OVERLAYS,
    kiosk_request=('other-child', 'parent', 60, True), kiosk_requests=KIOSKS,
    countdown_checks=COUNTDOWNS, assertions_after={'cleanup': 'visible-result'})


class HomeworkGameJourney(RequestFlowJourney, AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions={
            **fixture_actions(include_refusal=False, profile='game'),
            **work_document_actions(saves=SAVES), 'daytime-window': preset_ordinary_daytime,
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
        _surface, bound = REQUESTS[prefix]
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
        if stage.endswith(('-again-capture', '-homework-capture')) and stage != 'cycle-1-homework-capture':
            current = self.activity_observations[stage]
            earlier = self.activity_observations['cycle-1-homework-capture']
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


E2E_CASES = {'overlay-first-retained': execute}
