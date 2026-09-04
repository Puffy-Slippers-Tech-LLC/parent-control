import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREPARE_PATH = ROOT / "tests/integration/prepare_vm.py"
LAUNCHER_PATH = ROOT / "tests/integration/prepare-vm"


def test_launcher_syntax_fixed_path_and_secret_handling_source_contract():
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
    assert "CHECKOUT=/Data/Code/PST/parent-control" in launcher
    assert 'exec /usr/bin/python3 "$PREPARER"' in launcher
    assert 'if (( EUID != 0 )); then' in launcher
    assert 'exec sudo -- /usr/bin/python3 "$PREPARER"' in launcher
    assert "prep-vm:" in makefile
    assert source.count("getpass.getpass(") == 1
    assert 'runner.run(["chpasswd"], input_text=password_input)' in source
    assert "os.environ" not in source
    assert "PASSWORD=" not in source
    assert "password_input" not in launcher


def test_launcher_refuses_this_development_context_without_prompting():
    result = subprocess.run(
        [str(LAUNCHER_PATH)],
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
