"""LIFE04 install: compose verified administrator submission and public readback."""

from installed_journey import InstalledJourney, JourneyPlan
from package_command import BINDING, PackageCommand
from private_artifacts import require
from product_free_entry import ProductFreeEntryJourney, SCREENS, refuse_command


PLAN = JourneyPlan(
    prefix='package-install', worker_mode='package_install',
    screen_tags={**SCREENS, 'package-submitted': 'system:parent-command-context',
                 'package-result': 'system:parent-command-context'},
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


def observe_install(journey):
    """A separate checkpoint must establish completion and the final notice."""
    require(journey.package is not None, 'package-install:missing-command')
    return journey.package.read_result()


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
            observed['package'] = observe_install(self)
