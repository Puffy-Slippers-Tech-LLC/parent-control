"""Fixed helper entry and checked support loading in private descriptor trees.

Root identities alone are doubled by the existing private_store fixture. Inodes,
modes, links, replacement and source bytes are real. No installed app, service,
host lock, alarm or mount is changed; no subprocess is launched here.
"""
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

from tests.unit.test_kiosk_pin_storage import private_store


NAMES = ('kiosk_preparation_input', 'kiosk_view_receipt', 'kiosk_preparation_service')


@pytest.fixture
def entry(private_store, monkeypatch):
    scene, helper = private_store, private_store.helper
    support = scene.store / 'support'
    support.mkdir(mode=0o755)
    for name in NAMES:
        target = support / (name + '.py')
        target.write_text("value = 'checked source'\n")
        target.chmod(0o644)
        # A stale cache is neither trusted nor imported by the explicit loader.
        cache = support / '__pycache__'
        cache.mkdir(mode=0o755, exist_ok=True)
        (cache / (name + '.cpython-313.pyc')).write_bytes(b'foreign cache')
    (support / 'kiosk_preparation_service.py').write_text(
        'import kiosk_preparation_input\n'
        'import kiosk_view_receipt\n'
        'value = kiosk_preparation_input.value + kiosk_view_receipt.value\n')
    monkeypatch.setattr(helper, 'NATIVE_SUPPORT', support)
    monkeypatch.setattr(helper.os, 'geteuid', lambda: 0)
    monkeypatch.setitem(sys.modules, helper.__name__, helper)
    for name in ('kiosk_confinement', *NAMES):
        monkeypatch.setitem(sys.modules, name, SimpleNamespace(value='foreign imported module'))

    def checked(path):
        fd = scene.actual_open(path)
        os.close(fd)
        return Path(path)

    monkeypatch.setattr(helper, 'trusted', checked)
    return SimpleNamespace(helper=helper, support=support, scene=scene, checked=checked)


def test_checked_loader_uses_exact_source_without_search_or_bytecode(entry):
    helper, support = entry.helper, entry.support
    before_path = list(sys.path)
    before_cache = {p.name: p.read_bytes() for p in (support / '__pycache__').iterdir()}
    service = helper.native_preparation_service(time.monotonic_ns() + 5_000_000_000)
    assert service.value == 'checked sourcechecked source'
    assert service.__file__ == str(support / 'kiosk_preparation_service.py')
    assert sys.modules['kiosk_confinement'] is helper
    assert sys.path == before_path
    assert {p.name: p.read_bytes() for p in (support / '__pycache__').iterdir()} == before_cache


@pytest.mark.parametrize('mutation', ['write', 'owner', 'hardlink', 'symlink', 'ancestor'])
def test_loader_checks_opened_support_trust_after_named_check(entry, monkeypatch, mutation):
    helper, path = entry.helper, entry.support / (NAMES[0] + '.py')

    def replace_after_check(name):
        result = entry.checked(name)
        if mutation == 'write':
            path.chmod(0o666)
        elif mutation == 'owner':
            entry.scene.overrides[str(path)] = dict(st_uid=12345)
        elif mutation == 'hardlink':
            os.link(path, path.with_name('extra'))
        elif mutation == 'symlink':
            saved = path.with_name('original')
            path.rename(saved)
            path.symlink_to(saved.name)
        else:
            entry.support.chmod(0o777)
        return result

    monkeypatch.setattr(helper, 'trusted', replace_after_check)
    with pytest.raises(ValueError, match='runtime-untrusted-object'):
        helper.native_preparation_service(time.monotonic_ns() + 5_000_000_000)
    assert sys.modules[NAMES[0]].value == 'foreign imported module'


def test_loader_rejects_same_byte_inode_replacement_during_read(entry, monkeypatch):
    helper, path = entry.helper, entry.support / (NAMES[0] + '.py')
    original = helper.os.pread
    changed = False

    def replace(fd, size, offset):
        nonlocal changed
        data = original(fd, size, offset)
        if not changed:
            changed = True
            replacement = path.with_name('replacement')
            replacement.write_bytes(path.read_bytes())
            replacement.chmod(0o644)
            replacement.replace(path)
        return data

    monkeypatch.setattr(helper.os, 'pread', replace)
    before = len(list(Path('/proc/self/fd').iterdir()))
    with pytest.raises(ValueError, match='source-changed'):
        helper.native_preparation_service(time.monotonic_ns() + 5_000_000_000)
    assert len(list(Path('/proc/self/fd').iterdir())) == before
    assert sys.modules[NAMES[0]].value == 'foreign imported module'


@pytest.mark.parametrize('deadline', [0, 1, 120_000_000_000])
def test_loader_does_not_start_or_renew_expired_or_excess_budget(entry, deadline):
    absolute = deadline if deadline < 2 else time.monotonic_ns() + deadline
    with pytest.raises(TimeoutError, match='preparation-deadline'):
        entry.helper.native_preparation_service(absolute)


@pytest.mark.parametrize('role', ['manager', 'gate'])
def test_main_routes_exact_native_child_arguments(entry, monkeypatch, role):
    helper, calls = entry.helper, []
    deadline = str(time.monotonic_ns() + 5_000_000_000)
    monkeypatch.setattr(sys, 'argv', ['helper', '--native-channel', role, '3', deadline])
    monkeypatch.setattr(helper, 'prepare_native_channel', lambda *args: calls.append(args))
    monkeypatch.setattr(helper, 'prepare', lambda *args: pytest.fail('legacy preparation called'))
    assert helper.main() == 0
    assert calls == [(role, '3', deadline)]


@pytest.mark.parametrize('arguments', [[], ['--native-channel'],
    ['--native-channel', 'manager', '3'], ['--native-channel', 'manager', '3', '4', 'extra']])
def test_main_refuses_incomplete_native_arguments(entry, monkeypatch, arguments):
    helper = entry.helper
    monkeypatch.setattr(sys, 'argv', ['helper', *arguments])
    monkeypatch.setattr(helper, 'prepare_native_channel', lambda *args: pytest.fail('native called'))
    # A bare legacy argument remains validated by its existing role guard.
    monkeypatch.setattr(helper, 'prepare', lambda *args: (_ for _ in ()).throw(ValueError('invalid-caller')))
    assert helper.main() == 1


@pytest.mark.parametrize('role,channel,deadline', [('other', '3', '1'), ('gate', '4', '1'),
    ('gate', '3', '01'), ('gate', '3', '-1'), ('gate', '3', str(2**64))])
def test_fixed_entry_rejects_unbound_arguments_before_descriptor_use(entry, role, channel, deadline):
    with pytest.raises(ValueError, match='invalid-arguments'):
        entry.helper.prepare_native_channel(role, channel, deadline)
