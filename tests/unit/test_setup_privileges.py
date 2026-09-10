"""Fixed setup operations, sanitized execution and no generic root dispatch."""
import os
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT
helper = runpy.run_path(str(ROOT / 'tools/onpc-setup'))


@pytest.mark.parametrize('operation,relative,options', [
    ('codex-rules', 'tools/install_codex_rules.py', ['--system']),
    ('test-tools', 'tools/install_test_runner.py', []),
    ('graphical-policy', 'tools/install_graphical_test_policy.py', []),
    ('prepare-host', 'tests/integration/prepare_host.py', []),
])
def test_only_fixed_modules_and_arguments_are_selected(operation, relative, options):
    selected = helper['command'](ROOT, [operation])
    assert selected == ['/usr/bin/python3', '-B' if operation == 'prepare-host' else '-IB',
                        str(ROOT / relative), *options]


def test_host_dependencies_use_only_the_fixed_package_module():
    assert helper['command'](ROOT, ['dependencies']) == [
        '/bin/bash', str(ROOT / 'tools/setup_dependencies.sh')]
    assert helper['command'](ROOT, ['ppa-build-tools']) == [
        '/bin/bash', str(ROOT / 'tools/setup_dependencies.sh'), '--ppa-build-tools']


@pytest.mark.parametrize('args', [[], ['shell'], ['python3'], ['codex-rules', '/tmp/rules'],
                                  ['test-tools', '--command', 'arbitrary'], ['prepare-host', '--reset'],
                                  ['dependencies', '/tmp/install.sh'], ['ppa-build-tools', '--command', 'id'], ['checkout']])
def test_arbitrary_operations_and_trailing_arguments_are_refused(args):
    with pytest.raises(ValueError):
        helper['command'](ROOT, args)


def test_missing_or_symlinked_module_is_refused(tmp_path):
    (tmp_path / 'tools').mkdir()
    with pytest.raises(ValueError, match='missing'):
        helper['command'](tmp_path, ['codex-rules'])
    (tmp_path / 'tools/install_codex_rules.py').symlink_to(ROOT / 'tools/install_codex_rules.py')
    with pytest.raises(ValueError, match='unsafe'):
        helper['command'](tmp_path, ['codex-rules'])


def test_root_execution_uses_pinned_checkout_and_sanitized_environment(monkeypatch):
    namespace = helper['main'].__globals__
    monkeypatch.setitem(namespace, 'CHECKOUT', str(ROOT))
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setenv('PKEXEC_UID', '1000')
    monkeypatch.setenv('PYTHONPATH', '/tmp/untrusted')
    monkeypatch.setattr(helper['sys'], 'argv', ['onpc-setup', 'codex-rules'])
    run = Mock(return_value=SimpleNamespace(returncode=7))
    monkeypatch.setattr(helper['subprocess'], 'run', run)
    assert helper['main']() == 7
    assert run.call_args.kwargs['cwd'] == ROOT
    assert 'PYTHONPATH' not in run.call_args.kwargs['env']
    assert run.call_args.kwargs['env']['DEBIAN_FRONTEND'] == 'noninteractive'
    assert run.call_args.args[0][-1] == '--system'


@pytest.mark.parametrize('euid,caller', [(1000, '1000'), (0, '0'), (0, 'invalid')])
def test_unprivileged_or_unattributed_invocation_never_runs_module(monkeypatch, euid, caller):
    monkeypatch.setitem(helper['main'].__globals__, 'CHECKOUT', str(ROOT))
    monkeypatch.setattr(os, 'geteuid', lambda: euid)
    monkeypatch.setenv('PKEXEC_UID', caller)
    run = Mock()
    monkeypatch.setattr(helper['subprocess'], 'run', run)
    assert helper['main']() == 2
    run.assert_not_called()
