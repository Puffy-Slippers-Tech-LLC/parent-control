"""Case 139: one install/remove/reinstall/purge history through public actions."""

from accessible_ui import MATCH_APP
from installed_journey import JourneyPlan
from journey_blocks import (fresh_desktop, parent_management, package_installation,
                            station_entry, prefixed_stages, custom_allowance)
from journey_checks import (allowed_app_rows, installed_accounts, access_choice,
                           policy_projection, request_choices)
from native_fixtures import fixture_actions
from package_command import BINDING, REMOVE, REINSTALL, PURGE, FRESH_INSTALL
from package_lifecycle import record_lifecycle_journey
from request_flow import prepared_request, CHOICES
from ui_observations import SettingsObservation


ROLES = {'activated': 'parent', 'restricted-child': 'child', 'remove-parent': 'parent',
         'removed': 'parent', 'healthy-child': 'child', 'reinstall-parent': 'parent',
         'retained': 'parent', 'reapply-parent': 'parent', 'reblocked-child': 'child',
         'purge-parent': 'parent', 'purged': 'parent', 'fresh': 'parent'}
LOGINS = {prefix: prefixed_stages(prefix, fresh_desktop(role)) for prefix, role in ROLES.items()}
REBOOTS = tuple((prefix + '-reboot-requested', prefix + '-installed-greeter')
                for prefix in ('activated', 'removed', 'retained', 'purged', 'fresh'))
INSTALL = {**package_installation(),
           'activated-reboot-requested': 'system:parent-command-context', **LOGINS['activated']}
CONFIGURE = {
    **prefixed_stages('initial', parent_management()),
    'initial-apps': 'ui:parent-apps-page', 'initial-rows': 'ui:parent-app-rows',
    'initial-screen': 'ui:access-screen',
    'limit-enabled': 'ui:parent-toggle-enabled', 'save-enabled': 'ui:parent-save-enabled',
    **custom_allowance('initial-allowance', 4),
    'initial-apps-again': 'ui:parent-apps-page', 'initial-block': 'ui:access-permanent',
    'initial-block-read': 'ui:access-row', 'initial-policy': 'ui:kiosk-riley-language-policy',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry(), **prepared_request(prefix='open', entry='open', initial='default', **CHOICES),
    'open-cancel': 'ui:kiosk-request-cancel', 'open-returned': 'ui:gdm-station-returned',
    **LOGINS['restricted-child'],
    'blocked-before-remove': 'ui:overlay-native-command-blocked',
    'overlay-launch': 'ui:child-command-launch', 'overlay-choices': 'ui:overlay-valid-fraction-soft-read',
    'overlay-cancel': 'ui:overlay-request-cancel', 'restricted-logout': 'system:child-logout',
    **prepared_request(prefix='new', entry='new', initial='selected', **CHOICES),
    'approval-open': 'ui:kiosk-mate-open', 'approval-qualified': 'ui:kiosk-mate-qualified',
    'approval-rechecked': 'ui:kiosk-mate-rechecked', 'approval-success': 'ui:kiosk-mate-submit-success',
    'new-returned': 'ui:gdm-station-returned',
}
REMOVAL = {
    **LOGINS['remove-parent'], **prefixed_stages('before-remove', parent_management()),
    'active-grant': 'ui:kiosk-riley-language-policy',
    'remove-submitted': 'system:parent-command-context', 'remove-result': 'system:parent-command-context',
    'removed-reboot-requested': 'system:parent-command-context', **LOGINS['removed'],
    'removed-parent-logout': 'system:parent-logout', **LOGINS['healthy-child'],
    'healthy-command': 'ui:overlay-native-command-launch', 'healthy-opened': 'ui:overlay-native-opened',
    'healthy-submit': 'ui:overlay-native-submit', 'healthy-submitted': 'ui:overlay-native-submitted',
    'healthy-close': 'ui:overlay-native-close', 'healthy-closed': 'ui:overlay-native-closed',
    'healthy-child-logout': 'system:child-logout',
}
RESTORATION = {
    **LOGINS['reinstall-parent'],
    'reinstall-submitted': 'system:parent-command-context', 'reinstall-result': 'system:parent-command-context',
    'retained-reboot-requested': 'system:parent-command-context', **LOGINS['retained'],
    **prefixed_stages('retained', parent_management()),
    'retained-policy': 'ui:kiosk-riley-language-policy',
    'retained-switch': 'system:parent-switch-user', 'retained-greeter': 'ui:gdm-returned',
    **prefixed_stages('retained', station_entry()), 'retained-request': 'ui:kiosk-valid-fraction-soft-read',
    'retained-cancel': 'ui:kiosk-request-cancel', 'retained-returned': 'ui:gdm-station-returned',
    **LOGINS['reapply-parent'], **prefixed_stages('reapply', parent_management()),
    **custom_allowance('reapply-allowance', 5),
    'reapply-apps': 'ui:parent-apps-page', 'reapply-allowed': 'ui:access-allowed',
    'reapply-allowed-read': 'ui:access-row', 'reapply-block': 'ui:access-permanent',
    'reapply-block-read': 'ui:access-row', 'reapply-policy': 'ui:kiosk-riley-language-policy',
    'reapply-switch': 'system:parent-switch-user', 'reapply-greeter': 'ui:gdm-returned',
    **LOGINS['reblocked-child'], 'blocked-after-reinstall': 'ui:overlay-native-command-blocked',
    'reblocked-logout': 'system:child-logout', **LOGINS['purge-parent'],
    'purge-submitted': 'system:parent-command-context', 'purge-result': 'system:parent-command-context',
    'purged-reboot-requested': 'system:parent-command-context', **LOGINS['purged'],
    'fresh-submitted': 'system:parent-command-context', 'fresh-result': 'system:parent-command-context',
    'fresh-reboot-requested': 'system:parent-command-context', **LOGINS['fresh'],
    **prefixed_stages('fresh', parent_management()),
    'fresh-apps': 'ui:parent-apps-page', 'fresh-rows': 'ui:parent-app-rows',
    'fresh-switch': 'system:parent-switch-user', 'fresh-greeter': 'ui:gdm-returned',
    **prefixed_stages('fresh', station_entry()), 'fresh-request': 'ui:kiosk-lifecycle-defaults',
    'fresh-cancel': 'ui:kiosk-request-cancel', 'fresh-returned': 'ui:gdm-station-returned',
}
SCREENS = {**INSTALL, **CONFIGURE, **REMOVAL, **RESTORATION}
OPERATIONS = (('package-submitted', BINDING, 'package-result'),
              ('remove-submitted', REMOVE, 'remove-result'),
              ('reinstall-submitted', REINSTALL, 'reinstall-result'),
              ('purge-submitted', PURGE, 'purge-result'),
              ('fresh-submitted', FRESH_INSTALL, 'fresh-result'))
