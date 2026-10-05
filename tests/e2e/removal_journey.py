"""Case 139: one install/remove/reinstall/purge history through public actions."""

from accessible_ui import MATCH_APP
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, package_installation, station_entry
from journey_checks import allowed_app_rows, installed_accounts
from native_fixtures import fixture_actions
from package_command import BINDING, REMOVE, REINSTALL, PURGE, FRESH_INSTALL
from package_lifecycle import PackageLifecycleJourney
from private_artifacts import require
from request_flow import prepared_request, CHOICES
from ui_observations import SettingsObservation


def names(prefix, screens):
    return {prefix + '-' + stage: tag for stage, tag in screens.items()}


SCREENS = dict(package_installation())
PHASES = {stage: 'step-1' for stage in SCREENS}
CHALLENGES = {}
LOGIN_STAGES = []
REBOOTS = []


def add(screens, phase):
    require(not set(screens) & set(SCREENS), 'package-removal:duplicate-stage')
    SCREENS.update(screens)
    PHASES.update({stage: phase for stage in screens})


def login(prefix, role, phase, *, reboot=False):
    screens = names(prefix, fresh_desktop(role))
    if reboot:
        stage = prefix + '-reboot-requested'
        add({stage: 'system:parent-command-context'}, phase)
        REBOOTS.append((stage, next(iter(screens))))
    add(screens, phase)
    LOGIN_STAGES.extend(screens)
    first = next(stage for stage in screens if stage.endswith('-qualified'))
    CHALLENGES[prefix] = (role, first, first.removesuffix('-qualified') + '-rechecked')


def management(prefix, phase):
    add(names(prefix, parent_management()), phase)


def package(prefix, phase):
    add({prefix + '-submitted': 'system:parent-command-context',
         prefix + '-result': 'system:parent-command-context'}, phase)


def allowance(prefix, minutes, phase):
    add({prefix + '-open': 'ui:custom-' + str(minutes) + '-open',
         **{prefix + '-text-' + action: 'ui:text-daily-' + str(minutes) + '-' + action
            for action in ('focus', 'selected', 'read')},
         prefix + '-saved': 'ui:custom-' + str(minutes) + '-saved'}, phase)


login('activated', 'parent', 'step-1', reboot=True)
management('initial', 'step-2')
add({'initial-apps': 'ui:parent-apps-page', 'initial-rows': 'ui:parent-app-rows',
     'initial-screen': 'ui:access-screen',
     'limit-enabled': 'ui:parent-toggle-enabled', 'save-enabled': 'ui:parent-save-enabled',
     }, 'step-2')
allowance('initial-allowance', 4, 'step-2')
add({'initial-apps-again': 'ui:parent-apps-page', 'initial-block': 'ui:access-permanent',
     'initial-block-read': 'ui:access-row', 'initial-policy': 'ui:kiosk-riley-language-policy',
     'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned'}, 'step-2')
add(station_entry(), 'step-2')
add(prepared_request(prefix='open', entry='open', initial='default', **CHOICES), 'step-2')
add({'open-cancel': 'ui:kiosk-request-cancel', 'open-returned': 'ui:gdm-station-returned'}, 'step-2')
login('restricted-child', 'child', 'step-2')
add({'blocked-before-remove': 'ui:overlay-native-command-blocked',
     'overlay-launch': 'ui:child-command-launch',
     'overlay-choices': 'ui:overlay-valid-fraction-soft-read',
     'overlay-cancel': 'ui:overlay-request-cancel',
     'restricted-logout': 'system:child-logout'}, 'step-2')
add(prepared_request(prefix='new', entry='new', initial='selected', **CHOICES), 'step-2')
add({'approval-open': 'ui:kiosk-mate-open', 'approval-qualified': 'ui:kiosk-mate-qualified',
     'approval-rechecked': 'ui:kiosk-mate-rechecked', 'approval-success': 'ui:kiosk-mate-submit-success',
     'new-returned': 'ui:gdm-station-returned'}, 'step-2')
login('remove-parent', 'parent', 'step-3')
management('before-remove', 'step-3')
add({'active-grant': 'ui:kiosk-riley-language-policy'}, 'step-3')
package('remove', 'step-3')
login('removed', 'parent', 'step-3', reboot=True)
add({'removed-parent-logout': 'system:parent-logout'}, 'step-3')
login('healthy-child', 'child', 'step-3')
add({'healthy-command': 'ui:overlay-native-command-launch', 'healthy-opened': 'ui:overlay-native-opened',
     'healthy-submit': 'ui:overlay-native-submit', 'healthy-submitted': 'ui:overlay-native-submitted',
     'healthy-close': 'ui:overlay-native-close', 'healthy-closed': 'ui:overlay-native-closed',
     'healthy-child-logout': 'system:child-logout'}, 'step-3')
login('reinstall-parent', 'parent', 'step-4')
package('reinstall', 'step-4')
login('retained', 'parent', 'step-4', reboot=True)
management('retained', 'step-4')
add({'retained-policy': 'ui:kiosk-riley-language-policy',
     'retained-switch': 'system:parent-switch-user', 'retained-greeter': 'ui:gdm-returned',
     **names('retained', station_entry()),
     'retained-request': 'ui:kiosk-valid-fraction-soft-read',
     'retained-cancel': 'ui:kiosk-request-cancel', 'retained-returned': 'ui:gdm-station-returned'}, 'step-4')
