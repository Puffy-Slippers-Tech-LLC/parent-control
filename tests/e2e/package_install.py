"""LIFE04 install: compose verified administrator submission and public readback."""

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import package_installation
from package_command import BINDING, PackageCommand
from private_artifacts import require
from product_free_entry import ProductFreeEntryJourney, SCREENS, refuse_command


PLAN = JourneyPlan(
    prefix='package-install', worker_mode='package_install',
    screen_tags={'wrong-entry': SCREENS['wrong-entry'], **package_installation()},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS},
            'package-submitted': 'step-2', 'package-result': 'step-2'},
    stage_actions={'wrong-entry': 'refuse-command', 'package-submitted': 'install-package'},
    assertions_after={'wrong-entry': 'wrong-entry-refused',
                      'command-context': 'administrator-package-context',
                      'package-result': 'install-completed-with-reboot-notice'})


def submit_install(journey, guard):
    """One LIFE04 install input; retain the command even on uncertain failure."""
    require(journey.package is None, 'package-install:replay')
    guard()
    command = journey.package = PackageCommand(journey.transport, journey.context.verified)
    result = command.submit(BINDING, command.verified.inputs['package_sha256'], command.identity)
    guard()
    return result


def submit_release(journey, guard, binding, slot):
    """Finite upgrade leaves keep consumed commands in their recipe-owned slots."""
    from package_command import OLD_INSTALL, UPGRADE
    require((binding, slot) in ((OLD_INSTALL, 'previous_package'), (UPGRADE, 'upgrade_package')),
            'package-install:release-binding')
    require(getattr(journey, slot) is None, 'package-install:replay')
    guard()
    command = PackageCommand(journey.transport, journey.context.verified)
    setattr(journey, slot, command)
    label = 'previous' if binding == OLD_INSTALL else 'current'
    result = command.submit(binding, command.verified.upgrade_inputs['packages'][label]['sha256'],
                            command.identity)
    guard()
    return result


def observe_release(command, label, before, *, changed_boot=False):
    """Independent completion, public installed version and preservation proof."""
    require(command is not None and label in ('previous', 'current'), 'package-install:missing-command')
    output = command.read_result()
    first, second = command.read_identity(), command.read_identity()
    require(first == second, 'package-install:unstable-readback')
    require(first['version'] == command.verified.upgrade_inputs['packages'][label]['version'],
            'package-install:installed-version')
    preserved = dict(first['preserved'])
    if label == 'previous':
        # A genuine first installation creates package/dependency accounts.
        # Every pre-existing identity/language remains independently unchanged.
        preserved['accounts'] = {uid: preserved['accounts'].get(uid)
                                 for uid in before['preserved']['accounts']}
    require(preserved == before['preserved'], 'package-install:preservation')
    require((first['boot'] != before['boot'] if changed_boot else first['boot'] == before['boot']),
            'package-install:boot-continuity')
    if not changed_boot:
        require(first['session'] == before['session'], 'package-install:session-changed')
    return {**output, 'installed_version': first['version'], 'boot_sha256': first['boot'],
            'preservation_verified': True, 'independent_readback': True}, first


def observe_install(journey):
    """A separate checkpoint must establish completion and the final notice."""
    require(journey.package is not None, 'package-install:missing-command')
    return journey.package.read_result()


def observe_current_install(command, before):
    """Latest install completion/version/same boot with pre-existing state preserved."""
    require(command is not None and command.binding == BINDING, 'package-install:missing-command')
    output = command.read_result()
    first, second = command.read_identity(), command.read_identity()
    require(first == second, 'package-install:unstable-readback')
    require(before['version'] is None and
            first['version'] == command.package_identities()['current']['version'],
            'package-install:installed-version')
    preserved = dict(first['preserved'])
    preserved['accounts'] = {uid: preserved['accounts'].get(uid)
                             for uid in before['preserved']['accounts']}
    require(preserved == before['preserved'], 'package-install:preservation')
    require(first['packages'] == before['packages'], 'package-install:inputs-changed')
    require(first['boot'] == before['boot'], 'package-install:boot-continuity')
    require(first['session'] == before['session'], 'package-install:session-changed')
    return {**output, 'installed_version': first['version'], 'boot_sha256': first['boot'],
            'preservation_verified': True, 'independent_readback': True}


def check_install_result(journey, observed):
    """Attach independent public completion evidence before acknowledging a stage."""
    observed['package'] = observe_install(journey)


class PackageInstallJourney(ProductFreeEntryJourney):
    def __init__(self, context, progress):
        require(getattr(context, 'product_free', False) is True
                and getattr(context, 'asset_transfer', None) is not None,
                'package-install:setup-required')
        InstalledJourney.__init__(self, context, progress, PLAN,
            actions={'refuse-command': refuse_command, 'install-package': submit_install})
        self.package = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'package-result':
            check_install_result(self, observed)
