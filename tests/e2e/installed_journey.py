"""Installed customer journeys: setup, durable input gates and screen evidence.

Scenario plans own the ordered visible expectations and recorder phases. This
module owns transport/setup mechanics and boot continuity, never product probes.
"""

from dataclasses import dataclass, field
import json
import os
import re
import sys
import time

from check_graphical_smoke import module_result, screenshot
import command_documentation
import session_control
from observation_transport import ReadOnlyObservations
from private_artifacts import require
from parent_needles import semantic_tag
import system_runner as system
from vm_transport import Transport
from ui_observations import (
    RequestObservation, SettingsObservation, UiObservations, compare_settings,
)


@dataclass(frozen=True)
class JourneyPlan:
    """Trusted scenario declaration; screen_tags insertion order is execution order.

    advance_after opens a recorder phase before the current acknowledgement
    permits its first action, e.g. before closing a license viewer to return.
    """

    prefix: str
    worker_mode: str
    screen_tags: dict
    phases: dict
    advance_after: dict = field(default_factory=dict)
    stage_actions: dict = field(default_factory=dict)
    review_mode: str | None = None
    settings_checks: dict = field(default_factory=dict)
    invocations: tuple = ()
    assertions_after: dict = field(default_factory=dict)
    challenges: dict = field(default_factory=dict)
    reboot_transition: tuple = ()

    def __post_init__(self):
        # Invocation IDs are filenames and immutable observation identities,
        # independent of the public operation (which may occur many times).
        require(all(type(stage) is str and re.fullmatch(r'[a-z][a-z0-9-]*', stage)
                    and stage not in ('ready', 'setup-detached')
                    for stage in self.screen_tags), self.prefix + ':stage-plan')
        require(type(self.invocations) is tuple
                and len(set(self.invocations)) == len(self.invocations)
                and list(self.invocations) == [stage for stage in self.screen_tags
                                               if stage in self.invocations]
                and all(self.screen_tags[stage].startswith('ui:')
                        for stage in self.invocations), self.prefix + ':invocation-plan')
        require(set(self.assertions_after) <= set(self.screen_tags)
                and all(type(value) is str and re.fullmatch(r'[a-z][a-z0-9-]*', value)
                        for value in self.assertions_after.values())
                and len(set(self.assertions_after.values())) == len(self.assertions_after),
                self.prefix + ':assertion-plan')
        used = set()
        stages = list(self.screen_tags)
        require(type(self.reboot_transition) is tuple and
                (not self.reboot_transition or
                 len(self.reboot_transition) == 2 and
                 all(stage in stages for stage in self.reboot_transition) and
                 stages.index(self.reboot_transition[1]) ==
                 stages.index(self.reboot_transition[0]) + 1 and
                 self.screen_tags[self.reboot_transition[0]] == 'system:parent-command-context' and
                 self.screen_tags[self.reboot_transition[1]] == 'ui:gdm-list' and
                 self.reboot_transition[0] not in self.stage_actions),
                self.prefix + ':reboot-plan')
        for identity, binding in self.challenges.items():
            require(type(identity) is str and re.fullmatch(r'[a-z][a-z0-9-]*', identity)
                    and type(binding) is tuple and len(binding) == 3,
                    self.prefix + ':challenge-plan')
            role, first, second = binding
            require(role in ('parent', 'other-child') and first in self.invocations
                    and second in self.invocations and not {first, second} & used
                    and stages.index(second) == stages.index(first) + 1,
                    self.prefix + ':challenge-plan')
            recipient = 'gdm-parent-recipient' if role == 'parent' else 'gdm-standard-recipient'
            focus = 'gdm-focused' if role == 'parent' else 'gdm-standard-focused'
            require(stages.index(first) > 0
                    and self.screen_tags[stages[stages.index(first) - 1]] == 'ui:' + focus
                    and self.screen_tags[first] == 'ui:' + recipient
                    and self.screen_tags[second] == 'ui:' + recipient + '-rechecked',
                    self.prefix + ':challenge-plan')
            used.update((first, second))

    def challenge_at(self, stage):
        for identity, (role, first, second) in self.challenges.items():
            if stage in (first, second):
                return {'id': identity, 'role': role, 'surface': 'gdm',
                        'check': 'qualified' if stage == first else 'rechecked'}
        return None

    @property
    def stages(self):
        return ('ready', 'setup-detached', *self.screen_tags)


