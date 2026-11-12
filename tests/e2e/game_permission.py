"""289a: a parent's Soft choice controls the real game, preserving saved work."""
from accessible_ui import (KIOSK_BOUND_OPERATIONS, MATCH_APPS, MATCH_RULES,
                           NAMED_CHILD_OPERATIONS, OVERLAY_BOUND_OPERATIONS)
from feedback_composition import text_fragment
from installed_journey import JourneyPlan
from journey_blocks import (app_policy_entry, desktop_entry, game_usable_app,
                            overlay_entry, prefixed_stages)
from named_app_set import saved_rows
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney, policy_edit
from request_flow import approval_and_return
from synthetic_files import work_document_actions
from ui_observations import SettingsObservation


APPS = ((MATCH_APPS['A'], 'match-precise', 'allowed'),
        (MATCH_APPS['H'], 'match-hard-precise', 'permanent'),
        (MATCH_APPS['Game'], 'match-game-precise', 'conditional'))
SCREENS = app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                           initial_rows=False)
for index, (app, draft, access) in enumerate(APPS):
    SCREENS.update(policy_edit(app, draft, access, 'policy-' + str(index), setup=True))
SCREENS.update({**text_fragment('catalogue-clear', 'clear'), **saved_rows(APPS, 'saved'),
                'parent-logout': 'system:parent-logout'})
LOGINS = {}
CHALLENGES = {}
ACTIVITIES, OVERLAYS, KIOSKS = {}, {}, {}
for mode in ('windowed', 'fullscreen'):
    entry = prefixed_stages(mode + '-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
    LOGINS.update(entry)
    CHALLENGES[mode + '-entry'] = ('other-child', mode + '-entry-standard-recipient-qualified',
                                 mode + '-entry-standard-recipient-rechecked')
    work = {action: 'ui:work-jordan-' + action for action in (
        'open', 'opened', *(('edit', 'save', 'saved') if mode == 'windowed' else ()),
        'submit', 'submitted', 'activity')}
    screens = {**entry, **prefixed_stages(mode + '-work', work),
               mode + '-denied': 'ui:game-' + ('fullscreen-' if mode == 'fullscreen' else '') + 'command-blocked'}
    # The later inclusion uses the already qualified retained kiosk return.
    # Each mode starts in its own fresh child session with soft apps excluded.
    for name, surface, included in (('first', 'overlay', True),
                                     ('included', 'kiosk', True), ('excluded', 'overlay', False)):
        prefix = mode + '-' + name
        choices = dict(child='existing-fixture-child', approver='fixture-parent',
                       duration_seconds=900, allow_soft=included)
        flow = approval_and_return(prefix='new', entry='new' if surface == 'kiosk' else 'open', **choices, surface=surface,
                                   child_entry='retained' if surface == 'kiosk' else 'fresh')
        # Countdown arithmetic is already qualified; this slice independently
        # observes access, captured windows and usable saved work.
        del flow['countdown']
        if surface == 'overlay':
            # Reopening keeps the child's saved choices. Entry needs the
            # usable fixed-child form; FLOW20 selects and reads this request.
            flow = {**overlay_entry('request', 'panel',
                    form_operation='request-overlay-jordan-ready'), **flow}
            OVERLAYS.update({prefix + '-' + stage: ('other-child', 'parent', 900, included)
                             for stage, tag in flow.items()
                             if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})
        else:
            flow = {'leave-desktop': 'system:standard-desktop-identity',
                    'switch-user': 'system:standard-switch-user', 'gdm-switched': 'ui:gdm-returned',
                    **flow}
            if mode == 'fullscreen':
                flow['retained-desktop'] = 'system:standard-desktop-identity'
            login = prefixed_stages(prefix + '-retained', desktop_entry(
                'other-child', source='gdm', entry='retained'))
            LOGINS.update(login)
            CHALLENGES[prefix + '-retained'] = (
                'other-child', prefix + '-retained-standard-recipient-qualified',
                prefix + '-retained-standard-recipient-rechecked')
            KIOSKS.update({prefix + '-' + stage: ('other-child', 'parent', 900, True)
                           for stage, tag in flow.items()
                           if tag.removeprefix('ui:') in KIOSK_BOUND_OPERATIONS})
        screens.update(prefixed_stages(prefix, flow))
        if name == 'first':
            screens.update(prefixed_stages(mode + '-play', {
                **game_usable_app(level=1, mode=mode), 'capture': 'ui:game-policy-activity'}))
        elif included:
            screens[prefix + '-game'] = 'ui:game-policy-activity'
            ACTIVITIES[prefix + '-game'] = (mode + '-play-capture', 'same')
        else:
            screens[prefix + '-closed'] = 'ui:game-policy-closed'
            ACTIVITIES[prefix + '-closed'] = (mode + '-play-capture', 'closed')
            screens[prefix + '-denied'] = screens[mode + '-denied']
        if name != 'first':
            screens.update({prefix + '-work': 'ui:work-jordan-activity',
                            prefix + '-submit': 'ui:work-jordan-resubmit',
                            prefix + '-submitted': 'ui:work-jordan-submitted',
                            prefix + '-original': 'ui:work-jordan-activity',
                            prefix + '-hard': 'ui:native-hard-command-blocked'})
            for suffix in ('work', 'original'):
                ACTIVITIES[prefix + '-' + suffix] = (mode + '-work-activity', 'same')
    screens.update({mode + '-work-close': 'ui:work-jordan-close',
                    mode + '-work-closed': 'ui:work-jordan-closed',
                    mode + '-logout': 'system:standard-logout'})
    SCREENS.update(screens)
SCREENS['cleanup'] = 'ui:gdm-returned'
PLAN = JourneyPlan(
    prefix='game-permission', worker_mode='game_permission', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify', 'parent-logout': 'work-prepare',
                   'windowed-work-saved': 'work-jordan-saved', 'cleanup': 'work-cleanup'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    settings_checks={'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
                     'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    match_checks={'saved-' + role + '-match': (app, rule)
                  for role, app, rule in (('a', MATCH_APPS['A'], MATCH_RULES[0]),
                                         ('h', MATCH_APPS['H'], MATCH_RULES[3]),
                                         ('game', MATCH_APPS['Game'], MATCH_RULES[-1]))},
    access_checks={'saved-' + role + '-access': (app, access)
                   for role, (app, _draft, access) in zip(('a', 'h', 'game'), APPS)},
    invocations=tuple(stage for stage, tag in SCREENS.items()
        # Fullscreen retained entry observes the unlocked session identity
        # instead of Shell controls hidden by the game. It is still invoked.
        if (stage in LOGINS and not stage.endswith('entry-guard'))
        or stage.endswith(('request-panel', 'request-launch', 'request-form'))),
    challenges=CHALLENGES, activity_checks=ACTIVITIES,
    activity_entries={mode + '-included-retained-entry-guard': mode + '-play-capture'
                      for mode in ('windowed', 'fullscreen')},
    overlay_request=('other-child', 'parent', 900, True), overlay_requests=OVERLAYS,
    kiosk_request=('other-child', 'parent', 900, True), kiosk_requests=KIOSKS,
)


class GamePermissionJourney(AppPolicyJourney):
    def __init__(self, context, progress):
        work = work_document_actions()
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False, profile='game'),
            **{name: work[name] for name in ('work-prepare', 'work-jordan-saved', 'work-cleanup')}})
