"""Finite current-package lifecycle actions within the existing owned envelope."""

from functools import partial

from asset_transfer import AssetTransfer
from installed_journey import InstalledJourney, record_installed_journey
from package_command import BINDING, REMOVE, PURGE, REINSTALL, FRESH_INSTALL, PackageCommand
from private_artifacts import require


HISTORY = (BINDING, REMOVE, REINSTALL, PURGE, FRESH_INSTALL)


class PackageLifecycleJourney(InstalledJourney):
    def __init__(self, context, progress, plan, *, operations, actions=None, checks=None):
        require(not context.installed_snapshot and context.verified.upgrade_inputs is None,
                'package-lifecycle:product-free-current-required')
        require(type(operations) is tuple and len(operations) == len(HISTORY), 'package-lifecycle:plan')
        stages = list(plan.screen_tags)
        require(tuple(binding for _, binding, _ in operations) == HISTORY
                and all(submitted in stages and result in stages
                        and stages.index(result) == stages.index(submitted) + 1
                        and plan.screen_tags[submitted] == plan.screen_tags[result]
                        == 'system:parent-command-context' for submitted, _, result in operations)
                and [stages.index(submitted) for submitted, _, _ in operations] == sorted(
                    stages.index(submitted) for submitted, _, _ in operations), 'package-lifecycle:plan')
        self.operations = operations
        self.commands = {}
        self.entries = {}
        self.results = set()
        self.checks = dict(checks or {})
        require(set(self.checks) <= set(plan.screen_tags)
                and all(callable(check) for check in self.checks.values()), 'package-lifecycle:checks')
        self.public_captures = {}
        self.checked_stages = set()
        shared = dict(actions or {})
        for submitted, binding, _ in operations:
            name = 'package-' + binding
            require(plan.stage_actions.get(submitted) == name and name not in shared, 'package-lifecycle:plan')
            shared[name] = self.action(binding)
        super().__init__(context, progress, plan, actions=shared)
        context.asset_transfer = AssetTransfer(context.verified)
        context.asset_transfer.provision(context.lease, context.guestfs)
        context.product_free = True

    def action(self, binding):
        def submit(journey, guard):
            require(binding not in self.commands and all(previous in self.results
                    for previous in HISTORY[:HISTORY.index(binding)]), 'package-lifecycle:phase')
            guard()
            command = PackageCommand(self.transport, self.context.verified)
            before = command.read_identity()
            require(before['version'] == (command.package_identities()['current']['version']
                    if binding in (REMOVE, PURGE) else None), 'package-lifecycle:phase')
            self.entries[binding] = before
            self.commands[binding] = command  # Retain uncertain input, never replay.
            result = command.submit(binding, command.verified.inputs['package_sha256'], command.identity)
            guard()
            return result
        return submit

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        self.check_package_result(stage, observed)
        if stage in self.checks:
            require(stage not in self.checked_stages, 'package-lifecycle:check-replay')
            self.checks[stage](self, observed)
            self.checked_stages.add(stage)

    def check_package_result(self, stage, observed):
        matches = [binding for _, binding, result in self.operations if result == stage]
        if not matches:
            return
        binding = matches[0]
        require(binding in self.commands and binding not in self.results, 'package-lifecycle:missing-command')
        command, before = self.commands[binding], self.entries[binding]
        result = command.read_result()
        current = command.read_identity()
        require(current == command.read_identity(), 'package-lifecycle:unstable-readback')
        require(current['version'] == (None if binding in (REMOVE, PURGE) else
                command.package_identities()['current']['version']), 'package-lifecycle:installed-version')
        # Product-owned request-station removal is expected. Every other public
        # account identity, language and group set is preserved independently.
        accounts = {uid: value for uid, value in before['preserved']['accounts'].items()
                    if value['identity'][0] != 'oh-no-parent-control'}
        preserved = {**current['preserved'], 'accounts': {
            uid: current['preserved']['accounts'].get(uid) for uid in accounts}}
        require(preserved == {**before['preserved'], 'accounts': accounts},
                'package-lifecycle:personal-state-changed')
        require(current['packages'] == before['packages'] and current['boot'] == before['boot']
                and current['session'] == before['session'], 'package-lifecycle:continuity')
        observed['package'] = {**result, 'installed_version': current['version'],
                              'independent_readback': True, 'personal_state_preserved': True}
        self.results.add(binding)


def record_lifecycle_journey(recorder, context, plan, *, operations, checks, actions=None, timeout=3600):
    """Compose lifecycle commands and caller-owned public comparisons."""
    record_installed_journey(recorder, context, plan, timeout=timeout, actions=actions,
                            journey_type=partial(PackageLifecycleJourney, operations=operations, checks=checks))
