"""Guest pytest verdicts from the shared installed-product failure journal."""

from contextlib import contextmanager
from dataclasses import asdict, replace
import hashlib
import json
import os

import pytest


_active_case = None


@contextmanager
def allow_product_fault(component, category):
    """Allow one known category while the case owns a deliberate fault."""
    if _active_case is None:
        yield
        return
    from product_failure_journal import Allowance

    case = _active_case
    start = case.boundary()
    try:
        yield
    finally:
        end = case.boundary()
        if start is not None and end is not None:
            if start.boot_id == end.boot_id:
                case.allowances.append(Allowance(component, category, start.monotonic_usec,
                                                 end.monotonic_usec))
            else:
                case.incomplete = True


class CaseObservation:
    def __init__(self):
        self.incomplete = False
        self.allowances = []
        self.failed = False
        self.start = self.boundary()

    def boundary(self):
        from product_failure_journal import capture_boundary

        for _ in range(2):
            try:
                return capture_boundary()
            except (OSError, ValueError):
                pass
        self.incomplete = True
        return None

    def finish(self):
        from product_failure_journal import FailureEvaluation, evaluate_failures, read_failures

        end = self.boundary()
        result = FailureEvaluation(False, (), 'guest journal boundary unavailable', 0)
        if self.start is not None and end is not None:
            unexpected = []
            for _ in range(2):
                try:
                    observed = read_failures(self.start, end)
                    result = evaluate_failures(observed, start=self.start, end=end,
                                               allowances=self.allowances)
                except (OSError, ValueError, KeyError):
                    continue
                unexpected.extend(result.unexpected)
                if result.complete:
                    break
            result = FailureEvaluation(result.complete, tuple(dict.fromkeys(unexpected)),
                                       result.reason, result.unattributed)
        if self.incomplete and result.complete:
            return FailureEvaluation(False, result.unexpected, 'guest fault window unavailable',
                                     result.unattributed)
        return result


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    global _active_case
    if os.environ.get('ONPC_PRODUCT_FAILURE_OBSERVATION') == '1':
        import system_guest
        system_guest.guard()
        _active_case = CaseObservation()
    try:
        return (yield)
    finally:
        _active_case = None


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    report = yield
    case = _active_case
    if case is None:
        return report
    case.failed |= not report.passed or bool(getattr(report, 'wasxfail', None))
    if report.when != 'teardown':
        return report

    from system_progress import emit
    import system_guest

    result = case.finish()
    key = hashlib.sha256(item.nodeid.encode()).hexdigest()
    output = system_guest.PAYLOAD / 'results' / (
        'faults-' + os.environ['ONPC_SYSTEM_EXECUTION_PHASE'] + '-' + key + '.json')
    try:
        output.parent.mkdir(mode=0o700, exist_ok=True)
        with output.open('w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump({'nodeid': item.nodeid, **asdict(result),
                       'diagnostics': result.diagnostics}, stream)
    except OSError:
        result = replace(result, complete=False, reason='guest fault observation could not be saved')
    disposition = result.disposition(case_failed=case.failed)
    emit('product-observation', nodeid=item.nodeid, outcome=disposition,
         complete=result.complete, unexpected=len(result.unexpected))
    if result.unexpected and not case.failed:
        report.outcome = 'failed'
        report.longrepr = '\n'.join(result.diagnostics)
    elif disposition == 'blocked':
        item.session.shouldstop = 'required product fault observation unavailable'
    return report
