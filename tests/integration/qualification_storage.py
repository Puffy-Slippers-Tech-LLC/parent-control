"""Give standalone graphical qualifications the same bounded retention as E2E."""

from contextlib import contextmanager
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import test_retention
allocate = test_retention.allocate


@contextmanager
def session():
    if test_retention.token() is not None:
        yield
        return
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if uid <= 0 or os.geteuid() != 0:
        raise ValueError('retention: authenticated qualification caller required')
    from tools.test_storage import privileged_state
    store = test_retention.Store(privileged_state(uid))
    guard = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['retention_guard']
    with store.session(guard=lambda: guard(ROOT),
                       preserve_completed=test_retention.legacy_system_evidence):
        yield


@contextmanager
def recovery_session():
    """Retain recovery diagnostics without rotating unfinished VM evidence.

    This journal owns diagnostic files only. The caller's existing VM lease
    still controls recovery, while the storage owner excludes concurrent writers.
    """
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if uid <= 0 or os.geteuid() != 0:
        raise ValueError('retention: authenticated recovery caller required')
    from tools.test_storage import privileged_state
    store = test_retention.Store(privileged_state(uid).with_name(f'recovery-diagnostics-{uid}'))
    with store.session(recover=lambda state: True):
        yield
