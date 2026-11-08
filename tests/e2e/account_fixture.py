"""Shared single-use account fixtures for discovery and request-station journeys."""

import json
import re

from private_artifacts import require
import system_runner as system
import watch_activity


def account_fixture_call(context, journey, guard, operation, *, input=None, timeout=180):
    require(journey.context is context and journey.transport is not None,
            'account-fixture:controller-state')
    run = context.lease.state['run']
    require(isinstance(run, str) and re.fullmatch(r'[0-9a-f]{32}', run), 'account-fixture:run')
    guard()
    result = journey.transport.call([
        'env', f'ONPC_EXPECTED_RUN={run}', 'PYTHONDONTWRITEBYTECODE=1',
        '/usr/bin/python3', system.PAYLOAD + '/e2e_dynamic_account.py', operation,
    ], input=input, timeout=timeout)
    guard()
    return result


def station_fixture_actions(context, profile):
    """Bind fresh single-use FIX03 state and intent for each station attempt."""
    require(profile in ('no-child', 'no-approver', 'ineligible-approver'), 'station-fixture:profile')
    if profile == 'no-child':
        fixture = EmptyAccountFixture(context)
        action = 'prepare-empty'
        label = 'Preparing the fixed no-child station profile'
    elif profile == 'ineligible-approver':
        fixture = IneligibleApproverFixture(context)
        action = 'prepare-ineligible-approver'
        label = 'Preparing one locked administrator excluded from station choices'
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
        result = account_fixture_call(self.context, journey, guard, 'create', timeout=60)
        require(result == b"onpc-e2e: stage=dynamic-account outcome=created\n",
                "dynamic-account:unexpected-result")
        return {"eligible_account_created": True}


class SpareChildrenFixture:
    """Single-use one/two-child setup and removal in the same guarded attempt."""

    def __init__(self, context, *, count=2):
        require(type(count) is int and count in (1, 2), 'spare-child:profile')
        self.context, self.count = context, count
        self.prepared = self.removed = False
        self.identities = None

    def call(self, journey, guard, operation, *, input=None):
        return account_fixture_call(self.context, journey, guard, operation, input=input)

    def prepare(self, journey, guard):
        require(not self.prepared, 'spare-child:prepare-replay')
        self.prepared = True
        with watch_activity.operation('Preparing the disposable child account profile'):
            raw = self.call(journey, guard, 'prepare-two-spare-children' if self.count == 2
                            else 'prepare-one-spare-child')
        value = json.loads(raw)
        require(type(value) is dict and set(value) == (
            {'jordan', 'riley'} if self.count == 2 else {'jordan'})
            and all(type(uid) is int and 1000 <= uid <= (1 << 32) - 1 for uid in value.values())
            and len(set(value.values())) == self.count, 'spare-child:prepared-identities')
        self.identities = value
        return {'eligible_spare_children': self.count}

    def remove(self, journey, guard):
        require(self.prepared and self.identities is not None and not self.removed,
                'spare-child:remove-state')
        self.removed = True
        with watch_activity.operation('Removing the logged-out disposable child once'):
            result = self.call(journey, guard, 'remove-spare-child',
                               input=str(self.identities['jordan']).encode())
        require(result == (b'onpc-system: stage=account-deletion role=jordan outcome=visible\n'
                           b'onpc-e2e: stage=spare-child outcome=removed\n'),
                'spare-child:removal-result')
        return {'selected_spare_removed': True}


class SpareApproverFixture:
    """Fresh Sam and one role change; the owned snapshot restores both."""

    def __init__(self, context):
        self.context = context
        self.prepared = self.changed = False
        self.uid = None

    def prepare(self, journey, guard):
        require(not self.prepared, 'spare-approver:prepare-replay')
        self.prepared = True
        with watch_activity.operation('Preparing Sam as a disposable eligible parent'):
            value = json.loads(account_fixture_call(
                self.context, journey, guard, 'prepare-spare-approver'))
        require(type(value) is dict and set(value) == {'sam'}
                and type(value['sam']) is int and 1000 <= value['sam'] <= (1 << 32) - 1,
                'spare-approver:prepared-identity')
        self.uid = value['sam']
        return {'spare_approver_prepared': True}

    def demote(self, journey, guard):
        require(self.prepared and self.uid is not None and not self.changed,
                'spare-approver:role-state')
        self.changed = True
        with watch_activity.operation('Changing only the logged-out Sam account to standard'):
            result = account_fixture_call(self.context, journey, guard, 'demote-spare-approver',
                                          input=str(self.uid).encode())
        require(result == b'onpc-e2e: stage=spare-approver outcome=standard\n',
                'spare-approver:role-result')
        return {'spare_approver_now_standard': True}


class EmptyAccountFixture:
    operation = 'prepare-empty'
    result = b'onpc-e2e: stage=empty-account outcome=prepared\n'
    removed = 'eligible_accounts_removed'
    count = 2

    def __init__(self, context):
        self.context = context
        self.attempted = False

    def prepare(self, journey, guard):
        require(not self.attempted and journey.context is self.context
                and journey.transport is not None, "empty-account:controller-state")
        self.attempted = True
        result = account_fixture_call(self.context, journey, guard, self.operation, timeout=60)
        require(result == self.result,
                "empty-account:unexpected-result")
        return {self.removed: self.count}


class IneligibleApproverFixture(EmptyAccountFixture):
    operation = 'prepare-ineligible-approver'
    result = b'onpc-e2e: stage=ineligible-approver outcome=prepared\n'
    removed = 'ineligible_approvers_created'
    count = 1


class NoApproverFixture(EmptyAccountFixture):
    """After a nonempty form, detect/lock eligible parents; VM restoration undoes it."""

    def prepare(self, journey, guard):
        require(not self.attempted and journey.context is self.context
                and journey.transport is not None, 'no-approver:controller-state')
        self.attempted = True
        # Refuse a bad run before consuming the one-use public account list.
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
        result = account_fixture_call(self.context, journey, guard, 'prepare-no-approver',
                                      input=json.dumps(list(uids)).encode(), timeout=60)
        match = re.fullmatch(rb'onpc-e2e: stage=no-approver outcome=prepared locked=([1-9][0-9]*)\n',
                             result)
        require(match is not None and int(match[1]) >= len(uids),
            'no-approver:unexpected-result')
        return {'eligible_approvers_removed': int(match[1])}
