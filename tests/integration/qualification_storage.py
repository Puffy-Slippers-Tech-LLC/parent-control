"""Give standalone graphical qualifications the same bounded retention as E2E."""

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import test_retention
from owned_commands import observe_commands

_producer = ContextVar('qualification_command_producer', default=None)


def allocate(factory, *args, **kwargs):
    """Register before writes and attach the command log to the first allocation."""
    path = test_retention.allocate(factory, *args, **kwargs)
    producer = _producer.get()
    if producer is not None:
        producer.start(Path(path))
    return path


class _Producer:
    def __init__(self):
        self.command_count = 0
        self.command_bytes = 0
        self.command_path = None

    def start(self, directory):
        if self.command_path is None:
            self.command_path = directory / 'producer-commands.jsonl'

    def command(self, record):
        if self.command_path is None:
            raise ValueError('qualification: command before allocation')
        self.command_count += 1
        data = (json.dumps(dict(record, sequence=self.command_count),
                           allow_nan=False, sort_keys=True) + '\n').encode()
        self.command_bytes += len(data)
        if self.command_count > 8192 or len(data) > 65536 or self.command_bytes > 16 * 1024 * 1024:
            raise ValueError('qualification: command inventory exceeds bound')
        descriptor = os.open(self.command_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT
                             | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(descriptor, 'ab') as stream:
            test_retention.private(os.fstat(stream.fileno()), regular=True)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


@contextmanager
def _record_commands(check):
    if check is None:
        yield
        return
    producer = _Producer()
    token = _producer.set(producer)
    previous_umask = os.umask(0o077)
    try:
        with observe_commands(producer.command):
            yield producer
    finally:
        _producer.reset(token)
        os.umask(previous_umask)


@contextmanager
def session(*, check=None, target=None, inputs=None, lease=None, live=False, run=None,
            require_owner=False):
    if test_retention.token() is not None:
        journal, selected_run = json.loads(os.environ[test_retention.VARIABLE])
        store = test_retention.Store(journal)
        # Named qualifications may run beneath the dispatcher's held owner.
        # Only controllers requiring their own producer need an in-process session.
        if check is not None:
            test_retention.owner_descriptor()
        if ((require_owner or run is not None)
                and store.producer_binding()[3] != selected_run
                or run is not None and run != selected_run):
            raise ValueError('retention: qualification producer run changed')
        with _record_commands(check):
            yield
        return
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if uid <= 0 or os.geteuid() != 0:
        raise ValueError('retention: authenticated qualification caller required')
    from tools.test_storage import privileged_state
    store = test_retention.Store(privileged_state(uid))
    guard = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['retention_guard']
    with store.session(run=run, guard=lambda: guard(ROOT),
                       preserve_completed=test_retention.legacy_system_evidence):
        with _record_commands(check):
            yield


@contextmanager
def recovery_session(*, check=None, target=None, inputs=None, lease=None, live=False):
    """Retain recovery diagnostics without rotating unfinished VM work.

    This journal owns diagnostic files only. The caller's existing VM lease
    still controls recovery, while the storage owner excludes concurrent writers.
    """
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if uid <= 0 or os.geteuid() != 0:
        raise ValueError('retention: authenticated recovery caller required')
    from tools.test_storage import privileged_state
    path = privileged_state(uid)
    store = test_retention.Store(path.with_name(path.name.replace('retention-', 'recovery-diagnostics-', 1)))
    active = os.environ.get(test_retention.VARIABLE)
    if active is not None and json.loads(active)[0] == str(store.path):
        if store.producer_binding()[3] != json.loads(active)[1]:
            raise ValueError('retention: recovery producer run changed')
        with _record_commands(check):
            yield
        return
    if check is not None:
        # Reconcile only this diagnostic owner. Never touch the separate
        # unfinished VM execution journal or its recovery marker.
        store.reconcile(lambda: None)
    with store.session(recover=lambda state: True):
        with _record_commands(check):
            yield
