"""300k latest-only install, first Chinese notice and one reboot; no approval."""
from chinese_kiosk_lifecycle import (
    ChinesePresentationMixin, renewed_desktop, renewed_language_entry, set_desktop_language)
from customer_reboot import refuse_reboot
from installed_journey import JourneyPlan
from journey_blocks import product_free_desktop, station_entry
from native_fixtures import fixture_actions
from package_command import BINDING, PackageCommand
from package_install import observe_current_install, submit_install
from package_upgrade import refuse_input
from private_artifacts import require
from product_free_entry import ProductFreeEntryJourney


CHILD = renewed_desktop('language-', 'other-child', product_free=True)
CHILD['language-desktop'] = 'ui:chinese-standard-desktop'
ADMIN = renewed_desktop('install-', 'parent', product_free=True)
RETURN = renewed_desktop('return-', 'parent')
SCREENS = {
    'wrong-entry': 'ui:gdm-product-free-list', **product_free_desktop(),
    'language-setting': 'system:parent-command-context',
    'language-parent-logout': 'system:parent-logout', **CHILD,
    'language-child-logout': 'system:standard-logout', **ADMIN,
    'install-ready': 'system:parent-command-context',
    'package-submitted': 'system:parent-command-context',
    'package-result': 'system:parent-command-context',
    'package-reread': 'system:parent-command-context',
    'install-switch': 'system:parent-switch-user', **station_entry('initial-'),
    'initial-notice': 'ui:kiosk-initial-notice',
    'initial-notice-close': 'ui:kiosk-initial-notice-close',
    'initial-notice-return': 'ui:kiosk-initial-notice-return', **RETURN,
    'reboot-requested': 'system:parent-command-context',
    'reboot-greeter': 'ui:gdm-list', **station_entry('renewed-'),
    'initial-language': 'ui:kiosk-initial-language',
    'initial-language-cancel': 'ui:kiosk-initial-language-cancel',
    'initial-form': 'ui:kiosk-initial-form',
}
PLAN = JourneyPlan(prefix='chinese-current-install', worker_mode='chinese_current_install',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'wrong-entry': 'start'},
    invocations=(*CHILD, *ADMIN, *RETURN),
    challenges={
        'chinese-child': ('other-child', 'language-standard-recipient-qualified', 'language-standard-recipient-rechecked'),
        'install-parent': ('parent', 'install-recipient-qualified', 'install-recipient-rechecked'),
        'return-parent': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
    stage_actions={'wrong-entry': 'refuse-command', 'command-context': 'native-verify',
        'language-setting': 'language-setting', 'install-ready': 'renewed-entry',
        'package-submitted': 'install-package'},
    assertions_after={'wrong-entry': 'wrong-entry-refused',
        'command-context': 'chinese-assets-verified', 'language-setting': 'chinese-account-confirmed',
        'language-desktop': 'renewed-chinese-desktop', 'install-ready': 'renewal-preservation',
        'package-result': 'latest-install-version-notice-same-boot',
        'package-reread': 'independent-install-reread',
        'initial-notice': 'first-chinese-restart-notice',
        'reboot-greeter': 'changed-boot-greeter',
        'initial-language': 'first-chinese-chooser-and-default', 'initial-form': 'initial-chinese-form'})


def set_language(journey, guard):
    command = PackageCommand(journey.transport, journey.context.verified)
    before = command.read_identity()
    require(before['version'] is None and before['boot'] == journey.boot,
            'chinese-current-install:product-free-required')
    require(command.read_identity() == before, 'chinese-current-install:unstable-entry')
    journey.language_entry = before
    return set_desktop_language(journey, guard, product_free=True)


def install_entry(journey, guard):
    require(journey.install_entry is None, 'chinese-current-install:entry-replay')
    journey.install_entry = renewed_language_entry(journey, guard, journey.language_entry)
    require(journey.install_entry['version'] is None, 'chinese-current-install:product-free-required')
    command = PackageCommand(journey.transport, journey.context.verified)
    digest = command.verified.inputs['package_sha256']
    for binding, value, identity, code in (
        ('unregistered', digest, command.identity, 'package:unregistered-command'),
        (BINDING, 'f' * 64 if digest != 'f' * 64 else 'e' * 64, command.identity, 'package:wrong-artifact'),
        (BINDING, digest, {**command.identity, 'run': 'wrong'}, 'package:wrong-attempt'),
        (BINDING, digest, {**command.identity, 'domain_uuid': 'wrong'}, 'package:wrong-attempt')):
        refuse_input(command, binding, value, identity, code)
    guard()
    return {'independent_readback': True, 'renewed_session': True, 'preservation_verified': True}


def current_actions():
    return {**fixture_actions(profile='chinese', include_refusal=False),
        'refuse-command': refuse_reboot, 'language-setting': set_language,
        'renewed-entry': install_entry, 'install-package': submit_install}


class ChineseCurrentInstallJourney(ChinesePresentationMixin, ProductFreeEntryJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        require(context.verified.upgrade_inputs is None, 'chinese-current-install:single-package-required')
        super().__init__(context, progress, plan,
                         actions=current_actions() if actions is None else actions)
        self.package = self.language_entry = self.install_entry = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('package-result', 'package-reread'):
            observed['package'] = observe_current_install(self.package, self.install_entry)
            command = PackageCommand(self.transport, self.context.verified)
            refuse_input(command, BINDING, command.verified.inputs['package_sha256'],
                         command.identity, 'package:replay')
