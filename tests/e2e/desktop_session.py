"""DESK03/04 qualification: shared system switching and logout commands."""

import json
from pathlib import Path
from types import SimpleNamespace

from installed_journey import InstalledJourney, JourneyPlan, validate_boundary
from journey_blocks import (fresh_desktop, lock_challenge, lock_recipient,
                            parent_management, native_activity_entry, rejected_gdm_return)
from journey_checks import AllowanceJourney, RetainedSessionJourney

ENTRY = fresh_desktop('parent')
ENTRY_PHASES = {
    'ready': 'setup', 'setup-detached': 'setup',
    **{stage: 'start' if stage == 'installed-greeter' else 'step-1' for stage in ENTRY},
}


def _plan(prefix, worker_mode, extra, extra_phase):
    screens = {**ENTRY, **extra}
    return JourneyPlan(
        prefix=prefix, worker_mode=worker_mode, screen_tags=screens,
        phases={**ENTRY_PHASES, **{stage: extra_phase for stage in extra}},
        advance_after={'desktop': extra_phase},
    )


LOGOUT_PLAN = _plan(
    'desktop-logout', 'desktop_session_logout',
    {'logout': 'system:parent-logout',
     'gdm-logged-out': 'ui:gdm-returned'},
    'step-2')
SWITCH_PLAN = _plan(
    'desktop-switch', 'desktop_session_switch',
    {'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned'},
    'step-2')


def lock_plan(supplied=False):
    return _plan('lock-supplied' if supplied else 'lock-command',
        'lock_surface_supplied' if supplied else 'lock_surface_command',
        {'unlocked-refused': 'ui:parent-lock-unlocked-refused',
         'lock-ready': 'ui:desktop',
         **({} if supplied else {'lock': 'system:parent-lock'}),
         **lock_challenge(),
         'lock-refusals': 'ui:parent-lock-refusals',
         'independent-challenge': 'ui:parent-lock-challenge'}, 'step-2')


LOCK_PLAN = lock_plan()
SUPPLIED_LOCK_PLAN = lock_plan(supplied=True)
LOCK_RECIPIENT_PLAN = _plan('lock-recipient', 'lock_recipient', {
    'unlocked-refused': 'ui:parent-lock-unlocked-refused',
    'lock-ready': 'ui:desktop',
    'lock': 'system:parent-lock',
    **lock_challenge(),
    'lock-recipient-refusals': 'ui:parent-lock-recipient-refusals',
    'independent-challenge': 'ui:parent-lock-challenge',
    **lock_recipient(),
    'final-challenge': 'ui:parent-lock-challenge',
}, 'step-2')


def retained_unlock_plan(retained=False):
    """Two independent entries; exact activity comparisons belong to this slice."""
    screens = {
        **fresh_desktop('parent'), **parent_management(),
        'allowance-configured': 'ui:time-explanation-positive-read',
        'repeat-desktop': 'ui:desktop',
        'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
        **{'fresh-' + stage: tag for stage, tag in fresh_desktop('child').items()},
        **native_activity_entry('activity', child='child'),
        'unlocked-refused': 'ui:child-lock-unlocked-refused',
        'lock-ready': 'ui:fresh-child-desktop', 'lock': 'system:child-lock',
        **lock_challenge(account='child'),
        'lock-recipient-refusals': 'ui:child-lock-recipient-refusals',
        'independent-challenge': 'ui:child-lock-challenge',
        **({'return-greeter': 'system:child-return-greeter',
            'retained-greeter': 'ui:gdm-returned',
            'retained-list': 'ui:gdm-child-list', 'retained-focused': 'ui:gdm-child-focused',
            'retained-recipient-qualified': 'ui:gdm-child-recipient',
            'retained-recipient-rechecked': 'ui:gdm-child-recipient-rechecked'}
           if retained else lock_recipient(account='child')),
        'unlock-desktop': 'ui:fresh-child-desktop',
        'returned-activity': 'ui:overlay-native-activity',
        'resume-opened': 'ui:overlay-native-activity',
        'resume-submit': 'ui:overlay-native-resubmit',
        'resume-submitted': 'ui:overlay-native-submitted',
        'usable-activity': 'ui:overlay-native-activity',
    }
    return JourneyPlan(
        prefix='retained-unlock' if retained else 'child-unlock',
        worker_mode='retained_unlock_success' if retained else 'child_unlock_success',
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start'},
        invocations=tuple(stage for stage in screens if stage in fresh_desktop('parent')
                          or stage.startswith('fresh-') or (retained and stage in (
                              'retained-list', 'retained-focused', 'retained-recipient-qualified',
                              'retained-recipient-rechecked', 'unlock-desktop'))),
        challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
            'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
            **({'retained-login': ('child', 'retained-recipient-qualified',
                                  'retained-recipient-rechecked')} if retained else {})},
        balance_checks={'allowance-configured': 900},
        activity_checks={'returned-activity': ('activity-capture', 'same'),
                         'usable-activity': ('activity-capture', 'same')},
        assertions_after={'allowance-configured': 'positive-daily-time',
                          'returned-activity': 'original-activity-preserved',
                          'usable-activity': 'original-activity-usable'},
    )


