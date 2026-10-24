"""Guarded transport for C04j3's engineering-only installed transition probe."""
import json
from pathlib import Path

from private_artifacts import require
from watch_activity import operation


def qualify(journey, guard):
    guard()
    journey.context.verified.recheck()
    root = Path(__file__).resolve().parents[2]
    control = (root / 'tests/e2e/session_control.py').read_text()
    probe = (root / 'tests/integration/active_grant_disable_guest.py').read_text()
    source = ('import types\ncontrol = types.ModuleType("control")\n'
              f'exec({control!r}, control.__dict__)\nprobe_source = {probe!r}\n' + probe).encode()
    with operation('Engineering-only native disable and rollback observation in the unlocked child session'):
        raw = journey.transport.call(['/usr/bin/python3', '-I', '-'], input=source, timeout=240)
    require(type(raw) is bytes and 0 < len(raw) < 512 * 1024, 'disable-engineering:response-bound')
    value = json.loads(raw)
    require(type(value) is dict and value.get('engineering_only') is True
            and value.get('original_state_restored') is True
            and value.get('observer_joined') is True
            and value.get('checks') == ['disable', 'rollback-live-grant',
                'rollback-unrestricted', 'post-termination-unrestricted', 'preparation-readback-refusal'],
            'disable-engineering:incomplete')
    guard()
    journey.context.verified.recheck()
    return value
