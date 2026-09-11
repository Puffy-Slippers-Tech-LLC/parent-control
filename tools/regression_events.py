"""Pytest public hooks emit immediate, line-delimited regression evidence."""

import json
import os
import sys
from pathlib import Path

PREFIX = 'ONPC-TEST-EVENT '


def emit(kind, **fields):
    print('\n' + PREFIX + json.dumps(dict(kind=kind, **fields), ensure_ascii=True),
          file=sys.__stdout__, flush=True)


def pytest_collection_finish(session):
    if os.environ.get('ONPC_REGRESSION_EVENTS') == '1':
        emit('collection', total=len(session.items), collection_only=session.config.option.collectonly)


def pytest_runtest_logreport(report):
    if os.environ.get('ONPC_REGRESSION_EVENTS') != '1':
        return
    if report.failed or report.skipped or getattr(report, 'wasxfail', None):
        detail = str(report.longrepr) if report.longrepr else 'Unexpected pass of an expected failure'
        private = os.environ.get('ONPC_REGRESSION_PRIVATE')
        if private:
            path = Path(private) / 'regression-failures.jsonl'
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
