"""Forward guest pytest counts/failures without exporting raw guest output."""

import json
import sys
from contextlib import contextmanager

from tools.e2e_progress import Progress as WatchProgress
from tools.regression_events import PREFIX, write_event
from system_case_ids import identity_for_event


class SystemWatchProgress(WatchProgress):
    """Reuse the E2E display protocol with exact system execution identities."""

    def __init__(self, executions):
        cases = []
        for item in executions:
            nodeid = item.phase + '::' + item.case_id
            identity = identity_for_event(nodeid)
            cases.append(dict(case_id=nodeid, coverage_id=identity.numeric_id,
                              title=identity.title))
        super().__init__(cases, suite='system')

    def prepare_execution(self, item):
        self.prepare(item.phase + '::' + item.case_id)
        self.step('Preparing system check: ' + self.cases[self.value['current'] - 1]['title']
                  + '. System phase: ' + item.phase + '.')
        with self.lock:
            self.preparing = True

    def started(self, nodeid):
        self.case(nodeid)
        identity = identity_for_event(nodeid)
        self.step(identity.title + '. System phase: ' + nodeid.partition('::')[0] + '.')

    def finished(self):
        self.step('Collecting results and preparing the next system check or VM cleanup.')


@contextmanager
def watching(executions, lease):
    """Publish through the shared heartbeat and lease-owned display collector."""
    if not executions:
        yield None
        return
    import system_runner as system
    from e2e_watch import ProgressPublication
    progress = SystemWatchProgress(executions)
    previous = system.watch_progress
    previous_lease = getattr(lease, 'watch_progress', None)
    progress.prepare_execution(executions[0])
    publication = ProgressPublication(progress)
    system.watch_progress = lease.watch_progress = progress
    try:
        yield progress
    finally:
        system.watch_progress = previous
        lease.watch_progress = previous_lease
        publication.close()


class Progress:
    def __init__(self, phase, executions, *, watch=None):
        self.phase = phase
        self.expected = {item.case_id for item in executions}
        self.pending = b''
        self.operation = None
        self.watch = watch
        self.active = False

    def close(self):
        if self.operation is not None:
            self.operation.__exit__(None, None, None)
            self.operation = None
        if self.active:
            self.active = False
            if self.watch is not None:
                self.watch.finished()

    def __call__(self, data):
        self.pending += data
        while b'\n' in self.pending:
            raw, self.pending = self.pending.split(b'\n', 1)
            if not raw.startswith(PREFIX.encode()):
                continue
            try:
                event = json.loads(raw[len(PREFIX):])
                kind = event.get('kind')
                nodeid = event.get('nodeid', '').split('::', 1)[-1]
                if kind not in ('started', 'finished', 'failure') or nodeid not in self.expected:
                    continue
                result = dict(kind=kind, nodeid=self.phase + '::' + nodeid)
                identity = identity_for_event(result['nodeid'])
                if identity is not None:
                    result.update(case_id=identity.numeric_id, title=identity.title)
                    if kind == 'started':
                        from watch_activity import operation
                        self.close()
                        if self.watch is not None:
                            self.watch.started(result['nodeid'])
                        self.active = True
                        self.operation = operation(f'System case [{identity.numeric_id}]: {identity.title}')
                        self.operation.__enter__()
                    elif kind == 'finished':
                        self.close()
                if kind == 'failure':
                    result['detail'] = ('Installed test failed; traceback is flushed in '
                                        'guest results/regression-failures.jsonl and collected '
                                        'in this attempt’s private guest-results directory.')
                write_event(sys.stdout, **result)
            except (ValueError, TypeError, AttributeError):
                continue
        # An unrelated malformed diagnostic cannot accumulate unbounded memory.
        if len(self.pending) > 1024 * 1024:
            self.pending = b''
