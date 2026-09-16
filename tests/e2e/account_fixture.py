"""Controller side of the fixed E2E-003 account fixture events."""

import re

from private_artifacts import require
import system_runner as system


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
            "prepare-empty",
        ], timeout=60)
        require(result == b"onpc-e2e: stage=empty-account outcome=prepared\n",
                "empty-account:unexpected-result")
        guard()
        return {"eligible_accounts_removed": 2}
