"""289b: allowance saves keep Jordan's game but deny a second instance."""
from copy import deepcopy

from accessible_ui import (MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS,
                           OVERLAY_BOUND_OPERATIONS)
from child_saved_work import work_document_actions
from feedback_composition import text_fragment
from game_permission import APPS
from installed_journey import JourneyPlan
from journey_blocks import (allowance_selection, app_policy_entry, desktop_entry,
                            game_usable_app, overlay_entry, prefixed_stages)
from named_app_set import saved_rows
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney, policy_edit
from private_artifacts import require
from request_flow import approval_and_return
from time_profiles_dominant import DailyDominantProfileJourney
from ui_observations import SettingsObservation


SCREENS = app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                           initial_rows=False)
for index, (app, draft, access) in enumerate(APPS):
    SCREENS.update(policy_edit(app, draft, access, 'policy-' + str(index), setup=True))
SCREENS.update({**text_fragment('catalogue-clear', 'clear'), **saved_rows(APPS, 'saved'),
                'parent-desktop': 'ui:desktop', 'parent-switch': 'system:parent-switch-user',
                'parent-gdm': 'ui:gdm-returned'})
LOGINS, CHALLENGES, ACTIVITIES, ENTRIES, OVERLAYS = {}, {}, {}, {}, {}
SETTINGS = {'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
            'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))}


def entry(prefix, account, retained=False):
    screens = prefixed_stages(prefix, desktop_entry(
        account, source='gdm', entry='retained' if retained else 'fresh'))
    if retained and account == 'other-child':
        # Fullscreen games hide Shell's Activities control. The active unlocked
        # session and following game read establish the usable retained return.
        screens[prefix + '-desktop'] = 'system:standard-desktop-identity'
    LOGINS.update(screens)
    role = 'recipient' if account == 'parent' else 'standard-recipient'
    CHALLENGES[prefix] = (account, prefix + '-' + role + '-qualified',
                         prefix + '-' + role + '-rechecked')
    return screens


for mode in ('windowed', 'fullscreen'):
    if mode == 'fullscreen':
        # Independent fresh child entry: explicitly clear the first slice's
        # remaining grant and restore positive daily time through Parent.
        SCREENS.update({**entry('reset-parent', 'parent', True),
            'reset-retained': 'ui:retained-parent-read',
            **{'reset-' + action: 'ui:revoke-' + operation for action, operation in (
                ('open', 'open'), ('warning', 'warning'), ('confirm', 'confirm'),
                ('cleared', 'cleared-balances'))},
            **allowance_selection('reset-daily', (30,)),
            'reset-settings': 'ui:existing-returned', 'reset-balance': 'ui:time-explanation-reach-read',
            'reset-desktop': 'ui:desktop', 'reset-switch': 'system:parent-switch-user',
            'reset-gdm': 'ui:gdm-returned'})
        SETTINGS['reset-settings'] = SettingsObservation('existing-fixture-child', True, ('30 minutes',))
    screens = {**entry(mode + '-entry', 'other-child'),
        **prefixed_stages(mode + '-work', {action: 'ui:work-jordan-' + action for action in (
            'open', 'opened', *(('edit', 'save', 'saved') if mode == 'windowed' else ()),
            'submit', 'submitted', 'activity')})}
    prefix = mode + '-first'
    flow = {**overlay_entry('request', 'panel', form_operation='request-overlay-jordan-ready'),
            **approval_and_return(prefix='new', entry='open', surface='overlay',
                child='existing-fixture-child', approver='fixture-parent',
                duration_seconds=900, allow_soft=True)}
    del flow['countdown']
    OVERLAYS.update({prefix + '-' + stage: ('other-child', 'parent', 900, True)
                    for stage, tag in flow.items()
                    if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})
    screens.update({**prefixed_stages(prefix, flow),
        **prefixed_stages(mode + '-play', {**game_usable_app(level=1, mode=mode),
                                          'capture': 'ui:game-activity'})})
    for name, minutes, activity, capture, action, played in (
        ('positive', 45, 'game-activity', mode + '-play-capture', 'game-resume', 'game-resumed-activity'),
        ('zero', 0, 'game-resumed-activity', mode + '-positive-played', 'game-continue', 'game-continued-activity')):
        prefix = mode + '-' + name
        screens.update({prefix + '-leave': 'system:standard-desktop-identity',
            prefix + '-switch': 'system:standard-switch-user', prefix + '-gdm': 'ui:gdm-returned',
            **entry(prefix + '-parent', 'parent', True), prefix + '-retained': 'ui:retained-parent-read',
            # Deadline comparisons need a newly loaded status inside each read
            # bracket; merely expanding Parent can return its 30-second cache.
            **({mode + '-original-grant': 'ui:time-explanation-refresh-read'} if name == 'positive' else {}),
            **allowance_selection(prefix + '-daily', (minutes,)),
            prefix + '-settings': 'ui:existing-returned', prefix + '-balance': 'ui:time-explanation-refresh-read',
            prefix + '-parent-leave': 'ui:desktop', prefix + '-parent-switch': 'system:parent-switch-user',
            prefix + '-parent-gdm': 'ui:gdm-returned', **entry(prefix + '-child', 'other-child', True),
            prefix + '-game-before': 'ui:' + activity, prefix + '-work-before': 'ui:work-jordan-activity',
            prefix + '-denied': 'ui:game-' + ('fullscreen-' if mode == 'fullscreen' else '') + 'secondary-command-blocked',
            prefix + '-game-after': 'ui:' + activity, prefix + '-continue': 'ui:' + action,
            prefix + '-played': 'ui:' + played, prefix + '-hard': 'ui:native-hard-command-blocked',
            prefix + '-submit': 'ui:work-jordan-resubmit', prefix + '-submitted': 'ui:work-jordan-submitted',
            prefix + '-work-after': 'ui:work-jordan-activity'})
        SETTINGS[prefix + '-settings'] = SettingsObservation(
            'existing-fixture-child', True, (str(minutes) + ' minutes',))
        ENTRIES[prefix + '-child-entry-guard'] = capture
        for side in ('before', 'after'):
            ACTIVITIES[prefix + '-game-' + side] = (capture, 'same')
            ACTIVITIES[prefix + '-work-' + side] = (mode + '-work-activity', 'same')
    screens.update({mode + '-work-close': 'ui:work-jordan-close',
                    mode + '-work-closed': 'ui:work-jordan-closed',
                    mode + '-logout': 'system:standard-logout', mode + '-logged-out': 'ui:gdm-returned'})
    SCREENS.update(screens)
SCREENS['cleanup'] = 'ui:gdm-returned'
PLAN = JourneyPlan(
    prefix='retained-game-denial', worker_mode='retained_game_denial', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify', 'parent-switch': 'work-prepare',
                   'windowed-work-saved': 'work-jordan-saved', 'cleanup': 'work-cleanup'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    settings_checks=SETTINGS, balance_checks={'allowance-configured': 1800},
    match_checks={'saved-' + role + '-match': (app, rule) for role, app, rule in (
        ('a', MATCH_APPS['A'], MATCH_RULES[0]), ('h', MATCH_APPS['H'], MATCH_RULES[3]),
        ('game', MATCH_APPS['Game'], MATCH_RULES[-1]))},
    access_checks={'saved-' + role + '-access': (app, access)
                   for role, (app, _draft, access) in zip(('a', 'h', 'game'), APPS)},
    invocations=tuple(stage for stage in SCREENS if stage in LOGINS and not stage.endswith('entry-guard')
        or stage.endswith(('request-panel', 'request-launch', 'request-form'))),
    challenges=CHALLENGES, activity_checks=ACTIVITIES, activity_entries=ENTRIES,
    overlay_request=('other-child', 'parent', 900, True), overlay_requests=OVERLAYS,
)


class RetainedGameDenialJourney(AppPolicyJourney):
    def __init__(self, context, progress):
        work = work_document_actions()
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False, profile='game'),
            **{name: work[name] for name in ('work-prepare', 'work-jordan-saved', 'work-cleanup')}})
        self.original_grants = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'reset-balance':
            require(observed['ui']['time_explanation']['one_time']['seconds'] == 0,
                    'retained-game-denial:reset-grant')
        for mode in ('windowed', 'fullscreen'):
            if stage == mode + '-original-grant':
                balance = observed['ui']['time_explanation']
                require(balance['child'] == 'existing-fixture-child'
                        and balance['one_time']['seconds'] >= 900,
                        'retained-game-denial:original-grant')
                self.original_grants[mode] = (deepcopy(balance), tuple(self.ui.read_bounds))
            if stage not in (mode + '-positive-balance', mode + '-zero-balance'):
                continue
            before, bounds = self.original_grants[mode]
            balance = observed['ui']['time_explanation']
            low, high = DailyDominantProfileJourney.elapsed(bounds, tuple(self.ui.read_bounds))
            daily, grant, total = (balance[key]['seconds'] for key in ('daily', 'one_time', 'total'))
            precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time', 'total'))
            margin = precision + before['one_time']['precision_seconds'] + 2
            require(balance['child'] == before['child'] == 'existing-fixture-child'
                    and before['one_time']['seconds'] - high - margin <= grant
                        <= before['one_time']['seconds'] - low + margin
                    and grant - precision >= 300
                    and (daily == 0 if '-zero-' in stage else 0 < daily <= 2700)
                    and abs(total - max(daily, grant)) <= precision,
                    'retained-game-denial:original-grant-preserved')
            observed['comparison'] = {'original_grant_preserved': True,
                'elapsed_interval_seconds': [low, high], 'rounding_margin_seconds': margin}

    def check_activity(self, stage, observed):
        super().check_activity(stage, observed)
        if stage.endswith(('-positive-played', '-zero-played')):
            mode = stage.split('-', 1)[0]
            original = self.activity_observations[mode + '-play-capture']
            current = self.activity_observations[stage]
            require((current.binding, current.pid, current.endpoint, current.owner, current.state[:2]) ==
                    (original.binding, original.pid, original.endpoint, original.owner, original.state[:2]),
                    'retained-game-denial:original-playable-window')
            observed['comparison'] = {'original_window_playable': True, 'outcome': 'passed'}
