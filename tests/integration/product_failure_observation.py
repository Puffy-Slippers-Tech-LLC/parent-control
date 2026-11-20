"""Observe one case's current product through its already owned VM transport."""

from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess

from owned_commands import CommandError, cancellation_cleanup
from tests.support import product_failure_journal as journal
from tools.vm_source_snapshot import read_bytes
from watch_activity import observed


READER = Path(journal.__file__)
RUN_READER = "import sys; exec(compile(sys.stdin.buffer.read(), '<product-fault-reader>', 'exec'))"


class FailureObservation:
    def __init__(self, transport):
        self.transport = None
        self._open = False
        self._start = None
        self._awaiting_boot = False
        self._departing_span = None
        self._finished = False
        self._allowances = []
        self._results = []
        self._reason = ''
        self.attach(transport)

    def attach(self, transport):
        """Rebind the case between owned spans, or rotate credentials within one."""
        if self._finished or transport.product_failures not in (None, self):
            raise ValueError('product fault observation already bound')
        if self.transport is not None and self.transport is not transport:
            if ((self._open or self._awaiting_boot)
                    and any(self.transport.config[key] != transport.config[key]
                            for key in ('domain_uuid', 'domain_id'))):
                raise ValueError('product fault interval changed guest instance')
            self.transport.product_failures = None
        self.transport = transport
        transport.product_failures = self

    @observed('Reading the test guest’s product fault journal')
    def _call(self, *args):
        from vm_transport import transfer_diagnostic

        commands = self.transport.commands
        status = commands.last_returncode
        try:
            return json.loads(self.transport.call(
                ['/usr/bin/python3', '-I', '-c', RUN_READER, *args], input=read_bytes(READER),
                timeout=20, diagnostic_stdout=transfer_diagnostic,
            ))
        finally:
            commands.last_returncode = status

    def _boundary(self, mode):
        for _ in range(2):
            try:
                boundary = journal.Boundary(**self._call(mode))
                token_valid = (boundary.token == journal.BOOT_ORIGIN if mode == 'boot-origin'
                               else re.fullmatch(r'[0-9a-f]{32}', boundary.token))
                if (re.fullmatch(r'[0-9a-f]{32}', boundary.boot_id)
                        and type(boundary.monotonic_usec) is int and boundary.monotonic_usec > 0
                        and isinstance(boundary.cursor, str) and boundary.cursor
                        and token_valid):
                    return boundary
            except (CommandError, OSError, subprocess.SubprocessError, TypeError, ValueError):
                pass
        return None

    def boundary(self):
        """Fence an exact case action in the guest's occurrence order."""
        if not self._open:
            raise ValueError('no active product fault interval')
        marker = self._boundary('boundary')
        if marker is None:
            self._reason = self._reason or 'action boundary unavailable'
        return marker

    def start(self, *, at_boot=False):
        if self._finished:
            raise ValueError('product fault observation already finished')
        if self._open:
            return
        if self._awaiting_boot:
            self._reason = self._reason or 'new boot observation unavailable'
            self._awaiting_boot = False
            self._departing_span = None
        self._open = True
        self._start = self._boundary('boot-origin' if at_boot else 'boundary')
        if self._start is None:
            self._reason = self._reason or 'opening journal boundary unavailable'
            # Keep any faults observable after the first viable fence.
            if at_boot:
                self._start = self._boundary('boundary')

    def add_allowance(self, component, category, start, end):
        if start is None or end is None:
            self._reason = self._reason or 'action boundary unavailable'
        elif not self._open or self._start is None or start.boot_id != end.boot_id or (
                start.boot_id != self._start.boot_id):
            self._reason = self._reason or 'fault allowance crossed an observation boundary'
        else:
            self._allowances.append(journal.Allowance(
                component, category, start.monotonic_usec, end.monotonic_usec,
            ))

    @contextmanager
    def allow(self, component, category):
        start = self.boundary()
        try:
            yield
        finally:
            with cancellation_cleanup():
                self.add_allowance(component, category, start, self.boundary())

    def checkpoint(self):
        """Seal and read this boot before any action can lose its evidence."""
        span = self._close()
        if span is not None:
            self._results.append(self._read(*span))

    def _close(self):
        if not self._open:
            return
        start, self._start = self._start, None
        allowances, self._allowances = self._allowances, []
        self._open = False
        if start is None:
            return
        end = self._boundary('boundary')
        if end is None:
            self._reason = self._reason or 'closing journal boundary unavailable'
            return
        return start, end, allowances

    def _read(self, start, end, allowances, *, departed=False):
        start_json, end_json = (json.dumps(asdict(marker)) for marker in (start, end))
        mode = 'read-departed' if departed else 'read'
        partial_events = []
        for _ in range(2):
            try:
                observation = self._call(mode, start_json, end_json)
            except (CommandError, OSError, subprocess.SubprocessError, TypeError, ValueError):
                observation = None
            result = journal.evaluate_failures(observation, start=start, end=end,
                                               allowances=allowances, departed=departed)
            partial_events.extend(result.unexpected)
            if result.complete:
                break
        return journal.FailureEvaluation(
            result.complete, tuple(dict.fromkeys(partial_events)), result.reason, result.unattributed,
        )

    def before_reboot(self):
        if self._open:
            self._awaiting_boot = True
            span = self._close()
            if span is not None:
                self._results.append(self._read(*span))
                self._departing_span = span

    def after_reboot(self):
        if self._awaiting_boot:
            if self._departing_span is not None:
                before = self._results[-1]
                departed = self._read(*self._departing_span, departed=True)
                events = tuple(sorted(dict.fromkeys(before.unexpected + departed.unexpected),
                                      key=lambda event: event.monotonic_usec))
                self._results[-1] = journal.FailureEvaluation(
                    departed.complete, events, departed.reason,
                    max(before.unattributed, departed.unattributed),
                )
                self._departing_span = None
            self._awaiting_boot = False
            self.start(at_boot=True)

    @property
    def observed_spans(self):
        return sum(result.complete for result in self._results)

    def finish(self):
        if not self._finished:
            with cancellation_cleanup():
                self.checkpoint()
            self._finished = True
            self.transport.product_failures = None
        reason = self._reason or next((part.reason for part in self._results if not part.complete), '')
        if self._awaiting_boot:
            reason = reason or 'new boot observation unavailable'
        if not self._results:
            reason = reason or 'no verified journal interval'
        return journal.FailureEvaluation(
            not reason, tuple(event for part in self._results for event in part.unexpected),
            reason, sum(part.unattributed for part in self._results),
        )
