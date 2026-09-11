"""Forward guest pytest counts/failures without exporting raw guest output."""

import json
import sys

PREFIX = 'ONPC-TEST-EVENT '


class Progress:
    def __init__(self, phase, executions):
        self.phase = phase
        self.expected = {item.case_id for item in executions}
        self.pending = b''

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
                if kind not in ('finished', 'failure') or nodeid not in self.expected:
                    continue
                result = dict(kind=kind, nodeid=self.phase + '::' + nodeid)
                if kind == 'failure':
                    result['detail'] = ('Installed test failed; traceback is flushed in '
                                        'guest results/regression-failures.jsonl and collected '
                                        'in this attempt’s private guest-results directory.')
                print('\n' + PREFIX + json.dumps(result), file=sys.stdout, flush=True)
            except (ValueError, TypeError, AttributeError):
                continue
        # An unrelated malformed diagnostic cannot accumulate unbounded memory.
        if len(self.pending) > 1024 * 1024:
            self.pending = b''