CHILD_UNLOCK_PLAN = retained_unlock_plan()
RETAINED_UNLOCK_PLAN = retained_unlock_plan(True)


def retained_denial_plan(retained=False):
    """Configured zero denial on independent GDM and actual lock surfaces."""
    entry = fresh_desktop('parent')
    child_entry = {'fresh-' + stage: tag for stage, tag in fresh_desktop('child').items()}
    parent_entry = {'return-' + stage: tag for stage, tag in entry.items()}
    management = parent_management()
    screens = {
        **entry, **management,
        'allowance-configured': 'ui:time-explanation-positive-read',
        'logout-ready': 'ui:desktop', 'logout': 'system:parent-logout',
        'gdm-logged-out': 'ui:gdm-returned', **child_entry,
        'child-switch-ready': 'ui:fresh-child-desktop',
        'child-switch': 'system:child-switch-user', 'child-greeter': 'ui:gdm-returned',
        'retained-before': 'system:child-retained-locked', **parent_entry,
        **{'return-' + stage: tag for stage, tag in management.items()},
        'zero-configured': 'ui:time-explanation-zero-read',
        'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
        **({'retained-list': 'ui:gdm-child-list', 'retained-focused': 'ui:gdm-child-focused',
            'retained-recipient-qualified': 'ui:gdm-child-recipient',
            'retained-recipient-rechecked': 'ui:gdm-child-recipient-rechecked',
            'time-denied': 'ui:gdm-child-time-denied', **rejected_gdm_return()}
           if retained else {
               'enter-locked': 'system:child-enter-locked',
               'curtain': 'ui:child-lock-curtain', 'reveal-ready': 'ui:child-lock-reveal-ready',
               'time-denied': 'ui:child-lock-time-denied',
               'return-greeter': 'system:child-return-greeter', 'denied-returned': 'ui:gdm-returned'}),
        'retained-after': 'system:child-retained-locked',
    }
    invocation = set(entry) | set(child_entry) | set(parent_entry)
    if retained:
        invocation |= {'retained-list', 'retained-focused', 'retained-recipient-qualified',
                       'retained-recipient-rechecked', 'time-denied', *rejected_gdm_return()}
    return JourneyPlan(
        prefix='retained-denial' if retained else 'lock-denial',
        worker_mode='retained_unlock_denied' if retained else 'child_unlock_denied',
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start'},
        invocations=tuple(stage for stage in screens if stage in invocation),
        challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
            'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
            'renewed-login': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
            **({'retained-login': ('child', 'retained-recipient-qualified',
                                  'retained-recipient-rechecked')} if retained else {})},
        balance_checks={'allowance-configured': 900, 'zero-configured': 0},
        assertions_after={'allowance-configured': 'positive-daily-time',
                          'zero-configured': 'zero-daily-and-grant-time',
                          'time-denied': 'specific-time-denial-no-desktop',
                          'denied-returned': 'usable-account-list',
                          'retained-after': 'same-retained-locked-child'},
    )


CHILD_DENIAL_PLAN = retained_denial_plan()
RETAINED_DENIAL_PLAN = retained_denial_plan(True)


