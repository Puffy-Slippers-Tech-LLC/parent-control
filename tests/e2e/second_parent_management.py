"""Two administrators manage Jordan through their own fresh and retained windows."""

from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop, parent_management,
                            prefixed_stages)
from journey_checks import RetainedDesktopJourney
from ui_observations import SettingsObservation


SCREENS = {
    **prefixed_stages('jamie-fresh', desktop_entry('parent', source='gdm', entry='fresh')),
    **prefixed_stages('jamie-open', parent_management(parent='parent', child='existing')),
    'jamie-open-allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'jamie-saved': 'ui:existing-returned',
    'jamie-captured': 'ui:retained-parent-read',
    'jamie-session': 'system:parent-desktop-identity',
    **desktop_return('jamie-leave', account='parent'),
    **prefixed_stages('sam-fresh', desktop_entry('second-parent', source='gdm', entry='fresh')),
    **prefixed_stages('sam-open', parent_management(parent='second-parent', child='existing')),
    'sam-open-allowance-configured': 'ui:time-explanation-setup-positive-read',
    'sam-saved': 'ui:existing-returned',
    'sam-captured': 'ui:retained-parent-read',
    'sam-session': 'system:second-parent-desktop-identity',
    **prefixed_stages('jamie-back', desktop_entry('parent', source='desktop', entry='retained',
                                               source_account='second-parent')),
    **prefixed_stages('jamie-return', parent_management(parent='parent', child='existing', window='retained')),
    'jamie-return-allowance-configured': 'ui:time-explanation-enabled-thirty-read',
    'jamie-resaved': 'ui:existing-returned',
    'jamie-same-session': 'system:parent-desktop-identity',
    **prefixed_stages('sam-back', desktop_entry('second-parent', source='desktop', entry='retained',
                                             source_account='parent')),
    **prefixed_stages('sam-return', parent_management(parent='second-parent', child='existing', window='retained')),
    'sam-same-session': 'system:second-parent-desktop-identity',
}
ENTRY_ROLES = {'jamie-fresh': 'parent', 'sam-fresh': 'second-parent',
               'jamie-back': 'parent', 'sam-back': 'second-parent'}
LOGIN_STAGES = {prefix + '-' + stage for prefix, role in ENTRY_ROLES.items()
                for stage in fresh_desktop(role)}
PARENT_BINDINGS = {
    stage: 'second-parent' if stage.startswith('sam-') else 'parent'
    for stage, tag in SCREENS.items()
    if stage.startswith(('jamie-open-', 'sam-open-', 'jamie-return-', 'sam-return-'))
       or stage in ('jamie-saved', 'sam-saved', 'jamie-captured', 'sam-captured', 'jamie-resaved')
    if tag.startswith('ui:') and not stage.endswith('-desktop')
}
CHILD_STAGES = {stage: 'existing' for stage, tag in SCREENS.items()
                if tag in ('ui:retained-parent-read', 'ui:time-explanation-setup-thirty-read',
                           'ui:time-explanation-setup-positive-read',
                           'ui:time-explanation-enabled-thirty-read')}


def settings(minutes, enabled=True):
    return {'child': 'existing-fixture-child', 'limit_enabled': enabled,
            'allowance': [f'{minutes} minutes']}


PLAN = JourneyPlan(
    prefix='second-parent-management', worker_mode='second_parent_management', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'jamie-fresh-installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (role, prefix + '-recipient-qualified', prefix + '-recipient-rechecked')
                for prefix, role in ENTRY_ROLES.items()},
    parent_bindings=PARENT_BINDINGS, child_bindings=CHILD_STAGES,
    settings_checks={stage: SettingsObservation.from_settings(value) for stage, value in {
                     'jamie-saved': settings(30), 'sam-open-parent-selected': settings(30),
                     'sam-saved': settings(15), 'jamie-return-parent-selected': settings(15),
                     'jamie-resaved': settings(30), 'sam-return-parent-selected': settings(30)}.items()},
    balance_checks={'jamie-open-allowance-configured': 1800,
                    'sam-open-allowance-configured': 900,
                    'jamie-return-allowance-configured': 1800},
    assertions_after={'sam-saved': 'second-parent-management-save',
                      'jamie-return-parent-retained': 'original-first-parent-window-current-settings',
                      'sam-return-parent-retained': 'original-second-parent-window-current-settings',
                      'sam-same-session': 'both-parent-desktops-preserved'},
)


class SecondParentManagementJourney(RetainedDesktopJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN,
            parent_expected={'jamie-captured': {'page': 'screen-limits', 'settings': settings(30)},
                             'sam-captured': {'page': 'screen-limits', 'settings': settings(15)}},
            parent_checks={},
            window_checks={'jamie-return-parent-retained': 'jamie-captured',
                           'sam-return-parent-retained': 'sam-captured'},
            session_checks={'jamie-same-session': 'jamie-session',
                            'sam-same-session': 'sam-session'})
