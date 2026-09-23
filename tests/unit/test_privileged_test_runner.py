"""The category dispatcher must not become an arbitrary root command runner."""

from pathlib import Path
import runpy
import shutil
import subprocess
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

runner = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
select = runner['selection']


@pytest.fixture
def checkout(tmp_path):
    root = Path(__file__).resolve().parents[2]
    tools = tmp_path / 'tools'
    tools.mkdir()
    for name in ('regression_process.py', 'test_activity.py'):
        shutil.copy2(root / 'tools' / name, tools / name)
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


def test_system_update_pins_both_artifact_directories(checkout):
    command = select(checkout, ['system', '--artifacts', '/tmp/onpc-current',
                               '--previous-artifacts', '/var/tmp/onpc-previous',
                               '--area', 'session'])
    assert command[3:] == ['--artifacts', '/tmp/onpc-current',
                           '--previous-artifacts', '/var/tmp/onpc-previous', '--area=session']


def test_system_dispatch_preserves_explicit_fast_policy(checkout):
    args = ['system', '--artifacts', '/tmp/onpc-current']
    strict = select(checkout, args)
    fast = select(checkout, [*args, '--skip-backing-verification'])
    assert fast == [*strict, '--skip-backing-verification']


@pytest.mark.parametrize('path', ['relative', '/etc', '/tmp/unrelated',
                                  '/tmp/onpc-previous/../other'])
def test_system_update_rejects_unconfined_prior_payload(checkout, path):
    with pytest.raises((ValueError, SystemExit)):
        select(checkout, ['system', '--artifacts', '/tmp/onpc-current',
                         '--previous-artifacts', path])


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
    assert prerequisites.args[0] == [
        '/usr/bin/python3', '-IB', str(checkout / 'tools/regression_process.py'),
        '--cleanup-prerequisites',
    ]
    if safety_status == 0:
        assert 'user' not in execute.call_args_list[1].kwargs


@pytest.mark.parametrize('safety_status', [0, 1])
def test_unattended_dispatcher_leaves_checkout_build_cleanable(checkout, safety_status):
    """Exercise interpreter startup -> checkout imports -> real package clean.

    In-process runpy tests inherit pytest's no-bytecode setting and miss the
    installed dispatcher's interpreter flags. Publishing builds also use a fresh
    source snapshot, which omits caches left in the developer's checkout.
    """
    root = Path(__file__).resolve().parents[2]
    tools = checkout / 'tools'
    for name in ('onpc-test-runner', 'regression_process.py', 'test_launcher.py', 'test_activity.py',
                 'test_retention.py'):
        shutil.copy2(root / 'tools' / name, tools / name)
    installer = runpy.run_path(str(root / 'tools/install_test_runner.py'))
    rendered = installer['render_helper'](checkout, 'onpc-test-runner', None)
    installed = checkout.parent / 'installed-test-runner'
    installed.write_text(rendered)

    # Use the rendered helper's actual shebang in a fresh process. Only process
    # execution and signal/pipe setup are replaced; selection and the real
    # fixed cleanup-coordinator command still execute unchanged.
    probe = checkout.parent / 'dispatcher-probe'
    probe.write_text(rendered.splitlines()[0] + '\n' + textwrap.dedent('''\
        from contextlib import nullcontext
        import os
        from pathlib import Path
        import pwd
        import runpy
        import sys
        from unittest.mock import patch

        load = runpy.run_path
        dispatcher = load(sys.argv[1])
        calls = []
        safety_status = int(sys.argv[2])

        def execute(self, command, **kwargs):
            calls.append(command)
            return safety_status if len(calls) == 1 else 0

        def load_with_owned_process_stub(path):
            namespace = load(path)
            if Path(path).name == 'regression_process.py':
                namespace['Control'].installed = lambda self, **kwargs: nullcontext(self)
                namespace['Control'].run = execute
            return namespace

        with patch.object(runpy, 'run_path', load_with_owned_process_stub):
            status = dispatcher['run'](
                Path(dispatcher['CHECKOUT']),
                ['--unattended', 'system', '--artifacts', '/tmp/onpc-build-regression'],
                pwd.getpwuid(os.getuid()))
        assert status == safety_status
        assert len(calls) == (1 if safety_status else 2)
        assert calls[0][2].endswith('/tools/regression_process.py')
        assert calls[0][3:] == ['--cleanup-prerequisites']
        print('dispatcher checkout imports exercised')
        '''))
    probe.chmod(0o755)
    environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
                   'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([str(probe), str(installed), str(safety_status)],
                            cwd=checkout, env=environment, capture_output=True,
                            text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'dispatcher checkout imports exercised' in result.stdout

    debian = checkout / 'debian'
    debian.mkdir()
    for name in ('rules', 'control', 'changelog'):
        shutil.copy2(root / 'debian' / name, debian / name)
    caches = list(tools.rglob('__pycache__'))
    # Model the caller's inability to unlink files in a root-owned cache without
    # requiring root or leaving privileged artifacts in the real checkout.
    for cache in caches:
        cache.chmod(0o555)
    try:
        clean = subprocess.run(['/usr/bin/make', '-f', 'debian/rules', 'clean'],
                               cwd=checkout, env=environment, capture_output=True,
                               text=True, timeout=30, check=False)
        assert clean.returncode == 0, clean.stdout + clean.stderr
        assert not caches, 'the dispatcher must not write bytecode into the checkout'
    finally:
        for cache in caches:
            if cache.exists():
                cache.chmod(0o755)