class RetainedDenialJourney(RetainedSessionJourney):
    def __init__(self, context, progress, plan=RETAINED_DENIAL_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
                         session_checks={'retained-after': 'retained-before'})


class RetainedUnlockJourney(AllowanceJourney):
    def __init__(self, context, progress, plan=RETAINED_UNLOCK_PLAN, *, actions=None, transport=None):
        super().__init__(context, progress, plan, actions=actions, transport=transport)


class DesktopSessionJourney(InstalledJourney):
    """Installed envelope for one session-control attempt; review cannot pass it."""

    def __init__(self, context, progress, plan, *, actions=None, transport=None):
        super().__init__(context, progress, plan, actions=actions, transport=transport)


def run_attached(directory, lease, transport, ledger, plan, *, expected_inputs,
                 progress, actions=None, journey_type=InstalledJourney,
                 credentials=None, context=None, verified=None, timeout=600,
                 stop_before=None):
    """Use shared guarded input while the installed owner keeps its live guest.

    This completes controller stages and closes its worker. The caller retains
    the session, transport, VM watch and restoration authority; no completed
    worker module or customer acceptance result is claimed. A diagnostic may
    stop before a declared stage, retaining only its verified completed prefix.
    """
    from private_artifacts import require
    from fixture_credentials import FixtureCredentials
    import e2e_worker

    directory = Path(directory)
    require(stop_before is None or stop_before in plan.stages[2:],
            plan.prefix + ':attached-stop-stage')
    stages = (plan.stages if stop_before is None else
              plan.stages[:plan.stages.index(stop_before)])
    require(context is None or context.lease is lease, plan.prefix + ':attached-context')
    values = {} if context is None else vars(context).copy()
    values.update(directory=directory, lease=lease, commands=transport.commands)
    if verified is not None:
        values['verified'] = verified
    context = SimpleNamespace(**values)
    expected_inputs = dict(expected_inputs)

    # The dispatcher captures host helpers once. Uncaptured checkout reads are
    # allowed to stay live; source edits are not a mid-history failure gate.
    journey = journey_type(context, progress, plan, actions=actions, transport=transport)
    credentials = FixtureCredentials() if credentials is None else credentials
    require(type(credentials) is FixtureCredentials, plan.prefix + ':attached-credentials')
    credentials.provision_online(lease, transport)

    def step(guard):
        def guarded(**options):
            guard(**options)
            return guard()
        if stop_before is not None and (directory / (stop_before + '.request.json')).exists():
            guarded()
            validate_boundary(journey, directory, stop_before)
            return True
        journey.step(guarded)
        return stop_before is None and len(journey.steps) == len(stages)

    def validate():
        require(not journey.failed and journey.trace_token is None,
                plan.prefix + ':attached-incomplete')
        require([item['stage'] for item in journey.steps] == list(stages)
                and all(item.get('outcome') == 'passed' for item in journey.steps),
                plan.prefix + ':missing-stages')
        for observed in journey.steps[2:]:
            stage = observed['stage']
            kind, operation = plan.screen_tags[stage].split(':', 1)
            require(observed.get(kind, {}).get('operation') == operation
                    and observed[kind].get('outcome') == 'passed',
                    plan.prefix + ':' + kind + '-evidence')
            if plan.challenge_at(stage):
                require(observed.get('challenge') == plan.challenge_at(stage),
                        plan.prefix + ':challenge-evidence')

    worker = e2e_worker.run_distribution(
        directory, lease, ledger, expected_inputs=expected_inputs,
        observe=lambda: None, guarded_observe=step, validate=validate,
        credentials=credentials, attached=stop_before is None,
        maintenance=stop_before is not None, timeout=timeout,
        on_failure=lambda _category, code: (
            journey.collect_failure() if code != 'worker-interrupted' else None))
    require(worker['outcome'] == ('passed' if stop_before is None else 'scene-retained')
            and worker['scene_retained'] is True
            and worker['worker_stopped'] is True and worker['callback_closed'] is True,
            plan.prefix + ':attached-cleanup')
    worker['controller_observations'] = list(journey.steps)
    if stop_before is not None:
        worker['stop_before'] = stop_before
    return worker
