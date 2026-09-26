"""One fixed installed setup/greeter observation for the first Parent consumer."""

import json
import os
from types import SimpleNamespace

import check_graphical_smoke as smoke


class ParentSetupQualification(smoke.Qualification):
    def execute(self, lease, guestfs):
        self.checkpoint('attempt-started')
        try:
            lease.prepare()
            host_key = smoke.runner.bootstrap(self.commands, lease, self.directory, guestfs)
            lease.guard(off=True)
            lease.save('isolated')
            self.verified = smoke.VerifiedInputs(lease=lease, assets=self.assets)
            self.result['provenance'] = self.verified.inputs
            self.result['fixture_credentials'] = self.credentials.provision(
                lease, self.verified, self.directory, guestfs, self.commands)
            # Credentials remain controller-private: this worker only observes.
            input_review = self.result.get('scope') == 'installed-parent-input-qualification'
            standard_input_review = (
                self.result.get('scope') == 'installed-standard-input-qualification'
            )
            stages = ('ready', 'setup-detached', 'installed-greeter')
            if input_review:
                stages += ('installed-parent-prompt', 'installed-parent-dismissed')
            if standard_input_review:
                stages += ('installed-standard-prompt', 'installed-standard-dismissed')
            steps = []

            def observe(guard):
                if len(steps) == len(stages):
                    return
                stage = stages[len(steps)]
                path = self.directory / (stage + '.request.json')
                if not path.exists():
                    return
                smoke.require(not path.is_symlink() and path.stat().st_size <= 1024,
                              'setup:request-file')
                request = json.loads(path.read_text())
                smoke.require(set(request) == {'stage', 'screenshot'} and request['stage'] == stage,
                              'setup:request-schema')
                guard()
                self.active_stage = stage
                self.checkpoint('stage-started')
                if stage == 'ready':
                    smoke.require(request['screenshot'] is None, 'setup:early-screenshot')
                    reply = {'parent_setup': True}
                    if input_review:
                        reply['parent_input'] = True
                    if standard_input_review:
                        reply['parent_standard_input'] = True
                elif stage == 'setup-detached':
                    smoke.require(request['screenshot'] is None, 'setup:early-screenshot')
                    hostname = smoke.runner.address(lease.source, timeout=90)
                    (self.directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
                    config = {'directory': str(self.directory), 'hostname': hostname,
                              'domain_uuid': lease.source.uuid, 'domain_id': lease.view.domain_id,
                              'run': lease.state['run']}
                    vm = smoke.Transport(config, self.commands, guard=lambda _: lease.guard())
                    vm.probe_ready(timeout=180)
                    setup = smoke.installed_setup.InstalledSetup(self.directory, self.verified, vm)
                    reply = setup.run(guard)
                    self.result['installed_setup'] = reply
                else:
                    reply = smoke.screenshot(self.directory, request['screenshot'])
                    self.result[stage.replace('-', '_')] = {'screenshot': request['screenshot'], **reply}
                guard()
                pending = self.directory / (stage + '.reply.tmp')
                destination = self.directory / (stage + '.reply.json')
                smoke.require(not os.path.lexists(pending) and not os.path.lexists(destination),
                              'setup:reply-replay')
                steps.append({'stage': stage, 'outcome': 'passed'})
                self.result['steps'] = list(steps)
                # The reply authorizes the worker's next action. Retain the
                # observation durably first, then revalidate after storage.
                self.checkpoint('stage-observed')
                guard()
                with pending.open('x') as stream:
                    json.dump(reply, stream)
                pending.rename(destination)

            def validate():
                smoke.require(len(steps) == len(stages), 'setup:missing-stages')
                smoke.module_result(self.directory)

            self.result['worker_evidence'] = smoke.e2e_worker.run_distribution(
                self.directory, lease, self.ledger, expected_inputs=self.verified.source_files,
                observe=lambda: None, guarded_observe=observe, validate=validate,
                on_failure=self.failure, timeout=1800)
        finally:
            self.checkpoint('before-cleanup')


class ParentJourneyQualification(smoke.Qualification):
    """Shared installed setup and private image acquisition for Parent plans."""

    observation_only = False

    def attach_installed_snapshot(self, lease):
        """Reuse a prepared app snapshot; default qualifications stay on baseline."""
        return

    def prepare_context(self, context):
        """Optional fixed preparation before the graphical worker starts."""
        return

    def record_progress(self, journey, stage, observed):
        self.active_stage = stage
        self.result['steps'] = list(journey.steps)
        self.checkpoint('stage-observed')

    def execute(self, lease, guestfs):
        self.checkpoint('attempt-started')
        try:
            lease.prepare()
            self.attach_installed_snapshot(lease)
            host_key = smoke.runner.bootstrap(
                self.commands, lease, self.directory, guestfs,
                observation_only=self.observation_only)
            lease.guard(off=True)
            lease.save('isolated')
            self.verified = smoke.VerifiedInputs(lease=lease, assets=self.assets)
            self.result['provenance'] = self.verified.inputs
            self.result['fixture_credentials'] = self.credentials.provision(
                lease, self.verified, self.directory, guestfs, self.commands)
            context = SimpleNamespace(directory=self.directory, lease=lease, verified=self.verified,
                                      commands=self.commands, host_key=host_key)
            self.prepare_context(context)

            def progress(stage, observed):
                self.record_progress(journey, stage, observed)

            journey = self.journey(context, progress)
            self.result['worker_evidence'] = smoke.e2e_worker.run_distribution(
                self.directory, lease, self.ledger, expected_inputs=self.verified.source_files,
                observe=lambda: None, guarded_observe=journey.step, validate=journey.validate,
                on_failure=self.failure, timeout=1800, credentials=self.credentials)
            self.result['matched_screens'] = journey.validate()
        finally:
            self.checkpoint('before-cleanup')


class ParentAboutQualification(ParentJourneyQualification):
    @staticmethod
    def journey(context, progress):
        from parent_about import ParentJourney
        return ParentJourney(context, progress, review=True)


class ParentAccessQualification(ParentJourneyQualification):
    @staticmethod
    def journey(context, progress):
        from parent_access import ParentAccessJourney
        return ParentAccessJourney(context, progress, review=True)


class KioskEntryQualification(ParentJourneyQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_entry import KioskEntryJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskEntryJourney(context, progress)

    def attach_installed_snapshot(self, lease):
        from app_snapshot import snapshot_name
        version = self.commands.run(
            ['dpkg-deb', '-f', str(self.assets / 'package.deb'), 'Version']).decode().strip()
        name = snapshot_name(version)
        snap = lease.source.domain.snapshotLookupByName(name, 0)
        with lease.snapshot_status('Restoring', name):
            lease.source.domain.revertToSnapshot(
                snap, lease.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE)
        lease.source.connection.defineXML(lease.test_xml)
        lease.view.run = lease.state['run']
        lease.view.domain_id = None
        lease.state['domain_id'] = None
        lease.guard(off=True)
        lease.save('isolated')


class KioskValidDurationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_valid_duration import KioskValidDurationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskValidDurationJourney(context, progress)


class RequestDurationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from request_duration import RequestDurationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RequestDurationJourney(context, progress)


class RequestFlowQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from request_flow import RequestFlowJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RequestFlowJourney(context, progress)


class KioskEligibleChoicesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_eligible_choices import KioskEligibleChoicesJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskEligibleChoicesJourney(context, progress)


class KioskNoChildQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_no_child import KioskNoChildJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskNoChildJourney(context, progress)


class KioskNoApproverQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_no_approver import KioskNoApproverJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskNoApproverJourney(context, progress)


class RequestChoicesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from request_choices import RequestChoicesJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RequestChoicesJourney(context, progress)


class DesktopLogoutQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from desktop_session import DesktopSessionJourney, LOGOUT_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return DesktopSessionJourney(context, progress, LOGOUT_PLAN)


class DesktopSwitchQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from desktop_session import DesktopSessionJourney, SWITCH_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return DesktopSessionJourney(context, progress, SWITCH_PLAN)


class GdmNavigationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from gdm_navigation import GdmNavigationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return GdmNavigationJourney(context, progress)


class GdmRecipientQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from gdm_recipient import GdmRecipientJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return GdmRecipientJourney(context, progress)


class FreshDesktopQualification(KioskEntryQualification):
    role = None

    def journey(self, context, progress):
        from app_snapshot import snapshot_name
        from fresh_desktop import FreshDesktopJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FreshDesktopJourney(context, progress, role=self.role)


class FreshParentDesktopQualification(FreshDesktopQualification):
    role = 'parent'


class ShellSearchResultsQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from shell_search_results import ShellSearchResultsJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ShellSearchResultsJourney(context, progress)


class ParentSearchLaunchQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_search_launch import ParentSearchLaunchJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentSearchLaunchJourney(context, progress)


class ParentTerminalProviderQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_terminal_provider import ParentTerminalProviderJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentTerminalProviderJourney(context, progress)


class LicenseViewerProviderQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from license_viewer_provider import LicenseViewerProviderJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return LicenseViewerProviderJourney(context, progress)


class ChallengesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from challenges import ChallengesJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ChallengesJourney(context, progress)

    def record_progress(self, journey, stage, observed):
        plan = journey.plan
        self.result['active_phase'] = plan.phases[stage]
        super().record_progress(journey, stage, observed)
        if stage in plan.assertions_after:
            smoke.require(observed.get('ui', {}).get('outcome') == 'passed',
                          'challenges:public-result-required')
            self.result.setdefault('assertions', []).append({
                'stage': stage, **observed['assertion'], 'outcome': 'passed'})
            self.checkpoint('assertion')
        if stage in plan.advance_after:
            self.result['active_phase'] = plan.advance_after[stage]
            self.checkpoint('phase-started')


class RepeatedOperationsQualification(KioskEntryQualification):
    """Finite page cycles in the same owned snapshot/collection envelope."""

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from repeated_operations import RepeatedOperationsJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RepeatedOperationsJourney(context, progress)

    def record_progress(self, journey, stage, observed):
        # Fixed capability evidence has no scenario registration or coverage
        # credit. Record the same declared assertion-before-transition boundary
        # as the scenario recorder, within the existing durable envelope.
        plan = journey.plan
        self.result['active_phase'] = plan.phases[stage]
        super().record_progress(journey, stage, observed)
        if stage in plan.assertions_after:
            smoke.require(observed.get('comparison', {}).get('outcome') == 'passed',
                          'repeated:comparison-required')
            self.result.setdefault('assertions', []).append({
                'stage': stage, **observed['assertion'], 'outcome': 'passed'})
            self.checkpoint('assertion')
        if stage in plan.advance_after:
            self.result['active_phase'] = plan.advance_after[stage]
            self.checkpoint('phase-started')


class ShellSearchQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from shell_search import ShellSearchJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ShellSearchJourney(context, progress)


class FreshStandardDesktopQualification(FreshDesktopQualification):
    role = 'standard'


class KeyringStandardDesktopQualification(FreshDesktopQualification):
    role = 'standard'

    def journey(self, context, progress):
        from app_snapshot import snapshot_name
        from fresh_desktop import KeyringDesktopJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KeyringDesktopJourney(context, progress)


class GdmProductFreeQualification(ParentJourneyQualification):
    """Qualify Parent navigation without restoring or installing the product."""

    observation_only = True

    @staticmethod
    def journey(context, progress):
        from gdm_product_free import GdmProductFreeJourney
        context.product_free = True
        return GdmProductFreeJourney(context, progress)


class ProductFreeEntryQualification(ParentJourneyQualification):
    """FIX04 and fresh administrator entry on the accepted empty baseline."""

    observation_only = True

    def prepare_context(self, context):
        self.transfer = smoke.AssetTransfer(self.verified)
        self.result['asset_transfer'] = self.transfer.provision(context.lease, self.guestfs)
        context.product_free = True
        context.asset_transfer = self.transfer

    def execute(self, lease, guestfs):
        self.guestfs = guestfs
        super().execute(lease, guestfs)

    @staticmethod
    def journey(context, progress):
        from product_free_entry import ProductFreeEntryJourney
        return ProductFreeEntryJourney(context, progress)

    def record_progress(self, journey, stage, observed):
        plan = journey.plan
        self.result['active_phase'] = plan.phases[stage]
        super().record_progress(journey, stage, observed)
        if stage in plan.assertions_after:
            smoke.require(observed.get('ui', observed.get('system', {})).get('outcome') == 'passed',
                          'product-free-entry:result-required')
            self.result.setdefault('assertions', []).append({
                'stage': stage, **observed['assertion'], 'outcome': 'passed'})
            self.checkpoint('assertion')
        if stage in plan.advance_after:
            self.result['active_phase'] = plan.advance_after[stage]
            self.checkpoint('phase-started')


class PackageAuthorityQualification(ProductFreeEntryQualification):
    """Same empty-baseline entry, followed by one guarded package operation."""

    @staticmethod
    def journey(context, progress):
        from package_authority import PackageAuthorityJourney
        return PackageAuthorityJourney(context, progress)


class PackageInstallQualification(ProductFreeEntryQualification):
    """LIFE04 composition, with fresh entry and separate completion readback."""

    @staticmethod
    def journey(context, progress):
        from package_install import PackageInstallJourney
        return PackageInstallJourney(context, progress)


class CustomerRebootQualification(ProductFreeEntryQualification):
    """Fresh install and one planned reboot in the same owned attempt."""

    @staticmethod
    def journey(context, progress):
        from customer_reboot import CustomerRebootJourney
        return CustomerRebootJourney(context, progress)


class RequestExitQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from request_exit import RequestExitJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RequestExitJourney(context, progress)


class TimeExplanationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from time_explanation import TimeExplanationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return TimeExplanationJourney(context, progress)


class AppRestartQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from app_restart import AppRestartJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return AppRestartJourney(context, progress)


class SetAllowanceQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from set_allowance import SetAllowanceJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return SetAllowanceJourney(context, progress)


class AllowanceBoundariesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from allowance_boundaries import AllowanceBoundariesJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return AllowanceBoundariesJourney(context, progress)


class AllowanceQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from allowance import AllowanceJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return AllowanceJourney(context, progress)


class AllowancePresetsQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from allowance_presets import AllowancePresetsJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return AllowancePresetsJourney(context, progress)


class TextQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from text_qualification import TextJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return TextJourney(context, progress)


class FeedbackReadQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_read import FeedbackReadJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FeedbackReadJourney(context, progress)


class AppRowQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from app_row_observations import AppRowJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return AppRowJourney(context, progress)


class ParentToggleQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_toggle import ParentToggleJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentToggleJourney(context, progress)

    def prepare_context(self, context):
        """Create a disposable Parent session without qualifying login or launch."""
        with smoke.runner.operation('Preparing the Parent toggle qualification session'):
            context.lease.start()
            hostname = smoke.runner.address(context.lease.source, timeout=90)
            (context.directory / 'known-hosts').write_text(f'{hostname} {context.host_key}\n')
            config = {'directory': str(context.directory), 'hostname': hostname,
                      'domain_uuid': context.lease.source.uuid,
                      'domain_id': context.lease.view.domain_id,
                      'run': context.lease.state['run']}
            transport = smoke.Transport(
                config, context.commands, guard=lambda _: context.lease.guard())
            transport.probe_ready(timeout=180)
            smoke.installed_setup.InstalledSetup(
                context.directory, context.verified, transport).provision(context.lease.guard)
            transport.call(smoke.runner.guest_command(
                context.lease.state['run'], 'prepare-toggle-session'), timeout=120)
            # The shared stop retires the backing-byte lease before QEMU closes
            # its block graph and detaches observation for the completed boot.
            # The graphical worker must enter a new isolated, powered-off phase.
            context.lease.stop()
            context.lease.guard(off=True)
            context.lease.view.domain_id = None
            context.lease.state['domain_id'] = None
            context.lease.save('isolated')
