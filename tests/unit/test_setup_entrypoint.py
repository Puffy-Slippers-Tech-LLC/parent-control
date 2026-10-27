"""Exercise the real master in a disposable checkout with harmless modules."""
from tests.support.vm_registry import vm_name
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
    for name in ('tools', 'child', 'tests/integration', 'bin', 'config'):
        (root / name).mkdir(parents=True)
    master = (ROOT / 'setup.sh').read_text().replace('/usr/local/libexec/onpc-setup', str(root / 'installed-setup'))
    (root / 'setup.sh').write_text(master)
    (root / 'setup.sh').chmod(0o755)
    (root / 'installed-setup').touch()
    (root / 'Makefile').touch()
    (root / 'child/preview').touch(mode=0o755)
    release = root / 'os-release'
    release.write_text('ID=ubuntu\nVERSION_ID="26.04"\n')
    (root / 'tools/setup_platform.sh').write_text(
        (ROOT / 'tools/setup_platform.sh').read_text().replace('/etc/os-release', str(release)))
    stub = '''import json, os, pathlib, sys
name = pathlib.Path(__file__).name
with open(os.environ['ONPC_SETUP_TRACE'], 'a') as stream:
    stream.write(json.dumps([name, sys.argv[1:], os.getcwd()]) + '\\n')
if name == 'install_test_runner.py' and os.environ.get('ONPC_SETUP_FAIL') != name:
    pathlib.Path('installed-setup').touch()
sys.exit(7 if os.environ.get('ONPC_SETUP_FAIL') == name else 0)
'''
    for name in ('install_test_runner.py', 'install_graphical_test_policy.py', 'install_codex_rules.py', 'rpm_builder.py', 'deb_builder.py', 'install_watch_extension.py'):
        (root / 'tools' / name).write_text(stub)
    (root / 'tests/integration/prepare_baseline.py').write_text(stub)
    shutil.copy2(ROOT / 'tests/integration/test_account_password.py', root / 'tests/integration/test_account_password.py')
    (root / '.envrc').write_text("export TEST_ACCOUNT_PASSWORD='fixture-password'\n")
    (root / '.envrc').chmod(0o600)
    shutil.copy2(ROOT / 'tools/onpc-setup', root / 'tools/onpc-setup')
    shutil.copy2(ROOT / 'tests/integration/vm_config.py', root / 'tests/integration/vm_config.py')
    shutil.copy2(ROOT / 'config/test-vm.json', root / 'config/test-vm.json')
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
    for name in ('tools/setup_dependencies.sh', 'tools/setup_checkout.sh'):
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
TOOLS = [('install_test_runner.py', []), ('install_graphical_test_policy.py', []), *RULES,
         ('install_watch_extension.py', ['--if-available'])]
DEPS = [('setup_dependencies.sh.py', []), ('rpm_builder.py', []), ('setup_checkout.sh.py', [])]
FEDORA_DEPS = [DEPS[0], ('deb_builder.py', []), DEPS[2]]


@pytest.mark.parametrize('mode,expected', [
    ([], [*DEPS, *TOOLS]),
    (['--dependencies-only'], DEPS),
    (['--vm-host-only'], [('setup_dependencies.sh.py', ['--vm-host-only']), *TOOLS]),
    (['--ui-tests-only'], [('setup_checkout.sh.py', ['--ui-tests-only'])]),
    (['--ppa-build-tools'], [('setup_dependencies.sh.py', ['--ppa-build-tools'])]),
    (['--rpm-build-tools'], [('setup_dependencies.sh.py', ['--rpm-build-tools']), ('rpm_builder.py', [])]),
    (['--test-tools-only'], TOOLS),
    (['--codex-rules-only'], RULES),
    (['--replace-missing-baseline', '--vm', vm_name()],
     [('prepare_baseline.py', ['--replace-missing', '--vm', vm_name()]), *TOOLS]),
    (['--bootstrap-tools'], [('install_test_runner.py', []), *RULES]),
    (['--install-extension'], [('make', ['--no-print-directory', '_install-development-extension'])]),
])
def test_modes_repeat_complete_scope_from_any_working_directory(checkout, mode, expected):
    for _ in range(2):
        result, events = run_setup(checkout, *mode)
        assert result.returncode == 0, result.stderr
        assert events == expected
        assert not (checkout / 'authentication.log').exists()


