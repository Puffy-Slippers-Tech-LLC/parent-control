"""Shared single-use account fixtures for discovery and request-station journeys."""

import json
import re

from private_artifacts import require
import system_runner as system
import watch_activity


def station_fixture_actions(context, profile):
    """Bind fresh single-use FIX03 state and intent for each station attempt."""
    require(profile in ('no-child', 'no-approver'), 'station-fixture:profile')
    if profile == 'no-child':
        fixture = EmptyAccountFixture(context)
        action = 'prepare-empty'
        label = 'Preparing the fixed no-child station profile'
    else:
        fixture = NoApproverFixture(context)
        action = 'prepare-no-approver'
        label = 'Temporarily locking the observed approver accounts'

    def prepare(journey, guard):
        with watch_activity.operation(label):
            return fixture.prepare(journey, guard)

    return {action: prepare}


class DynamicAccountFixture:
    def __init__(self, context):
        self.context = context
        self.attempted = False

    def create(self, journey, guard):
        require(not self.attempted and journey.context is self.context
                and journey.transport is not None, "dynamic-account:controller-state")
        self.attempted = True
        run = self.context.lease.state["run"]
        require(isinstance(run, str) and re.fullmatch(r"[0-9a-f]{32}", run),
                "dynamic-account:run")
        guard()
        result = journey.transport.call([
            "env", f"ONPC_EXPECTED_RUN={run}", "PYTHONDONTWRITEBYTECODE=1",
            "/usr/bin/python3", system.PAYLOAD + "/e2e_dynamic_account.py", "create",
        ], timeout=60)
        require(result == b"onpc-e2e: stage=dynamic-account outcome=created\n",
                "dynamic-account:unexpected-result")
        guard()
        return {"eligible_account_created": True}


class EmptyAccountFixture:
    operation = 'prepare-empty'
    result = b'onpc-e2e: stage=empty-account outcome=prepared\n'
    removed = 'eligible_accounts_removed'

    def __init__(self, context):
        self.context = context
        self.attempted = False

    def prepare(self, journey, guard):
        require(not self.attempted and journey.context is self.context
                and journey.transport is not None, "empty-account:controller-state")
        self.attempted = True
        run = self.context.lease.state["run"]
        require(isinstance(run, str) and re.fullmatch(r"[0-9a-f]{32}", run),
                "empty-account:run")
        guard()
        result = journey.transport.call([
            "env", f"ONPC_EXPECTED_RUN={run}", "PYTHONDONTWRITEBYTECODE=1",
            "/usr/bin/python3", system.PAYLOAD + "/e2e_dynamic_account.py",
            self.operation,
        ], timeout=60)
        require(result == self.result,
                "empty-account:unexpected-result")
        guard()
        return {self.removed: 2}


class NoApproverFixture(EmptyAccountFixture):
    """After a nonempty form, detect/lock eligible parents; VM restoration undoes it."""

    def prepare(self, journey, guard):
        require(not self.attempted and journey.context is self.context
                and journey.transport is not None, 'no-approver:controller-state')
        self.attempted = True
        run = self.context.lease.state['run']
        require(isinstance(run, str) and re.fullmatch(r'[0-9a-f]{32}', run),
                'no-approver:run')
        ui = journey.ui
        require(ui is not None and ui.last_operation == 'kiosk-approver-baseline',
                'no-approver:public-baseline')
        uids, ui.approver_uids = ui.approver_uids, None
        require(type(uids) is tuple and bool(uids)
                and all(type(uid) is int and 1000 <= uid <= (1 << 32) - 1 for uid in uids)
                and len(uids) == len(set(uids)), 'no-approver:public-baseline')
        guard()
        result = journey.transport.call([
            'env', f'ONPC_EXPECTED_RUN={run}', 'PYTHONDONTWRITEBYTECODE=1',
            '/usr/bin/python3', system.PAYLOAD + '/e2e_dynamic_account.py',
            'prepare-no-approver',
        ], input=json.dumps(list(uids)).encode(), timeout=60)
        match = re.fullmatch(rb'onpc-e2e: stage=no-approver outcome=prepared locked=([1-9][0-9]*)\n',
                             result)
        require(match is not None and int(match[1]) >= len(uids),
            'no-approver:unexpected-result')
        guard()
        return {'eligible_approvers_removed': int(match[1])}
