"""A parent's Soft choice controls the real game, preserving saved work."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from accessible_ui import (KIOSK_BOUND_OPERATIONS, MATCH_APPS, MATCH_RULES,
                           NAMED_CHILD_OPERATIONS, OVERLAY_BOUND_OPERATIONS)
from calendar_fixture import preset_ordinary_daytime
from feedback_composition import text_fragment
from installed_journey import JourneyPlan
from journey_blocks import (app_policy_entry, desktop_entry, game_usable_app,
                            native_blocked_app, overlay_entry, prefixed_stages)
from named_app_set import saved_rows
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney, policy_edit
from private_artifacts import require
from request_flow import approval_and_return
from synthetic_files import work_document_actions
from ui_observations import SettingsObservation


APPS = ((MATCH_APPS['A'], 'match-precise', 'allowed'),
        (MATCH_APPS['H'], 'match-hard-precise', 'permanent'),
        (MATCH_APPS['Game'], 'match-game-precise', 'conditional'))


def permission_plan(child):
    """Jordan's two modes and Riley's missing windowed binding share one history."""
    require(child in ('existing', 'child'), 'game-permission:child')
    riley = child == 'child'
    who, account = ('riley', 'child') if riley else ('jordan', 'other-child')
    role = 'child' if riley else 'standard'
    identity = 'fixture-child' if riley else 'existing-fixture-child'
    modes = ('windowed',) if riley else ('windowed', 'fullscreen')
    screens = app_policy_entry(child=child, allowance='time-explanation-setup-thirty-read',
                               initial_rows=False)
    for index, (app, draft, access) in enumerate(APPS):
        screens.update(policy_edit(app, draft, access, 'policy-' + str(index), setup=True))
    screens.update({**text_fragment('catalogue-clear', 'clear'), **saved_rows(APPS, 'saved'),
                    'parent-logout': 'system:parent-logout'})
    logins, challenges, activities, overlays, kiosks = {}, {}, {}, {}, {}
    for mode in modes:
        entry = prefixed_stages(mode + '-entry', desktop_entry(account, source='gdm', entry='fresh'))
        logins.update(entry)
        challenges[mode + '-entry'] = (account, mode + '-entry-' + role + '-recipient-qualified',
                                      mode + '-entry-' + role + '-recipient-rechecked')
        work = {action: 'ui:work-' + who + '-' + action for action in (
            'open', 'opened', *(('edit', 'save', 'saved') if mode == 'windowed' else ()),
            'submit', 'submitted', 'activity')}
        history = {**entry, **prefixed_stages(mode + '-work', work),
                   mode + '-denied': 'ui:game-' + ('fullscreen-' if mode == 'fullscreen' else '') + 'command-blocked'}
        for name, surface, included in (('first', 'overlay', True),
                                        ('included', 'kiosk', True), ('excluded', 'overlay', False)):
            prefix = mode + '-' + name
            choices = dict(child=identity, approver='fixture-parent', duration_seconds=900, allow_soft=included)
            flow = approval_and_return(prefix='new', entry='new' if surface == 'kiosk' else 'open',
                **choices, surface=surface, child_entry='retained' if surface == 'kiosk' else 'fresh')
            # Access and captured work are this slice's results; countdown
            # arithmetic retains its existing qualification.
            del flow['countdown']
            if surface == 'overlay':
                # Entry must accept the child's remembered choices. The next
                # operation selects and independently reads this request.
                flow = {**overlay_entry('request', 'panel', form_operation=(
                    'request-overlay-' + who + '-ready')), **flow}
                overlays.update({prefix + '-' + stage: (account, 'parent', 900, included)
                                 for stage, tag in flow.items()
                                 if tag.removeprefix('ui:') in OVERLAY_BOUND_OPERATIONS})
            else:
                flow = {'leave-desktop': 'system:' + role + '-desktop-identity',
                        'switch-user': 'system:' + role + '-switch-user', 'gdm-switched': 'ui:gdm-returned',
                        **flow}
                if mode == 'fullscreen':
                    flow['retained-desktop'] = 'system:standard-desktop-identity'
                login = prefixed_stages(prefix + '-retained', desktop_entry(account, source='gdm', entry='retained'))
                logins.update(login)
                challenges[prefix + '-retained'] = (
                    account, prefix + '-retained-' + role + '-recipient-qualified',
                    prefix + '-retained-' + role + '-recipient-rechecked')
                kiosks.update({prefix + '-' + stage: (account, 'parent', 900, True)
                               for stage, tag in flow.items()
                               if tag.removeprefix('ui:') in KIOSK_BOUND_OPERATIONS})
            history.update(prefixed_stages(prefix, flow))
            if name == 'first':
                history.update(prefixed_stages(mode + '-play', {
                    **game_usable_app(level=1, mode=mode), 'capture': 'ui:game-policy-activity'}))
            elif included:
                history[prefix + '-game'] = 'ui:game-policy-activity'
                activities[prefix + '-game'] = (mode + '-play-capture', 'same')
            else:
                history[prefix + '-closed'] = 'ui:game-policy-closed'
                activities[prefix + '-closed'] = (mode + '-play-capture', 'closed')
                history[prefix + '-denied'] = history[mode + '-denied']
            if name != 'first':
                history.update({prefix + '-work': 'ui:work-' + who + '-activity',
                                prefix + '-submit': 'ui:work-' + who + '-resubmit',
                                prefix + '-submitted': 'ui:work-' + who + '-submitted',
                                prefix + '-original': 'ui:work-' + who + '-activity',
                                prefix + '-hard': native_blocked_app('H', child=account)['command']})
                for suffix in ('work', 'original'):
                    activities[prefix + '-' + suffix] = (mode + '-work-activity', 'same')
        history.update({mode + '-work-close': 'ui:work-' + who + '-close',
                        mode + '-work-closed': 'ui:work-' + who + '-closed',
                        mode + '-logout': 'system:' + role + '-logout'})
        screens.update(history)
    screens['cleanup'] = 'ui:gdm-returned'
    return JourneyPlan(
        prefix='riley-game-permission' if riley else 'game-permission',
        worker_mode='riley_game_permission' if riley else 'game_permission', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start'},
        stage_actions={'setup-detached': 'daytime-window', 'desktop': 'native-verify',
                       'parent-logout': 'work-prepare', 'windowed-work-saved': 'work-' + who + '-saved',
                       'cleanup': 'work-cleanup'},
        child_bindings={stage: child for stage, tag in screens.items()
                        if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
        settings_checks={'parent-selected': SettingsObservation(identity, False, ('0 minutes',)),
                         'saved-settings': SettingsObservation(identity, True, ('30 minutes',))},
        balance_checks={'allowance-configured': 1800},
        match_checks={'saved-' + name + '-match': (app, rule)
                      for name, app, rule in (('a', MATCH_APPS['A'], MATCH_RULES[0]),
                                             ('h', MATCH_APPS['H'], MATCH_RULES[3]),
                                             ('game', MATCH_APPS['Game'], MATCH_RULES[-1]))},
        access_checks={'saved-' + name + '-access': (app, access)
                       for name, (app, _draft, access) in zip(('a', 'h', 'game'), APPS)},
        invocations=tuple(stage for stage in screens
            if (stage in logins and not stage.endswith('entry-guard'))
            or stage.endswith(('request-panel', 'request-launch', 'request-form'))),
        challenges=challenges, activity_checks=activities,
        activity_entries={mode + '-included-retained-entry-guard': mode + '-play-capture' for mode in modes},
        overlay_request=(account, 'parent', 900, True), overlay_requests=overlays,
        kiosk_request=(account, 'parent', 900, True), kiosk_requests=kiosks,
    )


PLAN = permission_plan('existing')
RILEY_PLAN = permission_plan('child')


def daytime_window(journey, guard):
    preset = preset_ordinary_daytime(journey, guard)
    clock = journey.vm.local_calendar()
    now = datetime.fromtimestamp(clock['epoch_ns'] / 1e9, ZoneInfo(clock['timezone']))
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), now.tzinfo)
    remaining = midnight.timestamp() - now.timestamp()
    require(remaining > 3600, 'game-permission:midnight-margin')
    guard()
    return {'preset': preset, 'seconds_before_midnight': remaining}


class GamePermissionJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN):
        riley = plan is RILEY_PLAN
        who = 'riley' if riley else 'jordan'
        work = work_document_actions()
        super().__init__(context, progress, plan, actions={
            **fixture_actions(include_refusal=False, profile='game', child='child' if riley else 'existing'),
            **{name: work[name] for name in ('work-prepare', 'work-' + who + '-saved', 'work-cleanup')},
            'daytime-window': daytime_window})