@pytest.mark.parametrize('mode,failure,expected', [
    (['--replace-missing-baseline', '--vm', vm_name()], 'prepare_baseline.py',
     [('prepare_baseline.py', ['--replace-missing', '--vm', vm_name()])]),
    ([], 'setup_dependencies.sh.py', DEPS[:1]),
    ([], 'rpm_builder.py', DEPS[:2]),
    ([], 'setup_checkout.sh.py', DEPS),
    (['--dependencies-only'], 'setup_dependencies.sh.py', DEPS[:1]),
    (['--ui-tests-only'], 'setup_checkout.sh.py', [('setup_checkout.sh.py', ['--ui-tests-only'])]),
    (['--ppa-build-tools'], 'setup_dependencies.sh.py', [('setup_dependencies.sh.py', ['--ppa-build-tools'])]),
    (['--rpm-build-tools'], 'setup_dependencies.sh.py', [('setup_dependencies.sh.py', ['--rpm-build-tools'])]),
    (['--rpm-build-tools'], 'rpm_builder.py', [('setup_dependencies.sh.py', ['--rpm-build-tools']), ('rpm_builder.py', [])]),
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
    (['--help'], 0), (['--unknown'], 2), (['--test-tools-only', '--replace-missing-baseline'], 2),
    (['--prepare-vm'], 2), (['--prepare-baseline'], 2),
])
def test_help_and_invalid_selection_have_no_setup_side_effects(checkout, args, code):
    result, events = run_setup(checkout, *args)
    assert result.returncode == code
    assert not events
    if args == ['--help']:
        assert 'tools/prepare-vm' in result.stdout
        assert '--prepare-vm' not in result.stdout


@pytest.mark.skipif(os.geteuid() == 0, reason='authorization gate applies to unprivileged callers')
@pytest.mark.parametrize('mode', ['', '--test-tools-only', '--codex-rules-only',
                                  '--replace-missing-baseline', '--dependencies-only', '--ppa-build-tools', '--rpm-build-tools', '--vm-host-only', '--bootstrap-tools'])
def test_denied_routine_setup_never_falls_back_to_authentication(checkout, mode):
    vm_args = ['--vm', vm_name()] if mode == '--replace-missing-baseline' else []
    result, events = run_setup(checkout, mode, *vm_args, denied=True)
    assert result.returncode == 23
    assert not events
    assert not (checkout / 'authentication.log').exists()


@pytest.mark.parametrize('mode', [[], ['--bootstrap-tools']])
@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_first_install_authenticates_once_then_reuses_the_installed_grant(checkout, mode, distribution):
    (checkout / 'os-release').write_text(f'ID={distribution}\nVERSION_ID=44\n')
    (checkout / 'installed-setup').unlink()
    result, events = run_setup(checkout, *mode)
    assert result.returncode == 0, result.stderr
    deps = DEPS if distribution == 'ubuntu' else FEDORA_DEPS
    expected = [*deps, *TOOLS] if not mode else RULES
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


