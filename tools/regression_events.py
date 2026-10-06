"""Pytest public hooks emit immediate, line-delimited regression evidence."""

import json
import os
import re
import stat
import sys
from pathlib import Path

import pytest

PREFIX = 'ONPC-TEST-EVENT '


def completed_cases(value):
    # Keep resume validation self-contained: this plugin is also frozen into
    # the guest payload as system_progress, without the host checkpoint store.
    if value.startswith('@'):
        path = Path(value[1:])
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('invalid resume snapshot path')
        parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in path.parts[1:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent)
                parent = child
            source = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        finally:
            os.close(parent)
        with os.fdopen(source) as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                    or info.st_size > 16 * 1024 * 1024):
                raise ValueError('unsafe resume snapshot')
            cases = json.load(stream)
    else:
        cases = json.loads(value)
    if (not isinstance(cases, list) or len(cases) > 100000
            or any(not isinstance(case, str) or not case or len(case) > 65536
                   or any(ord(c) < 32 for c in case) for case in cases)
            or len(set(cases)) != len(cases)):
        raise ValueError('invalid resume case inventory')
    return set(cases)


def write_event(stream, kind, **fields):
    # Keep both delimiters in the record write. print() writes its trailing
    # newline separately, allowing background diagnostics to join the JSON.
    record = '\n' + PREFIX + json.dumps(dict(kind=kind, **fields), ensure_ascii=True) + '\n'
    stream.write(record)
    stream.flush()


def emit(kind, **fields):
    write_event(sys.__stdout__, kind, **fields)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items):
    value = os.environ.get('ONPC_TEST_COMPLETED_CASES')
    if value is None:
        return
    passed = completed_cases(value)
    omitted = [item for item in items if item.nodeid in passed]
    items[:] = [item for item in items if item.nodeid not in passed]
    session.onpc_resumed_nodeids = tuple(item.nodeid for item in omitted)
    session.onpc_resume_empty = bool(omitted and not items)
    if omitted:
        config.hook.pytest_deselected(items=omitted)


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == 5 and session.exitstatus == 5 and getattr(session, 'onpc_resume_empty', False):
        session.exitstatus = 0


def pytest_collection_finish(session):
    if os.environ.get('ONPC_REGRESSION_EVENTS') == '1':
        if not session.items:
            # Pytest calls this hook in finally, before a pending selector
            # UsageError reaches its terminal reporter. The runner rejects the
            # empty inventory immediately, so retain bounded, value-free sites
            # first. Do not change that rejection or expose parameter values.
            error = sys.exc_info()[1]
            messages = error.args if type(error).__name__ == 'UsageError' else ()
            sites = []
            for message in messages:
                if not isinstance(message, str):
                    continue
                match = re.match(
                    r'not found: (tests/(?:unit|ui)/test_[A-Za-z0-9_]+\.py'
                    r'(?:::[A-Za-z_][A-Za-z0-9_]*)+)(?:\[|\n|$)', message)
                if match and match[1] not in sites and len(sites) < 16:
                    sites.append(match[1])
            emit('collection_diagnostic',
                 error_kind=('selector-error' if messages else
                             'other-collection-error' if error is not None else
                             'no-pending-error'),
                 selector_error_count=len(messages), missing_test_sites=sites)
        inventory = ({'nodeids': [item.nodeid for item in session.items]}
                     if os.environ.get('ONPC_REGRESSION_INVENTORY') == '1' else {})
        emit('collection', total=len(session.items), collection_only=session.config.option.collectonly,
             **({'resume_empty': True} if getattr(session, 'onpc_resume_empty', False) else {}),
             **({'resumed_nodeids': list(session.onpc_resumed_nodeids)}
                if getattr(session, 'onpc_resumed_nodeids', ()) else {}),
             **inventory)


def pytest_runtest_logreport(report):
    if os.environ.get('ONPC_REGRESSION_EVENTS') != '1':
        return
    if report.failed or report.skipped or getattr(report, 'wasxfail', None):
        detail = str(report.longrepr) if report.longrepr else 'Unexpected pass of an expected failure'
        private = os.environ.get('ONPC_REGRESSION_PRIVATE')
        if private:
            path = Path(private) / 'regression-failures.jsonl'
            path.parent.mkdir(mode=0o700, exist_ok=True)
            with path.open('a', encoding='utf-8') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(json.dumps(dict(nodeid=report.nodeid, when=report.when,
                                             detail=detail)) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            detail = 'Installed test failed; detailed traceback: ' + str(path)
        emit('failure', nodeid=report.nodeid, when=report.when, detail=detail)
    if report.when == 'teardown':
        emit('finished', nodeid=report.nodeid)


def pytest_collectreport(report):
    if os.environ.get('ONPC_REGRESSION_EVENTS') == '1' and report.failed:
        emit('failure', nodeid=report.nodeid, when='collection', detail=str(report.longrepr))
