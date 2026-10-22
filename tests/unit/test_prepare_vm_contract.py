"""Only host baseline preparation is a public setup route."""
import os
import stat
import subprocess
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from tests.support.modules import load_module
from tests.support.paths import ROOT

def test_guest_launcher_and_make_target_are_removed():
    assert not (ROOT / 'tests/integration/prepare-vm').exists()
    makefile = (ROOT / 'Makefile').read_text()
    assert 'prepare-vm:' not in makefile
    assert 'prepare-baseline:' not in makefile
    result = subprocess.run(['bash', str(ROOT / 'setup.sh'), '--prepare-baseline'],
                            capture_output=True, text=True)
    assert result.returncode == 2
    result = subprocess.run(['bash', str(ROOT / 'setup.sh'), '--prepare-vm'],
                            capture_output=True, text=True)
    assert result.returncode == 2

def test_guest_preparation_accepts_no_interactive_password():
    source = (ROOT / 'tests/integration/prepare_vm.py').read_text()
    assert 'getpass' not in source
    assert 'runner.run(["chpasswd"], input_text=password_input)' in source
    assert 'os.environ' not in source

def test_prepare_baseline_is_an_executable_project_tool():
    path = ROOT / 'tools/prepare-vm'
    assert path.is_file()
    assert path.stat().st_mode & stat.S_IXUSR
    assert os.access(path, os.X_OK)
    assert not (ROOT / 'tools/prepare-baseline').exists()


@pytest.mark.parametrize('refusal', [None, 'finished, unmarked owner required',
                                    'pending source belongs to a superseded run'])
def test_host_build_recovers_pending_evidence_before_new_session(monkeypatch, tmp_path, refusal):
    # Private doubles exercise startup ordering without journals, VM work or builds.
    monkeypatch.setattr(sys, 'path', list(sys.path))
    host = load_module('onpc_test_prepare_vm_host', ROOT / 'tools/prepare_vm_host.py')
    events = []
    # The public preparation owner holds activity across the private worker.
    active = True
    store = None
    path = tmp_path / 'retention'
    control = object()
    error = ValueError(refusal) if refusal else None

    def activity(root, *, named_vm):
        pytest.fail('private worker must not reacquire the public owner activity lock')

    class Store:
        def __init__(self, location):
            nonlocal store
            assert active and location == path
            store = self

        @contextmanager
        def session(self):
            assert active
            events.append('session')
            yield

    @contextmanager
    def installed():
        events.append('control')
        yield control

    def recover(root, owner):
        assert active and root == host.ROOT and owner is store
        events.append('recovery')
        if error is not None:
            raise error

    def build(root, package_format, owner, environment, *, label):
        assert active and root == host.ROOT and package_format == 'rpm'
        assert owner is control and environment == {} and label == 'prepare-vm'
        events.append('build')
        return 'unused', 23

    monkeypatch.setattr(host.os, 'geteuid', lambda: 1000)
    for name, module in {
        'test_activity': SimpleNamespace(activity=activity, retention_path=lambda root: path),
        'test_launcher': SimpleNamespace(environment=lambda root: {}),
        'test_retention': SimpleNamespace(Store=Store),
        'regression_process': SimpleNamespace(Control=lambda: SimpleNamespace(installed=installed)),
        'prepare_appsnapshot': SimpleNamespace(build_artifacts=build),
        'runner_evidence': SimpleNamespace(recover_pending=recover),
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    if error is not None:
        with pytest.raises(ValueError) as caught:
            host.build_worker('rpm', -1)
        assert caught.value is error
        assert events == ['recovery']
    else:
        assert host.build_worker('rpm', -1) == 23
        assert events == ['recovery', 'session', 'control', 'build']
    assert active
