"""251: two parents alternate two children's retained work and game routines."""
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from accessible_ui import (GDM_DENIAL_OPERATIONS, KIOSK_BOUND_OPERATIONS,
    MANAGEMENT_OPERATIONS, MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS,
    OVERLAY_BOUND_OPERATIONS, PRESET_LABELS)
from calendar_fixture import preset_ordinary_daytime
from countdown import CountdownObservation, check_countdown_balance
from feedback_composition import text_fragment
from game_permission import APPS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (allowance_selection, desktop_entry, fresh_desktop,
    game_usable_app, parent_management, parent_selection, prefixed_stages,
    rejected_gdm_return, station_entry)
from named_app_set import saved_rows
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney, policy_edit
from private_artifacts import require
from request_composition import _estimate_read_bounds
from request_flow import RequestFlowJourney, approval_and_return
from synthetic_files import work_document_actions
from ui_observations import SettingsObservation


CHILDREN = {'jordan': ('existing', 'other-child', 'existing-fixture-child', 'standard'),
            'riley': ('child', 'child', 'fixture-child', 'child')}
ROUNDS = ((1, 'jordan', 60, 'overlay', 75, True),
          (1, 'riley', 0, 'kiosk', 7200, True),
          (2, 'riley', 120, 'overlay', 150, False),
          (2, 'jordan', 0, 'kiosk', 7200, False))


