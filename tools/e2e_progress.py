"""Safe spectator progress, separate from scenario evidence and acceptance."""

import json
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time


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
        self.started_ns = time.monotonic_ns()
        self.preparing = False
        self.next_value = None
        self.operation_key = None
        self.operation_started_ns = None
        self.suite_value = None
        self.publish_progress = None
        self.snapshot_value = None

    def suite_preparation(self, label):
        """Coarse controller milestones take precedence over detailed VM logs."""
        with self.lock:
            operation = 'Preparing e2e suite: ' + label
            if self.suite_value is None or self.suite_value['operation'] != operation:
                case = self.cases[0]
                self.suite_value = dict(current=1, total=len(self.cases),
                    case_id=str(case['coverage_id']), title=case['title'], step='',
                    operation=operation, started_ns=self.started_ns,
                    case_started_ns=self.started_ns, operation_started_ns=time.monotonic_ns())
        # Publish before entering a blocking snapshot operation; the heartbeat
        # thread may not get scheduled between this milestone and the next one.
        if self.publish_progress is not None:
            self.publish_progress()

    @contextmanager
    def snapshot_operation(self, label):
        """Reserve the footer, with its own timer, until the operation returns."""
        with self.lock:
            previous = self.snapshot_value
            self.snapshot_value = dict(operation=label,
                                       operation_started_ns=time.monotonic_ns())
        try:
            if self.publish_progress is not None:
                self.publish_progress()
            yield
        finally:
            with self.lock:
                self.snapshot_value = previous
            if self.publish_progress is not None:
                self.publish_progress()

    def suite_prepared(self):
        with self.lock:
            self.suite_value = None

    def prepare(self, case_id):
        self.case(case_id)
        self.preparing = True

    def prepare_next(self):
        with self.lock:
            index = self.value['current']
            if index < len(self.cases):
                case = self.cases[index]
                self.next_value = dict(current=index + 1, total=len(self.cases),
                    case_id=str(case['coverage_id']), title=case['title'], step='',
                    operation='Preparing VM: Waiting for VM cleanup',
                    started_ns=self.started_ns, case_started_ns=time.monotonic_ns())

    def preparation_output(self, line):
        with self.lock:
            target = self.next_value if self.next_value is not None else self.value
            if target and (self.next_value is not None or self.preparing):
                target['operation'] = 'Preparing VM: ' + line
        if self.publish_progress is not None:
            self.publish_progress()

    def case(self, case_id):
        index = next(i for i, case in enumerate(self.cases) if case['case_id'] == case_id)
        case = self.cases[index]
        with self.lock:
            if self.value.get('current') == index + 1:
                return
            started = (self.next_value or {}).get('case_started_ns', time.monotonic_ns())
            self.value = dict(current=index + 1, total=len(self.cases),
                              case_id=str(case['coverage_id']), title=case['title'],
                              step='', operation='Preparing VM: Waiting for VM preparation',
                              started_ns=self.started_ns, case_started_ns=started)
            self.next_value = None
            self.preparing = True
            self.worker = None
        print(f"e2e:case=[{index + 1}/{len(self.cases)}] [{case['coverage_id']}]: {case['title']}",
              file=sys.stderr, flush=True)
        if self.publish_progress is not None:
            self.publish_progress()

    def step(self, description):
        with self.lock:
            self.preparing = False
            self.value.update(step=description, operation='')
            self._time_operation(self.value)
            # Never carry the previous step's worker action into a new step.
            self.after = self.worker_sequence()
        print('e2e:step=' + description, file=sys.stderr, flush=True)
        if self.publish_progress is not None:
            self.publish_progress()

    def follow_worker(self, directory, labels):
        with self.lock:
            self.worker = Path(directory) / 'watch-operation.json'
            self.labels = labels
            self.after = 0

    def operation(self, label):
        """Trusted controller prose, never raw output or user-provided values."""
        with self.lock:
            self.value['operation'] = label
            self._time_operation(self.value)
            self.after = self.worker_sequence()
        print('e2e:operation=' + label, file=sys.stderr, flush=True)
        if self.publish_progress is not None:
            self.publish_progress()

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

    def snapshot(self, *, display=False):
        with self.lock:
            if self.suite_value is not None:
                result = dict(self.suite_value)
            elif display and self.next_value is not None:
                result = dict(self.next_value)
                result['operation_started_ns'] = result['case_started_ns']
            else:
                result = dict(self.value)
                value = self.worker_value()
                if value.get('sequence', 0) > self.after:
                    result['operation'] = value['operation']
                self._time_operation(result)
                if result:
                    result['operation_started_ns'] = self.operation_started_ns
            if result and self.snapshot_value is not None:
                result.update(self.snapshot_value)
            return result

    def _time_operation(self, value):
        if not value:
            return
        preparing = value['operation'].startswith('Preparing VM:')
        key = (value['case_started_ns'],
               'Preparing VM:' if preparing else (value['step'], value['operation']))
        if key != self.operation_key:
            self.operation_key = key
            self.operation_started_ns = (value['case_started_ns'] if preparing
                                         else time.monotonic_ns())
