"""DESK09/FLOW01 retained Parent entry, using public session/window proofs."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, prefixed_stages
from private_artifacts import require
from window_switch import window_switch_entry


def retained_parent_entry(*, source='desktop'):
    """Declared retained entry; no launch or child reselection is permitted."""
    require(source in ('desktop', 'same-user'), 'retained-parent:source')
    return {
        **({'source-desktop': 'ui:standard-desktop',
            'source-switch': 'system:standard-switch-user',
            'source-greeter': 'ui:gdm-returned',
            **fresh_desktop('parent')} if source == 'desktop' else
           {'desktop': 'ui:desktop'}),
        'parent-retained': 'ui:retained-parent-read',
    }


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


class RetainedParentJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.retained = None
        self.session_identity = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'before':
            require(self.retained is None, 'retained-parent:entry-replay')
            value = observed['ui']['retained_parent']
            require(value['page'] == 'app-limits' and value['settings'] == {
                'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['15 minutes']},
                'retained-parent:initial-settings')
            self.retained = deepcopy(value)
        elif stage in ('return-parent-retained', 'second-before', 'supplied-parent-retained'):
            require(self.retained is not None and observed['ui']['retained_parent'] == self.retained,
                    'retained-parent:window-child-page-settings-changed')
            observed['comparison'] = {'same_parent_window_child_page_settings': True}
        elif stage in ('focus-switch-parent-before', 'focus-switch-parent-ready', 'focus-switch-parent'):
            require(self.retained is not None and observed['ui']['window'] == self.retained['window'],
                    'retained-parent:foreground-window-replaced')
        elif stage == 'session-before':
            require(self.session_identity is None, 'retained-parent:session-replay')
            self.session_identity = observed['system']['session_sha256']
        elif stage in ('session-returned', 'session-supplied'):
            require(self.session_identity is not None
                    and observed['system']['session_sha256'] == self.session_identity,
                    'retained-parent:desktop-replaced')
            observed['comparison'] = {'same_parent_desktop': True}
