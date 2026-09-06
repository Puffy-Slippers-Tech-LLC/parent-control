"""Focused smoke evidence/sequence regressions; no processes or VM use."""

import json
from pathlib import Path
import struct
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
import check_graphical_smoke as smoke
sys.path.pop(0)


def png(directory, name='smoke-1.png', width=1024, height=768, suffix=b'fixture'):
    results = directory / 'testresults'
    results.mkdir(exist_ok=True)
    path = results / name
    path.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + struct.pack('!II', width, height) + suffix)
    return path


@pytest.mark.parametrize('name', ['../private', '/tmp/image.png', 'vars.json', 'smoke-a.png'])
def test_collector_refuses_unexpected_paths(tmp_path, name):
    with pytest.raises(RuntimeError, match='invalid-screenshot-name'):
        smoke.screenshot(tmp_path, name)


def test_collector_refuses_symlink(tmp_path):
    path = png(tmp_path)
    (path.parent / 'smoke-2.png').symlink_to(path)
    with pytest.raises(RuntimeError, match='screenshot-path'):
        smoke.screenshot(tmp_path, 'smoke-2.png')


@pytest.mark.parametrize('size', [(0, 768), (1024, 0), (8192, 768)])
def test_collector_refuses_unexpected_dimensions(tmp_path, size):
    png(tmp_path, width=size[0], height=size[1])
    with pytest.raises(RuntimeError, match='screen-size'):
        smoke.screenshot(tmp_path, 'smoke-1.png')


def test_evidence_contains_only_dimensions_and_digest(tmp_path):
    png(tmp_path, suffix=b'synthetic private canary')
    result = smoke.screenshot(tmp_path, 'smoke-1.png')
    assert set(result) == {'width', 'height', 'sha256'}
    assert result['width'] == 1024 and result['height'] == 768
    assert 'canary' not in json.dumps(result)


def test_unchanged_menu_refuses_acknowledgement(tmp_path):
    png(tmp_path)
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key')
    controller.steps = [{'stage': 'ready'}, {'stage': 'gdm', **smoke.screenshot(tmp_path, 'smoke-1.png')}]
    (tmp_path / 'menu.request.json').write_text(json.dumps({'stage': 'menu', 'screenshot': 'smoke-1.png'}))
    with pytest.raises(RuntimeError, match='unchanged-screen'):
        controller.step()
    assert not (tmp_path / 'menu.reply.json').exists()


def test_success_requires_all_stages_even_with_zero_backend_status(tmp_path):
    worker, server = Mock(), Mock(path=tmp_path / 'callback.sock')
    worker.poll.return_value = 0
    with patch.object(smoke, 'Adapter'), patch.object(smoke, 'CallbackServer', return_value=server), \
            patch.object(smoke, 'Worker', return_value=worker):
        with pytest.raises(RuntimeError, match='missing-stages'):
            smoke.run_backend(tmp_path, Mock(state={'run': 'a' * 32}), Mock(), 'host-key', smoke.runner.RunLedger())
    worker.close.assert_called_once()
    server.close.assert_called_once()


def test_fixed_observation_is_valid_python_and_contains_no_guest_mutation():
    compile(smoke.OBSERVATION, '<fixed-observation>', 'exec')
    assert "'is-active'" in smoke.OBSERVATION and "'show-session'" in smoke.OBSERVATION
    assert 'capture_output=True' in smoke.OBSERVATION


@pytest.mark.parametrize('result', [
    {'result': 'fail'}, {'result': 'softfail'}, {'result': 'ok', 'dents': 1},
    {'result': 'ok', 'details': [{'result': 'fail'}]},
])
def test_module_failure_cannot_be_hidden_by_successful_stage_files(tmp_path, result):
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps(result))
    with pytest.raises(RuntimeError, match='module-not-passed'):
        smoke.module_result(tmp_path)


def test_schedule_preflight_has_no_backend_or_lifecycle_configuration(tmp_path):
    commands = Mock(last_returncode=1)
    commands.run.return_value = (b'scheduling smoke tests/smoke.pm\n'
        b'Early exit has been requested with _EXIT_AFTER_SCHEDULE. Only evaluating test schedule.\n')
    smoke.schedule_preflight(tmp_path, commands)
    args = commands.run.call_args.args[0]
    assert '_EXIT_AFTER_SCHEDULE=1' in args
    assert '--exit-status-from-test-results' not in args
    assert not any(x.startswith(('BACKEND=', 'GENERAL_HW_')) for x in args)


@pytest.mark.parametrize('status,output', [(1, b'Compilation failed'), (0, b''),
    (1, b'scheduling smoke tests/smoke.pm\nCompilation failed')])
def test_schedule_failure_is_not_accepted_as_the_pinned_early_exit(tmp_path, status, output):
    commands = Mock(last_returncode=status)
    commands.run.return_value = output
    with pytest.raises(RuntimeError, match='schedule-preflight-failed'):
        smoke.schedule_preflight(tmp_path, commands)