login('reapply-parent', 'parent', 'step-4')
management('reapply', 'step-4')
allowance('reapply-allowance', 5, 'step-4')
add({'reapply-apps': 'ui:parent-apps-page', 'reapply-allowed': 'ui:access-allowed',
     'reapply-allowed-read': 'ui:access-row', 'reapply-block': 'ui:access-permanent',
     'reapply-block-read': 'ui:access-row', 'reapply-policy': 'ui:kiosk-riley-language-policy',
     'reapply-switch': 'system:parent-switch-user',
     'reapply-greeter': 'ui:gdm-returned'}, 'step-4')
login('reblocked-child', 'child', 'step-4')
add({'blocked-after-reinstall': 'ui:overlay-native-command-blocked',
     'reblocked-logout': 'system:child-logout'}, 'step-4')
login('purge-parent', 'parent', 'step-4')
package('purge', 'step-4')
login('purged', 'parent', 'step-4', reboot=True)
package('fresh', 'step-4')
login('fresh', 'parent', 'step-4', reboot=True)
management('fresh', 'step-4')
add({'fresh-apps': 'ui:parent-apps-page', 'fresh-rows': 'ui:parent-app-rows',
     'fresh-switch': 'system:parent-switch-user', 'fresh-greeter': 'ui:gdm-returned',
     **names('fresh', station_entry()), 'fresh-request': 'ui:kiosk-lifecycle-defaults',
     'fresh-cancel': 'ui:kiosk-request-cancel', 'fresh-returned': 'ui:gdm-station-returned'}, 'step-4')

OPERATIONS = (('package-submitted', BINDING, 'package-result'),
              ('remove-submitted', REMOVE, 'remove-result'),
              ('reinstall-submitted', REINSTALL, 'reinstall-result'),
              ('purge-submitted', PURGE, 'purge-result'),
              ('fresh-submitted', FRESH_INSTALL, 'fresh-result'))
PLAN = JourneyPlan(prefix='package-removal', worker_mode='package_removal', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', **PHASES, 'installed-greeter': 'start'},
    advance_after={'activated-desktop': 'step-2', 'new-returned': 'step-3',
                   'healthy-child-logout': 'step-4'},
    stage_actions={**{stage: 'package-' + binding for stage, binding, _ in OPERATIONS},
                   'desktop': 'native-verify'},
    invocations=tuple(LOGIN_STAGES), challenges=CHALLENGES,
    reboot_transition=REBOOTS[0], additional_reboot_transitions=tuple(REBOOTS[1:]),
    settings_checks={'initial-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'retained-parent-selected': SettingsObservation('fixture-child', True, ('4 minutes',)),
        'fresh-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',))},
    assertions_after={'package-result': 'installation-notice', 'remove-result': 'removal-notice',
                      'fresh-returned': 'visible-result'})


class RemovalJourney(PackageLifecycleJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, operations=OPERATIONS,
                         actions=fixture_actions(include_refusal=False) if actions is None else actions)
        self.policy = None
        self.choices = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('initial-rows', 'fresh-rows'):
            allowed_app_rows(self, observed)
        if stage in ('activated-installed-greeter', 'retained-installed-greeter', 'fresh-installed-greeter'):
            installed_accounts(self, observed)
        if stage in ('initial-block-read', 'reapply-allowed-read', 'reapply-block-read'):
            require(observed['ui'].get('access') == {'app': MATCH_APP,
                'choice': 'allowed' if stage == 'reapply-allowed-read' else 'permanent'},
                'package-removal:app-rule')
        if stage in ('initial-policy', 'active-grant', 'retained-policy'):
            policy = observed['ui']['language_policy']
            require(policy['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                    'allowance': ['4 minutes']} and any(row[0] == MATCH_APP and row[1] == 'permanent'
                    for row in policy['rows']), 'package-removal:policy')
            if stage == 'initial-policy':
                self.policy = {key: policy[key] for key in ('settings', 'rows')}
            else:
                require({key: policy[key] for key in ('settings', 'rows')} == self.policy,
                        'package-removal:retained-policy')
                require(policy['balances']['one_time'] > 0 if stage == 'active-grant' else
                        policy['balances']['one_time'] == 0, 'package-removal:grant')
        if stage == 'reapply-policy':
            policy = observed['ui']['language_policy']
            require(policy['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                    'allowance': ['5 minutes']} and any(row[0] == MATCH_APP and row[1] == 'permanent'
                    for row in policy['rows']), 'package-removal:reapplied-policy')
        if stage in ('open-estimate', 'new-estimate', 'overlay-choices', 'retained-request'):
            request = observed['ui']['valid_choice']['request']
            choices = {key: request[key] for key in ('child', 'approver', 'duration_seconds',
                                                    'custom_text', 'allow_soft')}
            require(choices == {'child': 'fixture-child', 'approver': 'fixture-parent',
                    'duration_seconds': 75, 'custom_text': '1.25', 'allow_soft': True},
                    'package-removal:request-choices')
            if stage == 'open-estimate':
                self.choices = choices
            else:
                require(choices == self.choices, 'package-removal:retained-request')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=3600, journey_type=RemovalJourney)


E2E_CASES = {'continuous': execute}
