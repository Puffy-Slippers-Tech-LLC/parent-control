"""Safe spectator progress, separate from scenario evidence and acceptance."""

import json
import os
from pathlib import Path
import re
import stat
import sys
import threading


def operation_labels(root):
    """Only literal messages in the maintained worker may leave private storage."""
    return {label for path in Path(root).glob('*.pm')
            for label in re.findall(r"onpc_progress::operation\('([^'\n]+)'\)", path.read_text())}


class Progress:
    def __init__(self, cases):
        self.cases = cases
        self.lock = threading.Lock()
        self.value = {}
        self.worker = None
        self.labels = set()
        self.after = 0

    def case(self, case_id):
        index = next(i for i, case in enumerate(self.cases) if case['case_id'] == case_id)
        case = self.cases[index]
        with self.lock:
            self.value = dict(current=index + 1, total=len(self.cases),
                              case_id=str(case['coverage_id']), title=case['title'],
                              step='', operation='')
            self.worker = None
        print(f"e2e:case=[{index + 1}/{len(self.cases)}] [{case['coverage_id']}]: {case['title']}",
              file=sys.stderr, flush=True)

    def step(self, description):
        with self.lock:
            self.value.update(step=description, operation='')
            # Never carry the previous step's worker action into a new step.
            self.after = self.worker_sequence()
        print('e2e:step=' + description, file=sys.stderr, flush=True)

    def follow_worker(self, directory, labels):
        with self.lock:
            self.worker = Path(directory) / 'watch-operation.json'
            self.labels = labels
            self.after = 0

    def operation(self, label):
        """Trusted controller prose, never raw output or user-provided values."""
        with self.lock:
            self.value['operation'] = label
            self.after = self.worker_sequence()
        print('e2e:operation=' + label, file=sys.stderr, flush=True)

    def worker_value(self):
        if self.worker is None:
            return {}
        try:
            fd = os.open(self.worker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 2048:
                    return {}
                value = json.loads(stream.read(2049))
            if (type(value) is dict and set(value) == {'sequence', 'operation'}
                    and type(value['sequence']) is int and value['sequence'] > 0
                    and type(value['operation']) is str and value['operation'] in self.labels):
                return value
        except (OSError, ValueError):
            pass
        return {}

    def worker_sequence(self):
        return self.worker_value().get('sequence', 0)

    def snapshot(self):
        with self.lock:
            result = dict(self.value)
            value = self.worker_value()
            if value.get('sequence', 0) > self.after:
                result['operation'] = value['operation']
            return result
