"""Exercise the real master in a disposable checkout with harmless modules."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


from tests.support.paths import ROOT


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / 'checkout with spaces'
    for name in ('tools', 'child', 'tests/integration', 'bin'):
        (root / name).mkdir(parents=True)
    master = (ROOT / 'setup.sh').read_text().replace('/usr/local/libexec/onpc-setup', str(root / 'installed-setup'))
    (root / 'setup.sh').write_text(master)
    (root / 'setup.sh').chmod(0o755)
    (root / 'installed-setup').touch()
    (root / 'Makefile').touch()
    (root / 'child/preview').touch(mode=0o755)
    stub = '''import json, os, pathlib, sys
name = pathlib.Path(__file__).name
with open(os.environ['ONPC_SETUP_TRACE'], 'a') as stream:
    stream.write(json.dumps([name, sys.argv[1:], os.getcwd()]) + '\\n')
if name == 'install_test_runner.py' and os.environ.get('ONPC_SETUP_FAIL') != name:
    pathlib.Path('installed-setup').touch()
sys.exit(7 if os.environ.get('ONPC_SETUP_FAIL') == name else 0)
'''
    for name in ('install_test_runner.py', 'install_graphical_test_policy.py', 'install_codex_rules.py'):
        (root / 'tools' / name).write_text(stub)
    (root / 'tests/integration/prepare_host.py').write_text(stub)
    shutil.copy2(ROOT / 'tools/onpc-setup', root / 'tools/onpc-setup')
    (root / 'tools/setup_privileges.py').write_text('''import os, pathlib, runpy, sys
if os.environ.get('ONPC_SETUP_DENIED'):
    sys.exit(23)
root = pathlib.Path(__file__).resolve().parents[1]
if not (root / 'installed-setup').is_file():
    sys.exit(23)
dispatcher = runpy.run_path(str(root / 'tools/onpc-setup'))
command = dispatcher['command'](root, sys.argv[1:])
os.execv(command[0], command)
''')
    for name in ('tools/setup_dependencies.sh', 'tools/setup_checkout.sh', 'tests/integration/prepare-vm'):
        module = Path(name).name + '.py'
        (root / name).write_text(
            '#!/bin/bash\n'
            f'/usr/bin/python3 -B "$(dirname -- "${{BASH_SOURCE[0]}}")/{module}" "$@"\n')
        (root / name).with_name(module).write_text(stub)
    # Privilege dispatch is exercised, but this fixture never elevates privileges.
    pkexec = root / 'bin/pkexec'
    pkexec.write_text('#!/bin/sh\n[ "$1" = "--keep-cwd" ] || exit 9\n'
                     'printf "authentication\\n" >> "$ONPC_SETUP_AUTH"\nshift\nexec "$@"\n')
    pkexec.chmod(0o755)
    make = root / 'bin/make'
    make.write_text('#!/usr/bin/python3\n' + stub)
    make.chmod(0o755)
    return root


def run_setup(root, *args, failure='', denied=False):
    trace = root / 'trace.jsonl'
    trace.write_text('')
    result = subprocess.run(
        ['/bin/bash', str(root / 'setup.sh'), *args], cwd=root.parent,
        env={**os.environ, 'PATH': f'{root / "bin"}:{os.environ["PATH"]}',
             'ONPC_SETUP_TRACE': str(trace), 'ONPC_SETUP_FAIL': failure,
             'ONPC_SETUP_AUTH': str(root / 'authentication.log'),
             'ONPC_SETUP_DENIED': '1' if denied else ''},
        capture_output=True, text=True, timeout=10,
    )
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    assert all(event[2] == str(root) for event in events)
    return result, [(name, args) for name, args, _cwd in events]


RULES = [('install_codex_rules.py', ['--system']), ('install_codex_rules.py', [])]
TOOLS = [('install_test_runner.py', []), ('install_graphical_test_policy.py', []), *RULES]
DEPS = [('setup_dependencies.sh.py', []), ('setup_checkout.sh.py', [])]


@pytest.mark.parametrize('mode,expected', [
    ([], [*DEPS, *TOOLS]),
    (['--dependencies-only'], DEPS),
    (['--ppa-build-tools'], [('setup_dependencies.sh.py', ['--ppa-build-tools'])]),
    (['--test-tools-only'], TOOLS),
    (['--codex-rules-only'], RULES),
    (['--prepare-host'], [('prepare_host.py', []), *TOOLS]),
    (['--bootstrap-tools'], [('install_test_runner.py', []), *RULES]),
    (['--prepare-vm'], [('prepare-vm.py', [])]),
    (['--install-extension'], [('make', ['--no-print-directory', '_install-development-extension'])]),
])
def test_modes_repeat_complete_scope_from_any_working_directory(checkout, mode, expected):
    for _ in range(2):
        result, events = run_setup(checkout, *mode)
        assert result.returncode == 0, result.stderr
        assert events == expected
        assert not (checkout / 'authentication.log').exists()


@pytest.mark.parametrize('mode,failure,expected', [
    (['--prepare-host'], 'prepare_host.py', [('prepare_host.py', [])]),
    ([], 'setup_dependencies.sh.py', DEPS[:1]),
    ([], 'setup_checkout.sh.py', DEPS),
    (['--dependencies-only'], 'setup_dependencies.sh.py', DEPS[:1]),
    (['--ppa-build-tools'], 'setup_dependencies.sh.py', [('setup_dependencies.sh.py', ['--ppa-build-tools'])]),
    (['--test-tools-only'], 'install_test_runner.py', [('install_test_runner.py', [])]),
    (['--test-tools-only'], 'install_graphical_test_policy.py', TOOLS[:2]),
    (['--codex-rules-only'], 'install_codex_rules.py', RULES[:1]),
])
def test_failure_stops_dependent_setup_and_can_be_retried(checkout, mode, failure, expected):
    result, events = run_setup(checkout, *mode, failure=failure)
    assert result.returncode == 7
    assert events == expected
    assert 'completed successfully' not in result.stdout
    result, _events = run_setup(checkout, *mode)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('args,code', [
    (['--help'], 0), (['--unknown'], 2), (['--test-tools-only', '--prepare-host'], 2),
])
def test_help_and_invalid_selection_have_no_setup_side_effects(checkout, args, code):
    result, events = run_setup(checkout, *args)
    assert result.returncode == code
    assert not events


@pytest.mark.skipif(os.geteuid() == 0, reason='authorization gate applies to unprivileged callers')
@pytest.mark.parametrize('mode', ['', '--test-tools-only', '--codex-rules-only', '--prepare-host',
                                  '--dependencies-only', '--ppa-build-tools', '--bootstrap-tools'])
def test_denied_routine_setup_never_falls_back_to_authentication(checkout, mode):
    result, events = run_setup(checkout, mode, denied=True)
    assert result.returncode == 23
    assert not events
    assert not (checkout / 'authentication.log').exists()


@pytest.mark.parametrize('mode', [[], ['--bootstrap-tools']])
def test_first_install_authenticates_once_then_reuses_the_installed_grant(checkout, mode):
    (checkout / 'installed-setup').unlink()
    result, events = run_setup(checkout, *mode)
    assert result.returncode == 0, result.stderr
    expected = [*DEPS, *TOOLS] if not mode else RULES
    assert events == [('install_test_runner.py', []), *expected]
    result, _events = run_setup(checkout, *mode)
    assert result.returncode == 0, result.stderr
    if os.geteuid() != 0:
        assert (checkout / 'authentication.log').read_text() == 'authentication\n'


def test_first_install_failure_stops_before_dependencies_and_can_be_retried(checkout):
    (checkout / 'installed-setup').unlink()
    result, events = run_setup(checkout, failure='install_test_runner.py')
    assert result.returncode == 7
    assert events == [('install_test_runner.py', [])]
    assert not (checkout / 'installed-setup').exists()
    result, events = run_setup(checkout)
    assert result.returncode == 0, result.stderr
    assert events == [('install_test_runner.py', []), *DEPS, *TOOLS]


@pytest.mark.skipif(os.geteuid() == 0, reason='authorization gate applies to unprivileged callers')
@pytest.mark.parametrize('mode', [[], ['--bootstrap-tools'], ['--dependencies-only']])
def test_unsafe_existing_installation_never_requests_authentication(checkout, mode):
    (checkout / 'installed-setup').unlink()
    (checkout / 'installed-setup').symlink_to('missing-target')
    result, events = run_setup(checkout, *mode)
    assert result.returncode == 23
    assert not events
    assert not (checkout / 'authentication.log').exists()


@pytest.mark.parametrize('target,mode', [
    ('prep-host', '--prepare-host'), ('prep-vm', '--prepare-vm'),
    ('install-extension', '--install-extension'),
])
def test_make_setup_aliases_only_delegate_to_master(checkout, target, mode):
    shutil.copy2(ROOT / 'Makefile', checkout / 'Makefile')
    (checkout / 'setup.sh').write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    result = subprocess.run(['make', '--no-print-directory', target], cwd=checkout,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == mode
