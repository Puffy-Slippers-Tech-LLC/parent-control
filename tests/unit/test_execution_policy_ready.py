import errno
import unittest
from types import SimpleNamespace
from unittest import mock

from tools import execution_policy_ready


class ExecutionPolicyReadinessTests(unittest.TestCase):
    @mock.patch("tools.execution_policy_ready.subprocess.run")
    def test_probe_execution_means_policy_is_not_ready(self, run):
        run.return_value = SimpleNamespace(
            returncode=execution_policy_ready.PROBE_EXECUTED
        )

        self.assertFalse(execution_policy_ready.policy_is_enforcing())

    @mock.patch("tools.execution_policy_ready.subprocess.run")
    def test_kernel_denial_means_policy_is_ready(self, run):
        run.side_effect = PermissionError(errno.EACCES, "denied")

        self.assertTrue(execution_policy_ready.policy_is_enforcing())

    @mock.patch("tools.execution_policy_ready.subprocess.run")
    def test_unexpected_probe_failure_fails_closed(self, run):
        run.return_value = SimpleNamespace(returncode=1)

        with self.assertRaises(execution_policy_ready.ReadinessError):
            execution_policy_ready.policy_is_enforcing()

    @mock.patch("tools.execution_policy_ready.time.sleep")
    @mock.patch("tools.execution_policy_ready.policy_is_enforcing")
    def test_wait_retries_until_kernel_denies_probe(self, is_enforcing, sleep):
        is_enforcing.side_effect = [False, True]

        execution_policy_ready.wait_until_enforcing()

        sleep.assert_called_once_with(execution_policy_ready.RETRY_SECONDS)


if __name__ == "__main__":
    unittest.main()
