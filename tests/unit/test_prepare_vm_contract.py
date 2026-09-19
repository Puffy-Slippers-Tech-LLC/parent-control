"""Only host baseline preparation is a public setup route."""
import os
import stat
import subprocess
from tests.support.paths import ROOT

def test_guest_launcher_and_make_target_are_removed():
    assert not (ROOT / 'tests/integration/prepare-vm').exists()
    makefile = (ROOT / 'Makefile').read_text()
    assert 'prepare-vm:' not in makefile
    assert 'prepare-baseline:' not in makefile
    result = subprocess.run(['bash', str(ROOT / 'setup.sh'), '--prepare-vm'],
                            capture_output=True, text=True)
    assert result.returncode == 2
    result = subprocess.run(['bash', str(ROOT / 'setup.sh'), '--prepare-baseline'],
                            capture_output=True, text=True)
    assert result.returncode == 2

def test_guest_preparation_accepts_no_interactive_password():
    source = (ROOT / 'tests/integration/prepare_vm.py').read_text()
    assert 'getpass' not in source
    assert 'runner.run(["chpasswd"], input_text=password_input)' in source
    assert 'os.environ' not in source

def test_prepare_baseline_is_an_executable_project_tool():
    path = ROOT / 'tools/prepare-baseline'
    assert path.is_file()
    assert path.stat().st_mode & stat.S_IXUSR
    assert os.access(path, os.X_OK)
