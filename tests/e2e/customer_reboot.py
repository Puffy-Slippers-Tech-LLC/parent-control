"""LIFE02: one customer reboot after a fresh, observed LIFE04 install."""

from dataclasses import replace

from installed_journey import InstalledJourney
from journey_blocks import reboot_desktop
from package_install import PLAN as INSTALL_PLAN, PackageInstallJourney, submit_install
from private_artifacts import EvidenceError, require
from product_free_entry import refuse_command


RETURN = reboot_desktop()
PLAN = replace(INSTALL_PLAN, prefix='customer-reboot', worker_mode='customer_reboot',
    screen_tags={**INSTALL_PLAN.screen_tags,
                 'reboot-requested': 'system:parent-command-context', **RETURN},
    phases={**INSTALL_PLAN.phases, 'reboot-requested': 'step-3',
            **{stage: 'step-3' for stage in RETURN}},
    assertions_after={**INSTALL_PLAN.assertions_after,
                      'reboot-installed-greeter': 'changed-boot-usable-gdm',
                      'reboot-desktop': 'administrator-desktop-after-reboot'},
    invocations=tuple(RETURN),
    challenges={'after-reboot': ('parent', 'reboot-recipient-qualified',
                                'reboot-recipient-rechecked')},
    reboot_transition=('reboot-requested', 'reboot-installed-greeter'))


def refuse_reboot(journey, guard):
    try:
        journey.submit_reboot(guard)
    except EvidenceError as error:
        require(str(error) == 'customer-reboot:reboot-entry', 'customer-reboot:wrong-refusal')
    else:
        require(False, 'customer-reboot:wrong-entry-accepted')
    return {**refuse_command(journey, guard), 'reboot_refused': True}


class CustomerRebootJourney(PackageInstallJourney):
    def __init__(self, context, progress):
        require(getattr(context, 'product_free', False) is True
                and getattr(context, 'asset_transfer', None) is not None,
                'customer-reboot:setup-required')
        InstalledJourney.__init__(self, context, progress, PLAN,
            actions={'refuse-command': refuse_reboot, 'install-package': submit_install})
        self.package = None
