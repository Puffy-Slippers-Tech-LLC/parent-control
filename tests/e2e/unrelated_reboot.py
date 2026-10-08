"""305a: finite normal Ubuntu libc6 reconfiguration after product activation."""

from dataclasses import replace

from customer_reboot import PLAN as REBOOT_PLAN
from package_command import PackageCommand, UNRELATED, UNRELATED_PACKAGE
from package_install import UnrelatedPackageJourney, check_install_result, submit_install, submit_unrelated
from private_artifacts import EvidenceError, require
from product_free_entry import refuse_command

STAGES = {stage: 'system:parent-command-context' for stage in (
    'unrelated-context', 'unrelated-submitted', 'unrelated-result')}
PLAN = replace(REBOOT_PLAN, prefix='unrelated-reboot', worker_mode='unrelated_reboot_request',
    screen_tags={**REBOOT_PLAN.screen_tags, **STAGES},
    phases={**REBOOT_PLAN.phases, **{stage: 'step-4' for stage in STAGES}},
    stage_actions={**REBOOT_PLAN.stage_actions, 'unrelated-submitted': 'unrelated-package'},
    assertions_after={**REBOOT_PLAN.assertions_after,
        'unrelated-context': 'activated-product-clean-system-entry',
        'unrelated-result': 'genuine-unrelated-request-product-and-boot-unchanged'})


def qualify_submission(journey, guard):
    """Qualification-only refusals surround the same consumer input leaf."""
    probe = PackageCommand(journey.transport, journey.context.verified)
    digest, identity = UNRELATED_PACKAGE['sha256'], probe.identity
    refusals = []
    for label, binding, value, owner in (
        ('unregistered', 'arbitrary-reconfiguration', digest, identity),
        ('artifact', UNRELATED, '0' + digest[1:], identity),
        ('vm', UNRELATED, digest, {**identity, 'domain_uuid': 'wrong-vm'}),
        ('attempt', UNRELATED, digest, {**identity, 'run': 'wrong-attempt'})):
        try:
            probe.submit(binding, value, owner)
        except EvidenceError:
            refusals.append(label)
        else:
            require(False, 'unrelated-package:invalid-input-accepted')
    result = submit_unrelated(journey, guard)
    try:
        journey.unrelated_package.submit(UNRELATED, digest, identity)
    except EvidenceError as error:
        require(str(error) == 'package:replay', 'unrelated-package:wrong-refusal')
        refusals.append('replay')
    else:
        require(False, 'unrelated-package:replay-accepted')
    return {**result, 'refusals': refusals}


class UnrelatedRebootJourney(UnrelatedPackageJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        require(context.product_free is True and context.asset_transfer is not None,
                'unrelated-package:setup-required')
        super().__init__(context, progress, plan, entry='unrelated-context', result='unrelated-result', actions=(
            {'refuse-command': refuse_command, 'install-package': submit_install,
             'unrelated-package': qualify_submission} if actions is None else actions))
        self.package = None

    def check_settings(self, stage, observed):
        if stage == 'unrelated-context':
            require(self.reboot_observed and self.package is not None,
                    'unrelated-package:activation-required')
        super().check_settings(stage, observed)
        if stage == 'package-result':
            check_install_result(self, observed)
