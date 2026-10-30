"""One fixed installed setup/greeter observation for the first Parent consumer."""

import json
import os
from types import SimpleNamespace

import check_graphical_smoke as smoke


class ParentSetupQualification(smoke.Qualification):
    def execute(self, lease, guestfs):
        self.checkpoint('attempt-started')
        try:
            with self.ledger.measure('preparation'):
                lease.prepare()
                host_key = smoke.runner.bootstrap(self.commands, lease, self.directory, guestfs,
                                                  system_product_free=True)
                lease.guard(off=True)
                lease.save('isolated')
                self.verified = smoke.VerifiedInputs(lease=lease, assets=self.assets, package_only=True)
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
                    vm = smoke.Transport(config, self.commands, guard=lambda _: lease.guard(), lease=lease)
                    vm.probe_ready(timeout=180)
                    from system_fixture_preparation import prepare
                    prepared = prepare(vm, lease, self.directory, self.fixture_selection)
                    setup = smoke.installed_setup.InstalledSetup(self.directory, self.verified, vm)
                    prepared['controller'].require_ready(prepared['receipt'])
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

            with self.ledger.measure('test'):
                self.result['worker_evidence'] = smoke.e2e_worker.run_distribution(
                    self.directory, lease, self.ledger, expected_inputs=self.verified.source_files,
                    observe=lambda: None, guarded_observe=observe, validate=validate,
                    on_failure=self.failure, timeout=1800)
        finally:
            self.checkpoint('before-cleanup')


class ParentJourneyQualification(smoke.Qualification):
    """Shared installed setup and private image acquisition for Parent plans."""

    observation_only = False

    upgrade_assets = False
    package_only = False
    system_product_free = False
    fixture_subsets = ('native',)
    fixture_caller = None
    worker_timeout = 1800

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

    def journey_failure(self, journey, category, code):
        self.failure(category, code)

    def execute(self, lease, guestfs):
        self.checkpoint('attempt-started')
        try:
            with self.ledger.measure('preparation'):
                lease.prepare()
                self.attach_installed_snapshot(lease)
                product_free = isinstance(self, (GdmProductFreeQualification,
                                               ProductFreeEntryQualification))
                host_key = smoke.runner.bootstrap(
                    self.commands, lease, self.directory, guestfs,
                    observation_only=self.observation_only,
                    **({'system_product_free': True} if self.system_product_free else
                       {'e2e_product_free': True} if product_free else
                       {'e2e_installed': True} if getattr(self, 'fixture_selection', None) is not None else {}))
                lease.guard(off=True)
                lease.save('isolated')
                self.verified = smoke.VerifiedInputs(lease=lease, assets=self.assets,
                                                    upgrade=self.upgrade_assets,
                    **({'package_only': True} if self.package_only or
                       getattr(self, 'fixture_selection', None) is not None else {}))
                self.result['provenance'] = self.verified.inputs
                if self.upgrade_assets:
                    self.result['upgrade_inputs'] = self.verified.upgrade_inputs
                self.result['fixture_credentials'] = self.credentials.provision(
                    lease, self.verified, self.directory, guestfs, self.commands)
                context = SimpleNamespace(directory=self.directory, lease=lease, verified=self.verified,
                                          commands=self.commands, host_key=host_key)
                context.fixture_selection = getattr(self, 'fixture_selection', None)
                context.fixture_subsets = self.fixture_subsets
                context.fixture_caller = self.fixture_caller
                self.prepare_context(context)

            def progress(stage, observed):
                self.record_progress(journey, stage, observed)

            journey = self.journey(context, progress)
            with self.ledger.measure('test'):
                self.result['worker_evidence'] = smoke.e2e_worker.run_distribution(
                    self.directory, lease, self.ledger, expected_inputs=self.verified.source_files,
                    observe=lambda: None, guarded_observe=journey.step, validate=journey.validate,
                    on_failure=lambda category, code: self.journey_failure(journey, category, code),
                    timeout=self.worker_timeout, credentials=self.credentials)
                self.result['matched_screens'] = journey.validate()
        except BaseException as error:
            code = (str(error) if isinstance(error, smoke.EvidenceError)
                    else smoke.runner.error_category(error))
            if not any(v['outcome'] == 'failed' for v in self.ledger.outcomes.values()):
                self.ledger.fail_outcome('infrastructure', code)
            raise
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
    def journey_failure(self, journey, category, code):
        super().journey_failure(journey, category, code)
        journey.collect_failure()

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_entry import KioskEntryJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskEntryJourney(context, progress)

    def attach_installed_snapshot(self, lease):
        from app_snapshot import input_identity, mismatch, mode_mismatch, snapshot_name
        from guest_inputs import Bundle
        package = self.assets / ('package.' + smoke.runner.package_format(lease.capture.state['guest']))
        version = smoke.runner.package_version(self.commands, package)
        name = snapshot_name(version)
        # Compare the frozen installation recipe and package, just as the
        # shared suite does. A release name alone cannot identify installed
        # bytes, and refreshing the test payload does not update the product.
        bundle = Bundle.from_staged(smoke.ROOT, self.directory / 'input')
        expected = input_identity(lease, self.assets, bundle, self.commands)
        snap = lease.source.domain.snapshotLookupByName(name, 0)
        import xml.etree.ElementTree as ET
        xml = snap.getXMLDesc(0)
        memory = ET.fromstring(xml).find('memory')
        online = memory is not None and memory.get('snapshot') == 'internal'
        mode = 'online' if online else 'offline'
        reason = mode_mismatch(xml, mode, **(
            {'offline_domain_xml': lease.original_xml} if not online else {})) or mismatch(xml, expected)
        smoke.require(reason is None, 'setup:installed-snapshot-stale:' + str(reason))
        lease.guard(off=True)
        smoke.require(snap.getXMLDesc(0) == xml, 'setup:installed-snapshot-changed')
        # Keep archive integrity distinct from installed-content equivalence
        # (DEB delivery timestamps can differ). Report both exact identities.
        self.result['installed_snapshot'] = {
            'name': name, 'mode': mode,
            'inputs': json.loads(ET.fromstring(xml).findtext('description')),
            'expected_inputs': json.loads(expected),
        }
        lease.installed_name, lease.installed_xml = name, xml
        if online:
            lease.installed_name, lease.installed_xml = name, xml
            lease.online_pending = True
            return
        with lease.snapshot_status('Restoring', name):
            lease.guard(off=True)
            smoke.require(snap.getXMLDesc(0) == xml, 'setup:installed-snapshot-changed')
            lease.source.domain.revertToSnapshot(
                snap, lease.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE)
        lease.source.connection.defineXML(lease.test_xml)
        lease.view.run = lease.state['run']
        lease.view.domain_id = None
        lease.state['domain_id'] = None
        lease.guard(off=True)
        lease.save('isolated')
        lease.online_pending = False
        lease.online_bootstrap = None
        lease._restored_name = name


class PublicDesktopSelectionQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from public_desktop_selection import PublicDesktopSelectionJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return PublicDesktopSelectionJourney(context, progress)


class StationShortcutsQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from station_shortcuts import StationShortcutsJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return StationShortcutsJourney(context, progress)


class KioskServiceVariationQualification(KioskEntryQualification):
    """One real automatic-login variation, followed by normal restored entry."""

    @staticmethod
    def journey(context, progress):
        from gdm_service_variation import qualify
        journey = KioskEntryQualification.journey(context, progress)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage == 'setup-detached':
                observed['service_variation'] = qualify(journey.transport, context.lease)
                smoke.require(observed['service_variation']['result'] == 'session-created'
                    and observed['service_variation']['app_execution_qualified'] is True,
                    'gdm-variation:app-execution-required')

        journey.check_settings = check
        return journey


class KioskServiceRouteQualification(KioskEntryQualification):
    """Real child-run su attempt, then public station restoration before verdict."""

    def journey(self, context, progress):
        from su_service_route import qualify
        journey = KioskEntryQualification.journey(context, progress)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage == 'setup-detached':
                self.result['service_route'] = qualify(journey.transport, context.lease)
                observed['service_route'] = self.result['service_route']

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        super().execute(lease, guestfs)
        # An earlier vendor authentication denial is useful evidence, never a
        # native account-gate pass. Finish normal entry/Cancel/return first.
        smoke.require(self.result['service_route'].get('qualified') is True,
                      'su-route:' + self.result['service_route']['result'])


class KioskRoutingVariationQualification(KioskEntryQualification):
    """Finite saved-routing controls, then normal restored public entry."""

    def journey(self, context, progress):
        from gdm_service_variation import qualify_routing
        journey = KioskEntryQualification.journey(context, progress)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage == 'setup-detached':
                self.result['routing_variation'] = qualify_routing(
                    journey.transport, context.lease, expectation='execution')
                observed['routing_variation'] = self.result['routing_variation']

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        super().execute(lease, guestfs)
        # Preserve actual outcomes and complete public recovery before
        # evaluating the shared operation's full qualification verdict.
        smoke.require(self.result['routing_variation'].get('qualified') is True,
                      'gdm-routing:' + self.result['routing_variation']['result'])


class KioskPreferencesConfinementQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_preferences_confinement import KioskPreferencesConfinementJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskPreferencesConfinementJourney(context, progress)


class KioskFeedbackConfinementQualification(KioskEntryQualification):
    def journey_failure(self, journey, category, code):
        try:
            super().journey_failure(journey, category, code)
        finally:
            journey.restore_fault()

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_feedback_confinement import KioskFeedbackConfinementJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskFeedbackConfinementJourney(context, progress)


class KioskNotificationWellbeingQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_notification_wellbeing import KioskNotificationWellbeingJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskNotificationWellbeingJourney(context, progress)


