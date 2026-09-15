import os
import subprocess


from tests.support.paths import ROOT
PREPARE_PATH = ROOT / "tests/integration/prepare_vm.py"
LAUNCHER_PATH = ROOT / "tests/integration/prepare-vm"


def test_launcher_syntax_checkout_relative_path_and_secret_handling_source_contract():
    result = subprocess.run(
        ["bash", "-n", str(LAUNCHER_PATH)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
    source = PREPARE_PATH.read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert 'BASH_SOURCE[0]' in launcher
    assert 'exec /usr/bin/python3 -B "$PREPARER"' in launcher
    assert 'if (( EUID != 0 )); then' in launcher
    assert 'exec sudo -- /usr/bin/python3 -B "$PREPARER"' in launcher
    assert "prepare-vm:" in makefile
    assert source.count("getpass.getpass(") == 1
    assert 'runner.run(["chpasswd"], input_text=password_input)' in source
    assert "os.environ" not in source
    assert "PASSWORD=" not in source
    assert "password_input" not in launcher


def test_launcher_refuses_this_development_context_without_prompting():
    result = subprocess.run(
        ['/bin/bash', str(LAUNCHER_PATH)],
        cwd=ROOT.parent,
        check=False,
        input="must-not-be-read\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode != 0
    assert "guard:checkout" in result.stderr
    assert "Shared test-account password" not in result.stderr


def test_relocated_launcher_runs_its_own_preparer_without_fixed_checkout(tmp_path):
    checkout = tmp_path / 'guest checkout'
    launcher = checkout / 'tests/integration/prepare-vm'
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes(LAUNCHER_PATH.read_bytes())
    preparer = launcher.with_name('prepare_vm.py')
    preparer.write_text('print(__file__)\n')
    # The fixture preparer performs no system operations; the sudo double
    # forwards only this test's Python invocation without requesting privilege.
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    sudo = binaries / 'sudo'
    sudo.write_text('#!/bin/sh\nshift\nexec "$@"\n')
    sudo.chmod(0o755)
    result = subprocess.run(
        ['bash', str(launcher)], cwd=checkout, check=False, capture_output=True, text=True,
        env={**os.environ, 'PATH': str(binaries) + os.pathsep + os.defpath})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(preparer)


def test_make_prepare_vm_needs_neither_compiler_nor_executable_launcher(tmp_path):
    (tmp_path / "Makefile").write_bytes((ROOT / "Makefile").read_bytes())
    master = tmp_path / 'setup.sh'
    master.write_bytes((ROOT / 'setup.sh').read_bytes())
    master.chmod(0o644)
    (tmp_path / 'child').mkdir()
    (tmp_path / 'child/preview').touch(mode=0o644)
    launcher = tmp_path / "tests/integration/prepare-vm"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("printf 'preparation launcher reached\\n'\n", encoding="utf-8")
    launcher.chmod(0o644)
    result = subprocess.run(
        ["make", "--no-print-directory", "prepare-vm", "CC=/nonexistent/onpc-compiler"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "preparation launcher reached\nsetup: selected setup completed successfully\n"
    assert result.stderr == ""
