"""One genuine package update followed by the shared public usability history."""
import check_graphical_smoke as smoke
from parent_setup_qualification import GdmProductFreeQualification, KioskEntryQualification


class KioskUpdateReentryQualification(GdmProductFreeQualification):
    upgrade_assets = True
    package_only = True
    observation_only = False
    system_product_free = True
    worker_timeout = 3600

    def journey_failure(self, journey, category, code):
        super().journey_failure(journey, category, code)
        journey.collect_failure()

    @staticmethod
    def make_journey(context, progress):
        from confinement_usability import ConfinementUsabilityJourney
        return ConfinementUsabilityJourney(context, progress)

    def journey(self, context, progress):
        from installed_setup import InstalledSetup
        journey = self.make_journey(context, progress)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage != 'setup-detached':
                return
            guard = context.lease.guard
            guard()
            setup = InstalledSetup(context.directory, context.verified, journey.transport)
            result = setup.run(guard, upgrade=True)
            self.result['update_activation'] = observed['update_activation'] = result['update_activation']

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        super().execute(lease, guestfs)
        smoke.require(self.result.get('update_activation', {}).get('candidate_reboot_verified') is True,
                      'kiosk-update:history-incomplete')


class KioskWhatsNewQualification(KioskEntryQualification):
    """Read a genuine upgrade restored in a fresh installed attempt."""

    upgrade_assets = True
    package_only = True
    release_notes_upgrade = True
    worker_timeout = 3600

    @staticmethod
    def journey(context, progress):
        from kiosk_whats_new import KioskWhatsNewJourney
        return KioskWhatsNewJourney(context, progress)
