"""One genuine package update followed by the shared public usability history."""
import json

import check_graphical_smoke as smoke
from parent_setup_qualification import GdmProductFreeQualification
import watch_activity


class KioskUpdateReentryQualification(GdmProductFreeQualification):
    upgrade_assets = True
    package_only = True
    observation_only = False
    system_product_free = True
    worker_timeout = 3600

    def journey_failure(self, journey, category, code):
        super().journey_failure(journey, category, code)
        journey.collect_failure()

    def journey(self, context, progress):
        from confinement_usability import ConfinementUsabilityJourney
        from fixture_credentials import ACCOUNTS
        from installed_setup import InstalledSetup
        journey = ConfinementUsabilityJourney(context, progress)
        check_settings = journey.check_settings
        usernames = tuple(account.username for account in ACCOUNTS.values())

        def ordinary_accounts():
            return [journey.transport.call(['getent', 'passwd', *usernames]),
                    *[journey.transport.call(['id', '-G', name]) for name in usernames]]

        def check(stage, observed):
            check_settings(stage, observed)
            if stage != 'setup-detached':
                return
            guard = context.lease.guard
            guard()
            setup = InstalledSetup(context.directory, context.verified, journey.transport)
            setup.provision(guard)
            accounts = ordinary_accounts()
            run = context.lease.state['run']
            try:
                with watch_activity.operation('Installing the genuine prior release and observing its activation'):
                    journey.transport.call(smoke.runner.guest_command(run, 'install-previous'), timeout=2400)
                    guard()
                    journey.transport.reboot()
                    guard()
                with watch_activity.operation('Updating the request station and observing its required activation'):
                    journey.transport.call(smoke.runner.guest_command(run, 'upgrade'), timeout=2400)
                    guard()
                    journey.transport.reboot()
                    guard()
                    journey.transport.call(smoke.runner.guest_command(run, 'verify-setup'), timeout=660)
                smoke.require(ordinary_accounts() == accounts, 'kiosk-update:ordinary-accounts-changed')
                journey.transport.copy(True, smoke.runner.PAYLOAD + '/results/',
                                       str(context.directory / 'update-results') + '/')
                result = json.loads((context.directory / 'update-results/update-activation.json').read_bytes())
                smoke.require(result['old_package_reboot_observed'] is True
                              and result['update_requested_reboot'] is True
                              and result['same_version_reinstall'] is False,
                              'kiosk-update:activation-incomplete')
                guard()
            except Exception as error:
                try:
                    guard()
                    journey.transport.copy(True, smoke.runner.PAYLOAD + '/private/',
                                           str(context.directory / 'update-private') + '/')
                except Exception:
                    error.add_note('kiosk-update:diagnostics-unavailable')
                raise
            self.result['update_activation'] = observed['update_activation'] = {
                **result, 'candidate_reboot_verified': True, 'ordinary_accounts_preserved': True}

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        super().execute(lease, guestfs)
        smoke.require(self.result.get('update_activation', {}).get('candidate_reboot_verified') is True,
                      'kiosk-update:history-incomplete')