class KioskServiceRecoveryQualification(KioskFeedbackConfinementQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_service_recovery import KioskServiceRecoveryJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskServiceRecoveryJourney(context, progress)


class KioskValidDurationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_valid_duration import KioskValidDurationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskValidDurationJourney(context, progress)


class RestrictedStationAboutQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from restricted_station_about import RestrictedStationAboutJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RestrictedStationAboutJourney(context, progress)


class RequestDurationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from request_duration import RequestDurationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RequestDurationJourney(context, progress)


class KioskApprovalQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_approval import KioskApprovalJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskApprovalJourney(context, progress)


class BaselineAuthPauseQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from baseline_auth_pause import BaselineAuthPauseJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return BaselineAuthPauseJourney(context, progress)


class BaselineAppEffectsQualification(KioskEntryQualification):
    # The journey manages Riley; native alone supplies Jordan's launchers.
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_baseline_app_effects'

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from baseline_app_effects import BaselineAppEffectsJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return BaselineAppEffectsJourney(context, progress)


class ConfinementUsabilityQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from confinement_usability import ConfinementUsabilityJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ConfinementUsabilityJourney(context, progress)


class BasicLocaleAuthQualification(ConfinementUsabilityQualification):
    """One basic-locale fault, real authentication and normal request reentry."""

    fault = None
    discovery_failure = False

    def journey(self, context, progress):
        from basic_locale_auth import BasicLocaleFault
        journey = super().journey(context, progress)
        self.fault = BasicLocaleFault(journey, context.lease,
                                     discovery_failure=self.discovery_failure)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage == 'setup-detached':
                observed['basic_locales'] = self.fault.install()
            elif stage in ('rejection-rejection-qualified', 'approval-qualified'):
                observed['basic_locales'] = self.fault.call('observe')
            elif stage == 'approved-balance':
                observed['basic_locales'] = self.fault.restore()
            elif stage == 'reentry-open-estimate':
                smoke.require(self.fault.restored, 'basic-locale:normal-reentry-before-restoration')
                observed.setdefault('comparison', {})['normal_language_request_restored'] = True

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        try:
            super().execute(lease, guestfs)
            smoke.require(self.fault is not None and self.fault.restored,
                          'basic-locale:history-incomplete')
        finally:
            if self.fault is not None:
                self.fault.restore()


class KioskOptionalArtworkQualification(KioskEntryQualification):
    """One missing optional image, real approval and restored request entry."""

    fault = None

    def journey(self, context, progress):
        from app_snapshot import snapshot_name
        from kiosk_optional_artwork import KioskOptionalArtworkJourney
        from optional_artwork_fault import OptionalArtworkFault
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        journey = KioskOptionalArtworkJourney(context, progress)
        self.fault = OptionalArtworkFault(journey, context.lease)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage == 'gdm-switched':
                observed['optional_artwork'] = self.fault.install()
            elif stage == 'new-estimate':
                observed['optional_artwork'] = self.fault.call('observe')
            elif stage == 'approved-balance':
                observed['optional_artwork'] = self.fault.restore()
            elif stage == 'reentry-open-estimate':
                smoke.require(self.fault.restored, 'optional-artwork:normal-reentry-before-restoration')

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        try:
            super().execute(lease, guestfs)
            smoke.require(self.fault is not None and self.fault.restored,
                          'optional-artwork:history-incomplete')
        finally:
            if self.fault is not None:
                self.fault.restore()


class LocaleDiscoveryAuthQualification(BasicLocaleAuthQualification):
    """One failed locale command with real approval and normal request reentry."""

    discovery_failure = True


class ChildIsolationQualification(KioskEntryQualification):
    """One missing child home with healthy and restored genuine requests."""

    fault = None

    def journey(self, context, progress):
        from app_snapshot import snapshot_name
        from child_isolation import ChildIsolationJourney
        from child_isolation_fault import ChildIsolationFault
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        journey = ChildIsolationJourney(context, progress)
        self.fault = ChildIsolationFault(journey, context.lease)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage == 'setup-greeter':
                observed['child_isolation'] = self.fault.install()
            elif stage == 'unavailable-greeter':
                observed['child_isolation'] = self.fault.restore()
            elif stage in ('restored-new-estimate', 'reentry-usable'):
                smoke.require(self.fault.restored, 'child-isolation:request-before-restoration')

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        try:
            super().execute(lease, guestfs)
            smoke.require(self.fault is not None and self.fault.restored,
                          'child-isolation:history-incomplete')
        finally:
            if self.fault is not None:
                self.fault.restore()


class KioskLeaseVariationQualification(ConfinementUsabilityQualification):
    """Owned lease controls followed by the complete short public history."""

    lease_expectation = 'recovery'

    def journey(self, context, progress):
        from kiosk_lease_variation import qualify
        journey = ConfinementUsabilityQualification.journey(context, progress)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage == 'setup-detached':
                self.result['lease_variation'] = qualify(
                    journey.transport, context.lease, expectation=self.lease_expectation)
                observed['lease_variation'] = self.result['lease_variation']

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        # ParentJourneyQualification uses an explicit 1800-second worker
        # deadline for both these controls and the restored public history.
        super().execute(lease, guestfs)
        smoke.require(self.result['lease_variation'].get('qualified') is True,
                      'kiosk-lease:qualification-incomplete')


class KioskAdmissionContentionQualification(KioskLeaseVariationQualification):
    """Brief installed writer contention followed by usable public reentry."""

    lease_expectation = 'contention'


class KioskIdentityHelperQualification(ConfinementUsabilityQualification):
    """Temporary helper outage, restoration and the short public use history."""

    def journey(self, context, progress):
        import watch_activity
        journey = super().journey(context, progress)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage != 'setup-detached':
                return
            context.lease.guard()
            with watch_activity.operation('Checking temporary identity helper failure and recovery'):
                raw = journey.transport.call([
                    'env', 'ONPC_EXPECTED_RUN=' + context.lease.state['run'],
                    '/usr/bin/python3', '-B',
                    smoke.runner.PAYLOAD + '/system_kiosk_admission.py',
                    'identity-helper-recovery'], timeout=240)
            smoke.require(type(raw) is bytes and 0 < len(raw) <= 65536,
                          'identity-helper:response-bound')
            result = json.loads(raw)
            smoke.require(type(result) is dict and result.get('qualified') is True
                          and result.get('restored') is True,
                          'identity-helper:recovery-incomplete')
            context.lease.guard()
            self.result['identity_helper'] = observed['identity_helper'] = result

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        super().execute(lease, guestfs)
        smoke.require(self.result.get('identity_helper', {}).get('restored') is True,
                      'identity-helper:history-incomplete')


class KioskConfigurationRecoveryQualification(ConfinementUsabilityQualification):
    """One installed configure interruption, retry and restored public use."""

    worker_timeout = 2400

    def journey(self, context, progress):
        import watch_activity
        journey = super().journey(context, progress)
        check_settings = journey.check_settings

        def check(stage, observed):
            check_settings(stage, observed)
            if stage != 'setup-detached':
                return
            context.lease.guard()
            try:
                with watch_activity.operation('Checking interrupted configuration and supported recovery'):
                    raw = journey.transport.call([
                        'env', 'ONPC_EXPECTED_RUN=' + context.lease.state['run'],
                        '/usr/bin/python3', '-B',
                        smoke.runner.PAYLOAD + '/system_first_configure.py',
                        'reconfiguration-recovery'], timeout=1200)
                smoke.require(type(raw) is bytes and 0 < len(raw) <= 65536,
                              'configuration-recovery:response-bound')
                result = json.loads(raw)
                smoke.require(type(result) is dict and result.get('qualified') is True
                              and result.get('restored') is True,
                              'configuration-recovery:retry-incomplete')
                context.lease.guard()
            except Exception as error:
                try:
                    context.lease.guard()
                    journey.transport.copy(True, smoke.runner.PAYLOAD + '/private/',
                        str(context.directory / 'configuration-recovery-private') + '/')
                    context.lease.guard()
                    journey.transport.copy(True, smoke.runner.PAYLOAD + '/results/',
                        str(context.directory / 'configuration-recovery-results') + '/')
                except Exception:
                    error.add_note('configuration-recovery:diagnostics-unavailable')
                raise
            self.result['configuration_recovery'] = observed['configuration_recovery'] = result

        journey.check_settings = check
        return journey

    def execute(self, lease, guestfs):
        super().execute(lease, guestfs)
        smoke.require(self.result.get('configuration_recovery', {}).get('restored') is True,
                      'configuration-recovery:history-incomplete')


class BaselineJourneyQualification(KioskEntryQualification):
    # This fixed caller selects its finite closure before VM acquisition.
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_baseline_journey'

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from baseline_journey import BaselineJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return BaselineJourney(context, progress)


class ActiveGrantDisableQualification(KioskEntryQualification):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_active_grant_disable'

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from active_grant_disable import ActiveGrantDisableJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ActiveGrantDisableJourney(context, progress)


class ActiveGrantDisableEngineeringQualification(ActiveGrantDisableQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from active_grant_disable import ActiveGrantDisableJourney, ENGINEERING_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ActiveGrantDisableJourney(context, progress, ENGINEERING_PLAN)


class ChineseNativeAuthQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from chinese_native_auth import ChineseNativeAuthJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ChineseNativeAuthJourney(context, progress)


class KioskApprovedFlowQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_approved_flow import KioskApprovedFlowJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskApprovedFlowJourney(context, progress)


class ApprovalFlowRejectionQualification(KioskEntryQualification):
    outcome = 'rejection'

    @classmethod
    def journey(cls, context, progress):
        from app_snapshot import snapshot_name
        from approval_flow import ApprovalFlowJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        from approval_flow import plan
        return ApprovalFlowJourney(context, progress, plan(cls.outcome))


class ApprovalFlowCancelQualification(ApprovalFlowRejectionQualification):
    outcome = 'cancel'


class AuthResultQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from auth_result import AuthResultJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return AuthResultJourney(context, progress)


class KioskRejectionQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_rejection import KioskRejectionJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskRejectionJourney(context, progress)


class MatePromptQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from mate_prompt import MatePromptJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return MatePromptJourney(context, progress)


class KioskMultipleQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_multiple import KioskMultipleJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskMultipleJourney(context, progress)


class KioskIneligibleQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_multiple import KioskIneligibleJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskIneligibleJourney(context, progress)


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


class LockSurfaceQualification(KioskEntryQualification):
    supplied = False

    @classmethod
    def journey(cls, context, progress):
        from app_snapshot import snapshot_name
        from desktop_session import DesktopSessionJourney, LOCK_PLAN, SUPPLIED_LOCK_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return DesktopSessionJourney(context, progress,
                                     SUPPLIED_LOCK_PLAN if cls.supplied else LOCK_PLAN)


class SuppliedLockSurfaceQualification(LockSurfaceQualification):
    supplied = True


class LockRecipientQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from desktop_session import DesktopSessionJourney, LOCK_RECIPIENT_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return DesktopSessionJourney(context, progress, LOCK_RECIPIENT_PLAN)


class RetainedParentQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from retained_parent import RetainedParentJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RetainedParentJourney(context, progress)


class RetainedEntryQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from retained_entry import RetainedEntryJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RetainedEntryJourney(context, progress)


class RetainedUnlockQualification(KioskEntryQualification):
    retained = True

    @classmethod
    def journey(cls, context, progress):
        from app_snapshot import snapshot_name
        from desktop_session import RetainedUnlockJourney, CHILD_UNLOCK_PLAN, RETAINED_UNLOCK_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RetainedUnlockJourney(context, progress,
                                    RETAINED_UNLOCK_PLAN if cls.retained else CHILD_UNLOCK_PLAN)


class ChildUnlockQualification(RetainedUnlockQualification):
    retained = False


class RetainedDenialQualification(KioskEntryQualification):
    retained = True

    @classmethod
    def journey(cls, context, progress):
        from app_snapshot import snapshot_name
        from desktop_session import RetainedDenialJourney, CHILD_DENIAL_PLAN, RETAINED_DENIAL_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RetainedDenialJourney(context, progress,
                                    RETAINED_DENIAL_PLAN if cls.retained else CHILD_DENIAL_PLAN)


class ChildDenialQualification(RetainedDenialQualification):
    retained = False


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


class IndependentNetworkQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from dataclasses import replace
        from app_snapshot import snapshot_name
        from fresh_desktop import PARENT_PLAN
        from installed_journey import InstalledJourney
        from vm_internet_qualification import qualify
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        plan = replace(PARENT_PLAN, stage_actions={'desktop': 'independent-network'})
        return InstalledJourney(context, progress, plan, actions={'independent-network': qualify})


class SyntheticFilesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from dataclasses import replace
        from app_snapshot import snapshot_name
        from fresh_desktop import PARENT_PLAN
        from installed_journey import InstalledJourney
        from synthetic_files import qualify
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        plan = replace(PARENT_PLAN, stage_actions={'desktop': 'synthetic-files'})
        return InstalledJourney(context, progress, plan, actions={'synthetic-files': qualify})


class DocumentOpenQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from dataclasses import replace
        from app_snapshot import snapshot_name
        from fresh_desktop import PARENT_PLAN
        from installed_journey import InstalledJourney
        from synthetic_files import qualify_text
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        plan = replace(PARENT_PLAN, stage_actions={'desktop': 'document-open'})
        return InstalledJourney(context, progress, plan, actions={'document-open': qualify_text})


class ArchiveOpenQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from dataclasses import replace
        from app_snapshot import snapshot_name
        from fresh_desktop import PARENT_PLAN
        from installed_journey import InstalledJourney
        from synthetic_files import qualify_zip
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        plan = replace(PARENT_PLAN, stage_actions={'desktop': 'archive-open'})
        return InstalledJourney(context, progress, plan, actions={'archive-open': qualify_zip})


class SourceChangeQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from dataclasses import replace
        from app_snapshot import snapshot_name
        from fresh_desktop import PARENT_PLAN
        from installed_journey import InstalledJourney
        from synthetic_files import qualify_source_change
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        plan = replace(PARENT_PLAN, stage_actions={'desktop': 'source-change'})
        return InstalledJourney(context, progress, plan,
                                actions={'source-change': qualify_source_change})


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


class ParentWebsiteQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from license_viewer_provider import ParentWebsiteJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentWebsiteJourney(context, progress)


class ParentPrivacyQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from license_viewer_provider import ParentPrivacyJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentPrivacyJourney(context, progress)


class ParentSupportQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from license_viewer_provider import ParentSupportJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentSupportJourney(context, progress)


class ParentInformationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from license_viewer_provider import ParentInformationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentInformationJourney(context, progress)


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


class FreshChildAllowedQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from fresh_child_allowed import FreshChildAllowedJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FreshChildAllowedJourney(context, progress)


class FreshChildDeniedQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from fresh_child_denied import FreshChildDeniedJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FreshChildDeniedJourney(context, progress)


class CountdownQualification(ChallengesQualification):
    present = True

    def journey(self, context, progress):
        from app_snapshot import snapshot_name
        from countdown_qualification import CountdownJourney, PLAN, OFF_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return CountdownJourney(context, progress, PLAN if self.present else OFF_PLAN)


class CountdownOffQualification(CountdownQualification):
    present = False


class CountdownSessionQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from countdown_qualification import CountdownJourney, SESSION_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return CountdownJourney(context, progress, SESSION_PLAN)


class CountdownAnimationQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from countdown_animation import CountdownAnimationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return CountdownAnimationJourney(context, progress)


class CountdownMinutesQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from countdown_qualification import CountdownMinutesJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return CountdownMinutesJourney(context, progress)


class CountdownTicksQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from countdown_qualification import CountdownTicksJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return CountdownTicksJourney(context, progress)


class NaturalExpiryQualification(ChallengesQualification):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_natural_expiry'

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from natural_expiry import NaturalExpiryJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return NaturalExpiryJourney(context, progress)


class ShellPanelQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from shell_panel import ShellPanelJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ShellPanelJourney(context, progress)


class OverlayValidChoicesQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_valid_choices import OverlayValidChoicesJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayValidChoicesJourney(context, progress)


class OverlayPromptQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_prompt import OverlayPromptJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayPromptJourney(context, progress)


class OverlayApprovedExitQualification(ChallengesQualification):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_overlay_approved_exit'

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_approved_exit import OverlayApprovedExitJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayApprovedExitJourney(context, progress)


class ApprovalReturnNewQualification(OverlayApprovedExitQualification):
    fixture_caller = 'check_e2e_compose_approval_and_return_to_the_child'

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from approval_return import ApprovalReturnJourney, NEW_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ApprovalReturnJourney(context, progress, NEW_PLAN)


class ApprovalReturnOpenQualification(ApprovalReturnNewQualification):
    @staticmethod
    def journey(context, progress):
        from approval_return import ApprovalReturnJourney, OPEN_PLAN
        from app_snapshot import snapshot_name
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ApprovalReturnJourney(context, progress, OPEN_PLAN)


class OverlayRejectionQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_rejection import OverlayRejectionJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayRejectionJourney(context, progress)


class OverlayApprovalImmediateQualification(OverlayApprovedExitQualification):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_overlay_approval'

    @staticmethod
    def journey(context, progress):
        from overlay_approved_exit import IMMEDIATE_PLAN
        journey = OverlayApprovedExitQualification.journey(context, progress)
        return type(journey)(context, progress, IMMEDIATE_PLAN)


class OverlayTranslatedApprovalQualification(OverlayApprovedExitQualification):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_overlay_translated_approval'

    @staticmethod
    def journey(context, progress):
        from overlay_approved_exit import TRANSLATED_PLAN
        journey = OverlayApprovedExitQualification.journey(context, progress)
        return type(journey)(context, progress, TRANSLATED_PLAN)


class OverlayFlowRejectionQualification(OverlayApprovedExitQualification):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_overlay_approval'

    @staticmethod
    def journey(context, progress):
        from overlay_approved_exit import FLOW_REJECTION_PLAN
        journey = OverlayApprovedExitQualification.journey(context, progress)
        return type(journey)(context, progress, FLOW_REJECTION_PLAN)


class OverlayFlowCancelQualification(OverlayApprovedExitQualification):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_overlay_approval'

    @staticmethod
    def journey(context, progress):
        from overlay_approved_exit import FLOW_CANCEL_PLAN
        journey = OverlayApprovedExitQualification.journey(context, progress)
        return type(journey)(context, progress, FLOW_CANCEL_PLAN)


class OverlayChoicesQualification(ChallengesQualification):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS as fixture_subsets
    fixture_caller = 'check_e2e_overlay_choices'

    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_choices import OverlayChoicesJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayChoicesJourney(context, progress)


class ChoicesOverlayToKioskQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from choices_overlay_to_kiosk import ChoicesOverlayToKioskJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ChoicesOverlayToKioskJourney(context, progress)


class CrossSurfaceQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from cross_surface import PLAN
        from request_composition import KioskRequestJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskRequestJourney(context, progress, PLAN)


class OverlayLicenseQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_license import OverlayLicenseJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayLicenseJourney(context, progress)


class OverlayBrowserLinksQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_license import BROWSER_LINKS_PLAN, OverlayLicenseJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayLicenseJourney(context, progress, BROWSER_LINKS_PLAN)


class OverlayInformationQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_license import INFORMATION_PLAN, OverlayLicenseJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayLicenseJourney(context, progress, INFORMATION_PLAN)


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

    def prepare_context(self, context):
        context.product_free = True

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
        context.product_free = True
        context.asset_transfer = self.transfer
        context.after_asset_transfer = lambda _transport, receipt: self.result.update(
            asset_transfer=receipt)

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


class UpgradeAssetsQualification(ProductFreeEntryQualification):
    upgrade_assets = True

    def prepare_context(self, context):
        super().prepare_context(context)
        def after_transfer(transport, receipt):
            from upgrade_assets_qualification import provisioning_refusals
            self.result['asset_transfer'] = receipt
            self.result['transfer_refusals'] = provisioning_refusals(
                self.verified, context.lease, self.guestfs, self.transfer,
                transport=transport)
        context.after_asset_transfer = after_transfer

    @staticmethod
    def journey(context, progress):
        from upgrade_assets_qualification import journey
        return journey(context, progress)


class ChineseLanguageQualification(ProductFreeEntryQualification):
    @staticmethod
    def journey(context, progress):
        from chinese_language_qualification import journey
        return journey(context, progress)


class DesktopLanguageQualification(ProductFreeEntryQualification):
    @staticmethod
    def journey(context, progress):
        from desktop_language_qualification import journey
        return journey(context, progress)


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


class RestartNoticeQualification(ProductFreeEntryQualification):
    @staticmethod
    def journey(context, progress):
        from restart_notice import RestartNoticeJourney
        return RestartNoticeJourney(context, progress)


class UnrelatedRebootQualification(ProductFreeEntryQualification):
    @staticmethod
    def journey(context, progress):
        from unrelated_reboot import UnrelatedRebootJourney
        return UnrelatedRebootJourney(context, progress)


class PackageUpgradeQualification(ProductFreeEntryQualification):
    upgrade_assets = True

    @staticmethod
    def journey(context, progress):
        from package_upgrade import PackageUpgradeJourney
        return PackageUpgradeJourney(context, progress)


class ChineseKioskLifecycleQualification(ProductFreeEntryQualification):
    upgrade_assets = True

    @staticmethod
    def journey(context, progress):
        from chinese_kiosk_lifecycle import ChineseKioskJourney
        return ChineseKioskJourney(context, progress)


class ChineseCurrentInstallQualification(ProductFreeEntryQualification):
    @staticmethod
    def journey(context, progress):
        from chinese_current_install import ChineseCurrentInstallJourney
        return ChineseCurrentInstallJourney(context, progress)


class RequestExitQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from request_exit import RequestExitJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RequestExitJourney(context, progress)


class RevokeCancelQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from time_explanation import RevokeCancelJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RevokeCancelJourney(context, progress)


class RevocationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from time_explanation import RevokeConfirmJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RevokeConfirmJourney(context, progress)


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


class DailyTimeProfileQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from time_profiles_daily import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class SameDailyTimeProfileQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from time_profiles_daily import journey, SAME_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress, SAME_PLAN)


class GrantOnlyProfileQualification(KioskEntryQualification):
    revoke_first = False
    daily_minutes = 0

    @classmethod
    def journey(cls, context, progress):
        from app_snapshot import snapshot_name
        from grant_only_profile import GrantOnlyProfileJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return GrantOnlyProfileJourney(context, progress, revoke_first=cls.revoke_first,
                                       daily_minutes=cls.daily_minutes)


class GrantOnlyRevokeQualification(GrantOnlyProfileQualification):
    revoke_first = True


class CombinedTimeProfileQualification(GrantOnlyProfileQualification):
    daily_minutes = 4


class RealIntervalQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from real_interval_qualification import RealIntervalJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RealIntervalJourney(context, progress)


class FreshThirtyAllowanceQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from fresh_thirty_allowance import FreshThirtyAllowanceJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FreshThirtyAllowanceJourney(context, progress)


class JordanThirtyAllowanceQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from fresh_thirty_allowance import FreshThirtyAllowanceJourney, JORDAN_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FreshThirtyAllowanceJourney(context, progress, JORDAN_PLAN)


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


class WindowSwitchQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from window_switch import WindowSwitchJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return WindowSwitchJourney(context, progress)


class FeedbackLengthQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_length import FeedbackLengthJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FeedbackLengthJourney(context, progress)


class FeedbackRejectionQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_rejection import FeedbackRejectionJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FeedbackRejectionJourney(context, progress)


class BlockSemanticsQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_block_semantics import BlockSemanticsJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return BlockSemanticsJourney(context, progress)


class FeedbackFormatsQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_formats_qualification import FeedbackFormatsJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FeedbackFormatsJourney(context, progress)


class FeedbackLinkQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_formats_qualification import FeedbackLinkJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FeedbackLinkJourney(context, progress)


class FormatQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from format_qualification import FormatJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FormatJourney(context, progress)


class TraceStableStateQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from trace_stable_state import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class TraceTransitionQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from trace_transition import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class AccessibilityInputTraceQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from accessibility_input_trace import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class CustomSaveTraceQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from custom_save_trace import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class NamedChildCustomSavesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from named_child_custom_saves import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class FeedbackCollectionQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_collection import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class ParentSaveTraceQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_save_trace import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class ComposeObservationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from compose_observation import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class FeedbackStatesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_states import FeedbackStatesJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FeedbackStatesJourney(context, progress)


class FeedbackPrivacyQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_privacy import FeedbackPrivacyJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FeedbackPrivacyJourney(context, progress)


class FeedbackResetQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from feedback_reset import FeedbackResetJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return FeedbackResetJourney(context, progress)


class DiagnosticExportQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from diagnostic_export import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class SaveChooserQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from save_chooser import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class FileChooserQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from file_chooser import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class AttachmentItemsQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from attachment_items import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class AttachmentPreviewQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from attachment_preview import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class AttachmentBoundariesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from attachment_boundaries import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


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


class MatchSaveCancelQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from match_save_cancel import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class MatchEditorQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from match_save_cancel import journey, EDITOR_PLAN
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress, EDITOR_PLAN)


class RejectedParentRuleQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from rejected_parent_rule import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class AccessChoicesQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from access_choices import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class PolicyQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from policy_qualification import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)


class PolicyLegendQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from policy_legend import PolicyLegendJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return PolicyLegendJourney(context, progress)


class CatalogueQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from catalogue import CatalogueJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return CatalogueJourney(context, progress)


class CatalogueSearchQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from catalogue_search import CatalogueSearchJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return CatalogueSearchJourney(context, progress)


class NativeFixtureQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from native_fixture_qualification import NativeFixtureJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return NativeFixtureJourney(context, progress)


class NativeActivityQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from native_activity import NativeActivityJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return NativeActivityJourney(context, progress)


class RetainedAppVisitsQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from retained_app_visits import RetainedAppVisitsJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RetainedAppVisitsJourney(context, progress)


class NativeAppQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from native_app import NativeAppJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return NativeAppJourney(context, progress)


class RileyNativeGridQualification(ChallengesQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from riley_native_grid import RileyNativeGridJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return RileyNativeGridJourney(context, progress)


class NativeGridQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from native_grid_usable import NativeGridJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return NativeGridJourney(context, progress)


class ParentLanguageQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_language import ParentLanguageJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentLanguageJourney(context, progress)


class ParentRtlQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_language import ParentRtlJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentRtlJourney(context, progress)


class ParentDialogLanguageQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_language import ParentDialogLanguageJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentDialogLanguageJourney(context, progress)


class ParentHebrewPolicyQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_language import ParentHebrewPolicyJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentHebrewPolicyJourney(context, progress)


class ParentLanguageIsolationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_language import ParentLanguageIsolationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentLanguageIsolationJourney(context, progress)


class KioskLanguageQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_language import KioskLanguageJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskLanguageJourney(context, progress)


class KioskLanguageRestorationQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_language_restoration import KioskLanguageRestorationJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskLanguageRestorationJourney(context, progress)


class OverlayLanguageQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_language import OverlayLanguageJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayLanguageJourney(context, progress)


class PanelLanguageQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from panel_language import PanelLanguageJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return PanelLanguageJourney(context, progress)


class OverlayReminderEditingQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from overlay_reminders import OverlayReminderJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return OverlayReminderJourney(context, progress)


class KioskReminderBindingQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from kiosk_reminders import KioskReminderJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return KioskReminderJourney(context, progress)


class ReminderFullscreenPreferenceQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from reminder_fullscreen import ReminderFullscreenJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ReminderFullscreenJourney(context, progress)


class ParentToggleQualification(KioskEntryQualification):
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from parent_toggle import ParentToggleJourney
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return ParentToggleJourney(context, progress)

class PublicConnectivityControlsQualification(ParentToggleQualification):
    """Reuse UI17's qualified sign-in/launch and LIFE06's public composition."""
    @staticmethod
    def journey(context, progress):
        from app_snapshot import snapshot_name
        from public_connectivity_controls import journey
        version = json.loads((smoke.ROOT / 'data/app.json').read_bytes())['version']
        context.installed_snapshot = snapshot_name(version)
        return journey(context, progress)