def matched_screens(directory, plan, observations=()):
    """Reconcile ordered public UI results; legacy/security needles stay strict.

    ui: operations use fresh, durable accessibility results, not image scores.
    A worker marker alone, or a prior observation, cannot satisfy a stage.
    """
    module_result(directory)
    details = json.loads((directory / 'testresults/result-smoke.json').read_bytes())['details']
    stages, screens = [], []
    last_match = None
    marker = plan.prefix + '-'
    for index, detail in enumerate(details):
        if 'needle' in detail:
            require(detail.get('result') == 'ok' and detail.get('area')
                    and all(a.get('result') == 'ok' and a.get('similarity') == 100
                            for a in detail['area']), plan.prefix + ':match-quality')
            last_match = (index, detail)
        title = detail.get('title', '')
        if not title.startswith(marker):
            continue
        stage = title.removeprefix(marker)
        require(stage in plan.screen_tags and stage not in stages and detail.get('result') == 'ok',
                plan.prefix + ':screen-order')
        stages.append(stage)
        tag = plan.screen_tags[stage]
        if tag.startswith('ui:'):
            matches = [item for item in observations if item['stage'] == stage]
            require(len(matches) == 1 and matches[0].get('ui', {}).get('operation') == tag[3:]
                    and matches[0]['ui'].get('outcome') == 'passed', plan.prefix + ':ui-evidence')
            if plan.challenge_at(stage):
                require(matches[0].get('challenge') == plan.challenge_at(stage),
                        plan.prefix + ':challenge-evidence')
            screens.append({'stage': stage, 'detail_index': index, 'ui': matches[0]['ui']})
            last_match = None
            continue
        if tag.startswith('command:'):
            matches = [item for item in observations if item['stage'] == stage]
            require(len(matches) == 1 and matches[0].get('command', {}).get('operation') == tag[8:]
                    and matches[0]['command'].get('outcome') == 'passed',
                    plan.prefix + ':command-evidence')
            screens.append({'stage': stage, 'detail_index': index,
                            'command': matches[0]['command']})
            last_match = None
            continue
        if tag.startswith('system:'):
            matches = [item for item in observations if item['stage'] == stage]
            require(len(matches) == 1 and matches[0].get('system', {}).get('operation') == tag[7:]
                    and matches[0]['system'].get('outcome') == 'passed',
                    plan.prefix + ':system-evidence')
            screens.append({'stage': stage, 'detail_index': index,
                            'system': matches[0]['system']})
            last_match = None
            continue
        require(last_match is not None and semantic_tag(last_match[1]['needle']) == tag,
                plan.prefix + ':screen-order')
        match_index, match = last_match
        screens.append({'stage': stage, 'needle': match['needle'], 'detail_index': match_index,
                        **screenshot(directory, match.get('screenshot'))})
        last_match = None  # A prior match cannot authorize another stage.
    require(stages == list(plan.screen_tags), plan.prefix + ':missing-screens')
    return screens


