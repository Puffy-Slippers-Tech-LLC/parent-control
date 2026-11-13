"""Requested host matrix: private registries, doubled SSH, and tiny Git trees.

No live VM, helper, network, account or checkout is accessed. Real Git/Make
children for source capture are bounded, waited and confined to pytest storage.
"""
import io
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace

import pytest

import host_dispatch
import launcher_controller
import remote_sources
from vm_selection import vm_config


@pytest.mark.parametrize('names', [
    ('local', 'myserver', 'worker2'),
    ('desk-7', 'node-b', 'node-c'),
])
@pytest.mark.parametrize('controller,targets', [
    (0, (0,)),                     # Workstation controller, workstation VM.
    (1, (1,)),                     # SSH controller, its own VM.
    (0, (1,)),                     # Workstation controller, SSH VM.
    (0, (0, 1)),                   # One command with both real-use host roles.
    (0, (0, 1, 2)),                # Three hosts; all SSH originates at the desk.
])
def test_command_host_matrix(tmp_path, monkeypatch, names, controller, targets):
    tool = tmp_path / 'tool checkout'
    destination = tool if controller == 0 else tmp_path / 'controller checkout'
    branch = 'main' if controller == 0 else 'controller'
    branches = [dict(name='main', host=names[0], repo_root=str(tool))]
    if controller:
        branches.append(dict(name=branch, host=names[controller], repo_root=str(destination)))
    branches.extend(dict(name='worker-' + str(index), host=names[index],
                         repo_root=str(tmp_path / ('worker checkout ' + str(index))))
                    for index in range(1, 3)
                    if not any(item['host'] == names[index] for item in branches))
    document = dict(agent='codex', hosts=[dict(name=name, enabled='true', max_compute_unit=2,
        # Deliberately invert these legacy labels. Identity decides locality.
        transport='local' if index == 1 else 'ssh', ssh_port=2200 + index)
        for index, name in enumerate(names)], branches=branches,
        families=[dict(family='ubuntu26.04-x86_64', package_format='deb',
            fixture_path='common/ubuntu/common', vms=[dict(name='Guest-' + str(index),
                id=str(index + 1), enabled='true', host=names[index],
                disk_anchor=str(tmp_path / ('guest-' + str(index) + '.qcow2')))
                for index in range(3)])])
    branch_by_root = {Path(item['repo_root']): item['name'] for item in branches}
    for root in branch_by_root:
        (root / 'config').mkdir(parents=True)
        (root / 'tools').mkdir()
        (root / 'config/environment.json').write_text(json.dumps(document))
        (root / 'tools/run-tests').write_text('# private launcher fixture\n')
    monkeypatch.setattr(vm_config, 'ROOT', tool)
    monkeypatch.setattr(vm_config, 'current_branch', lambda: 'main')
    monkeypatch.setattr(host_dispatch, 'git', lambda root, *args: branch_by_root[Path(root)])
    monkeypatch.setattr(launcher_controller, '__file__', str(tool / 'tools/launcher_controller.py'))
    monkeypatch.setattr(launcher_controller, '_local_checkout', lambda root, name:
        None if (root, name) == (tool, 'main') else pytest.fail('wrong local controller'))
    monkeypatch.setattr(launcher_controller, '_early_sync', lambda *args: False)
    monkeypatch.setattr('test_source.admission', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr('test_launcher.environment', lambda root: {'PATH': '/usr/bin'})
    selector = ','.join('Guest-' + str(index) for index in targets)
    monkeypatch.setattr(sys, 'argv', [str(tool / 'tools/run-tests'), '--branch', branch,
                                     '--vm', selector, 'system'])
    hops, operations = [], []

    def remote_vm(route, control, command, **kwargs):
        assert route.root == destination, 'VM source must come from the controller'
        argv = host_dispatch.ssh_command(route.host, command)
        assert argv[-2] == route.host.name
        assert shlex.split(argv[-1]) == command
        hops.append((names[controller], route.host.name))
        operations.append((route.vm.name, 'ssh'))
        return 0

    monkeypatch.setattr(remote_sources.RemoteVM, 'run', remote_vm)

    def entry():
        _, vms = vm_config.execution(selector, destination / 'config/environment.json', remote=True)
        for vm in vms:
            status = host_dispatch.vm_tool(destination, vm, 'test-vm', ['--vm', vm.name, 'status'])
            if status is None:
                operations.append((vm.name, 'local'))
            else:
                assert status == 0
        return 0

    def ssh_controller(argv, **kwargs):
        assert argv[0] == 'ssh' and argv[-2] == names[controller]
        remote = shlex.split(argv[-1])
        assert remote[4:7] == [str(destination), branch, 'run-tests']
        assert remote[7:] == ['--vm', selector, 'system']
        hops.append((names[0], names[controller]))
        return SimpleNamespace(returncode=entry())

    monkeypatch.setattr(launcher_controller.subprocess, 'run', ssh_controller)
    assert launcher_controller.dispatch(entry) == 0
    assert operations == [('Guest-' + str(index), 'local' if index == controller else 'ssh')
                          for index in targets]
    assert hops == ([ (names[0], names[controller]) ] if controller else []) + [
        (names[controller], names[index]) for index in targets if index != controller]
    assert all(source == names[0] for source, _target in hops)


def test_source_transfer_uses_controller_working_bytes_without_touching_host_checkout(tmp_path):
    from test_storage import scratch_descriptors
    from tools.vm_source_snapshot import receive_transfer, transfer_archive
    controller = tmp_path / 'controller'
    controller.mkdir()
    (controller / 'tools').mkdir()
    (controller / 'Makefile').write_text("package-source-files:\n\t@printf '%s\\n' payload.txt\n")
    (controller / '.gitignore').write_text('output/\nnode_modules/\n')
    (controller / 'payload.txt').write_text('committed controller source\n')
    system = controller / 'tests/system'
    system.mkdir(parents=True)
    (system / 'test_install.py').write_text('def test_install(): pass\n')
    (system / 'pytest.ini').write_text('[pytest]\n')
    environment = dict(os.environ, GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')

    def git(*arguments):
        return subprocess.run(['git', '-c', 'user.name=Routing test',
            '-c', 'user.email=routing@example.invalid', '-c', 'commit.gpgsign=false',
            '-c', 'core.hooksPath=/dev/null', *arguments], cwd=controller,
            env=environment, check=True, capture_output=True, timeout=10,
            pass_fds=scratch_descriptors())

    git('init', '--quiet', '-b', 'controller')
    git('add', '--all')
    git('commit', '--quiet', '-m', 'Private controller fixture')
    (controller / 'payload.txt').write_text('uncommitted controller change\n')
    ambiguous = controller / 'tools/future-input.unfamiliar'
    ambiguous.write_text('new controller input\n')
    ignored = controller / 'tools/node_modules'
    ignored.mkdir()
    with (ignored / 'large-generated-file').open('wb') as stream:
        stream.truncate(1024 ** 3)
    own_checkout = tmp_path / 'vm-host-checkout'
    own_checkout.mkdir()
    (own_checkout / 'payload.txt').write_text('VM host source stays independent\n')
    archive = io.BytesIO()
    manifest = transfer_archive(controller, archive)
    assert len(archive.getvalue()) < 65536
    assert 'tools/future-input.unfamiliar' in manifest
    assert all('node_modules' not in name for name in manifest)
    received = tmp_path / 'run-owned-source'
    archive.seek(0)
    receive_transfer(archive, received, manifest)
    assert (received / 'payload.txt').read_text() == 'uncommitted controller change\n'
    assert (received / 'tools/future-input.unfamiliar').read_text() == 'new controller input\n'
    assert (received / 'tests/system/test_install.py').read_text() == 'def test_install(): pass\n'
    assert (received / 'tests/system/pytest.ini').read_text() == '[pytest]\n'
    assert git('show', 'HEAD:payload.txt').stdout == b'committed controller source\n'
    assert (own_checkout / 'payload.txt').read_text() == 'VM host source stays independent\n'


def test_guest_options_are_not_interpreted_as_host_artifact_inputs(tmp_path, monkeypatch):
    verify = pytest.fail
    monkeypatch.setattr(remote_sources, 'verify_artifacts', verify)
    assert remote_sources.artifact_inputs(tmp_path,
        ['tools/test-vm', '--vm', 'Guest', 'exec', '--',
         'printf', '%s\\n', '--artifacts', str(tmp_path)], {}) == {}


@pytest.mark.parametrize('changed', [False, True])
def test_recording_serving_requires_current_publication_identity(tmp_path, changed):
    import recording_storage
    store = recording_storage.Store(root=tmp_path)
    with store.begin('system', 'check_identity') as owner:
        owner.path.write_bytes(b'playable recording double')
        path = owner.publish(['Guest'], validate=lambda path: True)
    if changed:
        path.write_bytes(b'substituted recording')
        with pytest.raises(ValueError, match='recordings:'):
            with store.open_published(path):
                pytest.fail('changed recording served')
    else:
        with store.open_published(path) as stream:
            assert stream.read() == b'playable recording double'
    foreign = store.path / 'system-check_unknown-Guest.webm'
    foreign.write_bytes(b'keep unrelated media')
    with pytest.raises(ValueError, match='no current publication'):
        with store.open_published(foreign):
            pytest.fail('unowned recording served')
    assert foreign.read_bytes() == b'keep unrelated media'
