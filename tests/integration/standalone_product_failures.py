"""Join product fault intervals before publishing a named system check verdict."""

from contextlib import contextmanager
from contextvars import ContextVar
import sys

from tools.test_results import OBSERVATION_BLOCKED_STATUS


# Recovery and storage tools may inspect or retire an earlier owner's VM. The
# graphics diagnostics use only an empty baseline or a powered-off VM, and the
# retained refresh protocol independently proves the product is absent.
_WITHOUT_PRODUCT = frozenset({
    'check_test_recovery', 'check_graphical_recovery', 'check_system_recovery',
    'check_tmp_storage', 'check_tmp_storage_cleanup', 'check_storage_migration',
    'check_retained_runs_cleanup', 'check_graphical_attachment',
    'check_graphical_transport', 'check_fixture_live_refresh',
})
_active = ContextVar('standalone_product_failure_check', default=None)


class Check:
    def __init__(self, name):
        self.name = name
        self.started = set()
        self.observers = {}
        self.summary = None

    def ready(self, transport):
        from product_failure_observation import FailureObservation

        lease = transport.lease
        key = lease, transport.config['domain_id']
        self.started.add(key)
        observer = self.observers.get(key)
        if observer is not None:
            # The online snapshot rotates its SSH key and guest run marker
            # without restarting the guest or dropping the observed interval.
            if observer.transport is not transport:
                observer.attach(transport)
            return
        observer = transport.product_failures or FailureObservation(transport)
        self.observers[key] = observer
        # A snapshot resumed from memory carries the capture boot's journal.
        # Its first authenticated connection establishes the fresh boundary.
        observer.start(at_boot=not getattr(transport, 'retained_boot', False))

    def result(self):
        if self.summary is None:
            evaluations = [observer.finish() for observer in self.observers.values()]
            diagnostics = [message for value in evaluations for message in value.diagnostics]
            missing = self.started.difference(self.observers)
            if not evaluations or missing:
                diagnostics.insert(0, 'Product fault observation incomplete (missing owned interval)')
            self.summary = {
                'complete': bool(evaluations) and not missing and all(value.complete for value in evaluations),
                'unexpected': sum(len(value.unexpected) for value in evaluations),
                'guest_instances': len(self.started),
                'verified_intervals': sum(value.observed_spans for value in self.observers.values()),
                'diagnostics': list(dict.fromkeys(diagnostics))[:12],
            }
        return self.summary

    def verdict(self, status, report=None):
        summary = self.result()
        independent_status = status
        if summary['unexpected'] and status in (0, OBSERVATION_BLOCKED_STATUS):
            status = 1
        elif not summary['complete'] and status == 0:
            status = OBSERVATION_BLOCKED_STATUS
        if report is not None:
            report['product_failure_observation'] = summary
            if status == OBSERVATION_BLOCKED_STATUS:
                report['outcome'] = 'observation-blocked'
            elif status:
                report['outcome'] = 'failed'
                if status != independent_status:
                    report.setdefault('category', 'product-failure:unexpected')
        return status

    def publish(self, status):
        from tools.regression_events import write_event

        status = self.verdict(status)
        outcome = 'blocked' if status == OBSERVATION_BLOCKED_STATUS else 'failed' if status else 'passed'
        write_event(sys.stdout, 'product-failure-observation', nodeid=self.name,
                    outcome=outcome, **self.summary)
        for message in self.summary['diagnostics']:
            print(f'{self.name}: {message}', flush=True)
        return status


@contextmanager
def observe_check(name):
    """Gate the already validated standalone target after it joins its cleanup."""
    if not name.startswith('check_') or name in _WITHOUT_PRODUCT:
        yield
        return
    check = Check(name)
    token = _active.set(check)
    try:
        try:
            yield
        except SystemExit as error:
            status = check.publish(0 if error.code is None else error.code)
            if status == error.code or (status == 0 and error.code is None):
                raise
            raise SystemExit(status) from None
        except BaseException:
            check.publish(1)
            raise
        else:
            status = check.publish(0)
            if status:
                raise SystemExit(status)
    finally:
        _active.reset(token)


def transport_ready(transport):
    check = _active.get()
    if check is not None and transport.lease is not None:
        check.ready(transport)


def vm_started(lease):
    check = _active.get()
    if check is not None:
        check.started.add((lease, lease.state['domain_id']))


def verdict(status, report):
    """Apply the same gate to a check's retained terminal report, if present."""
    check = _active.get()
    return status if check is None else check.verdict(status, report)


def instance_summary(transport):
    """Return the cached observation for an individual restored guest."""
    check = _active.get()
    if check is None:
        return None
    observer = check.observers.get((transport.lease, transport.config['domain_id']))
    if observer is None:
        return {'complete': False, 'unexpected': 0, 'verified_intervals': 0,
                'diagnostics': ['Product fault observation incomplete (missing owned interval)']}
    result = observer.finish()
    return {'complete': result.complete, 'unexpected': len(result.unexpected),
            'verified_intervals': observer.observed_spans, 'diagnostics': list(result.diagnostics)}