PLAN = JourneyPlan(prefix='package-removal', worker_mode='package_removal', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in INSTALL}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in CONFIGURE},
            **{stage: 'step-3' for stage in REMOVAL},
            **{stage: 'step-4' for stage in RESTORATION}},
    advance_after={'activated-desktop': 'step-2', 'new-returned': 'step-3',
                   'healthy-child-logout': 'step-4'},
    stage_actions={**{stage: 'package-' + binding for stage, binding, _ in OPERATIONS},
                   'desktop': 'native-verify'},
    invocations=tuple(stage for _, screens in LOGINS.items() for stage in screens),
    challenges={prefix: (role, prefix + ('-recipient-qualified' if role == 'parent' else
                    '-child-recipient-qualified'), prefix + ('-recipient-rechecked' if role == 'parent'
                    else '-child-recipient-rechecked')) for prefix, role in ROLES.items()},
    reboot_transition=REBOOTS[0], additional_reboot_transitions=REBOOTS[1:],
    settings_checks={'initial-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'retained-parent-selected': SettingsObservation('fixture-child', True, ('4 minutes',)),
        'fresh-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',))},
    assertions_after={'package-result': 'installation-notice', 'remove-result': 'removal-notice',
                      'fresh-returned': 'visible-result'})

SAVED_POLICY = {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['4 minutes']}
SAVED_CHOICES = {**CHOICES, 'custom_text': '1.25'}
CHECKS = {
    **{stage: allowed_app_rows for stage in ('initial-rows', 'fresh-rows')},
    **{stage: installed_accounts for stage in ('activated-installed-greeter',
                                             'retained-installed-greeter', 'fresh-installed-greeter')},
    **{stage: access_choice(MATCH_APP, choice) for stage, choice in (
        ('initial-block-read', 'permanent'), ('reapply-allowed-read', 'allowed'),
        ('reapply-block-read', 'permanent'))},
    'initial-policy': policy_projection(SAVED_POLICY, row=(MATCH_APP, 'permanent'), capture='policy'),
    'active-grant': policy_projection(SAVED_POLICY, row=(MATCH_APP, 'permanent'), same='policy', grant='positive'),
    'retained-policy': policy_projection(SAVED_POLICY, row=(MATCH_APP, 'permanent'), same='policy', grant='zero'),
    'reapply-policy': policy_projection({**SAVED_POLICY, 'allowance': ['5 minutes']}, row=(MATCH_APP, 'permanent')),
    'open-estimate': request_choices(SAVED_CHOICES, capture='choices'),
    **{stage: request_choices(SAVED_CHOICES, same='choices') for stage in (
        'new-estimate', 'overlay-choices', 'retained-request')},
}


def execute(recorder, context):
    record_lifecycle_journey(recorder, context, PLAN, operations=OPERATIONS, checks=CHECKS,
                             actions=fixture_actions(include_refusal=False), timeout=3600)


E2E_CASES = {'continuous': execute}
