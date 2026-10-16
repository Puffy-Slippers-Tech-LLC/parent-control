"""Forward guest pytest counts/failures without exporting raw guest output."""

import json
import sys

from tools.regression_events import PREFIX, write_event
from system_case_ids import identity_for_event


class Progress:
    def __init__(self, phase, executions):
        self.phase = phase
        self.expected = {item.case_id for item in executions}
        self.pending = b''
        self.operation = None

    def close(self):
        if self.operation is not None:
            self.operation.__exit__(None, None, None)
            self.operation = None

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
