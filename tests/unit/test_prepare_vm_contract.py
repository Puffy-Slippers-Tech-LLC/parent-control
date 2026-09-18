"""Only host baseline preparation is a public setup route."""
import subprocess
from tests.support.paths import ROOT

def test_guest_launcher_and_make_target_are_removed():
    assert not (ROOT / 'tests/integration/prepare-vm').exists()
    assert 'prepare-vm:' not in (ROOT / 'Makefile').read_text()
    result = subprocess.run(['bash', str(ROOT / 'setup.sh'), '--prepare-vm'],
                            capture_output=True, text=True)
    assert result.returncode == 2

def test_guest_preparation_accepts_no_interactive_password():
    source = (ROOT / 'tests/integration/prepare_vm.py').read_text()
    assert 'getpass' not in source
    assert 'runner.run(["chpasswd"], input_text=password_input)' in source
    assert 'os.environ' not in source

def test_make_prepare_baseline_needs_no_compiler(tmp_path):
    (tmp_path / 'Makefile').write_bytes((ROOT / 'Makefile').read_bytes())
    master = tmp_path / 'setup.sh'
    master.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    master.chmod(0o755)
    result = subprocess.run(['make', '--no-print-directory', 'prepare-baseline',
                             'CC=/nonexistent/onpc-compiler'], cwd=tmp_path,
                             capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '--prepare-baseline'
