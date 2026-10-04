"""LIFE04 genuine release upgrade composed with the existing LIFE02 boundary."""
from dataclasses import replace

from customer_reboot import PLAN as REBOOT_PLAN, refuse_reboot
from package_command import OLD_INSTALL, UPGRADE, PackageCommand
from package_install import submit_release, observe_release
from private_artifacts import EvidenceError, require
from product_free_entry import ProductFreeEntryJourney

EXTRA = {stage: 'system:parent-command-context' for stage in (
    'upgrade-context', 'upgrade-submitted', 'upgrade-result', 'upgrade-reread')}
PLAN = replace(REBOOT_PLAN, prefix='package-upgrade', worker_mode='package_upgrade',
    screen_tags={**REBOOT_PLAN.screen_tags, **EXTRA},
    phases={**REBOOT_PLAN.phases, **{stage: 'step-4' for stage in EXTRA}},
    stage_actions={'wrong-entry': 'upgrade-refuse', 'package-submitted': 'install-previous',
                   'upgrade-context': 'upgrade-entry', 'upgrade-submitted': 'upgrade-current'},
    assertions_after={**REBOOT_PLAN.assertions_after,
        'package-result': 'authentic-old-install-completed',
        'upgrade-context': 'activated-old-release-entry',
        'upgrade-result': 'real-upgrade-completed-with-reboot-notice',
        'upgrade-reread': 'upgrade-same-boot-preservation'})


def refuse_input(command, binding, digest, identity, code):
    try:
        command.validate_input(binding, digest, identity)
    except EvidenceError as error:
        require(str(error) == code, 'package-upgrade:wrong-refusal')
    else:
        require(False, 'package-upgrade:missing-refusal')


def entry_refusal(journey, guard):
    result = refuse_reboot(journey, guard)
    # The shared command-context refusal independently proves there is no
    # active fixture administrator at this greeter; no package input is released.
    return {**result, 'package_entry_refused': True}


def install_previous(journey, guard):
    command = PackageCommand(journey.transport, journey.context.verified)
    inputs = command.verified.upgrade_inputs['packages']
    journey.release_entry = command.read_identity()
    require(journey.release_entry['version'] is None, 'package-upgrade:product-free-required')
    require(command.read_identity() == journey.release_entry, 'package-upgrade:unstable-entry')
    for binding, digest, identity, code in (
        ('unregistered', inputs['previous']['sha256'], command.identity, 'package:unregistered-command'),
        (OLD_INSTALL, inputs['current']['sha256'], command.identity, 'package:wrong-artifact'),
        (OLD_INSTALL, inputs['previous']['sha256'], {**command.identity, 'run': 'wrong'}, 'package:wrong-attempt'),
        (OLD_INSTALL, inputs['previous']['sha256'], {**command.identity, 'domain_uuid': 'wrong'}, 'package:wrong-attempt')):
        refuse_input(command, binding, digest, identity, code)
    try:
        command.submit(UPGRADE, inputs['current']['sha256'], command.identity)
    except EvidenceError as error:
        require(str(error) == 'package:wrong-phase', 'package-upgrade:phase-refusal')
    else:
        require(False, 'package-upgrade:wrong-phase-accepted')
    require(not command.attempted, 'package-upgrade:phase-refusal-consumed')
    guard()
    return submit_release(journey, guard, OLD_INSTALL, 'previous_package')


def upgrade_entry(journey, guard):
    guard()
    result, current = observe_release(journey.previous_package, 'previous',
                                     journey.release_entry, changed_boot=True)
    require(current['boot'] == journey.boot and journey.reboot_observed,
            'package-upgrade:activation-required')
    journey.activated_entry = current
    command = PackageCommand(journey.transport, journey.context.verified)
    inputs = command.verified.upgrade_inputs['packages']
    refuse_input(command, OLD_INSTALL, inputs['previous']['sha256'], command.identity, 'package:replay')
    refuse_input(command, UPGRADE, inputs['previous']['sha256'], command.identity, 'package:wrong-artifact')
    guard()
    return result


def upgrade_current(journey, guard):
    require(journey.activated_entry is not None, 'package-upgrade:activation-required')
    return submit_release(journey, guard, UPGRADE, 'upgrade_package')


class PackageUpgradeJourney(ProductFreeEntryJourney):
    """Reusable lifecycle observations; the qualification owns only its envelope."""
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        require(context.verified.upgrade_inputs is not None, 'package-upgrade:inputs-required')
        super().__init__(context, progress, plan, actions={
            'upgrade-refuse': entry_refusal, 'install-previous': install_previous,
            'upgrade-entry': upgrade_entry, 'upgrade-current': upgrade_current} if actions is None else actions)
        self.previous_package = self.upgrade_package = None
        self.release_entry = self.activated_entry = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'package-result':
            observed['package'], _ = observe_release(self.previous_package, 'previous', self.release_entry)
        elif stage in ('upgrade-result', 'upgrade-reread'):
            observed['package'], _ = observe_release(self.upgrade_package, 'current', self.activated_entry)
            command = PackageCommand(self.transport, self.context.verified)
            inputs = command.verified.upgrade_inputs['packages']
            refuse_input(command, UPGRADE, inputs['current']['sha256'], command.identity, 'package:replay')
