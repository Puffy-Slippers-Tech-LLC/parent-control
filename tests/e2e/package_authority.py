"""005 fixed command qualification; installation composition remains separate."""

from installed_journey import InstalledJourney, JourneyPlan
from package_command import BINDING, PackageCommand
from private_artifacts import EvidenceError, require
from product_free_entry import ProductFreeEntryJourney, SCREENS, refuse_command

PLAN = JourneyPlan(prefix='package-authority', worker_mode='package_authority',
    screen_tags={**SCREENS, 'package-submitted': 'system:parent-command-context',
                 'package-result': 'system:parent-command-context'},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS},
            'package-submitted': 'step-2', 'package-result': 'step-2'},
    stage_actions={'wrong-entry': 'refuse-command', 'package-submitted': 'submit-package'},
    assertions_after={'wrong-entry': 'wrong-entry-refused',
                      'command-context': 'administrator-package-context',
                      'package-result': 'package-completion-notice'})


def submit_package(journey, guard):
    command = journey.package = PackageCommand(journey.transport, journey.context.verified)
    digest, identity = command.verified.inputs['package_sha256'], command.identity
    rejected = []
    for label, binding, artifact, owner in (
        ('unregistered', 'arbitrary-shell', digest, identity),
        ('artifact', BINDING, ('0' if digest[0] != '0' else '1') + digest[1:], identity),
        ('vm', BINDING, digest, {**identity, 'domain_uuid': 'wrong-vm'}),
        ('attempt', BINDING, digest, {**identity, 'run': 'wrong-attempt'}),
    ):
        try:
            command.submit(binding, artifact, owner)
        except EvidenceError:
            rejected.append(label)
        else:
            require(False, 'package:invalid-input-accepted')
    guard()
    command.submit(BINDING, digest, identity)
    guard()
    try:
        command.submit(BINDING, digest, identity)
    except EvidenceError as error:
        require(str(error) == 'package:replay', 'package:unexpected-replay-refusal')
        rejected.append('replay')
    else:
        require(False, 'package:replay-accepted')
    return {'submitted': True, 'refusals': rejected}


class PackageAuthorityJourney(ProductFreeEntryJourney):
    def __init__(self, context, progress):
        require(getattr(context, 'product_free', False) is True
                and getattr(context, 'asset_transfer', None) is not None,
                'package:setup-required')
        InstalledJourney.__init__(self, context, progress, PLAN,
            actions={'refuse-command': refuse_command, 'submit-package': submit_package})
        self.package = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'package-result':
            require(self.package is not None, 'package:missing-command')
            observed['package'] = self.package.read_result()
