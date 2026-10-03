"""Host UI timings in the launcher's retained category stream, without UI data.

One synchronous pytest worker owns a recorder. Nested durations are inclusive;
self_seconds excludes instrumented children. No threads, files or UI reads.
"""

from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import sys
import time

from tools.regression_events import emit, write_event


QUERY_METHODS = {
    'org.a11y.atspi.Accessible': (
        'GetAttributes', 'GetRole', 'GetRoleName', 'GetState', 'GetChildren',
        'GetApplication', 'GetRelationSet', 'GetInterfaces'),
    'org.a11y.atspi.Cache': ('GetItems',),
    'org.freedesktop.DBus': ('GetNameOwner', 'GetConnectionUnixProcessID'),
}


class Timings:
    def __init__(self, sink=emit, clock=time.monotonic, process_clock=time.process_time):
        self.sink, self.clock = sink, clock
        self.process_clock = process_clock
        self.nodeid, self.phase = '', ''
        self.started = self.last = clock()
        self.metrics = {}
        self.stack = []
        self.stream = None
        self.spans = []
        self.sequence = 0
        self.output_seconds = 0.0
        self.output_started = 0.0
        self.cpu_started = process_clock()
        self.queries = {'sync': {}, 'batch': {}, 'batch_sizes': {}}

    def _emit(self, kind, **fields):
        started = self.clock()
        try:
            self.sink(kind, **fields)
        finally:
            self.output_seconds += self.clock() - started

    @classmethod
    def retained(cls):
        # Called from the outer setup hook before pytest redirects fd 1 for
        # a case. Keep checkpoints on the launcher's pipe during fd capture.
        # This duplicate is private, non-inheritable and closed at session end.
        stream = os.fdopen(os.dup(sys.__stdout__.fileno()), 'w', encoding='utf-8')
        recorder = cls(lambda kind, **fields: write_event(stream, kind, **fields))
        recorder.stream = stream
        return recorder

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    def begin(self, nodeid, phase):
        self.nodeid, self.phase = nodeid, phase
        self.started = self.last = self.clock()
        self.cpu_started = self.process_clock()
        self.output_started = self.output_seconds
        self.queries = {'sync': {}, 'batch': {}, 'batch_sizes': {}}
        self.metrics = {}
        self.publish('begin')

    def publish(self, status):
        now = self.clock()
        self._emit('ui-timing', nodeid=self.nodeid, phase=self.phase,
                  status=status, monotonic=now, started=self.started,
                  elapsed_seconds=now - self.started,
                  cpu_seconds=self.process_clock() - self.cpu_started,
                  output_seconds=self.output_seconds - self.output_started,
                  queries={group: {name: dict(value) for name, value in metrics.items()}
                           for group, metrics in self.queries.items()},
                  operations={name: dict(value) for name, value in self.metrics.items()},
                  active=[{'operation': name, 'elapsed_seconds': now - start}
                          for name, start, _children in self.stack])
        self.last = now

    @contextmanager
    def measure(self, name):
        frame = [name, self.clock(), 0.0]
        self.stack.append(frame)
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            elapsed = self.clock() - frame[1]
            self.stack.pop()
            if self.stack:
                self.stack[-1][2] += elapsed
            metric = self.metrics.setdefault(name, dict(
                count=0, errors=0, seconds=0.0, self_seconds=0.0, max_seconds=0.0))
            metric['count'] += 1
            metric['errors'] += int(failed)
            metric['seconds'] += elapsed
            metric['self_seconds'] += elapsed - frame[2]
            metric['max_seconds'] = max(metric['max_seconds'], elapsed)
            if self.clock() - self.last >= 5:
                self.publish('progress')

    def wrap(self, function, name):
        @wraps(function)
        def measured(*args, **kwargs):
            with self.measure(name):
                return function(*args, **kwargs)
        return measured

    @staticmethod
    def query_kind(interface, method, args):
        # Finite protocol names only. Never retain bus/path, arbitrary property
        # names, input values, UI results or exception text.
        if type(interface) is not str or type(method) is not str:
            return 'other'
        if interface == 'org.freedesktop.DBus.Properties' and method == 'Get':
            if (isinstance(args, (list, tuple)) and len(args) == 2
                    and args[0] == 'org.a11y.atspi.Accessible'
                    and args[1] in ('AccessibleId', 'Name', 'ChildCount')):
                return 'property.' + args[1]
            return 'property.other'
        if method in QUERY_METHODS.get(interface, ()):
            return method
        return 'other'

    def wrap_rpc(self, function):
        @wraps(function)
        def measured(api, bus, path, interface, method, signature='', args=()):
            kind = self.query_kind(interface, method, args)
            with self.measure('atspi.rpc'):
                started, failed = self.clock(), False
                try:
                    return function(api, bus, path, interface, method, signature, args)
                except BaseException:
                    failed = True
                    raise
                finally:
                    elapsed = self.clock() - started
                    metric = self.queries['sync'].setdefault(kind, dict(
                        count=0, errors=0, seconds=0.0, max_seconds=0.0))
                    metric['count'] += 1
                    metric['errors'] += int(failed)
                    metric['seconds'] += elapsed
                    metric['max_seconds'] = max(metric['max_seconds'], elapsed)
        return measured

    def wrap_batch(self, function):
        @wraps(function)
        def measured(api, queries):
            # The transport validates its own inputs. Do not consume iterators
            # or inspect an oversized/malformed request before delegating it.
            kinds = ([self.query_kind(query[2], query[3], query[5]) for query in queries]
                     if isinstance(queries, (list, tuple)) and len(queries) <= 64
                     and all(isinstance(query, tuple) and len(query) == 6
                             for query in queries) else [])
            with self.measure('atspi.batch'):
                started, failed = self.clock(), False
                try:
                    results = function(api, queries)
                    for kind, result in zip(kinds, results):
                        metric = self.queries['batch'].setdefault(kind, dict(count=0, errors=0))
                        metric['count'] += 1
                        metric['errors'] += int(isinstance(result, Exception))
                    return results
                except BaseException:
                    failed = True
                    raise
                finally:
                    # Wall time belongs to the batch, not to every parallel
                    # query. Occupancy exposes serial tiny-frontier pipelines.
                    metric = self.queries['batch_sizes'].setdefault(str(len(kinds)), dict(
                        count=0, aborted=0, seconds=0.0))
                    metric['count'] += 1
                    metric['aborted'] += int(failed)
                    metric['seconds'] += self.clock() - started
        return measured

    def wrap_iterator(self, function, name):
        @wraps(function)
        def measured(*args, **kwargs):
            # Time iteration, not construction of a lazy traversal. yield from
            # forwards close/throw to the original generator exactly once.
            with self.measure(name):
                yield from function(*args, **kwargs)
        return measured

    @staticmethod
    def source(function):
        # Code location only: never repr(callable), closure cells or arguments.
        code = getattr(function, '__code__', None)
        if code is None:
            return 'external'
        try:
            path = Path(code.co_filename).relative_to(Path(__file__).resolve().parents[2])
        except ValueError:
            return 'external'
        return f'{path}:{code.co_firstlineno}'

    @contextmanager
    def span(self, name, **details):
        """Retain entry before calling work, with correlated nested completion.

        RPCs remain aggregates: one record per RPC would perturb the reader.
        A missing end localizes an unfinished high-level operation or wait stage;
        it does not by itself prove a deadlock.
        """
        self.sequence += 1
        identity = self.sequence
        parent = self.spans[-1] if self.spans else None
        before = {key: dict(value) for key, value in self.metrics.items()}
        started = previous = self.clock()
        last_stage = None
        stages = {}

        def event(status, **fields):
            self._emit('ui-trace', nodeid=self.nodeid, phase=self.phase,
                      span=identity, parent=parent, operation=name,
                      status=status, monotonic=self.clock(), **fields)

        def checkpoint(stage, attempt):
            nonlocal previous, last_stage
            now = self.clock()
            if last_stage is not None:
                stages[last_stage] = stages.get(last_stage, 0.0) + now - previous
            event('stage', stage=stage, attempt=attempt)
            previous, last_stage = now, stage

        event('begin', **details)
        self.spans.append(identity)
        failed = False
        try:
            yield checkpoint
        except BaseException:
            failed = True
            raise
        finally:
            now = self.clock()
            if last_stage is not None:
                stages[last_stage] = stages.get(last_stage, 0.0) + now - previous
            self.spans.pop()
            operations = {
                key: {field: value[field] - before.get(key, {}).get(field, 0)
                      for field in ('count', 'errors', 'seconds', 'self_seconds')}
                for key, value in self.metrics.items()
                if value['count'] != before.get(key, {}).get('count', 0)}
            event('end', failed=failed, elapsed_seconds=now - started,
                  stages=stages, operations=operations)

    def wait_trace(self, predicate):
        return self.span('reader.wait-attempts', predicate=self.source(predicate))

    def wrap_span(self, function, name):
        @wraps(function)
        def measured(*args, **kwargs):
            with self.span(name):
                return function(*args, **kwargs)
        return measured

    def wrap_reader_run(self, function):
        @wraps(function)
        def measured(reader, operation, *args, **kwargs):
            from tests.e2e.accessible_ui import OPERATIONS
            name = operation if operation in OPERATIONS else 'unregistered'
            with self.span('reader.run', registered_operation=name):
                previous = reader.timing

                def retain(value):
                    self._emit('ui-reader-timing', nodeid=self.nodeid, phase=self.phase,
                              span=self.spans[-1], **value)
                    if previous is not None:
                        previous(value)

                reader.timing = retain
                try:
                    return function(reader, operation, *args, **kwargs)
                finally:
                    reader.timing = previous
        return measured

    @contextmanager
    def lifecycle(self, manager, name):
        # Delegate the original exception/suppression protocol exactly once.
        with self.measure(name + '.setup'):
            value = manager.__enter__()
        try:
            yield value
        except BaseException:
            import sys
            with self.measure(name + '.teardown'):
                suppressed = manager.__exit__(*sys.exc_info())
            if not suppressed:
                raise
        else:
            with self.measure(name + '.teardown'):
                manager.__exit__(None, None, None)
