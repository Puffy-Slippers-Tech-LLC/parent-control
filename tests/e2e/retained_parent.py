"""DESK09/FLOW01 retained Parent entry, using public session/window proofs."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, prefixed_stages, retained_parent_entry
from journey_checks import RetainedDesktopJourney
from window_switch import window_switch_entry


ENTRY = fresh_desktop('parent')
AWAY = prefixed_stages('away', fresh_desktop('other-child'))
RETURN = prefixed_stages('return', retained_parent_entry())
INDEPENDENT = prefixed_stages('independent', fresh_desktop('parent'))
AGAIN = prefixed_stages('again', fresh_desktop('other-child'))
SCREENS = {
    **ENTRY, **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'before': 'ui:retained-parent-leave', 'session-before': 'system:parent-desktop-identity',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned', **AWAY, **RETURN,
    'session-returned': 'system:parent-desktop-identity',
    **window_switch_entry('focus-'),
    'second-before': 'ui:retained-parent-leave',
    'second-desktop': 'ui:desktop', 'second-switch': 'system:parent-switch-user',
    'second-greeter': 'ui:gdm-returned', **AGAIN,
    'independent-source': 'ui:standard-desktop',
    'independent-switch': 'system:standard-switch-user',
    'independent-greeter': 'ui:gdm-returned', **INDEPENDENT,
    **prefixed_stages('supplied', retained_parent_entry(source='same-user')),
    'session-supplied': 'system:parent-desktop-identity',
    'close': 'ui:retained-parent-close', 'absent-refused': 'ui:retained-parent-absent-refused',
}
LOGIN_PREFIXES = ('', 'away-', 'return-', 'again-', 'independent-')
LOGIN_STAGES = {prefix + stage for prefix in LOGIN_PREFIXES
                for stage in fresh_desktop('other-child' if prefix in ('away-', 'again-') else 'parent')}
PLAN = JourneyPlan(
    prefix='retained-parent', worker_mode='retained_parent', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if list(SCREENS).index(stage) <= list(SCREENS).index('before')
               else 'step-2' for stage in SCREENS}, 'installed-greeter': 'start'},
    advance_after={'before': 'step-2'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix.rstrip('-') or 'initial':
        ('other-child', prefix + 'standard-recipient-qualified', prefix + 'standard-recipient-rechecked')
        if prefix in ('away-', 'again-') else
        ('parent', prefix + 'recipient-qualified', prefix + 'recipient-rechecked')
        for prefix in LOGIN_PREFIXES},
    assertions_after={'return-parent-retained': 'same-parent-window-child-page-settings',
                      'session-returned': 'same-parent-desktop',
                      'supplied-parent-retained': 'independent-retained-entry',
                      'absent-refused': 'absent-window-refused-without-relaunch'},
)


class RetainedParentJourney(RetainedDesktopJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            parent_expected={'before': {'page': 'app-limits', 'settings': {
                'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['15 minutes']}}},
            parent_checks={stage: 'before' for stage in
                           ('return-parent-retained', 'second-before', 'supplied-parent-retained')},
            window_checks={stage: 'before' for stage in
                           ('focus-switch-parent-before', 'focus-switch-parent-ready', 'focus-switch-parent')},
            session_checks={'session-returned': 'session-before', 'session-supplied': 'session-before'})