class InstalledJourney:
    """One guarded stage rendezvous, with durable observations before replies."""

    def __init__(self, context, progress, plan, *, review=False, actions=None):
        require(type(review) is bool and (not review or plan.review_mode is not None),
                plan.prefix + ':review-mode')
        self.context, self.progress, self.plan = context, progress, plan
        self.watch_progress = getattr(getattr(context, 'recorder', None), 'progress', None)
        self.review = review
        self.actions = actions or {}
        require(set(self.actions) == set(plan.stage_actions.values())
                and set(plan.stage_actions) <= set(plan.stages), plan.prefix + ':stage-actions')
        self.steps = []
        self.vm = None
        self.transport = None
        self.ui = None
        self.boot = None
        self.reboot_submitted = False
        self.reboot_observed = False
        self.failed = False
        self.prompt_counts = {}
        self.settings_observations = {}
        self.request_observations = {}
        for stage, expected in plan.settings_checks.items():
            require(stage in plan.screen_tags and
                    (type(expected) is SettingsObservation or
                     type(expected) is str and expected in plan.screen_tags and
                     list(plan.screen_tags).index(expected) < list(plan.screen_tags).index(stage)),
                    plan.prefix + ':settings-plan')

    def check_settings(self, stage, observed):
        """Compare recipe-supplied values before fixture actions or durable reply."""
        if not self.plan.settings_checks:
            return
        settings = observed.get('ui', {}).get('settings')
        if settings is not None:
            require(stage not in self.settings_observations, 'ui:selection-replay')
            current = SettingsObservation.from_settings(settings)
            expected = self.plan.settings_checks.get(stage)
            if type(expected) is str:
                require(expected in self.settings_observations, 'ui:missing-settings-observation')
                expected = self.settings_observations[expected]
            if expected is not None:
                observed['comparison'] = compare_settings(current, expected)
            self.settings_observations[stage] = current
        else:
            require(stage not in self.plan.settings_checks, 'ui:missing-settings-observation')

    def check_request(self, stage, observed):
        value = observed.get('ui', {}).get('request')
        if value is None:
            return
        require(stage not in self.request_observations, 'ui:request-replay')
        self.request_observations[stage] = RequestObservation.from_request(
            value, operation=observed.get('ui', {}).get('operation', 'kiosk-request-form'))

    def dismiss_system_prompt(self, stage, point, guard):
        """Retired coordinate rendezvous; the guest adapter owns semantic Cancel."""
        require(False, 'ui:prompt-coordinate-route-refused')

    def step(self, guard):
        require(not self.failed, self.plan.prefix + ':previous-failure')
        try:
            self._step(guard)
        except BaseException:
            self.failed = True
            raise

    def submit_reboot(self, guard):
        """Only the declared input stage may consume this attempt's reboot."""
        require(not self.failed and self.plan.reboot_transition and
                len(self.steps) < len(self.plan.stages) and
                self.plan.stages[len(self.steps)] == self.plan.reboot_transition[0],
                self.plan.prefix + ':reboot-entry')
        require(not self.reboot_submitted and self.boot is not None,
                self.plan.prefix + ':reboot-replay')
        guard()
        require(self.vm.read('boot')['boot_sha256'] == self.boot,
                self.plan.prefix + ':boot-changed')
        # Record intent before any input; an uncertain command is never replayed.
        self.reboot_submitted = True
        with (self.context.directory / 'customer-reboot-intent.json').open('x') as stream:
            json.dump({'stage': self.plan.reboot_transition[0],
                       'previous_boot_sha256': self.boot}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        guard()
        self.transport.request_customer_reboot(self.boot)
        guard()
        return {'submitted': True, 'previous_boot_sha256': self.boot}

    def _step(self, guard):
        plan, context = self.plan, self.context
        if len(self.steps) == len(plan.stages):
            return
        stage = plan.stages[len(self.steps)]
        path = context.directory / (stage + '.request.json')
        if not path.exists():
            return
        require(not path.is_symlink() and path.stat().st_size <= 1024, plan.prefix + ':request-file')
        request = json.loads(path.read_bytes())
        require(request == {'stage': stage, 'screenshot': None}, plan.prefix + ':request-schema')
        pending = context.directory / (stage + '.reply.tmp')
        destination = context.directory / (stage + '.reply.json')
        require(not os.path.lexists(pending) and not os.path.lexists(destination),
                plan.prefix + ':reply-replay')
        guard()
        observed = {'stage': stage, 'outcome': 'observed' if self.review else 'passed'}
        if stage == 'ready':
            reply = {plan.worker_mode: True}
            if plan.invocations:
                reply['invocations'] = list(plan.invocations)
            if plan.challenges:
                reply['challenge_bindings'] = {key: list(value) for key, value in plan.challenges.items()}
            if self.review:
                reply[plan.review_mode] = True
        elif stage == 'setup-detached':
            install_current = getattr(context, 'install_current_package', False)
            product_free = getattr(context, 'product_free', False)
            require(type(product_free) is bool and type(install_current) is bool
                    and not (product_free and (install_current or
                             getattr(context, 'installed_snapshot', None))) and
                    (install_current is True or product_free
                     or getattr(context, 'installed_snapshot', None)),
                    plan.prefix + ':installed-snapshot-required')
            if self.watch_progress is not None:
                self.watch_progress.operation('Preparing the application connection')
            hostname = system.address(context.lease.source, timeout=90)
            (context.directory / 'known-hosts').write_text(f'{hostname} {context.host_key}\n')
            config = {'directory': str(context.directory), 'hostname': hostname,
                'domain_uuid': context.lease.source.uuid, 'domain_id': context.lease.view.domain_id,
                'run': context.lease.state['run']}
            transport = Transport(config, context.commands, guard=lambda _: context.lease.guard())
            transport.probe_ready(timeout=180)
            # The snapshot's installed app persists, but its helper payload
            # belongs to the snapshot-creation run. Bootstrap has already bound
            # the guard marker to this attempt's package and selected inputs.
            if product_free:
                observed['setup'] = {'product_free_baseline': True}
            else:
                from installed_setup import InstalledSetup
                setup = InstalledSetup(context.directory, context.verified, transport)
                if install_current:
                    observed['setup'] = setup.run(guard, verify=False)
                else:
                    setup.provision(guard)
                    observed['setup'] = {'installed_snapshot': context.installed_snapshot}
            self.vm = ReadOnlyObservations(transport)
            self.transport = transport
            if product_free and getattr(context, 'asset_transfer', None) is not None:
                observed['setup']['assets'] = context.asset_transfer.observe(self.vm)
            reply = {'setup_complete': True}
        else:
            # Harness boot identity is continuity metadata, never a product
            # policy/session probe or customer assertion.
            if plan.reboot_transition and stage == plan.reboot_transition[1]:
                require(self.reboot_submitted and not self.reboot_observed,
                        plan.prefix + ':unplanned-reboot')
                transition = self.vm.wait_boot_change(self.boot)
                require(transition['previous_boot_sha256'] == self.boot and
                        transition['boot_changed'] is True and
                        transition['boot_sha256'] != self.boot,
                        plan.prefix + ':reboot-result')
                self.boot = transition['boot_sha256']
                self.reboot_observed = True
                self.ui = None  # Never carry a pre-reboot recipient or UI cache.
                observed['boot_transition'] = transition
            current = self.vm.read('boot')['boot_sha256']
            require(self.boot is None or self.boot == current, plan.prefix + ':boot-changed')
            self.boot = current
            observed['boot_sha256'] = current
            tag = plan.screen_tags[stage]
            if tag.startswith('ui:'):
                if self.ui is None:
                    self.ui = UiObservations(self.transport, progress=self.watch_progress)
                challenge = plan.challenge_at(stage)
                observed['ui'] = (self.ui.observe_challenge(tag[3:], challenge)
                                  if challenge else self.ui.observe(tag[3:]))
                if challenge:
                    observed['challenge'] = challenge
            elif tag.startswith('command:'):
                observed['command'] = command_documentation.observe(self.transport, tag[8:])
            elif tag.startswith('system:'):
                observed['system'] = session_control.observe(self.transport, tag[7:])
            reply = {'observed': stage}
            if plan.challenge_at(stage):
                reply['challenge'] = observed['challenge']
            if tag == 'ui:station-entry-branch':
                reply['station_destination'] = observed['ui']['branch']['destination']
            if tag == 'ui:station-default-entry':
                reply['station_destination'] = observed['ui']['entry']['destination']
            if observed.get('ui', {}).get('focused') is True:
                reply['ui_focused'] = True
        self.check_settings(stage, observed)
        self.check_request(stage, observed)
        if plan.reboot_transition and stage == plan.reboot_transition[0]:
            observed['reboot'] = self.submit_reboot(guard)
        if stage in plan.assertions_after:
            require(not self.review, plan.prefix + ':assertion-review')
            observed['assertion'] = {'id': plan.assertions_after[stage],
                                     'phase': plan.phases[stage]}
        if stage in plan.stage_actions:
            if self.watch_progress is not None:
                self.watch_progress.operation(
                    'Preparing the login-keyring prompt'
                    if plan.stage_actions[stage] == 'prepare-keyring'
                    else 'Checking command refusal outside the fixture desktop'
                    if plan.stage_actions[stage] == 'refuse-command'
                    else 'Preparing the declared child-account fixture')
            action = self.actions[plan.stage_actions[stage]]
            observed['fixture'] = action(self, guard)
        guard()
        self.steps.append(observed)
        self.progress(stage, observed)
        print(plan.prefix + ':stage-observed=' + stage, file=sys.stderr, flush=True)
        guard()
        with pending.open('x') as stream:
            json.dump(reply, stream)
        pending.rename(destination)

    def validate(self):
        require(not self.failed, self.plan.prefix + ':previous-failure')
        require([s['stage'] for s in self.steps] == list(self.plan.stages),
                self.plan.prefix + ':missing-stages')
        return matched_screens(self.context.directory, self.plan, self.steps)


def record_installed_journey(recorder, context, plan, *, timeout=1800, actions=None,
                             journey_type=InstalledJourney):
    """Run a strict customer plan through the existing recorder and worker gate.

    Phases describe when each observation belongs; advance_after describes when
    the *next input* starts a new phase. All storage completes before that input.
    """
    require(set(plan.phases) == set(plan.stages)
            and set(plan.advance_after) <= set(plan.screen_tags), plan.prefix + ':phase-plan')

    def artifact(name, kind, value):
        return recorder.artifact(plan.prefix + '-' + name, kind,
                                 (json.dumps(value, sort_keys=True)+'\n').encode(), reviewed=True)

    active = None
    phase = None
    boot = None

    def enter(next_phase):
        nonlocal active, phase
        if next_phase == phase:
            return
        if active is not None:
            closing, active = active, None
            closing.__exit__(None, None, None)
        opening = recorder.step(next_phase)
        opening.__enter__()
        active, phase = opening, next_phase

    def progress(stage, observed):
        nonlocal boot
        if 'boot_sha256' in observed:
            boot = observed['boot_sha256']
        enter(plan.phases[stage])
        if boot is not None:
            recorder.continuity(boot=boot)
        artifact(stage, 'action-trace', observed)
        recorder.checkpoint('observation')
        if stage in plan.assertions_after:
            ref = artifact(stage + '-result', 'screen', observed)
            recorder.assertion(plan.assertions_after[stage], artifact_ids=[ref])
        if stage in plan.advance_after:
            enter(plan.advance_after[stage])
            recorder.continuity(boot=boot)

    try:
        enter('setup')
        recorder.progress.operation('Provisioning the declared fixture accounts')
        context.credentials.provision(context.lease, context.verified, context.directory,
                                      context.guestfs, context.commands)
        artifact('inputs', 'input-provenance', context.verified.inputs)
        journey = journey_type(context, progress, plan, actions=actions)
        worker = context.run_worker(observe=lambda: None, guarded_observe=journey.step,
                                    validate=journey.validate, authenticate=True, timeout=timeout)
        require(worker['shutdown_verified'] is True, plan.prefix + ':shutdown-unverified')
        ref = artifact('matched-screens', 'screen', journey.validate())
        if not plan.assertions_after:
            recorder.assertion('visible-result', artifact_ids=[ref])
        enter('end')
        recorder.continuity(boot=boot)
        artifact('continuity', 'continuity', {'boot_sha256': boot, 'stages': list(plan.stages)})
        artifact('outcome', 'outcomes', {'outcome': worker['outcome']})
        artifact('worker-cleanup', 'cleanup', {name: worker[name] for name in
            ('worker_stopped', 'callback_closed', 'shutdown_verified')})
    finally:
        if active is not None:
            active.__exit__(*sys.exc_info())