def build_plan():
    screens, children, parents, settings, texts, saves, activities, entries = ({} for _ in range(8))
    overlays, kiosks, challenges, countdowns, requests, sessions, balance_pairs = ({} for _ in range(7))
    logins, windows, balances = set(), {}, {}
    last_work, soft = {}, {'jordan': True, 'riley': False}
    minutes = {'jordan': 0, 'riley': 0}
    opened_parents = set()

    def add(prefix, fragment, who=None, parent=None):
        fragment = prefixed_stages(prefix, fragment) if prefix else fragment
        require(not set(fragment) & set(screens), 'family-routines:duplicate-stage')
        screens.update(fragment)
        children.update({stage: CHILDREN[who][0] for stage, tag in fragment.items()
            if who is not None and tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS})
        parents.update({stage: parent for stage, tag in fragment.items()
            if parent is not None and tag.removeprefix('ui:') in MANAGEMENT_OPERATIONS})
        if who is not None:
            binding = (CHILDREN[who][1], 'other-parent', 75 if who == 'jordan' else 150, soft[who])
            overlays.update({stage: binding for stage, tag in fragment.items()
                if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})
        return fragment

    def entry(prefix, account, retained=False, who=None, capture=None, expected='success'):
        fragment = desktop_entry(account, source='gdm', entry='retained' if retained else 'fresh', expected=expected)
        add(prefix, fragment, who)
        logins.update(stage for stage in prefixed_stages(prefix, fresh_desktop(account, expected)))
        recipient = 'child-recipient' if account == 'child' else 'standard-recipient' if account == 'other-child' else 'recipient'
        challenges[prefix] = (account, prefix + '-' + recipient + '-qualified', prefix + '-' + recipient + '-rechecked')
        if capture:
            entries[prefix + '-entry-guard'] = capture
        if who is not None and expected == 'success':
            sessions[prefix + '-entry-guard'] = (who, 'entry')
            sessions[prefix + '-desktop'] = (who, 'active')

    def leave(prefix, account, who=None):
        role = 'standard' if account == 'other-child' else account
        add(prefix, {'leave': 'system:' + role + '-desktop-identity',
            'switch': 'system:' + role + '-switch-user', 'gdm': 'ui:gdm-returned'}, who)
        if who:
            sessions[prefix + '-leave'] = (who, 'leaving')
            sessions[prefix + '-gdm'] = (who, 'away')

    def select(prefix, who, parent):
        add(prefix, parent_selection(child=CHILDREN[who][0], screen_limits=True), who, parent)
        settings[prefix + '-parent-selected'] = SettingsObservation(CHILDREN[who][2], True, (PRESET_LABELS[minutes[who]],))

    def management(prefix, parent, who):
        retained = parent in opened_parents
        entry(prefix + '-entry', parent, retained)
        add(prefix, parent_management(parent=parent, child=CHILDREN[who][0],
                                     window='retained' if retained else 'new'), who, parent)
        windows[prefix + '-parent-retained'] = parent
        settings[prefix + '-parent-selected'] = SettingsObservation(
            CHILDREN[who][2], True, (PRESET_LABELS[minutes[who]],))
        add(prefix, {'session': 'system:' + parent + '-desktop-identity'})
        # The intermediate peer can already be selected in this window and
        # still display values from before the other parent's edits. Switching
        # away makes the final named-child selection reload current settings;
        # compare that result above, not the intermediate navigation read.
        opened_parents.add(parent)

    def rows(prefix, who, parent):
        add(prefix, {'apps': 'ui:existing-apps' if who == 'jordan' else 'ui:parent-apps-page',
            **saved_rows(APPS, 'rows')}, who, parent)

    def profile(prefix, who, parent, allowance):
        add(prefix, allowance_selection('daily', (allowance,)), who, parent)
        add(prefix, {'off': 'ui:parent-toggle-disabled', 'on': 'ui:parent-toggle-enabled',
            'settings': 'ui:existing-returned' if who == 'jordan' else 'ui:parent-selected',
            'balance': 'ui:time-explanation-refresh-read'}, who, parent)
        minutes[who] = allowance
        settings[prefix + '-settings'] = SettingsObservation(CHILDREN[who][2], True, (PRESET_LABELS[allowance],))
        balances[prefix + '-balance'] = (who, 'profile', allowance)

    def work(prefix, who, *, text=None, initial=False, close=False):
        prior = last_work.get(who, 'No submitted draft')
        actions = ('close', 'closed') if close else (
            (*(('open', 'opened') if initial else ()),
             *(('edit', 'save', 'saved', 'submit', 'submitted') if text else ('capture', 'resubmit', 'submitted')),
             *(('capture',) if text else ())))
        text = text or prior
        fragment = add(prefix, {action: 'ui:work-' + who + '-' + ('activity' if action == 'capture' else action)
                                for action in actions}, who)
        texts.update({stage: (text, prior) for stage in fragment})
        if text != prior:
            saves[prefix + '-saved-bytes'] = (who, text)
        if not close:
            if who in last_work and text == prior:
                activities[prefix + '-capture'] = (last_capture[who], 'same')
            last_work[who] = text
            if text != prior or initial:
                last_capture[who] = prefix + '-capture'

    def choices(prefix, who, *, seed=False):
        account, seconds = CHILDREN[who][1], 75 if who == 'jordan' else 150
        binding = (account, 'other-parent', seconds, soft[who])
        fragment = add(prefix, {'launch': 'ui:child-command-launch',
            **({'select': 'ui:overlay-request-select'} if seed else {}),
            'read': 'ui:overlay-request-read', 'cancel': 'ui:overlay-request-cancel',
            'returned': 'ui:overlay-desktop'}, who)
        overlays.update({stage: binding for stage, tag in fragment.items()
                         if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})

    def peer_work(prefix, who):
        entry(prefix, CHILDREN[who][1], True, who, last_capture[who])
        work(prefix + '-work', who)
        choices(prefix + '-choices', who)
        leave(prefix, CHILDREN[who][1], who)

    def peer_parent(prefix, who, parent, before=None):
        select(prefix, who, parent)
        add(prefix, {'balance': 'ui:time-explanation-refresh-read'}, who, parent)
        balances[prefix + '-balance'] = (who, 'peer', minutes[who])
        if before:
            balance_pairs[prefix + '-balance'] = before + '-balance'
            settings[prefix + '-parent-selected'] = before + '-parent-selected'
        rows(prefix, who, parent)

    last_capture = {}
    entry('initial', 'parent')
    add('initial', parent_management(child='existing'), 'jordan', 'parent')
    for who in CHILDREN:
        if who == 'riley':
            add('setup-riley', parent_selection(child='child', screen_limits=True), who, 'parent')
        add('setup-' + who, {'enable': 'ui:parent-toggle-enabled'}, who, 'parent')
        add('setup-' + who, allowance_selection('daily', (120,)), who, 'parent')
        minutes[who] = 120
        add('setup-' + who, {'balance': 'ui:time-explanation-refresh-read',
            'apps': 'ui:existing-apps' if who == 'jordan' else 'ui:parent-apps-page'}, who, 'parent')
        balances['setup-' + who + '-balance'] = (who, 'profile', 120)
        for index, (app, draft, access) in enumerate(APPS):
            add('setup-' + who, policy_edit(app, draft, access, 'policy-' + str(index), setup=True), who, 'parent')
        add('setup-' + who, text_fragment('catalogue-clear', 'clear'), who, 'parent')
        add('setup-' + who, saved_rows(APPS, 'rows'), who, 'parent')
    add('setup', {'window': 'ui:retained-parent-read'}, 'riley', 'parent')
    windows['setup-window'] = 'parent'
    opened_parents.add('parent')
    leave('setup', 'parent')
    for who in CHILDREN:
        entry('initial-' + who, CHILDREN[who][1], who=who)
        work('initial-' + who + '-work', who, text=who.title() + ' initial', initial=True)
        choices('initial-' + who + '-choices', who, seed=True)
        leave('initial-' + who, CHILDREN[who][1], who)
        add('seed-' + who, station_entry())
        fragment = add('seed-' + who, {'select': 'ui:kiosk-request-select', 'read': 'ui:kiosk-request-read',
            'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned'})
        kiosks.update({stage: (CHILDREN[who][1], 'parent', 75 if who == 'jordan' else 150, soft[who])
                       for stage, tag in fragment.items() if tag.removeprefix('ui:') in KIOSK_BOUND_OPERATIONS})

    for visit, (round_number, who, allowance, surface, seconds, included) in enumerate(ROUNDS, 1):
        root, parent = 'visit-' + str(visit), 'parent' if visit % 2 else 'second-parent'
        peer = 'riley' if who == 'jordan' else 'jordan'
        management(root + '-before', parent, peer)
        peer_parent(root + '-peer-before', peer, parent)
        leave(root + '-before', parent)
        peer_work(root + '-peer-before-child', peer)
        management(root + '-edit', parent, who)
        peer_parent(root + '-selected-before', who, parent)
        select(root + '-selected-current', who, parent)
        profile(root + '-profile', who, parent, allowance)
        leave(root + '-edit', parent)
        bound = (CHILDREN[who][1], 'other-parent' if surface == 'overlay' else 'parent', seconds, included)
        if surface == 'overlay':
            entry(root + '-child', CHILDREN[who][1], True, who, last_capture[who])
            add(root, {'before-countdown': 'ui:child-countdown-present'}, who)
        request = approval_and_return(prefix='new', entry='new', surface=surface,
            child=CHILDREN[who][2], approver='other-fixture-parent' if surface == 'overlay' else 'fixture-parent',
            duration_seconds=seconds, allow_soft=included, **({'child_entry': 'retained'} if surface == 'kiosk' else {}))
        fragment = add(root + '-request', request, who)
        (overlays if surface == 'overlay' else kiosks).update({stage: bound for stage, tag in fragment.items()
            if tag.removeprefix('ui:') in (OVERLAY_BOUND_OPERATIONS if surface == 'overlay' else KIOSK_BOUND_OPERATIONS)})
        if surface == 'kiosk':
            retained = root + '-request-retained'
            logins.update(prefixed_stages(retained, fresh_desktop(CHILDREN[who][1])))
            recipient = CHILDREN[who][3] + '-recipient'
            challenges[retained] = (CHILDREN[who][1], retained + '-' + recipient + '-qualified', retained + '-' + recipient + '-rechecked')
            entries[retained + '-entry-guard'] = last_capture[who]
            sessions[retained + '-entry-guard'] = (who, 'entry')
            sessions[retained + '-desktop'] = (who, 'active')
        countdowns[root + '-request-countdown'] = (root + '-request-new-estimate', 'estimate', 1, 300)
        requests[root + '-request-new-estimate'] = (who, surface, root + ('-before-countdown' if surface == 'overlay' else '-profile-balance'))
        work(root + '-work', who, text=who.title() + ' round ' + str(round_number))
        if included:
            add(root + '-game', {**game_usable_app(level=1, mode='windowed'), 'capture': 'ui:game-policy-activity'}, who)
            if who == 'jordan':
                add(root + '-game', {'resume': 'ui:game-resume', 'resumed': 'ui:game-resumed',
                    'progress': 'ui:game-resumed-activity'}, who)
        else:
            add(root + '-game', {'closed': 'ui:game-policy-closed', 'denied': 'ui:game-command-blocked'}, who)
            activities[root + '-game-closed'] = ('visit-' + ('1' if who == 'jordan' else '2') + '-game-capture', 'closed')
        add(root, {'hard-denied': 'ui:native-hard-command-blocked' if who == 'jordan' else 'ui:overlay-native-hard-command-blocked'}, who)
        soft[who] = included
        choices(root + '-choices', who, seed=True)
        leave(root + '-child-done', CHILDREN[who][1], who)
        management(root + '-after', parent, peer)
        peer_parent(root + '-peer-after', peer, parent, root + '-peer-before')
        leave(root + '-after', parent)
        peer_work(root + '-peer-after-child', peer)

    # Riley's transition must clear only Riley's grant. Jordan stays grant-only.
    management('daily-before', 'parent', 'jordan')
    peer_parent('daily-jordan-before', 'jordan', 'parent')
    select('daily-riley', 'riley', 'parent')
    profile('daily-riley', 'riley', 'parent', 120)
    peer_parent('daily-jordan-after', 'jordan', 'parent', 'daily-jordan-before')
    leave('daily-parent', 'parent')
    peer_work('daily-jordan', 'jordan')
    entry('daily-riley', 'child', True, 'riley', last_capture['riley'])
    work('daily-riley-work', 'riley')
    choices('daily-riley-choices', 'riley')
    add('daily-riley', {'game-denied': 'ui:game-command-blocked', 'hard-denied': 'ui:overlay-native-hard-command-blocked'}, 'riley')
    leave('daily-riley', 'child', 'riley')
    management('revoke-parent', 'second-parent', 'riley')
    peer_parent('revoke-riley-before', 'riley', 'second-parent')
    select('revoke-jordan', 'jordan', 'second-parent')
    # Revoke is a declared management operation as well as a named-child input.
    add('revoke-jordan', {action: 'ui:revoke-' + action for action in ('open', 'warning', 'confirm')}, 'jordan', 'second-parent')
    add('revoke-jordan', {'balance': 'ui:time-explanation-refresh-read'}, 'jordan', 'second-parent')
    balances['revoke-jordan-balance'] = ('jordan', 'revoked', 0)
    peer_parent('revoke-riley-after', 'riley', 'second-parent', 'revoke-riley-before')
    rows('final-riley', 'riley', 'second-parent')
    select('final-jordan', 'jordan', 'second-parent')
    rows('final-jordan', 'jordan', 'second-parent')
    leave('revoke-parent', 'second-parent')
    entry('revoked-jordan', 'other-child', True, 'jordan', expected='time-denied')
    add('revoked-jordan', rejected_gdm_return(), 'jordan')
    add('final-station', station_entry())
    for who in CHILDREN:
        fragment = add('final-' + who, {'child': 'ui:kiosk-request-child', 'choices': 'ui:kiosk-request-read'})
        kiosks.update({stage: (CHILDREN[who][1], 'parent', 75 if who == 'jordan' else 150, False)
                       for stage in fragment})
    add('final-station', {'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned'})
    entry('final-riley', 'child', True, 'riley', last_capture['riley'])
    work('final-riley-work', 'riley')
    add('final-riley', {'game-denied': 'ui:game-command-blocked', 'hard-denied': 'ui:overlay-native-hard-command-blocked'}, 'riley')
    work('final-riley-work', 'riley', close=True)
    add('', {'cleanup': 'system:child-desktop-identity'})

    for stage, tag in screens.items():
        if tag == 'ui:child-countdown-present':
            who = 'jordan' if children[stage] == 'existing' else 'riley'
            binding = overlays.get(stage, kiosks.get(stage, (CHILDREN[who][1], 'other-parent', 75, False)))
            overlays[stage] = kiosks[stage] = binding
    plan = JourneyPlan(prefix='family-routines', worker_mode='family_routines', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup', **{stage: 'step-2' if stage.startswith('visit-') else
                'step-3' if stage.startswith(('daily-', 'revoke-', 'revoked-', 'final-')) or stage == 'cleanup' else
                'start' if stage in ('initial-entry-guard', 'initial-installed-greeter') else 'step-1' for stage in screens}},
        stage_actions={'setup-detached': 'daytime-window', 'initial-desktop': 'native-verify',
            'setup-switch': 'work-prepare', 'cleanup': 'work-cleanup',
            **{stage.removesuffix('-bytes'): stage for stage in saves}},
        invocations=tuple(stage for stage, tag in screens.items() if stage in logins
            or tag.removeprefix('ui:') in GDM_DENIAL_OPERATIONS or stage.endswith('-choices-launch')),
        challenges=challenges, child_bindings=children, parent_bindings=parents,
        settings_checks=settings, work_texts=texts, activity_checks=activities, activity_entries=entries,
        match_checks={stage: (MATCH_APPS[role], MATCH_RULES[rule]) for stage in screens
            for role, rule in (('A', 0), ('H', 3), ('Game', -1)) if stage.endswith('-rows-' + role.lower() + '-match')},
        access_checks={stage: (app, access) for stage in screens for app, _draft, access in APPS
            if stage.endswith('-rows-' + next(role.lower() for role, identity in MATCH_APPS.items() if identity == app) + '-access')},
        overlay_request=('other-child', 'other-parent', 75, True), overlay_requests=overlays,
        kiosk_request=('other-child', 'other-parent', 75, True), kiosk_requests=kiosks,
        countdown_checks=countdowns, assertions_after={'cleanup': 'visible-result'})
    return plan, saves, windows, balances, balance_pairs, requests, sessions


