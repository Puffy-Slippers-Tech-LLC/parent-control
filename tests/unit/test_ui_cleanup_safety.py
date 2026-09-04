"""Host-safe regression for the UI launcher's owned-process cleanup."""

import ast
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("exited, stubborn", [(False, False), (False, True), (True, False)])
def test_ui_cleanup_signals_only_recorded_launches(tmp_path, exited, stubborn):
    root = Path(__file__).resolve().parents[2]
    path = root / "tests/ui/conftest.py"
    tree = ast.parse(path.read_text())
    fixture = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == "launch_ui")
    fixture.decorator_list = []
    owned = Mock()
    owned.poll.return_value = 0 if exited else None
    if stubborn:
        owned.wait.side_effect = [subprocess.TimeoutExpired("preview", 5), 0]
    unrelated = Mock()
    popen = Mock(return_value=owned)
    namespace = {"ROOT": root, "sys": SimpleNamespace(executable="python"),
                 "subprocess": SimpleNamespace(Popen=popen, STDOUT=subprocess.STDOUT,
                                                TimeoutExpired=subprocess.TimeoutExpired)}
    exec(compile(ast.Module(body=[fixture], type_ignores=[]), str(path), "exec"), namespace)
    lifecycle = namespace["launch_ui"](SimpleNamespace(environment={}), tmp_path)
    launch = next(lifecycle)
    process, _log = launch("request_component_preview", wait_for_application=False)
    assert process is owned
    with pytest.raises(StopIteration):
        next(lifecycle)
    assert owned.terminate.call_count == (0 if exited else 1)
    assert owned.kill.call_count == (1 if stubborn else 0)
    assert unrelated.mock_calls == []
    assert popen.call_count == 1
