"""Give standalone graphical qualifications the same bounded retention as E2E."""

from contextlib import contextmanager
import hashlib
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
    checkout = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    store = test_retention.Store(Path('/var/tmp') /
                                f'onpc-test-retention-root-{uid}-{checkout}')
    guard = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['retention_guard']
    with store.session(guard=lambda: guard(ROOT),
                       preserve_completed=test_retention.legacy_system_evidence):
        yield
