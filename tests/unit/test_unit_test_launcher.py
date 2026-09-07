"""Selection and execution boundaries for the persistently approved unit launcher."""

from pathlib import Path
import os
import runpy
import shutil
import subprocess
from unittest.mock import Mock

import pytest


LAUNCHER = Path(__file__).resolve().parents[2] / 'tools/run-unit-tests'
runner = runpy.run_path(str(LAUNCHER.with_name('test_launcher.py')))


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / 'checkout'
    unit = root / 'tests/unit'
    unit.mkdir(parents=True)
    (unit / 'test_z_cleanup_safety.py').write_text('def test_z(): pass\n')
    (unit / 'test_a_cleanup_safety.py').write_text('def test_a(): pass\n')
    (unit / 'test_graphical_lease.py').write_text('def test_lease(): pass\n')
    (unit / 'helper.py').touch()
    (root / 'tools').mkdir()
    shutil.copy2(LAUNCHER, root / 'tools/run-unit-tests')
    shutil.copy2(LAUNCHER.with_name('test_launcher.py'), root / 'tools/test_launcher.py')
    return root


def test_globs_expand_sorted_with_explicit_files_and_duplicates(checkout):
    assert runner['selection'](checkout, [
        'tests/unit/test_*cleanup_safety.py', 'tests/unit/test_graphical_lease.py',
        './tests/unit/test_a_cleanup_safety.py',
    ]) == [
        'tests/unit/test_a_cleanup_safety.py', 'tests/unit/test_z_cleanup_safety.py',
        'tests/unit/test_graphical_lease.py',
    ]


@pytest.mark.parametrize('pattern', ['test_?_*safety.py', 'test_[az]_cleanup_safety.py'])
def test_other_filename_globs(checkout, pattern):
    assert len(runner['selection'](checkout, ['tests/unit/' + pattern])) == 2


def test_nested_glob_and_node_suffix_stays_literal(checkout):
    nested = checkout / 'tests/unit/nested'
    nested.mkdir()
    (nested / 'test_case.py').touch()
    node = '::test_case[a*b?[$(echo nope); text]]'
    assert runner['selection'](checkout, ['tests/unit/**/test_case.py' + node]) == [
        'tests/unit/nested/test_case.py' + node,
    ]


@pytest.mark.parametrize('selector', [
    '', '.', '/tmp/test_external.py', 'tests/component/test_case.py',
    'tests/unit/../component/test_case.py', 'tests/unit/missing.py',
    'tests/unit/test_no_match*.py', 'tests/unit/helper.py',
    'tests/unit::test_case', 'tests/unit/test_graphical_lease.py::',
    'tests/unit/test_graphical_lease.py\n',
])
def test_invalid_selector_rejected_even_with_valid_selection(checkout, selector):
    with pytest.raises(ValueError):
        runner['selection'](checkout, ['tests/unit/test_graphical_lease.py', selector])


@pytest.mark.parametrize('selector', [
    'tests/unit', 'tests/unit/test_*.py', 'tests/unit/test_link.py',
])
def test_rejects_external_symlink_in_file_glob_or_directory(checkout, selector):
    outside = checkout.parent / 'test_external.py'
    outside.touch()
    (checkout / 'tests/unit/test_link.py').symlink_to(outside)
    with pytest.raises(ValueError):
        runner['selection'](checkout, [selector])


@pytest.mark.parametrize('selector', ['tests/unit', 'tests/unit/linked/test_case.py'])
def test_rejects_symlink_directory(checkout, selector):
    outside = checkout.parent / 'external'
    outside.mkdir()
    (outside / 'test_case.py').touch()
    (checkout / 'tests/unit/linked').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        runner['selection'](checkout, [selector])


def test_rejects_symlink_unit_root(checkout):
    unit = checkout / 'tests/unit'
    moved = checkout / 'tests/moved'
    unit.rename(moved)
    unit.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError):
        runner['selection'](checkout, ['tests/unit/test_graphical_lease.py'])


def test_options_can_be_interspersed_with_paths():
    selectors, options = runner['arguments']([
        '-q', 'tests/unit/test_one.py', '-vv', '-k', 'alpha or beta',
        'tests/unit/test_two.py', '-m', 'unit', '--maxfail=2', '--tb', 'short',
        '--collect-only', '--disable-warnings', '--durations', '0', '-x', '-s',
    ])
    assert selectors == ['tests/unit/test_one.py', 'tests/unit/test_two.py']
    assert options == [
        '-q', '-v', '-v', '-x', '-s', '--collect-only', '--disable-warnings',
        '-k=alpha or beta', '-m=unit', '--maxfail=2', '--durations=0', '--tb=short',
    ]


def test_defaults_to_whole_unit_directory():
    assert runner['arguments']([]) == (['tests/unit'], [])


@pytest.mark.parametrize('arguments', [
    ['-c', '/tmp/config.ini'], ['-p', 'external_plugin'], ['--pyargs', 'package'],
    ['--rootdir=/tmp'], ['--override-ini', 'testpaths=/tmp'],
    ['--junitxml=/tmp/output.xml'], ['@/tmp/arguments'],
    ['--maxfail=-1'], ['--durations', 'invalid'], ['--tb', 'invalid'],
    ['--col'], ['-k'],
])
def test_rejects_unsupported_or_invalid_options(checkout, arguments):
    with pytest.raises(ValueError):
        selectors, _ = runner['arguments'](arguments)
        runner['selection'](checkout, selectors)


def test_main_validates_all_selections_before_exec_and_redacts_values(checkout, monkeypatch, capsys):
    main = runner['main']
    monkeypatch.setitem(main.__globals__, '__file__', str(checkout / 'tools/run-unit-tests'))
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    execute = Mock()
    monkeypatch.setattr(os, 'execve', execute)
    for arguments in ([
        'tests/unit/test_graphical_lease.py', 'tests/unit/test_private_sentinel*.py',
    ], ['--tb=private_sentinel']):
        assert main(arguments) == 2
        assert 'private_sentinel' not in capsys.readouterr().err
    execute.assert_not_called()


def test_refuses_root_execution(monkeypatch, capsys):
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    execute = Mock()
    monkeypatch.setattr(os, 'execve', execute)
    assert runner['main'](['tests/unit']) == 2
    assert 'unprivileged user' in capsys.readouterr().err
    execute.assert_not_called()


@pytest.mark.parametrize('body,options,expected', [
    ('def test_pass(): pass\n', [], 0),
    ('def test_fail(): assert False\n', [], 1),
    ('def test_pass(): pass\n', ['-k', 'no_such_test'], 5),
    ('def test_pass(): pass\n', ['--collect-only'], 0),
])
def test_real_launcher_from_other_cwd_preserves_pytest_status(
        checkout, monkeypatch, body, options, expected):
    # These fixture tests never start or signal other processes. subprocess owns
    # the one launcher process, which execs pytest in place.
    (checkout / 'tests/unit/test_status.py').write_text(body)
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    monkeypatch.setenv('PYTEST_ADDOPTS', '--rootdir=/missing-private-sentinel')
    monkeypatch.setenv('PYTEST_PLUGINS', 'missing_private_sentinel')
    result = subprocess.run(
        [str(checkout / 'tools/run-unit-tests'), 'tests/unit/test_stat*.py', '-q', *options],
        cwd=checkout.parent, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == expected, result.stdout + result.stderr
    assert 'starting pytest with 1 validated selection(s)' in result.stderr
    assert 'private_sentinel' not in result.stdout + result.stderr
    assert not list((checkout / 'tests/unit').rglob('*.pyc'))
