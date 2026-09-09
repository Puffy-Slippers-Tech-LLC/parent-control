"""Exercise real evidence redaction while replacing account and OS reads."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import system_guest as guest

def collect_local(monkeypatch, tmp_path, payload):
    """Exercise real collection while substituting all OS reads."""
    monkeypatch.setattr(guest, 'PAYLOAD', payload)
    monkeypatch.setattr(guest, 'Path', lambda value: (
        tmp_path / 'absent-product-logs' if value == '/var/log/oh-no-parent-control'
        else Path(value)))
    monkeypatch.setattr(guest, 'Commands', lambda: Mock(run=Mock(return_value=b'')))
    import pwd
    monkeypatch.setattr(pwd, 'getpwall', lambda: [SimpleNamespace(
        pw_uid=1001, pw_name='private-user', pw_gecos='Private <Test> & User',
        pw_dir='/home/private-user')])
    guest.collect({'run': 'a' * 32, 'package_sha256': 'b' * 64,
                   'baseline_sha256': 'c' * 64, 'selected_inputs_sha256': 'd' * 64}, 'failed')
