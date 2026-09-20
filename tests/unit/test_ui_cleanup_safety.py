"""Host-safe regression for the UI launcher's owned-process cleanup."""

import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.support import preview


@pytest.mark.parametrize("exited, stubborn", [(False, False), (False, True), (True, False)])
def test_ui_cleanup_signals_only_recorded_launches(tmp_path, monkeypatch, exited, stubborn):
    owned = Mock()
    owned.poll.return_value = 0 if exited else None
    if stubborn:
        owned.wait.side_effect = [subprocess.TimeoutExpired("preview", 5), 0]
    unrelated = Mock()
    popen = Mock(return_value=owned)
    monkeypatch.setattr(preview.subprocess, "Popen", popen)
    with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
        process, _log = launch("request_component_preview", wait_for_application=False)
        assert process is owned
    assert owned.terminate.call_count == (0 if exited else 1)
    assert owned.kill.call_count == (1 if stubborn else 0)
    assert unrelated.mock_calls == []
    assert popen.call_count == 1
    assert popen.call_args.kwargs["stdout"].closed


def test_failed_spawn_closes_its_log(tmp_path, monkeypatch):
    popen = Mock(side_effect=OSError("spawn refused"))
    monkeypatch.setattr(preview.subprocess, "Popen", popen)
    with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
        with pytest.raises(OSError, match="spawn refused"):
            launch("parent_preview")
        assert popen.call_args.kwargs["stdout"].closed


def test_failed_discovery_still_reaps_owned_preview(tmp_path, monkeypatch):
    process = Mock(poll=Mock(return_value=None))
    monkeypatch.setattr(preview.subprocess, "Popen", Mock(return_value=process))
    session = Mock(environment={})
    identify = Mock(side_effect=RuntimeError("not visible"))
    with pytest.raises(RuntimeError, match="not visible"):
        with preview.preview_applications(session, tmp_path) as launch:
            launch("parent_preview")
            identify("parent-window")
    session.wait_for_app.assert_not_called()
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)


def test_name_based_discovery_refuses_before_launch(tmp_path, monkeypatch):
    popen = Mock()
    monkeypatch.setattr(preview.subprocess, "Popen", popen)
    session = Mock(environment={})
    with preview.preview_applications(session, tmp_path) as launch:
        with pytest.raises(ValueError, match="public automation ID"):
            launch("parent_preview", wait_for_application=True)
    popen.assert_not_called()
    session.wait_for_app.assert_not_called()


def test_readiness_owners_include_only_live_explicit_launches(tmp_path, monkeypatch):
    process = Mock(pid=123, poll=Mock(return_value=None))
    monkeypatch.setattr(preview.subprocess, "Popen", Mock(return_value=process))
    with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
        assert launch.owner_pids() == frozenset()
        owned, log_path = launch("parent_preview")
        assert owned is process and log_path == tmp_path / "parent_preview.log"
        assert launch.owner_pids() == {123}
        process.poll.return_value = 0
        assert launch.owner_pids() == frozenset()


def test_cleanup_failure_does_not_abandon_other_owned_previews(tmp_path, monkeypatch):
    first = Mock(poll=Mock(return_value=None))
    second = Mock(poll=Mock(return_value=None), terminate=Mock(side_effect=OSError("cleanup refused")))
    popen = Mock(side_effect=[first, second])
    monkeypatch.setattr(preview.subprocess, "Popen", popen)
    with pytest.raises(BaseExceptionGroup, match="cleanup failed"):
        with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
            launch("parent_preview", wait_for_application=False)
            launch("kiosk_preview", wait_for_application=False)
    first.terminate.assert_called_once()
    first.wait.assert_called_once_with(timeout=5)
    assert all(call.kwargs["stdout"].closed for call in popen.call_args_list)
