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
    from product_failure_journal import Allowance, action_time, decode_action_time

    case = _active_case
    start_boot, start = decode_action_time(case.capture(action_time, 'action opening'))
    try:
        yield
    finally:
        end_boot, end = decode_action_time(case.capture(action_time, 'action closing'))
        if start is None or end is None:
            case.reason = case.reason or 'guest fault window unavailable'
        elif start_boot != end_boot or start > end:
            case.reason = case.reason or 'guest fault window changed'
        elif start < end:
            case.allowances.append(Allowance(component, category, start, end))


class CaseObservation:
    def __init__(self):
        self.reason = ''
        self.allowances = []
        self.failed = False
        self.start = self.boundary('opening journal')

    def boundary(self, role):
        from product_failure_journal import capture_boundary

        return self.capture(capture_boundary, role)

    def capture(self, capture, role):
        from product_failure_journal import EvidenceUnavailable, evidence_reason

        try:
            return capture()
        except EvidenceUnavailable as error:
            reason = evidence_reason(str(error), 'guest journal evidence unavailable')
        except (OSError, ValueError):
            reason = 'guest journal evidence unavailable'
        self.reason = self.reason or f'{role} boundary unavailable ({reason})'
        return None

    def finish(self):
        from product_failure_journal import (
            EvidenceUnavailable, FailureEvaluation, evaluate_failures, evidence_reason, read_failures,
        )

        if self.start is None:
            return FailureEvaluation(False, (), self.reason, 0)
        end = self.boundary('closing journal')
        if end is None:
            return FailureEvaluation(False, (), self.reason, 0)
        try:
            observed = read_failures(self.start, end)
        except EvidenceUnavailable as error:
            reason = evidence_reason(str(error), 'guest journal evidence unavailable')
            return FailureEvaluation(False, (), self.reason or reason, 0)
        except (OSError, ValueError, KeyError):
            return FailureEvaluation(False, (), self.reason or 'guest journal evidence unavailable', 0)
        result = evaluate_failures(observed, start=self.start, end=end, allowances=self.allowances)
        return replace(result, complete=False, reason=self.reason) if self.reason else result


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
        result = replace(result, complete=False,
                         reason=result.reason or 'guest fault observation could not be saved')
    disposition = result.disposition(case_failed=case.failed)
    emit('product-observation', nodeid=item.nodeid, outcome=disposition,
         complete=result.complete, unexpected=len(result.unexpected))
    if result.unexpected and not case.failed:
        report.outcome = 'failed'
        report.longrepr = '\n'.join(result.diagnostics)
    elif disposition == 'blocked':
        item.session.shouldstop = 'required product fault observation unavailable'
    return report