def test_make_setup_aliases_only_delegate_to_master(checkout):
    shutil.copy2(ROOT / 'Makefile', checkout / 'Makefile')
    (checkout / 'setup.sh').write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    result = subprocess.run(['make', '--no-print-directory', 'install-extension'], cwd=checkout,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '--install-extension'


def test_missing_password_fails_before_privilege_dispatch_or_any_setup(checkout):
    (checkout / '.envrc').unlink()
    result, events = run_setup(checkout, '--replace-missing-baseline', '--vm', vm_name(), denied=True)
    assert result.returncode == 1
    assert 'TEST_ACCOUNT_PASSWORD' in result.stderr
    assert not events
    assert not (checkout / 'authentication.log').exists()


def test_gui_fixture_prerequisites_are_in_the_master_dependency_route():
    import shlex
    packages = shlex.split((ROOT / 'tools/setup_dependencies.sh').read_text(), comments=True)
    packages = {token.split('=', 1)[0] for token in packages}
    assert {'flatpak', 'snapd', 'squashfs-tools', 'fonts-dejavu-core', 'xkb-data',
            'libc-bin', 'gir1.2-gtk-4.0', 'gir1.2-glib-2.0', 'python3',
            'python3-gi', 'python3-gi-cairo'} <= packages


@pytest.mark.parametrize('mode,expected', [
    ([], [*FEDORA_DEPS, *TOOLS]),
    (['--dependencies-only'], FEDORA_DEPS),
    (['--rpm-build-tools'], [('setup_dependencies.sh.py', ['--rpm-build-tools'])]),
    (['--vm-host-only'], [('setup_dependencies.sh.py', ['--vm-host-only']), *TOOLS]),
    (['--ppa-build-tools'], []),
])
def test_fedora_prepares_deb_container_while_rpm_only_setup_stays_native(checkout, mode, expected):
    (checkout / 'os-release').write_text('ID=fedora\nVERSION_ID=44\n')
    result, events = run_setup(checkout, *mode)
    assert result.returncode == (2 if mode == ['--ppa-build-tools'] else 0), result.stderr
    assert events == expected


def test_fedora_deb_builder_failure_stops_checkout_setup_and_can_be_retried(checkout):
    (checkout / 'os-release').write_text('ID=fedora\nVERSION_ID=44\n')
    result, events = run_setup(checkout, '--dependencies-only', failure='deb_builder.py')
    assert result.returncode == 7
    assert events == FEDORA_DEPS[:2]
    result, events = run_setup(checkout, '--dependencies-only')
    assert result.returncode == 0, result.stderr
    assert events == FEDORA_DEPS


@pytest.mark.parametrize('release', ['ID=fedora\nVERSION_ID=43\n',
                                   'ID=org.freedesktop.platform\nVERSION_ID=25.08\n'])
def test_unsupported_environment_fails_before_authentication_or_mutation(checkout, release):
    (checkout / 'installed-setup').unlink()
    (checkout / 'os-release').write_text(release)
    result, events = run_setup(checkout)
    assert result.returncode == 1
    assert not events
    assert not (checkout / 'authentication.log').exists()


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('mode', [[], ['--rpm-build-tools'], ['--vm-host-only']])
def test_package_routes_select_native_tools_and_keep_vm_dependencies_optional(tmp_path, distribution, mode):
    root = tmp_path / 'package checkout'
    (root / 'tools').mkdir(parents=True)
    release = root / 'os-release'
    release.write_text(f'ID={distribution}\nVERSION_ID=44\n')
    (root / 'tools/setup_platform.sh').write_text(
        (ROOT / 'tools/setup_platform.sh').read_text().replace('/etc/os-release', str(release)))
    # Only this disposable fixture removes the root gate; package commands are
    # private recording doubles, with no privileged host or network operations.
    script = root / 'tools/setup_dependencies.sh'
    script.write_text((ROOT / 'tools/setup_dependencies.sh').read_text().replace('EUID != 0', '0 != 0'))
    trace = root / 'packages.jsonl'
    binaries = root / 'bin'
    binaries.mkdir()
    for name in ('dnf', 'apt-get', 'add-apt-repository'):
        tool = binaries / name
        tool.write_text('#!/usr/bin/python3\nimport json, os, pathlib, sys\n'
                        'with open(os.environ["ONPC_PACKAGE_TRACE"], "a") as stream:\n'
                        '    stream.write(json.dumps([pathlib.Path(sys.argv[0]).name, *sys.argv[1:]]) + "\\n")\n')
        tool.chmod(0o755)
    result = subprocess.run(['/bin/bash', str(script), *mode],
                            env={**os.environ, 'PATH': f'{binaries}:{os.environ["PATH"]}',
                                 'ONPC_PACKAGE_TRACE': str(trace)},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    commands = [json.loads(line) for line in trace.read_text().splitlines()]
    tokens = {token for command in commands for token in command}
    if distribution == 'fedora':
        assert all(command[:3] == ['dnf', '-y', 'install'] for command in commands)
        if mode != ['--vm-host-only']:
            requires = {line.split(':', 1)[1].strip()
                        for line in (ROOT / 'rpm/oh-no-parent-control.spec.in').read_text().splitlines()
                        if line.startswith('BuildRequires:')}
            assert requires <= tokens
        assert {'apt-get', 'apparmor', 'sbuild', 'gir1.2-gtk-4.0'}.isdisjoint(tokens)
        assert ('podman' in tokens) == (mode != ['--vm-host-only'])
        if mode != ['--vm-host-only']:
            assert {'shadow-utils-subid', 'passt', 'slirp4netns', 'fuse-overlayfs'} <= tokens
        if not mode:
            # Fedora splits the daemon and the Python client used by Dogtail.
            assert {'gnome-ponytail-daemon', 'python3-gnome-ponytail-daemon', 'gtk3'} <= tokens
        assert ('libvirt-daemon-kvm' in tokens) == (mode == ['--vm-host-only'])
    else:
        assert all(command[0] != 'dnf' for command in commands)
        if not mode:
            assert 'gir1.2-gtk-3.0' in tokens  # Dogtail rawinput imports GTK 3 on both hosts.
        assert ('libvirt-daemon-system' in tokens) == (mode == ['--vm-host-only'])
    assert ('os-autoinst' in tokens) == (mode == ['--vm-host-only'])
