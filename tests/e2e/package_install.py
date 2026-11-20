"""LIFE04 install: compose verified administrator submission and public readback."""

from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import package_installation
from package_command import BINDING, OLD_INSTALL, UPGRADE, PackageCommand
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
    require((binding, slot) in ((OLD_INSTALL, 'previous_package'), (UPGRADE, 'upgrade_package')),
            'package-install:release-binding')
    require(getattr(journey, slot) is None, 'package-install:replay')
    guard()
    command = PackageCommand(journey.transport, journey.context.verified)
    setattr(journey, slot, command)
    label = 'previous' if binding == OLD_INSTALL else 'current'
    failures = getattr(journey.transport, 'product_failures', None)
    if binding == OLD_INSTALL and failures is not None:
        failures.checkpoint()
    result = command.submit(binding, command.verified.upgrade_inputs['packages'][label]['sha256'],
                            command.identity)
    guard()
    return result


def observe_release(command, label, before, *, changed_boot=False):
    """Independent completion, public installed version and preservation proof."""
    require(command is not None and (label, command.binding) in (
        ('previous', OLD_INSTALL), ('current', UPGRADE)), 'package-install:wrong-release')
    output, current = command.read_result(include_identity=True)
    preserved = dict(current['preserved'])
    expected = deepcopy(before['preserved'])
    if label == 'previous':
        # A genuine first installation creates package/dependency accounts.
        # Every pre-existing identity/language remains independently unchanged.
        preserved['accounts'] = {uid: preserved['accounts'].get(uid)
                                 for uid in before['preserved']['accounts']}
    else:
        # Upgrading permanently disables shell login for the reserved station.
        # Require that exact migration, preserving its UID, other fields and
        # every ordinary account. The journey still checks graphical entry.
        station = [account for account in expected['accounts'].values()
                   if account['identity'][0] == 'oh-no-parent-control']
        require(len(station) == 1, 'package-install:kiosk-account')
        station[0]['identity'][6] = '/usr/sbin/nologin'
    require(preserved == expected, 'package-install:preservation')
    require((current['boot'] != before['boot'] if changed_boot else current['boot'] == before['boot']),
            'package-install:boot-continuity')
    if not changed_boot:
        require(current['session'] == before['session'], 'package-install:session-changed')
    return {**output, 'installed_version': current['version'], 'boot_sha256': current['boot'],
            'preservation_verified': True, 'independent_readback': True}, current


def observe_install(journey):
    """A separate checkpoint must establish completion and the final notice."""
    require(journey.package is not None, 'package-install:missing-command')
    return journey.package.read_result()


def submit_unrelated(journey, guard):
    """One normal distribution reconfiguration; retain uncertain consumption."""
    from package_command import UNRELATED
    require(journey.unrelated_package is None, 'unrelated-package:replay')
    guard()
    command = journey.unrelated_package = PackageCommand(journey.transport, journey.context.verified)
    inputs = journey.unrelated_inputs
    result = command.submit(UNRELATED, inputs['sha256'], command.identity, unrelated=inputs)
    guard()
    return result


def observe_unrelated(command, before, inputs):
    """Separate command completion, genuine system request and preservation."""
    from package_command import UNRELATED
    require(command is not None and command.binding == UNRELATED, 'unrelated-package:missing-command')
    completion, current = command.read_result(include_identity=True)
    require(current == before == command.entry, 'unrelated-package:product-or-boot-changed')
    system = command.read_unrelated(inputs)
    return {'completion': completion, 'system': system, 'product_identity_unchanged': True,
            'boot_sha256': current['boot'], 'independent_readback': True}


class UnrelatedPackageJourney(InstalledJourney):
    """Bind clean entry and independent result to caller-declared endpoints."""

    def __init__(self, context, progress, plan, *, entry, result, actions=None):
        stages = list(plan.screen_tags)
        submissions = [stage for stage, action in plan.stage_actions.items()
                       if action == 'unrelated-package']
        require(entry in stages and result in stages and len(submissions) == 1
                and stages.index(entry) < stages.index(submissions[0]) < stages.index(result)
                and all(plan.screen_tags[stage] == 'system:parent-command-context'
                        for stage in (entry, submissions[0], result)), 'unrelated-package:plan')
        super().__init__(context, progress, plan, actions=actions)
        self.unrelated_entry_stage, self.unrelated_result_stage = entry, result
        self.unrelated_package = self.unrelated_entry = self.unrelated_inputs = None
        self.unrelated_result_observed = False
        if getattr(context, 'installed_snapshot', None):
            from asset_transfer import AssetTransfer
            require(getattr(context, 'asset_transfer', None) is None,
                    'unrelated-package:transfer-replay')
            context.asset_transfer = AssetTransfer(context.verified)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == self.unrelated_entry_stage:
            from copy import deepcopy
            require(self.unrelated_entry is None and (getattr(self.context, 'installed_snapshot', None)
                    or self.reboot_observed), 'unrelated-package:activation-required')
            command = PackageCommand(self.transport, self.context.verified)
            entry = command.read_identity()
            require(entry['version'] == command.package_identities()['current']['version']
                    and entry['boot'] == self.boot, 'unrelated-package:product-identity')
            observed['unrelated_entry'] = command.read_unrelated(entry=True)
            self.unrelated_inputs = deepcopy(observed['unrelated_entry']['package'])
            self.unrelated_entry = deepcopy(entry)
        if stage == self.unrelated_result_stage:
            require(self.unrelated_entry is not None and not self.unrelated_result_observed,
                    'unrelated-package:entry-required')
            observed['unrelated_package'] = observe_unrelated(self.unrelated_package, self.unrelated_entry,
                                                             self.unrelated_inputs)
            self.unrelated_result_observed = True


def unrelated_journey(*, entry, result):
    """Recorder-compatible shared comparison engine; recipes own endpoints."""
    from functools import partial
    return partial(UnrelatedPackageJourney, entry=entry, result=result)


def observe_current_install(command, before):
    """Latest install completion/version/same boot with pre-existing state preserved."""
    require(command is not None and command.binding == BINDING, 'package-install:missing-command')
    output, current = command.read_result(include_identity=True)
    require(before['version'] is None, 'package-install:unexpected-entry-version')
    preserved = dict(current['preserved'])
    preserved['accounts'] = {uid: preserved['accounts'].get(uid)
                             for uid in before['preserved']['accounts']}
    require(preserved == before['preserved'], 'package-install:preservation')
    require(current['packages'] == before['packages'], 'package-install:inputs-changed')
    require(current['boot'] == before['boot'], 'package-install:boot-continuity')
    require(current['session'] == before['session'], 'package-install:session-changed')
    return {**output, 'installed_version': current['version'], 'boot_sha256': current['boot'],
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
