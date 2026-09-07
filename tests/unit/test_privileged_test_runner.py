"""The category dispatcher must not become an arbitrary root command runner."""

from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

runner = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
select = runner['selection']


@pytest.fixture
def checkout(tmp_path):
    integration = tmp_path / 'tests/integration'
    integration.mkdir(parents=True)
    (integration / 'check_future_feature.py').touch()
    (integration / 'system_runner.py').touch()
    unit = tmp_path / 'tests/unit'
    unit.mkdir()
    (unit / 'test_future_cleanup_safety.py').touch()
    (unit / 'test_graphical_lease.py').touch()
    return tmp_path


def test_future_check_needs_no_allowlist_change(checkout):
    command = select(checkout, ['integration', 'check_future_feature'])
    assert command == ['/usr/bin/python3', '-B',
                       str(checkout / 'tests/integration/check_future_feature.py')]


@pytest.mark.parametrize('name', ['../check_future_feature', '/tmp/check_other.py',
                                   'graphical_worker', '-c', 'check_x;id'])
def test_rejects_non_category_paths_and_code(checkout, name):
    with pytest.raises((ValueError, SystemExit)):
        select(checkout, ['integration', name])


def test_rejects_extra_arguments(checkout):
    with pytest.raises(ValueError):
        select(checkout, ['integration', 'check_future_feature', '--command', 'id'])


def test_rejects_symlink(checkout, tmp_path):
    (checkout / 'tests/integration/check_link.py').symlink_to(tmp_path / 'other.py')
    with pytest.raises(ValueError):
        select(checkout, ['integration', 'check_link'])


def test_system_selector_stays_a_single_argument(checkout):
    value = 'test_example[foo]; echo surprise'
    command = select(checkout, ['system', '--list', '--test', value])
    assert command[-2:] == [f'--test={value}', '--list']


@pytest.mark.parametrize('arguments', [[], ['--artifacts', 'relative'], ['--command', 'id']])
def test_system_rejects_invalid_options(checkout, arguments):
    with pytest.raises(ValueError):
        select(checkout, ['system', *arguments])


@pytest.mark.parametrize('safety_status', [0, 1])
def test_prerequisites_drop_privileges_and_gate_root_test(checkout, monkeypatch, safety_status):
    execute = Mock(side_effect=[SimpleNamespace(returncode=safety_status),
                               SimpleNamespace(returncode=0)])
    monkeypatch.setattr(runner['subprocess'], 'run', execute)
    monkeypatch.setattr(runner['os'], 'getgrouplist', lambda *args: [1000])
    caller = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture', pw_dir='/tmp')
    assert runner['run'](checkout, ['integration', 'check_future_feature'], caller) == safety_status
    assert execute.call_count == (2 if safety_status == 0 else 1)
    prerequisites = execute.call_args_list[0]
    assert prerequisites.kwargs['user'] == 1000
    assert prerequisites.kwargs['group'] == 1000
    assert any(p.endswith('test_future_cleanup_safety.py') for p in prerequisites.args[0])
    if safety_status == 0:
        assert 'user' not in execute.call_args_list[1].kwargs
