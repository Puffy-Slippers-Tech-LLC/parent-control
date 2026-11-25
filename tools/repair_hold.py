"""Release and join the test session that owns a repair's live VM."""

import json
from pathlib import Path
import time

FLAG = '--repair-hold'
VARIABLE = 'ONPC_TEST_REPAIR_HOLD'
EVENT = 'VM repair hold: '
RECORD = 'repair-hold.json'
RELEASE = 'repair-release'


def read(repair_run):
    try:
        record = json.loads((repair_run / RECORD).read_text())
    except FileNotFoundError:
        return None
    if (not isinstance(record, dict) or not isinstance(record.get('session'), str)
            or not isinstance(record.get('failure'), dict)):
        raise ValueError('invalid VM repair hold record')
    return record


def release(root, hold, *, join=False):
    from detached_launcher import busy, lock, private_directory
    from test_storage import directory

    session = Path(hold['session'])
    base = directory('sessions', root=root)
    if (session.parent != base and not (session.parent.parent == base
            and session.parent.name.startswith('vm-'))):
        raise ValueError('repair hold belongs to another test session')
    if len(session.name) != 32 or any(c not in '0123456789abcdef' for c in session.name):
        raise ValueError('invalid repair hold session')
    if not session.exists():
        return  # A completed session may have been retired.
    private_directory(session)
    with lock(session / 'owner') as owner:
        if busy(owner):
            (session / RELEASE).touch(mode=0o600)
        if join:
            while busy(owner):
                time.sleep(.1)