PLAN, SAVES, WINDOWS, BALANCES, BALANCE_PAIRS, REQUESTS, SESSIONS = build_plan()


class FamilyRoutinesJourney(RequestFlowJourney, AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions={
            **fixture_actions(include_refusal=False, profile='game'), **work_document_actions(saves=SAVES),
            'daytime-window': preset_ordinary_daytime})
        self.parent_windows, self.parent_sessions, self.balances, self.samples, self.estimates = ({} for _ in range(5))
        self.active, self.intervals = {}, []

    def check_estimate(self, observed):
        # This case dates each estimate from its own child/surface below.
        pass

    def check_countdown(self, stage, observed):
        # The shared comparison uses one default child; this composition binds
        # the current child independently at each request endpoint.
        if stage in PLAN.countdown_checks:
            before, _seconds, precision, maximum = PLAN.countdown_checks[stage]
            choice = self.estimates[before]
            child = choice['request']['child']
            current = CountdownObservation.from_value(observed['ui']['countdown'], present=True, child=child)
            observed.setdefault('comparison', {}).update(check_countdown_balance(current,
                seconds=choice['estimate']['seconds'], precision_seconds=precision,
                observed_monotonic_ns=choice['observed_monotonic_ns'], max_elapsed_seconds=maximum))

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage)
        if operation in ('system:parent-desktop-identity', 'system:second-parent-desktop-identity'):
            parent = operation.removeprefix('system:').removesuffix('-desktop-identity')
            identity = observed['system']['session_sha256']
            require(parent not in self.parent_sessions or self.parent_sessions[parent] == identity,
                    'family-routines:original-parent-desktop')
            self.parent_sessions[parent] = identity
        if stage == 'initial-desktop':
            clock = self.vm.local_calendar()
            now = datetime.fromtimestamp(clock['epoch_ns'] / 1e9, ZoneInfo(clock['timezone']))
            midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), now.tzinfo)
            require(midnight.timestamp() - now.timestamp() > 5400, 'family-routines:midnight-margin')
        if stage in WINDOWS:
            parent, value = WINDOWS[stage], observed['ui']['retained_parent']['window']
            if parent in self.parent_windows:
                require(value == self.parent_windows[parent], 'family-routines:original-parent-window')
            self.parent_windows[parent] = deepcopy(value)
        if stage in SESSIONS:
            who, event = SESSIONS[stage]
            clock = self.vm.local_calendar()
            stamp = (clock['guest_monotonic_start_ns'], clock['guest_monotonic_end_ns'])
            if event == 'entry':
                require(who not in self.active, 'family-routines:activity-order')
                self.active[who] = [stamp]
            else:
                self.active[who].append(stamp)
                if event == 'away':
                    times = self.active.pop(who)
                    require(len(times) == 4, 'family-routines:activity-order')
                    self.intervals.append((who, times))
        if stage.endswith('-before-countdown'):
            self.samples[stage] = deepcopy(observed['ui']['countdown'])
        if stage in BALANCES:
            who, kind, minutes = BALANCES[stage]
            balance = observed['ui']['time_explanation']
            require(balance['child'] == CHILDREN[who][2], 'family-routines:balance-child')
            daily, grant, total = (balance[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            require(abs(total - max(daily, grant)) <= precision, 'family-routines:larger-source')
            require(daily == 0 if minutes == 0 else daily >= 300, 'family-routines:daily-margin')
            require(grant == 0 if kind in ('profile', 'revoked') else total >= 300, 'family-routines:grant-source')
            if stage in BALANCE_PAIRS:
                before = self.balances[BALANCE_PAIRS[stage]]
                elapsed = (balance['observed_monotonic_ns'] - before['observed_monotonic_ns']) / 1e9
                margin = precision + max(before[key]['precision_seconds'] for key in ('daily', 'one_time')) + 2
                require(0 <= elapsed <= 5400 and abs(grant - max(0, before['one_time']['seconds'] - elapsed)) <= margin,
                        'family-routines:peer-grant-changed')
                intervals = [times for child, times in self.intervals if child == who
                    and before['observed_monotonic_ns'] <= times[0][0] <= times[-1][1] <= balance['observed_monotonic_ns']]
                low = sum((times[2][0] - times[1][1]) / 1e9 for times in intervals)
                high = sum((times[3][1] - times[0][0]) / 1e9 for times in intervals)
                require(max(0, before['daily']['seconds'] - high) - margin <= daily <=
                        max(0, before['daily']['seconds'] - low) + margin, 'family-routines:peer-daily-changed')
                observed.setdefault('comparison', {})['untouched_peer_time_sources'] = True
            self.balances[stage] = deepcopy(balance)

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage not in REQUESTS:
            return
        who, surface, before_stage = REQUESTS[stage]
        choice = observed['ui']['valid_choice']
        require(choice['request']['child'] == CHILDREN[who][2] and choice['estimate']['kind'] == 'fixed',
                'family-routines:estimate-child')
        start, end = _estimate_read_bounds(choice)
        if surface == 'overlay':
            before = self.samples[before_stage]
            require(0 <= (end - before['observed_monotonic_ns']) / 1e9 <= 600 and before['seconds'] >= 300,
                    'family-routines:estimate-margin')
            low = before['seconds'] - (end - before['observed_monotonic_ns']) / 1e9
            high = before['seconds'] - (start - before['observed_monotonic_ns']) / 1e9
            margin = 2
        else:
            before = self.balances[before_stage]
            require(before['daily']['seconds'] == before['one_time']['seconds'] == 0,
                    'family-routines:grant-only-request')
            low = high = 0
            margin = 0
        requested = choice['request']['duration_seconds']
        require(low + requested - margin <= choice['estimate']['seconds'] <= high + requested + margin,
                'family-routines:request-increment')
        self.estimates[stage] = deepcopy(choice)

    def check_activity(self, stage, observed):
        super().check_activity(stage, observed)
        if stage in ('visit-1-work-capture', 'visit-2-work-capture', 'visit-3-work-capture', 'visit-4-work-capture'):
            who = 'riley' if stage.startswith(('visit-2-', 'visit-3-')) else 'jordan'
            original = self.activity_observations['initial-' + who + '-work-capture']
            current = self.activity_observations[stage]
            require((current.pid, current.endpoint, current.owner) == (original.pid, original.endpoint, original.owner),
                    'family-routines:original-work-window')


def execute(recorder, context):
    from e2e_fixture_preparation import RILEY_GAME_SUBSETS
    context.fixture_subsets = RILEY_GAME_SUBSETS
    context.fixture_caller = 'E2E-051/jordan'
    record_installed_journey(recorder, context, PLAN, timeout=5400, journey_type=FamilyRoutinesJourney)


E2E_CASES = {'jordan': execute}
