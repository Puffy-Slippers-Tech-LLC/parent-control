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
import threading
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
@pytest.mark.parametrize('launcher', [
    'run-tests', 'run-unit-tests', 'run-ui-tests', 'fix-tests', 'execute-plan', 'sync-whatsnew',
])
def test_command_host_matrix(tmp_path, monkeypatch, names, controller, targets, launcher):
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
        families=[dict(family='ubuntu26.04-x86_64', package_format='deb', vm_tags='general',
            fixture_path='common/ubuntu/common', vms=[dict(name='Guest-' + str(index),
                id=str(index + 1), enabled='true', host=names[index],
                disk_anchor=str(tmp_path / ('guest-' + str(index) + '.qcow2')))
                for index in range(3)])])
    branch_by_root = {Path(item['repo_root']): item['name'] for item in branches}
    for root in branch_by_root:
        (root / 'config').mkdir(parents=True)
        (root / 'tools').mkdir()
        (root / 'config/environment.json').write_text(json.dumps(document))
        (root / 'tools' / launcher).write_text('# private launcher fixture\n')
    monkeypatch.setattr(vm_config, 'ROOT', tool)
    monkeypatch.setattr(vm_config, 'current_branch', lambda: 'main')
    monkeypatch.setattr(host_dispatch, 'git', lambda root, *args: branch_by_root[Path(root)])
    monkeypatch.setattr(launcher_controller, '__file__', str(tool / 'tools/launcher_controller.py'))
    monkeypatch.setattr(launcher_controller, '_local_checkout', lambda root, name:
        None if branch_by_root.get(root) == name else pytest.fail('wrong local controller'))
    synchronized = []
    def synchronize(*args, **kwargs):
        assert args == (destination, branch)
        assert kwargs == dict(previous_runs=[], retained_start=False, live=False,
                             on_boundary_admitted=None, check_only=False)
        synchronized.append(launcher)
        return False
    monkeypatch.setattr(launcher_controller, '_startup_sync', synchronize)
    monkeypatch.setattr('test_source.admission', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr('test_launcher.environment', lambda root: {'PATH': '/usr/bin'})
    selector = ','.join('Guest-' + str(index) for index in targets)
    monkeypatch.setattr(sys, 'argv', [str(tool / 'tools' / launcher), '--branch', branch,
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
        assert synchronized == [launcher]
        assert launcher_controller.public_arguments(launcher) == [
            '--branch', branch, '--vm', selector, 'system']
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
        assert remote[4:7] == [str(destination), branch, launcher]
        assert json.loads(remote[7]) == ['--branch', branch, '--vm', selector, 'system']
        assert remote[8:] == ['--vm', selector, 'system']
        hops.append((names[0], names[controller]))
        # Execute destination admission too: the SSH bootstrap must not let a
        # remotely placed job bypass synchronization before workflow imports.
        monkeypatch.setattr(launcher_controller, '__file__',
                            str(destination / 'tools/launcher_controller.py'))
        monkeypatch.setattr(sys, 'argv', [str(destination / 'tools' / launcher), *remote[8:]])
        monkeypatch.setenv(launcher_controller.DESTINATION, json.dumps(dict(
            root=str(destination), branch=branch, launcher=launcher, pid=os.getpid(),
            public_argv=json.loads(remote[7]))))
        return SimpleNamespace(returncode=launcher_controller.dispatch(entry))

    monkeypatch.setattr(launcher_controller.subprocess, 'run', ssh_controller)
    assert launcher_controller.dispatch(entry) == 0
    assert operations == [('Guest-' + str(index), 'local' if index == controller else 'ssh')
                          for index in targets]
    assert hops == ([ (names[0], names[controller]) ] if controller else []) + [
        (names[controller], names[index]) for index in targets if index != controller]
    assert all(source == names[0] for source, _target in hops)

    # Inspection must work behind a repair writer, even when a native command
    # has inherited its environment labels but none of its descriptors. The
    # same controller/host matrix covers a server-local reader without SSH.
    monkeypatch.setenv('ONPC_TEST_SOURCE_FD', '2147483647')
    monkeypatch.setattr(remote_sources, 'capsule',
        lambda *args, **kwargs: pytest.fail('artifact inspection captured source'))
    reads = []
    def read_artifact(argv, **kwargs):
        remote = shlex.split(argv[-1])
        host = argv[-2]
        anchor = next(item['repo_root'] for item in branches if item['host'] == host)
        assert remote == ['/usr/bin/env', '-C', anchor, '/usr/bin/pkexec',
            '--disable-internal-agent', '--keep-cwd', '/usr/local/libexec/onpc-test-artifacts',
            'read', '/var/tmp/onpc-owned/report with spaces.json', '--bytes', '128']
        assert kwargs['cwd'] == destination and kwargs['timeout'] == 60
        reads.append(host)
        return SimpleNamespace(returncode=7)
    monkeypatch.setattr(host_dispatch.subprocess, 'run', read_artifact)
    _, vms = vm_config.execution(selector, destination / 'config/environment.json', remote=True)
    for vm in vms:
        status = host_dispatch.artifact_reader(destination, vm,
            ['read', '/var/tmp/onpc-owned/report with spaces.json', '--bytes', '128'])
        assert status == (None if vm.host.name == names[controller] else 7)
        with pytest.raises(ValueError, match='artifacts requires'):
            host_dispatch.artifact_reader(destination, vm, ['export', '/var/tmp/onpc-owned/report'])
    assert reads == [names[index] for index in targets if index != controller]


def test_source_transfer_uses_controller_working_bytes_without_touching_host_checkout(tmp_path, monkeypatch):
    from test_storage import scratch_descriptors
    from tools.vm_source_snapshot import receive_transfer, transfer_archive
    controller = tmp_path / 'controller'
    controller.mkdir()
    (controller / 'tools').mkdir()
    (controller / 'config').mkdir()
    document = dict(agent='codex', hosts=[dict(name='fixture-host', transport='local',
        enabled='true', max_compute_unit=1)], branches=[dict(name='controller',
        host='fixture-host', repo_root=str(controller))], families=[dict(
        family='ubuntu26.04-x86_64', package_format='deb', vm_tags='general',
        fixture_path='common/ubuntu/common', vms=[dict(name='Fixture-Guest', id='1',
        enabled='true', host='fixture-host', disk_anchor=str(tmp_path / 'guest.qcow2'))])])
    (controller / 'config/environment.json').write_text(json.dumps(document))
    allocator_marker = tmp_path / 'allocator-loaded'
    allocator = controller / 'tools/test_storage.py'
    allocator.write_text('from pathlib import Path\n'
        'ROOT = Path(__file__).resolve().parents[1]\n'
        'BASE = ROOT / "output/test-runs"\n'
        f'Path({str(allocator_marker)!r}).write_text(str(ROOT))\n')
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

    # Normal assignments keep the accepted closure while the original checkout
    # contains unverified repair edits. Local replay also loads its allocator
    # from that closure, before it can inspect a request or touch a VM/helper.
    import host_compute
    import test_source
    for name in (host_compute.VARIABLE, host_compute.TOKENS):
        monkeypatch.delenv(name, raising=False)
    for name in (test_source.VARIABLE, test_source.WRITER, test_source.IMPORTS,
                 test_source.STARTUP_READER, test_source.STARTUP_WRITER):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(test_source, '_local', threading.local())
    monkeypatch.setattr(vm_config, 'current_branch', lambda: 'controller')
    run = subprocess.run
    def bounded(*args, **kwargs):
        kwargs.setdefault('timeout', 10)
        return run(*args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', bounded)
    with remote_sources.FrozenSources(controller) as frozen:
        captured = frozen.directory
        baseline = dict(frozen.source)
        (controller / 'payload.txt').write_text('unverified repair source\n')
        allocator.write_text('raise RuntimeError("unverified live allocator executed")\n')
        def live_reader(*args, **kwargs):
            pytest.fail('ordinary frozen dispatch reacquired the live source reader')
        monkeypatch.setattr('test_source.reader', live_reader)
        with frozen.use():
            assert remote_sources.current_sources(controller) is frozen
        with remote_sources.capsule(controller, frozen.host,
                [str(controller / 'tools/test-vm')], {}, sources=frozen) as (command, payload, request):
            assert command[0] == '/usr/bin/python3'
            assert command[-1] == str(frozen.directory)
            assert request['source_identity'] == baseline
            header_size = int.from_bytes(payload.read(8), 'big')
            header = json.loads(payload.read(header_size))
            second = tmp_path / 'frozen-dispatch'
            receive_transfer(io.BytesIO(payload.read(header['size'])), second, header['manifest'])
            assert (second / 'payload.txt').read_text() == 'uncommitted controller change\n'
            result = subprocess.run(command, input=b'\0' * 8, cwd=controller,
                env=environment, capture_output=True, timeout=10, check=False,
                pass_fds=scratch_descriptors())
            assert result.returncode != 0
            assert b'invalid request header' in result.stderr
            assert b'unverified live allocator executed' not in result.stderr
            assert allocator_marker.read_text() == str(frozen.directory)

        # The ordinary local route keeps the nonce-qualified completion protocol
        # rather than accepting an exit status or a stale controller checkpoint.
        received = dict(evidence={'source': baseline}, handoffs=[])
        transcript = []
        class Reply:
            stopped = threading.Event()

            def run(self, command, *, input_stream, output, **kwargs):
                size = int.from_bytes(input_stream.read(8), 'big')
                request = json.loads(input_stream.read(size))
                prefix = b'\0' + (remote_sources.RESULT + request['receipt'] + ' ').encode()
                output(b'ordinary output\n' + prefix[:7])
                assert b''.join(transcript) == b'ordinary output\n'
                output(prefix[7:] + json.dumps(dict(kind='result', value=received)).encode() + b'\0')
                return 0
        route = remote_sources.RemoteVM(controller, host=frozen.host, sources=frozen)
        assert route.run(Reply(), [str(controller / 'tools/test-vm')],
                         env={}, output=transcript.append) == 0
        assert route.result == received
        assert b''.join(transcript) == b'ordinary output\n'
    assert not captured.exists()



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
