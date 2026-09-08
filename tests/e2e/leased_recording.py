"""Connect one recorded scenario to the existing lease's sole cleanup owner.

The caller prepares and holds the lease, freezes provenance, and keeps the
collector open. This adapter neither acquires nor restores nor releases a VM.
Each independent case uses its own exact selection and complete outer attempt.
"""

import copy
import sys

from private_artifacts import require


class LeasedScenario:
    """Record actions now and finalize evidence after restoration, before release.

    ``cleanup`` is a trusted read/report callback returning CLEANUP_FIELDS from
    actual worker, VM, host and source checks. It must not mutate or release the
    lease. The existing Lease.__exit__ invokes our finalizer even after failure.
    ``result`` must be called after leaving that context so a release failure
    cannot be mistaken for the earlier held-lease acceptance candidate.
    """

    def __init__(self, recorder, verified, *, cleanup):
        lease = verified.lease
        cases = recorder.contract.plan['cases']
        require(lease.fd is not None and lease.state['phase'] == 'isolated'
                and lease.state['domain_id'] is None, 'recording:prepared-lease-required')
        require(lease.finalize is None, 'recording:finalizer-already-owned')
        require(lease.ledger is not None, 'recording:lease-ledger-required')
        require(len(cases) == 1 and not recorder.records, 'recording:independent-case-required')
        require(len(cases[0]['phases']['cleanup']) == 1
                and cases[0]['phases']['cleanup'][0]['operation'] == 'outer-reset',
                'recording:outer-cleanup-required')
        verified.recheck_contract(recorder.contract)
        self.recorder, self.verified, self.lease = recorder, verified, lease
        self.ledger = lease.ledger
        self.cleanup = cleanup
        self.case_id = cases[0]['case_id']
        self.cleanup_step = cases[0]['phases']['cleanup'][0]['id']
        self._identity = (lease.fd, lease.state['run'], lease.state['domain_uuid'])
        self._started = self._finished = False
        self._cleanup_context = None
        self._first_error = None
        self._summary = None
        self._finalizer = self._finalize
        lease.finalize = self._finalizer

    def _check_identity(self, lease):
        require(lease is self.lease and lease.finalize is self._finalizer
                and lease.ledger is self.ledger
                and (lease.fd, lease.state['run'], lease.state['domain_uuid']) == self._identity,
                'recording:lease-identity-changed')

    def _remember(self, error, category, code):
        self._first_error = self._first_error if self._first_error is not None else error
        try:
            self.recorder.failure(category, code)
        except BaseException:
            # A failed checkpoint is already latched by the recorder. Never
            # replace the operation's error or interrupt the lease's cleanup.
            pass

    def execute(self, callback):
        require(not self._started and not self._finished, 'recording:attempt-already-started')
        self._started = True
        try:
            self.recorder.begin_case(self.case_id)
            self._check_identity(self.lease)
            require(self.lease.state['phase'] == 'isolated'
                    and self.lease.state['domain_id'] is None, 'recording:prepared-lease-required')
            self.verified.recheck_contract(self.recorder.contract)
            callback(self.recorder)
        except BaseException as error:
            self._remember(error, 'infrastructure', 'scenario-interrupted'
                           if isinstance(error, KeyboardInterrupt) else 'scenario-execution-failed')
            raise
        finally:
            original = sys.exception()
            try:
                self.recorder.checkpoint('before-cleanup')
                # Enter before Lease.__exit__ starts the actual outer reset.
                # Finish only from its post-restoration, held-lease callback.
                context = self.recorder.step(self.cleanup_step)
                context.__enter__()
                self._cleanup_context = context
            except BaseException as error:
                self._remember(error, 'collection', 'scenario-cleanup-checkpoint-failed')
                if original is None:
                    raise

    def _finalize(self, lease):
        require(not self._finished, 'recording:attempt-already-finalized')
        self._finished = True
        cleanup_state = None
        failure = None
        try:
            require(self._started, 'recording:attempt-not-started')
            self._check_identity(lease)
            require(lease.state['phase'] == 'complete', 'recording:cleanup-incomplete')
            lease.guard(off=True)
            self.verified.recheck_contract(self.recorder.contract)
            require(self._cleanup_context is not None, 'recording:cleanup-not-started')
            cleanup_state = self.cleanup(self.recorder, lease)
        except BaseException as error:
            failure = error
            self._remember(error, 'cleanup', 'scenario-cleanup-failed')
        finally:
            if self._cleanup_context is not None:
                try:
                    self._cleanup_context.__exit__(
                        type(failure) if failure is not None else None, failure,
                        failure.__traceback__ if failure is not None else None)
                except BaseException as error:
                    failure = failure if failure is not None else error
                    self._remember(error, 'collection', 'scenario-cleanup-checkpoint-failed')
            if cleanup_state is None:
                from evidence import CLEANUP_FIELDS
                cleanup_state = {key: 'incomplete' if key == 'lease_phase' else False
                                 for key in CLEANUP_FIELDS}
            try:
                self.recorder.end_case(cleanup_state)
                self._check_identity(lease)
                self._summary = self.recorder.validate(self.verified)
            except BaseException as error:
                failure = failure if failure is not None else error
                self._first_error = self._first_error if self._first_error is not None else error
        if failure is not None:
            raise failure

    def result(self):
        """Reject early access, failed restoration/collection, or failed release."""
        require(self._finished and self.lease.fd is None, 'recording:lease-not-released')
        require(self._first_error is None and self._summary is not None
                and not any(item['outcome'] == 'failed'
                            for item in self.ledger.outcomes.values()),
                'recording:attempt-failed')
        return copy.deepcopy(self._summary)
