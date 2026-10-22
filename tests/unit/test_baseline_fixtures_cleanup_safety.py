"""In-memory guestfs, no VM, process, global cache or real ownership changes.

Compatible with parallel unit and cleanup scheduling.
"""
import copy
import hashlib
import json
from pathlib import PurePosixPath
import stat
from unittest.mock import Mock

import pytest
import baseline_fixtures as fixture
import baseline_console as console


class Guest:
    def __init__(self):
        self.nodes = {}
        self.writes = []
        self.links = {}
        self.mkdir('/')
        for path in ('/var', '/var/lib', '/opt', '/usr', '/usr/share', '/usr/share/applications',
                     '/usr/sbin', '/home', '/etc', '/etc/fapolicyd', '/etc/fapolicyd/trust.d'):
            self.mkdir(path)
        rows = []
        for index, name in enumerate(('onpc-child-riley', 'onpc-child-jordan', 'onpc-parent-jamie'), 1000):
            self.mkdir('/home/' + name)
            self.chown(index, index, '/home/' + name)
            self.chmod(0o700, '/home/' + name)
            rows.append(f'{name}:x:{index}:{index}::/home/{name}:/bin/bash')
        self.write('/etc/passwd', ('\n'.join(rows) + '\n').encode())
        self.write('/etc/group', b'root:x:0:\nfapolicyd:x:987:\n')
        self.chmod(0o644, '/etc/group')
        self.write('/etc/os-release', b'ID=ubuntu\nVERSION_ID=26.04\n')
        self.write(fixture.BACKEND_CONFIG, b'# native configuration\ntrust = debdb,file\nintegrity = none\n')
        self.chmod(0o644, fixture.BACKEND_CONFIG)
        for path in ('/usr/sbin/fapolicyd', '/usr/sbin/fapolicyd-cli'):
            self.write(path, ('native package ' + path).encode())
            self.chmod(0o755, path)
        self.package_payloads = {path: self.read_file(path) for path in
                                 ('/usr/sbin/fapolicyd', '/usr/sbin/fapolicyd-cli')}
        self.writes.clear()

    def exists(self, path): return path in self.nodes
    def is_symlink(self, path): return path in self.links
    def realpath(self, path):
        for parent in (PurePosixPath(path), *PurePosixPath(path).parents):
            if str(parent) in self.links:
                if str(parent) == '/usr/sbin' and self.links[str(parent)] == '/usr/bin':
                    return '/usr/bin' + path[len('/usr/sbin'):]
                return '/unexpected'
        return path
    def set_fedora(self):
        self.write('/etc/os-release', b'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n')
        self.write(fixture.BACKEND_CONFIG, b'# native configuration\ntrust = rpmdb,file\nintegrity = none\n')
        self.mkdir('/usr/bin')
        for path in tuple(self.package_payloads):
            canonical = path.replace('/usr/sbin/', '/usr/bin/')
            self.nodes[canonical] = self.nodes.pop(path)
            self.package_payloads[canonical] = self.package_payloads.pop(path)
        self.nodes['/usr/sbin'][0]['st_mode'] = stat.S_IFLNK | 0o777
        self.links['/usr/sbin'] = '/usr/bin'
        for path in ('/etc/fapolicyd/rules.d', '/usr/share/fapolicyd',
                     '/usr/share/fapolicyd/sample-rules'):
            self.mkdir(path)
        stock = {name: b'# fixed stock source\n' for name in fixture.native_assets.NATIVE_STOCK_RULE_NAMES}
        stock.update({'42-trusted-elf.rules': b'allow perm=execute all : trust=1\n',
                      '70-trusted-lang.rules': b'deny_audit perm=open all : ftype=text/x-python trust=0\n',
                      '90-deny-execute.rules': b'deny_audit perm=execute all : all\n'})
        self.policy_payloads = {'/usr/share/fapolicyd/default-ruleset.known-libs':
                                ('\n'.join(stock) + '\n').encode()}
        self.policy_payloads.update({'/usr/share/fapolicyd/sample-rules/' + name: data
                                     for name, data in stock.items()})
        for path, data in self.policy_payloads.items():
            self.write(path, data)
            self.chmod(0o644, path)
        for name, data in stock.items():
            path = '/etc/fapolicyd/rules.d/' + name
            self.write(path, data)
            self.chmod(0o644, path)
            self.chown(0, 987, path)
    def lstatns(self, path): return dict(self.nodes[path][0])
    def mkdir(self, path):
        assert path not in self.nodes
        self.nodes[path] = [{'st_uid': 0, 'st_gid': 0, 'st_mode': stat.S_IFDIR | 0o755,
                            'st_nlink': 1, 'st_ino': len(self.nodes) + 1, 'st_dev': 1}, b'']
    def chown(self, uid, gid, path): self.nodes[path][0].update(st_uid=uid, st_gid=gid)
    def chmod(self, mode, path): self.nodes[path][0]['st_mode'] = stat.S_IFMT(self.nodes[path][0]['st_mode']) | mode
    def write(self, path, data):
        if path not in self.nodes:
            self.nodes[path] = [{'st_uid': 0, 'st_gid': 0, 'st_mode': stat.S_IFREG | 0o600,
                                'st_nlink': 1, 'st_ino': len(self.nodes) + 1, 'st_dev': 1}, b'']
        self.nodes[path][1] = data
        self.writes.append(path)
    def read_file(self, path): return self.nodes[path][1]
    def checksum(self, algorithm, path): return hashlib.new(algorithm, self.read_file(path)).hexdigest()
    def mv(self, source, target): self.nodes[target] = self.nodes.pop(source)
    def sync(self): pass
    def rm(self, path):
        self.nodes.pop(path)
        self.writes.append(path)
    def umask(self, mode): assert mode == 0o077
    def filesize(self, path): return len(self.read_file(path))
    def is_file(self, path): return path in self.nodes and stat.S_ISREG(self.nodes[path][0]['st_mode'])
    def is_dir(self, path): return path in self.nodes and stat.S_ISDIR(self.nodes[path][0]['st_mode'])
    def ln_s(self, target, path): self.links[path] = target
    def find(self, path):
        return sorted(name[len(path) + 1:] for name in set(self.nodes) | set(self.links)
                      if name.startswith(path + '/'))
    def command(self, argv):
        if argv[:2] == ['dpkg-query', '-S']:
            return 'fapolicyd: ' + argv[2] + '\n'
        if argv[:2] == ['dpkg-query', '--control-show']:
            return ''.join(hashlib.md5(data).hexdigest() + '  ' + path.lstrip('/') + '\n'
                           for path, data in self.package_payloads.items())
        if argv[:2] == ['dpkg-query', '-W']:
            return 'fapolicyd 1.3.3-1build1\n'
        if argv[:2] == ['rpm', '-qf']:
            return 'fapolicyd'
        if argv[:2] == ['rpm', '-q']:
            if argv[3] == fixture.native_assets.NATIVE_RULE_MANIFEST:
                return ''.join(path + '\t' + hashlib.sha256(data).hexdigest()
                    + '\t' + str(stat.S_IFREG | 0o644) + '\troot\troot\t0\n'
                    for path, data in self.policy_payloads.items())
            if argv[3].startswith('%{FILEDIGESTALGO}'):
                return '8\n' + ''.join(path + '\t' + hashlib.sha256(data).hexdigest() + '\n'
                                       for path, data in self.package_payloads.items())
            return 'fapolicyd 0:1.3.4-2.fc44\n'
        os_id = 'fedora' if b'ID=fedora\n' in self.read_file('/etc/os-release') else 'ubuntu'
        if argv == [fixture.native_tool_paths(os_id)['cli'], '--check-config']:
            fixture.file_backend_config(self.read_file(fixture.BACKEND_CONFIG), os_id)
            return 'Daemon config is OK\n'
        assert argv[:2] == [fixture.native_tool_paths(os_id)['cli'], '--file'] and argv[2] in ('add', 'update')
        assert argv[4:] == ['--trust-file', PurePosixPath(fixture.TRUST_PENDING).name]
        path = argv[3]
        row = f'{path} {self.filesize(path)} {self.checksum("sha256", path)}\n'.encode()
        if argv[2] == 'add':
            # Real native add deduplicates by path across every trust fragment,
            # even if its old size/hash differs. Do not hide that CLI behavior.
            for candidate in self.nodes:
                if candidate.startswith('/etc/fapolicyd/trust.d/') and self.is_file(candidate):
                    if any(line.split() and line.split()[0] == path.encode()
                           for line in self.read_file(candidate).splitlines()):
                        raise RuntimeError('native CLI duplicate target')
            content = self.read_file(fixture.TRUST_PENDING) + row
        else:
            lines = self.read_file(fixture.TRUST_PENDING).splitlines(keepends=True)
            assert any(line.split() and line.split()[0] == path.encode() for line in lines)
            content = b''.join(row if line.split() and line.split()[0] == path.encode() else line
                               for line in lines)
        self.write(fixture.TRUST_PENDING, content)
        return ''


@pytest.fixture
def prepared():
    guest = Guest()
    payload = {key: ('distinct-' + key).encode() for key in
               ('A', 'H', 'S', 'N', 'mechanical', 'onpc-test-gui.py', 'gtk_automation.py',
                'trusted-hard', 'trusted-soft', 'trusted-activity')}
    return guest, payload


def test_first_repeat_owned_update_and_preserved_unrelated_state(prepared):
    guest, payload = prepared
    guest.write('/opt/unrelated', b'keep')
    fixture.reconcile(guest, payload)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    assert guest.nodes == before and guest.writes == []
    fixture.reconcile(guest, payload | {'A': b'new distinct A'})
    fixture.verify(guest)
    assert guest.read_file('/opt/unrelated') == b'keep'
    assert guest.read_file(fixture.assets.PREFIX + '/Exact Fixture.AppImage') == b'new distinct A'
    assert guest.read_file(fixture.assets.PREFIX + '/PrismLauncher.AppImage') == payload['N']


def test_clean_retirement_removes_complete_legacy_payload_and_exact_trust_only(prepared):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    guest.write('/opt/unrelated', b'preserved')
    environment = fixture.environment_files(fixture.accounts(guest))
    before = {path: copy.deepcopy(guest.nodes[path]) for path in environment}
    backend = copy.deepcopy(guest.nodes[fixture.BACKEND_CONFIG])
    fixture.reconcile_clean(guest, fixture.prepare_vm.preparation_digest())
    fixture.verify_clean(guest)
    assert not any(guest.exists(path) for path in fixture.movable_files(guest))
    assert not guest.exists(fixture.TRUST_FILE) and not guest.exists(fixture.TRUST_RECORD)
    assert {path: guest.nodes[path] for path in environment} == before
    assert guest.nodes[fixture.BACKEND_CONFIG] == backend
    assert guest.read_file('/opt/unrelated') == b'preserved'
    prior = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile_clean(guest)
    assert guest.nodes == prior and guest.writes == []


def test_clean_baseline_preparation_needs_no_movable_payload(prepared):
    guest, _ = prepared
    fixture.reconcile_clean(guest)
    fixture.verify_clean(guest)
    assert not any(guest.exists(path) for path in fixture.movable_files(guest))


@pytest.fixture
def native_rules_guest(prepared):
    guest, _ = prepared
    # Debian ships examples rather than an active admin policy. Its checksum
    # manifest, not a presumed example directory, selects this one vendor unit.
    for path in ('/usr/share/doc', '/usr/share/doc/fapolicyd',
                 '/usr/share/doc/fapolicyd/examples',
                 '/usr/share/doc/fapolicyd/examples/rules.d'):
        guest.mkdir(path)
    source = '/usr/share/doc/fapolicyd/examples/rules.d/95-allow-open.rules'
    data = b'# Vendor open policy; execution keeps its native default.\nallow perm=open all : all\n'
    guest.write(source, data)
    guest.chmod(0o644, source)
    guest.package_payloads[source] = data
    guest.writes.clear()
    return guest, source, data


@pytest.mark.parametrize('existing_directory', [False, True])
def test_native_rules_first_repeat_and_readonly_verification_preserve_unrelated_state(
        native_rules_guest, existing_directory):
    guest, source, data = native_rules_guest
    if existing_directory:
        guest.mkdir(fixture.NATIVE_RULES_ROOT)
        guest.chown(0, 42, fixture.NATIVE_RULES_ROOT)
        guest.chmod(0o750, fixture.NATIVE_RULES_ROOT)
    guest.write('/opt/unrelated', b'preserved')
    before = copy.deepcopy(guest.nodes)
    fixture.reconcile_native_rules(guest)
    assert guest.read_file(fixture.NATIVE_RULES_FILE) == data
    assert guest.lstatns(fixture.NATIVE_RULES_FILE)['st_gid'] == 987
    assert stat.S_IMODE(guest.lstatns(fixture.NATIVE_RULES_FILE)['st_mode']) == 0o644
    assert guest.read_file(source) == data
    assert not guest.exists(fixture.NATIVE_RULES_COMPILED)
    assert not guest.exists(fixture.TRUST_FILE)
    assert not guest.exists(fixture.RECORD)
    assert not any(path.startswith('/var/lib/fapolicyd') for path in guest.nodes)
    assert all(guest.nodes[path] == value for path, value in before.items())
    record = fixture.verify_native_rules(guest)
    assert record['source']['path'] == source and record['complete'] is True
    assert record['target']['sha256'] == hashlib.sha256(data).hexdigest()
    assert stat.S_IMODE(guest.lstatns(fixture.NATIVE_RULES_RECORD)['st_mode']) == 0o600
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile_native_rules(guest)
    fixture.verify_native_rules(guest)
    assert guest.nodes == before and guest.writes == []


def test_native_rules_package_update_refreshes_receipt_only_for_same_qualified_bytes(
        native_rules_guest, monkeypatch):
    guest, _, _ = native_rules_guest
    fixture.reconcile_native_rules(guest)
    target = copy.deepcopy(guest.nodes[fixture.NATIVE_RULES_FILE])
    actual_command = guest.command
    def command(argv):
        if argv[:2] == ['dpkg-query', '-W']:
            return 'fapolicyd 1.3.3-1build2\n'
        return actual_command(argv)
    monkeypatch.setattr(guest, 'command', command)
    guest.writes.clear()
    with pytest.raises(ValueError):
        fixture.verify_native_rules(guest)
    assert guest.writes == []
    fixture.reconcile_native_rules(guest)
    assert fixture.verify_native_rules(guest)['native']['version'] == '1.3.3-1build2'
    assert guest.nodes[fixture.NATIVE_RULES_FILE] == target
    assert set(guest.writes) == {fixture.NATIVE_RULES_RECORD + '.new'}


@pytest.mark.parametrize('boundary', ['receipt-partial', 'receipt-stage', 'intent', 'directory', 'partial-write',
                                     'group', 'mode', 'publish', 'complete'])
def test_native_rules_interrupted_first_publication_retries_only_durable_owned_state(
        native_rules_guest, monkeypatch, boundary):
    guest, _, data = native_rules_guest
    actual_write, actual_move = guest.write, guest.mv
    actual_chown, actual_chmod, actual_mkdir = guest.chown, guest.chmod, guest.mkdir
    failed = False
    def write(path, value):
        nonlocal failed
        if not failed and boundary == 'receipt-partial' and path == fixture.NATIVE_RULES_RECORD + '.new':
            actual_write(path, value[:30])
            failed = True
            raise OSError('interrupted native policy')
        if not failed and boundary == 'partial-write' and path == fixture.NATIVE_RULES_PENDING:
            actual_write(path, value[:5])
            failed = True
            raise OSError('interrupted native policy')
        actual_write(path, value)
    def move(source, target):
        nonlocal failed
        record = json.loads(guest.read_file(source)) if target == fixture.NATIVE_RULES_RECORD else None
        if not failed and boundary == 'receipt-stage' and record and not record['complete']:
            failed = True
            raise OSError('interrupted native policy')
        actual_move(source, target)
        if not failed and ((boundary == 'intent' and record and not record['complete'])
                           or (boundary == 'complete' and record and record['complete'])
                           or (boundary == 'publish' and target == fixture.NATIVE_RULES_FILE)):
            failed = True
            raise OSError('interrupted native policy')
    def chown(uid, gid, path):
        nonlocal failed
        actual_chown(uid, gid, path)
        if not failed and boundary == 'group' and path == fixture.NATIVE_RULES_PENDING and gid == 987:
            failed = True
            raise OSError('interrupted native policy')
    def chmod(mode, path):
        nonlocal failed
        actual_chmod(mode, path)
        if not failed and boundary == 'mode' and path == fixture.NATIVE_RULES_PENDING and mode == 0o644:
            failed = True
            raise OSError('interrupted native policy')
    def mkdir(path):
        nonlocal failed
        actual_mkdir(path)
        if not failed and boundary == 'directory' and path == fixture.NATIVE_RULES_ROOT:
            failed = True
            raise OSError('interrupted native policy')
    for name, implementation in (('write', write), ('mv', move), ('chown', chown),
                                 ('chmod', chmod), ('mkdir', mkdir)):
        monkeypatch.setattr(guest, name, implementation)
    with pytest.raises(OSError, match='interrupted native policy'):
        fixture.reconcile_native_rules(guest)
    # Native tmpfiles may normalize this stage's group on the next public boot.
    if guest.exists(fixture.NATIVE_RULES_PENDING):
        actual_chown(0, 987, fixture.NATIVE_RULES_PENDING)
    fixture.reconcile_native_rules(guest)
    fixture.verify_native_rules(guest)
    assert guest.read_file(fixture.NATIVE_RULES_FILE) == data
    assert not guest.exists(fixture.NATIVE_RULES_PENDING)
    assert not guest.exists(fixture.NATIVE_RULES_RECORD + '.new')


@pytest.mark.parametrize('fault', ['foreign-rule', 'unrecorded-target', 'legacy', 'compiled',
                                 'root-link', 'root-writable', 'source-link', 'source-hardlink',
                                 'source-owner', 'source-writable', 'source-changed',
                                 'source-semantics', 'ambiguous-source', 'target-stage',
                                 'receipt-link', 'receipt-stage'])
def test_native_rules_first_placement_refuses_complete_foreign_boundary_before_writes(
        native_rules_guest, fault):
    guest, source, data = native_rules_guest
    if fault in ('foreign-rule', 'unrecorded-target', 'root-link', 'root-writable', 'target-stage'):
        guest.mkdir(fixture.NATIVE_RULES_ROOT)
    if fault == 'foreign-rule': guest.write(fixture.NATIVE_RULES_ROOT + '/10-foreign.rules', b'# keep\n')
    if fault == 'unrecorded-target':
        guest.write(fixture.NATIVE_RULES_FILE, data)
        guest.chown(0, 987, fixture.NATIVE_RULES_FILE)
        guest.chmod(0o644, fixture.NATIVE_RULES_FILE)
    if fault == 'legacy': guest.write(fixture.NATIVE_RULES_LEGACY, b'# keep\n')
    if fault == 'compiled': guest.write(fixture.NATIVE_RULES_COMPILED, data)
    if fault == 'root-link': guest.links[fixture.NATIVE_RULES_ROOT] = '/foreign'
    if fault == 'root-writable': guest.chmod(0o775, fixture.NATIVE_RULES_ROOT)
    if fault == 'source-link': guest.links[source] = '/foreign'
    if fault == 'source-hardlink': guest.nodes[source][0]['st_nlink'] = 2
    if fault == 'source-owner': guest.chown(1000, 0, source)
    if fault == 'source-writable': guest.chmod(0o664, source)
    if fault == 'source-changed': guest.write(source, data + b'# unqualified\n')
    if fault == 'source-semantics':
        guest.write(source, b'allow perm=any all : all\n')
        guest.package_payloads[source] = guest.read_file(source)
    if fault == 'ambiguous-source':
        guest.package_payloads['/usr/share/fapolicyd/95-allow-open.rules'] = data
    if fault == 'target-stage': guest.write(fixture.NATIVE_RULES_PENDING, b'unknown stage')
    if fault == 'receipt-link':
        guest.write(fixture.NATIVE_RULES_RECORD, b'unknown receipt')
        guest.links[fixture.NATIVE_RULES_RECORD] = '/foreign'
    if fault == 'receipt-stage': guest.write(fixture.NATIVE_RULES_RECORD + '.new', b'unknown receipt')
    before = copy.deepcopy(guest.nodes)
    links = dict(guest.links)
    guest.writes.clear()
    with pytest.raises(ValueError):
        fixture.reconcile_native_rules(guest)
    assert guest.nodes == before and guest.links == links and guest.writes == []


@pytest.mark.parametrize('fault', ['target-bytes', 'target-link', 'target-hardlink', 'target-group',
                                 'target-mode', 'target-missing', 'foreign-rule', 'legacy',
                                 'compiled-semantics', 'compiled-link', 'record-owner',
                                 'record-shape', 'source-update'])
def test_native_rules_owned_repeat_refuses_substitution_without_repair(native_rules_guest, fault):
    guest, source, data = native_rules_guest
    fixture.reconcile_native_rules(guest)
    if fault == 'target-bytes': guest.write(fixture.NATIVE_RULES_FILE, data + b'# changed\n')
    if fault == 'target-link': guest.links[fixture.NATIVE_RULES_FILE] = '/foreign'
    if fault == 'target-hardlink': guest.nodes[fixture.NATIVE_RULES_FILE][0]['st_nlink'] = 2
    if fault == 'target-group': guest.chown(0, 42, fixture.NATIVE_RULES_FILE)
    if fault == 'target-mode': guest.chmod(0o664, fixture.NATIVE_RULES_FILE)
    if fault == 'target-missing': guest.rm(fixture.NATIVE_RULES_FILE)
    if fault == 'foreign-rule': guest.write(fixture.NATIVE_RULES_ROOT + '/10-foreign.rules', b'# keep\n')
    if fault == 'legacy': guest.write(fixture.NATIVE_RULES_LEGACY, b'# keep\n')
    if fault in ('compiled-semantics', 'compiled-link'):
        guest.write(fixture.NATIVE_RULES_COMPILED, b'allow perm=execute all : all\n')
        guest.chmod(0o644, fixture.NATIVE_RULES_COMPILED)
        if fault == 'compiled-link': guest.links[fixture.NATIVE_RULES_COMPILED] = '/foreign'
    if fault == 'record-owner': guest.chown(1000, 0, fixture.NATIVE_RULES_RECORD)
    if fault == 'record-shape':
        record = json.loads(guest.read_file(fixture.NATIVE_RULES_RECORD))
        record['unexpected'] = True
        guest.write(fixture.NATIVE_RULES_RECORD, json.dumps(record).encode())
    if fault == 'source-update':
        guest.write(source, data + b'# qualified vendor comment update\n')
        guest.package_payloads[source] = guest.read_file(source)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    for operation in (fixture.verify_native_rules, fixture.reconcile_native_rules):
        with pytest.raises(ValueError): operation(guest)
        assert guest.nodes == before and guest.writes == []


def test_native_rules_native_compiler_output_is_inspected_readonly_without_creating_it(native_rules_guest):
    guest, _, data = native_rules_guest
    fixture.reconcile_native_rules(guest)
    guest.write(fixture.NATIVE_RULES_COMPILED, b'# Native fagenrules output\n' + data)
    guest.chown(0, 987, fixture.NATIVE_RULES_COMPILED)
    guest.chmod(0o644, fixture.NATIVE_RULES_COMPILED)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.verify_native_rules(guest)
    fixture.reconcile_native_rules(guest)
    assert guest.nodes == before and guest.writes == []


@pytest.mark.parametrize('fault', ['link', 'hardlink', 'owner', 'group', 'public-bytes', 'no-intent'])
def test_native_rules_retry_refuses_ambiguous_stage_before_any_write(native_rules_guest, monkeypatch, fault):
    guest, _, _ = native_rules_guest
    actual_write = guest.write
    def write(path, data):
        actual_write(path, data)
        if path == fixture.NATIVE_RULES_PENDING:
            raise OSError('interrupted native stage')
    monkeypatch.setattr(guest, 'write', write)
    with pytest.raises(OSError, match='interrupted native stage'):
        fixture.reconcile_native_rules(guest)
    monkeypatch.setattr(guest, 'write', actual_write)
    if fault == 'link': guest.links[fixture.NATIVE_RULES_PENDING] = '/foreign'
    if fault == 'hardlink': guest.nodes[fixture.NATIVE_RULES_PENDING][0]['st_nlink'] = 2
    if fault == 'owner': guest.chown(1000, 0, fixture.NATIVE_RULES_PENDING)
    if fault == 'group': guest.chown(0, 42, fixture.NATIVE_RULES_PENDING)
    if fault == 'public-bytes':
        guest.chmod(0o644, fixture.NATIVE_RULES_PENDING)
        guest.write(fixture.NATIVE_RULES_PENDING, b'foreign public content\n')
    if fault == 'no-intent': guest.rm(fixture.NATIVE_RULES_RECORD)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile_native_rules(guest)
    assert guest.nodes == before and guest.writes == []


def test_clean_environment_retry_preserves_owned_stage_between_chown_and_chmod(prepared, monkeypatch):
    guest, _ = prepared
    original = guest.chmod
    failed = False
    def interrupted(mode, path):
        nonlocal failed
        if (not failed and mode == 0o644 and path.endswith('.onpc-baseline-new')
                and '/home/onpc-child-riley/' in path):
            failed = True
            assert guest.lstatns(path)['st_uid'] == 1000
            assert stat.S_IMODE(guest.lstatns(path)['st_mode']) == 0o600
            raise RuntimeError('interrupted ownership placement')
        original(mode, path)
    monkeypatch.setattr(guest, 'chmod', interrupted)
    with pytest.raises(RuntimeError, match='interrupted ownership placement'):
        fixture.reconcile_clean(guest)
    monkeypatch.setattr(guest, 'chmod', original)
    fixture.reconcile_clean(guest)
    fixture.verify_clean(guest)


@pytest.mark.parametrize('fault', ['bytes', 'owner', 'link', 'foreign-admission'])
def test_clean_retirement_refuses_ambiguous_legacy_ownership_before_mutation(prepared, fault):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    target = fixture.assets.PREFIX + '/PrismLauncher.AppImage'
    if fault == 'bytes':
        guest.write(target, b'foreign bytes')
    elif fault == 'owner':
        guest.chown(0, 0, target)
    elif fault == 'link':
        guest.links[target] = '/unrelated'
    else:
        guest.write('/etc/fapolicyd/trust.d/foreign.trust',
                    (target + ' 4 ' + 'a' * 64 + '\n').encode())
    prior = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError):
        fixture.reconcile_clean(guest, fixture.prepare_vm.preparation_digest())
    assert guest.nodes == prior and guest.writes == []


def test_clean_retirement_resumes_only_its_exact_durable_members(prepared, monkeypatch):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    original = guest.rm
    removed = []
    def interrupted(path):
        original(path)
        removed.append(path)
        if len(removed) == 3:
            raise RuntimeError('interrupted deletion')
    monkeypatch.setattr(guest, 'rm', interrupted)
    with pytest.raises(RuntimeError, match='interrupted deletion'):
        fixture.reconcile_clean(guest, fixture.prepare_vm.preparation_digest())
    assert guest.exists(fixture.RETIRE_RECORD)
    monkeypatch.setattr(guest, 'rm', original)
    fixture.reconcile_clean(guest, fixture.prepare_vm.preparation_digest())
    fixture.verify_clean(guest)


@pytest.mark.parametrize('boundary', [None, 'write', 'rename', 'record'])
def test_fedora_finite_admission_repeat_update_and_interruption(prepared, monkeypatch, boundary):
    guest, payload = prepared
    guest.set_fedora()
    target = fixture.native_assets.NATIVE_POLICY_PATHS[1]
    temporary = target + '.onpc-baseline-new'
    original_write, original_move = guest.write, guest.mv
    failed = False
    def write(path, data):
        nonlocal failed
        original_write(path, data)
        if boundary == 'write' and path == temporary and not failed:
            failed = True
            raise OSError('interrupted admission')
    def move(source, destination):
        nonlocal failed
        if boundary == 'rename' and source == temporary and not failed:
            failed = True
            raise OSError('interrupted admission')
        original_move(source, destination)
        if boundary == 'record' and source == temporary and not failed:
            failed = True
            raise OSError('interrupted admission')
    monkeypatch.setattr(guest, 'write', write)
    monkeypatch.setattr(guest, 'mv', move)
    if boundary:
        with pytest.raises(OSError, match='interrupted admission'):
            fixture.reconcile(guest, payload)
    fixture.reconcile(guest, payload)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes
    changed = payload | {'A': b'updated distinct A', 'gtk_automation.py': b'updated Python'}
    fixture.reconcile(guest, changed)
    fixture.verify(guest)
    record = json.loads(guest.read_file(fixture.RECORD))
    for path in fixture.native_assets.NATIVE_POLICY_PATHS:
        assert record['files'][path] == {'sha256': guest.checksum('sha256', path),
                                         'mode': 0o644, 'uid': 0, 'gid': 987}
        assert b'uid=1000,1001 :' in guest.read_file(path)
        assert b'trust=0\n' in guest.read_file(path)
    assert hashlib.sha256(changed['A']).hexdigest().encode() in guest.read_file(target)
    assert hashlib.sha256(payload['A']).hexdigest().encode() not in guest.read_file(target)
    assert all(not path.endswith('.onpc-baseline-new') for path in guest.nodes)


@pytest.mark.parametrize('fault', ['collision', 'bytes', 'mode', 'owner', 'group', 'hardlink',
    'link', 'foreign-policy', 'stock-bytes', 'sample-bytes', 'listing-bytes', 'stock-layout', 'uid'])
def test_fedora_admission_refuses_custom_policy_and_stale_owned_rules_without_writes(prepared, fault):
    guest, payload = prepared
    guest.set_fedora()
    target = fixture.native_assets.NATIVE_POLICY_PATHS[0]
    if fault == 'collision':
        guest.write(target, b'foreign')
        guest.chmod(0o644, target)
        guest.chown(0, 987, target)
    else:
        fixture.reconcile(guest, payload)
        if fault == 'bytes': guest.write(target, b'foreign')
        if fault == 'mode': guest.chmod(0o666, target)
        if fault == 'owner': guest.chown(1000, 987, target)
        if fault == 'group': guest.chown(0, 0, target)
        if fault == 'hardlink': guest.nodes[target][0]['st_nlink'] = 2
        if fault == 'link': guest.links[target] = '/foreign'
        if fault == 'foreign-policy': guest.write('/etc/fapolicyd/rules.d/95-administrator.rules', b'deny all')
        if fault == 'stock-bytes': guest.write('/etc/fapolicyd/rules.d/90-deny-execute.rules', b'deny all')
        if fault == 'sample-bytes': guest.write('/usr/share/fapolicyd/sample-rules/90-deny-execute.rules', b'allow all')
        if fault == 'listing-bytes': guest.write('/usr/share/fapolicyd/default-ruleset.known-libs', b'foreign.rules\n')
        if fault == 'stock-layout':
            listing = '/usr/share/fapolicyd/default-ruleset.known-libs'
            # Even an internally valid new RPM inventory needs compatibility
            # review before admissions may cross different native boundaries.
            changed = guest.read_file(listing).replace(b'70-trusted-lang.rules', b'70-new-language-policy.rules')
            guest.write(listing, changed)
            guest.policy_payloads[listing] = changed
        if fault == 'uid':
            guest.write('/etc/passwd', guest.read_file('/etc/passwd').replace(b':1000:1000:', b':1003:1000:'))
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises((ValueError, KeyError)):
        fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


def test_ubuntu_has_no_native_fixture_admission_outputs(prepared):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    assert not set(fixture.native_assets.NATIVE_POLICY_PATHS) & set(guest.nodes)
    assert not set(fixture.native_assets.NATIVE_POLICY_PATHS) & set(json.loads(guest.read_file(fixture.RECORD))['files'])


def pre_admission_fedora_baseline(guest, payload, monkeypatch, old_digest):
    """Build the exact prior declaration and its genuinely bound trust receipt."""
    declaration = fixture.declared_files
    def previous_files(g, identities, source_hashes=None, **options):
        return declaration(g, identities, source_hashes, include_native_policy=False)
    with monkeypatch.context() as previous:
        previous.setattr(fixture, 'declared_files', previous_files)
        previous.setattr(fixture.prepare_vm, 'preparation_digest', lambda: old_digest)
        fixture.reconcile(guest, payload)


@pytest.mark.parametrize('fault', [None, 'current-digest', 'absent-digest', 'wrong-old-digest',
    'partial-record', 'disk-one', 'disk-both', 'stage', 'stage-link', 'stock',
    'fixture', 'record-identity', 'trust-binding'])
def test_recorded_old_fedora_baseline_inspection_is_read_only_and_requires_exact_prior_state(prepared, monkeypatch, fault):
    guest, payload = prepared
    guest.set_fedora()
    old_digest = '1' * 64
    pre_admission_fedora_baseline(guest, payload, monkeypatch, old_digest)
    first, second = fixture.native_assets.NATIVE_POLICY_PATHS
    digest = old_digest
    if fault == 'current-digest': digest = fixture.prepare_vm.preparation_digest()
    if fault == 'absent-digest': digest = None
    if fault == 'wrong-old-digest': digest = '2' * 64
    if fault == 'partial-record':
        record = json.loads(guest.read_file(fixture.RECORD))
        record['files'][first] = {'sha256': 'a' * 64, 'mode': 0o644, 'uid': 0, 'gid': 987}
        guest.write(fixture.RECORD, json.dumps(record).encode())
    if fault in ('disk-one', 'disk-both'):
        for path in ((first,) if fault == 'disk-one' else (first, second)):
            guest.write(path, b'foreign unrecorded admission')
            guest.chmod(0o644, path)
            guest.chown(0, 987, path)
    if fault == 'stage': guest.write(first + '.onpc-baseline-new', b'foreign staging')
    if fault == 'stage-link': guest.links[second + '.onpc-baseline-new'] = '/foreign'
    if fault == 'stock': guest.write('/etc/fapolicyd/rules.d/90-deny-execute.rules', b'changed stock')
    if fault == 'fixture': guest.write(fixture.native_assets.executable_path('A'), b'changed fixture')
    if fault == 'record-identity': guest.chmod(0o644, fixture.RECORD)
    if fault == 'trust-binding':
        transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
        transaction['complete']['preparation_script_sha256'] = '3' * 64
        guest.write(fixture.TRUST_RECORD, json.dumps(transaction).encode())
    before, links = copy.deepcopy(guest.nodes), dict(guest.links)
    guest.writes.clear()
    if fault:
        with pytest.raises(ValueError): fixture.verify(guest, digest)
    else:
        fixture.verify(guest, old_digest)
        assert not set(fixture.native_assets.NATIVE_POLICY_PATHS) & set(guest.nodes)
        # An inspection waiver cannot make this baseline current preparation.
        with pytest.raises(ValueError): fixture.verify(guest)
    assert guest.nodes == before and guest.links == links and not guest.writes


def legacy_native_baseline(guest, payload, monkeypatch):
    """Prepare the prior recorded layout using its finite declaration."""
    current = fixture.assets.files
    def old_files(accounts):
        files = {path: spec for path, spec in current(accounts).items() if '/Versioned/' not in path}
        for path in files:
            if path.endswith('/' + fixture.assets.desktop_id('S')):
                source, mode, role = files[path]
                files[path] = (source.replace(b'/Versioned/', b'/'), mode, role)
        return files
    with monkeypatch.context() as previous:
        previous.setattr(fixture.assets, 'files', old_files)
        fixture.reconcile(guest, payload)


@pytest.mark.parametrize('boundary', [None, 'write', 'rename', 'record'])
def test_safe_versioned_upgrade_is_additive_and_resumes_owned_placement(prepared, monkeypatch, boundary):
    guest, payload = prepared
    legacy_native_baseline(guest, payload, monkeypatch)
    original = copy.deepcopy(guest.nodes)
    target = fixture.assets.PREFIX + '/Versioned/Lunar Client-3.7.17.AppImage'
    temporary = target + '.onpc-baseline-new'
    actual_write, actual_move = guest.write, guest.mv
    failed = False
    def write(path, data):
        nonlocal failed
        actual_write(path, data)
        if not failed and boundary == 'write' and path == temporary:
            failed = True
            raise OSError('interrupted versioned placement')
    def move(source, destination):
        nonlocal failed
        if not failed and boundary == 'rename' and source == temporary:
            failed = True
            raise OSError('interrupted versioned rename')
        actual_move(source, destination)
        if not failed and boundary == 'record' and source == temporary:
            failed = True
            raise OSError('interrupted versioned record')
    monkeypatch.setattr(guest, 'write', write)
    monkeypatch.setattr(guest, 'mv', move)
    if boundary:
        with pytest.raises(OSError, match='interrupted versioned'): fixture.reconcile(guest, payload)
    fixture.reconcile(guest, payload)
    fixture.verify(guest)
    for path, node in original.items():
        if (path in (fixture.RECORD, fixture.TRUST_RECORD)
                or path.endswith('/' + fixture.assets.desktop_id('S'))):
            continue
        assert guest.nodes[path] == node
    assert guest.read_file(target) == payload['S']
    for name in fixture.assets.GUI_FILES:
        assert guest.read_file(fixture.assets.PREFIX + '/Versioned/' + name) == payload[name]
    legacy, = fixture.assets.legacy_executable_paths()
    assert guest.nodes[legacy] == original[legacy]
    assert not any(path.endswith('.onpc-baseline-new') for path in guest.nodes)
    complete = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    assert guest.nodes == complete and not guest.writes


@pytest.mark.parametrize('fault', ['collision', 'link', 'hardlink', 'owner', 'mode', 'bytes', 'staging'])
def test_safe_versioned_inputs_refuse_foreign_or_stale_state_without_writes(prepared, monkeypatch, fault):
    guest, payload = prepared
    target = fixture.assets.PREFIX + '/Versioned/Lunar Client-3.7.17.AppImage'
    if fault == 'collision':
        legacy_native_baseline(guest, payload, monkeypatch)
        owner = fixture.accounts(guest)['other']
        fixture.directory(guest, str(PurePosixPath(target).parent), owner.pw_uid, owner.pw_gid, create=True)
        guest.write(target, payload['S'])
        guest.chown(owner.pw_uid, owner.pw_gid, target)
        guest.chmod(0o755, target)
    else:
        fixture.reconcile(guest, payload)
        if fault == 'link': guest.links[target] = '/foreign'
        if fault == 'hardlink': guest.nodes[target][0]['st_nlink'] = 2
        if fault == 'owner': guest.chown(999, 999, target)
        if fault == 'mode': guest.chmod(0o777, target)
        if fault == 'bytes': guest.write(target, b'foreign')
        if fault == 'staging': guest.write(target + '.onpc-baseline-new', b'foreign')
    before = copy.deepcopy(guest.nodes)
    links = dict(guest.links)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and guest.links == links and not guest.writes


@pytest.mark.parametrize('fault', ['missing', 'empty', 'aliased-trusted', 'aliased-untrusted'])
def test_trusted_payload_substitution_is_refused_before_any_write(prepared, fault):
    guest, payload = prepared
    if fault == 'missing': del payload['trusted-hard']
    if fault == 'empty': payload['trusted-hard'] = b''
    if fault == 'aliased-trusted': payload['trusted-hard'] = payload['trusted-soft']
    if fault == 'aliased-untrusted': payload['trusted-hard'] = payload['mechanical']
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


def test_native_tool_paths_are_closed_and_shared_by_preparation_and_live_readers():
    from tests.fixtures.native_trust import native_tool_paths
    assert native_tool_paths('ubuntu') == {
        'daemon': '/usr/sbin/fapolicyd', 'cli': '/usr/sbin/fapolicyd-cli'}
    assert native_tool_paths('fedora') == {
        'daemon': '/usr/bin/fapolicyd', 'cli': '/usr/bin/fapolicyd-cli'}
    for invalid in ('debian', 'Fedora', '', None):
        with pytest.raises(ValueError): native_tool_paths(invalid)


@pytest.mark.parametrize('fault', ['missing-alias', 'alias-owner', 'alias-target',
                                 'tool-alias', 'canonical-tool-link', 'canonical-directory-link'])
def test_fedora_native_tool_alias_guard_preserves_strict_canonical_fixture_guards(prepared, monkeypatch, fault):
    guest, payload = prepared
    guest.set_fedora()
    if fault == 'missing-alias':
        guest.nodes.pop('/usr/sbin')
        guest.links.pop('/usr/sbin')
    if fault == 'alias-owner': guest.chown(1000, 1000, '/usr/sbin')
    if fault == 'alias-target': guest.links['/usr/sbin'] = '/foreign'
    if fault == 'tool-alias':
        actual_realpath = guest.realpath
        monkeypatch.setattr(guest, 'realpath', lambda path:
                            '/foreign' if path == '/usr/sbin/fapolicyd-cli' else actual_realpath(path))
    if fault == 'canonical-tool-link': guest.links['/usr/bin/fapolicyd-cli'] = '/foreign'
    if fault == 'canonical-directory-link': guest.links['/usr/bin'] = '/foreign'
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('prefix', ['', '/'])
def test_native_find_separator_is_normalized_without_changing_trust_scope(prepared, monkeypatch, prefix):
    guest, payload = prepared
    path = '/etc/fapolicyd/trust.d/administrator.trust'
    guest.write(path, b'/administrator 1 ' + b'a' * 64 + b'\n')
    before = copy.deepcopy(guest.nodes[path])
    actual_find = guest.find
    monkeypatch.setattr(guest, 'find', lambda root: [prefix + name for name in actual_find(root)])
    fixture.reconcile(guest, payload)
    fixture.verify_trusted(guest)
    assert guest.nodes[path] == before


@pytest.mark.parametrize('names', [
    [''], ['/'], ['//administrator.trust'], ['../outside'], ['/../outside'],
    ['nested/../administrator.trust'], ['nested//file'], ['./administrator.trust'],
    ['nested/./file'], ['bad\x00name'], ['/etc/fapolicyd/trust.d/administrator.trust'],
    ['administrator.trust', '/administrator.trust'], ['missing.trust'],
])
def test_native_find_rejects_unsafe_ambiguous_or_missing_entries_before_any_write(prepared, monkeypatch, names):
    guest, payload = prepared
    guest.write('/etc/fapolicyd/trust.d/administrator.trust', b'/administrator 1 ' + b'a' * 64 + b'\n')
    monkeypatch.setattr(guest, 'find', lambda root: names)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError, match='trust-enumeration-unsafe'):
        fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('gid', [0, 42, 999])
def test_readonly_foreign_trust_scan_accepts_nonwritable_root_owned_vendor_group_without_adoption(prepared, legacy, gid):
    guest, payload = prepared
    path = ('/etc/fapolicyd/fapolicyd.trust' if legacy else
            '/etc/fapolicyd/trust.d/administrator.trust')
    guest.write(path, b'/administrator 1 ' + b'a' * 64 + b'\n')
    guest.chown(0, gid, path)
    guest.chmod(0o644, path)
    before = copy.deepcopy(guest.nodes[path])
    fixture.reconcile(guest, payload)
    fixture.verify_trusted(guest)
    assert guest.nodes[path] == before
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    assert guest.nodes[path] == before and not guest.writes


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('fault', ['owner', 'hardlink', 'symlink', 'type', 'mode'])
def test_foreign_trust_metadata_refusal_retains_only_fixed_safe_predicates(prepared, legacy, fault):
    guest, payload = prepared
    path = ('/etc/fapolicyd/fapolicyd.trust' if legacy else
            '/etc/fapolicyd/trust.d/private-person-secret.trust')
    guest.write(path, b'private trust payload')
    guest.chown(0, 42, path)
    guest.chmod(0o644, path)
    if fault == 'owner': guest.chown(1000, 42, path)
    if fault == 'hardlink': guest.nodes[path][0]['st_nlink'] = 2
    if fault == 'symlink':
        guest.nodes[path][0]['st_mode'] = stat.S_IFLNK | 0o777
        guest.links[path] = '/private-target'
    if fault == 'type': guest.nodes[path][0]['st_mode'] = stat.S_IFIFO | 0o644
    if fault == 'mode': guest.chmod(0o664, path)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(fixture.ForeignTrustMetadataError) as caught:
        fixture.reconcile(guest, payload)
    diagnostic = str(caught.value)
    assert diagnostic.startswith('baseline:fixtures-foreign-trust-metadata;sourcekind='
                                 + ('legacy' if legacy else 'fragment'))
    assert ';root_group=0;' in diagnostic
    assert all(private not in diagnostic for private in (path, 'private', '42', '1000'))
    for key in ('root_owner', 'canonical', 'regular', 'singlylinked', 'mode'):
        assert ';' + key + '=' in diagnostic
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('path', [fixture.TRUST_FILE, fixture.TRUST_RECORD,
                                fixture.assets.TRUSTED_NATIVE['trusted-hard'][0]])
def test_owned_trust_and_fixture_outputs_refuse_unexpected_group(prepared, path):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    guest.chown(0, 42, path)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('fault,predicate', [('owner', 'root_owner=0'), ('group', 'root_group=0'),
                                          ('hardlink', 'singlylinked=0'), ('link', 'canonical=0'),
                                          ('type', 'regular=0'), ('mode', 'mode=0644')])
def test_owned_fragment_reports_exact_safe_metadata_predicate_without_repair(prepared, fault, predicate):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    path = fixture.TRUST_FILE
    if fault == 'owner': guest.chown(1000, 0, path)
    if fault == 'group': guest.chown(0, 42, path)
    if fault == 'hardlink': guest.nodes[path][0]['st_nlink'] = 2
    if fault == 'link': guest.links[path] = '/private-substitution'
    if fault == 'type': guest.nodes[path][0]['st_mode'] = stat.S_IFIFO | 0o600
    if fault == 'mode': guest.chmod(0o644, path)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(fixture.OwnedTrustMetadataError) as caught:
        fixture.reconcile(guest, payload)
    diagnostic = str(caught.value)
    assert diagnostic.startswith('baseline:fixtures-owned-trust-metadata;sourcekind=owned-fragment;')
    assert predicate in diagnostic
    assert ';native_group=' + ('0' if fault in ('owner', 'group') else '1') in diagnostic
    assert path not in diagnostic and 'private' not in diagnostic and '1000' not in diagnostic
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('os_id', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('gid', [0, 987])
def test_recorded_legacy_trust_bytes_migrate_only_to_fixed_native_group(prepared, os_id, gid):
    guest, payload = prepared
    if os_id == 'fedora': guest.set_fedora()
    fixture.reconcile(guest, payload)
    transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
    del transaction['complete']['native']['service_gid']
    del transaction['complete']['trust_file_metadata']
    fixture.write_record(guest, transaction, fixture.TRUST_RECORD)
    guest.chown(0, gid, fixture.TRUST_FILE)
    before = {path: copy.deepcopy(guest.nodes[path]) for path in fixture.declared_files(
        guest, fixture.accounts(guest))}
    trust_bytes = guest.read_file(fixture.TRUST_FILE)
    fixture.reconcile(guest, payload)
    record = fixture.verify_trusted(guest)
    assert record['native']['service_gid'] == 987
    assert record['trust_file_metadata'] == {'mode': 0o600, 'uid': 0, 'gid': 987}
    assert guest.lstatns(fixture.TRUST_FILE)['st_gid'] == 987
    assert guest.read_file(fixture.TRUST_FILE) == trust_bytes
    assert all(guest.nodes[path] == node for path, node in before.items())


@pytest.mark.parametrize('legacy,gid,substitute', [(True, 42, False), (True, 987, True),
                                                 (False, 0, False), (False, 42, False)])
def test_native_group_binding_never_adopts_foreign_group_or_unrecorded_bytes(prepared, legacy, gid, substitute):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    if legacy:
        transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
        del transaction['complete']['native']['service_gid']
        del transaction['complete']['trust_file_metadata']
        fixture.write_record(guest, transaction, fixture.TRUST_RECORD)
    guest.chown(0, gid, fixture.TRUST_FILE)
    if substitute: guest.write(fixture.TRUST_FILE, guest.read_file(fixture.TRUST_FILE) + b'# foreign\n')
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'zero', 'negative', 'overflow',
                                 'nonascii', 'malformed', 'owner', 'mode', 'link', 'hardlink', 'changed'])
def test_fixed_native_group_must_be_unambiguous_root_owned_and_nonzero_before_writes(prepared, fault):
    guest, payload = prepared
    if fault == 'changed': fixture.reconcile(guest, payload)
    if fault == 'missing': guest.write('/etc/group', b'root:x:0:\n')
    if fault == 'duplicate': guest.write('/etc/group', b'fapolicyd:x:987:\nfapolicyd:x:988:\n')
    value = {'zero': '0', 'negative': '-1', 'overflow': str(2 ** 32),
             'nonascii': '\u0661', 'changed': '988'}.get(fault)
    if value is not None: guest.write('/etc/group', f'fapolicyd:x:{value}:\n'.encode())
    if fault == 'malformed': guest.write('/etc/group', b'fapolicyd:x:987\n')
    if fault == 'owner': guest.chown(1000, 0, '/etc/group')
    if fault == 'mode': guest.chmod(0o664, '/etc/group')
    if fault == 'link': guest.links['/etc/group'] = '/foreign'
    if fault == 'hardlink': guest.nodes['/etc/group'][0]['st_nlink'] = 2
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('field,value', [('mode', 0o644), ('mode', True), ('uid', 1000),
                                      ('gid', 0), ('gid', 42), ('gid', True),
                                      ('service_gid', 0), ('service_gid', True), ('service_gid', 2 ** 32)])
def test_trust_schema_binds_exact_native_metadata(prepared, field, value):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    record = fixture.verify_trusted(guest)
    record['native' if field == 'service_gid' else 'trust_file_metadata'][field] = value
    with pytest.raises(ValueError): fixture.validate_trusted_shape(record)


@pytest.mark.parametrize('published_legacy', [False, True])
def test_native_staging_group_survives_two_interruptions_without_losing_digest_proof(prepared, monkeypatch, published_legacy):
    guest, payload = prepared
    if published_legacy:
        fixture.reconcile(guest, payload)
        transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
        del transaction['complete']['native']['service_gid']
        del transaction['complete']['trust_file_metadata']
        fixture.write_record(guest, transaction, fixture.TRUST_RECORD)
        guest.chown(0, 0, fixture.TRUST_FILE)
    actual_chown, actual_move = guest.chown, guest.mv
    failures = 0
    def chown(uid, gid, path):
        nonlocal failures
        actual_chown(uid, gid, path)
        if failures == 0 and path == fixture.TRUST_PENDING and gid == 987:
            failures += 1
            raise OSError('after final native group assignment')
    def move(source, target):
        nonlocal failures
        actual_move(source, target)
        if failures == 1 and target == fixture.TRUST_RECORD:
            intent = json.loads(guest.read_file(target))['pending']
            if intent and intent['trust_file_sha256'] is None:
                failures += 1
                raise OSError('after retry intent before staging write')
    monkeypatch.setattr(guest, 'chown', chown)
    monkeypatch.setattr(guest, 'mv', move)
    for _ in range(2):
        with pytest.raises(OSError): fixture.reconcile(guest, payload)
    fixture.reconcile(guest, payload)
    assert failures == 2 and not guest.exists(fixture.TRUST_PENDING)
    fixture.verify_trusted(guest)


@pytest.mark.parametrize('fault', ['foreign-group', 'mode', 'owner', 'link', 'hardlink', 'no-intent'])
def test_staged_native_group_never_relaxes_private_identity_or_durable_intent(prepared, monkeypatch, fault):
    guest, payload = prepared
    def interrupt(argv):
        if argv[1:2] == ['--file']:
            guest.write(fixture.TRUST_PENDING, b'partial native write')
            raise OSError('native write interrupted')
        return actual(argv)
    actual = guest.command
    monkeypatch.setattr(guest, 'command', interrupt)
    with pytest.raises(OSError): fixture.reconcile(guest, payload)
    guest.chown(0, 42 if fault == 'foreign-group' else 987, fixture.TRUST_PENDING)
    if fault == 'mode': guest.chmod(0o640, fixture.TRUST_PENDING)
    if fault == 'owner': guest.chown(1000, 987, fixture.TRUST_PENDING)
    if fault == 'link': guest.links[fixture.TRUST_PENDING] = '/foreign'
    if fault == 'hardlink': guest.nodes[fixture.TRUST_PENDING][0]['st_nlink'] = 2
    if fault == 'no-intent':
        transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
        transaction['pending'] = None
        fixture.write_record(guest, transaction, fixture.TRUST_RECORD)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('os_id,stage', [('ubuntu', 'trust'), ('fedora', 'trust'), ('ubuntu', 'backend')])
def test_public_retry_after_native_tmpfiles_group_normalization_regenerates_private_partial_stage(prepared, monkeypatch, os_id, stage):
    guest, payload = prepared
    if os_id == 'fedora': guest.set_fedora()
    guest.chown(0, 987, fixture.BACKEND_CONFIG)
    if stage == 'backend':
        guest.write(fixture.BACKEND_CONFIG, b'trust = debdb\n')
    actual_write, actual_command = guest.write, guest.command
    failed = False
    def write(path, data):
        nonlocal failed
        if stage == 'backend' and not failed and path == fixture.BACKEND_PENDING:
            actual_write(path, b'partial native config')
            failed = True
            raise OSError('interrupted backend write')
        actual_write(path, data)
    def command(argv):
        nonlocal failed
        if stage == 'trust' and not failed and argv[1:2] == ['--file']:
            actual_write(fixture.TRUST_PENDING, b'partial native trust')
            failed = True
            raise OSError('interrupted native trust write')
        return actual_command(argv)
    monkeypatch.setattr(guest, 'write', write)
    monkeypatch.setattr(guest, 'command', command)
    with pytest.raises(OSError): fixture.reconcile(guest, payload)
    pending = fixture.TRUST_PENDING if stage == 'trust' else fixture.BACKEND_PENDING
    assert stat.S_IMODE(guest.lstatns(pending)['st_mode']) == 0o600
    # Public preparation boots its guest setup before offline reconciliation.
    # Native `Z /etc/fapolicyd - root fapolicyd -` changes groups, not modes.
    for path in tuple(guest.nodes):
        if path == '/etc/fapolicyd' or path.startswith('/etc/fapolicyd/'):
            guest.chown(0, 987, path)
    fixture.reconcile(guest, payload)
    fixture.verify_trusted(guest)
    assert not guest.exists(pending)
    assert b'partial' not in guest.read_file(fixture.TRUST_FILE)


@pytest.mark.parametrize('os_id,sources', [('ubuntu', 'debdb'), ('ubuntu', 'file,debdb'),
                                        ('fedora', 'rpmdb,file'), ('fedora', 'file,rpmdb')])
def test_backend_preparation_preserves_native_config_bytes_metadata_and_source_order(prepared, monkeypatch, os_id, sources):
    guest, payload = prepared
    if os_id == 'fedora': guest.set_fedora()
    before = ('# native options\r\n  trust\t= ' + sources + '  # preserve\r\nintegrity = none\r\n').encode()
    guest.write(fixture.BACKEND_CONFIG, before)
    guest.chown(0, 42, fixture.BACKEND_CONFIG)
    guest.chmod(0o640, fixture.BACKEND_CONFIG)
    metadata = guest.lstatns(fixture.BACKEND_CONFIG)
    commands = []
    actual = guest.command
    monkeypatch.setattr(guest, 'command', lambda argv: (commands.append(argv), actual(argv))[1])
    fixture.reconcile(guest, payload)
    after = before.replace(b'debdb', b'debdb,file', 1) if sources == 'debdb' else before
    assert guest.read_file(fixture.BACKEND_CONFIG) == after
    current = guest.lstatns(fixture.BACKEND_CONFIG)
    assert all(current[key] == metadata[key] for key in ('st_mode', 'st_uid', 'st_gid'))
    if sources != 'debdb': assert current == metadata
    record = json.loads(guest.read_file(fixture.BACKEND_RECORD))
    assert bytes.fromhex(record['before_hex']) == before and bytes.fromhex(record['after_hex']) == after
    assert record['complete'] is True
    provenance = fixture.verify_trusted(guest)
    assert provenance['backend']['sources'] == fixture.file_backend_sources(after, os_id)
    first_check = commands.index([fixture.native_tool_paths(os_id)['cli'], '--check-config'])
    assert all(index > first_check for index, argv in enumerate(commands) if '--file' in argv)
    nodes = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    assert guest.nodes == nodes and not guest.writes


@pytest.mark.parametrize('placement', ['legacy', 'fragment', 'nested'])
def test_backend_activation_refuses_unrelated_inactive_trust_before_any_write(prepared, placement):
    guest, payload = prepared
    guest.write(fixture.BACKEND_CONFIG, b'trust = debdb\n')
    path = '/etc/fapolicyd/fapolicyd.trust'
    if placement != 'legacy':
        if placement == 'nested': guest.mkdir('/etc/fapolicyd/trust.d/admin')
        path = '/etc/fapolicyd/trust.d/' + ('admin/' if placement == 'nested' else '') + 'administrator.trust'
    guest.write(path, b'# administrator record\n/administrator 123 ' + b'a' * 64 + b'\n')
    nodes = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError, match='inactive-foreign-trust'): fixture.reconcile(guest, payload)
    assert guest.nodes == nodes and not guest.writes


def test_backend_migrates_only_old_record_proven_fixture_fragment(prepared):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    # Previous preparer published these exact entries but did not enable file.
    transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
    del transaction['complete']['backend']
    del transaction['complete']['trust_file_metadata']
    del transaction['complete']['native']['service_gid']
    guest.write(fixture.TRUST_RECORD, json.dumps(transaction).encode())
    guest.nodes.pop(fixture.BACKEND_RECORD)
    guest.write(fixture.BACKEND_CONFIG, b'# old native default\ntrust = debdb\n')
    untrusted = {path: copy.deepcopy(guest.nodes[path]) for path, _ in fixture.assets.NATIVE.values()}
    fixture.reconcile(guest, payload)
    fixture.verify_trusted(guest)
    assert guest.read_file(fixture.BACKEND_CONFIG) == b'# old native default\ntrust = debdb,file\n'
    assert all(guest.nodes[path] == node for path, node in untrusted.items())


@pytest.mark.parametrize('contents', [b'# missing\n', b'trust = debdb\ntrust = file\n',
                                     b'trust = administrator\n', b'trust = debdb,file,file\n'])
def test_backend_refuses_unrecognized_native_source_declaration_before_writes(prepared, contents):
    guest, payload = prepared
    guest.write(fixture.BACKEND_CONFIG, contents)
    nodes = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == nodes and not guest.writes


@pytest.mark.parametrize('boundary', ['intent', 'partial-write', 'metadata', 'publish', 'native-check', 'complete'])
def test_backend_interrupted_owned_enablement_retries_before_any_trust_publication(prepared, monkeypatch, boundary):
    guest, payload = prepared
    original = b'# preserve all native options\ntrust = debdb\nintegrity = none\n'
    guest.write(fixture.BACKEND_CONFIG, original)
    guest.chown(0, 42, fixture.BACKEND_CONFIG)
    actual_write, actual_move, actual_chown, actual_command = guest.write, guest.mv, guest.chown, guest.command
    failed = False

    def write(path, data):
        nonlocal failed
        if not failed and boundary == 'partial-write' and path == fixture.BACKEND_PENDING:
            actual_write(path, data[:5])
            failed = True
            raise OSError('interrupted config write')
        actual_write(path, data)

    def chown(uid, gid, path):
        nonlocal failed
        actual_chown(uid, gid, path)
        if not failed and boundary == 'metadata' and path == fixture.BACKEND_PENDING and gid == 42:
            failed = True
            raise OSError('interrupted config metadata')

    def move(source, target):
        nonlocal failed
        actual_move(source, target)
        record = json.loads(guest.read_file(target)) if target == fixture.BACKEND_RECORD else None
        if not failed and ((boundary == 'intent' and record and not record['complete'])
                           or (boundary == 'complete' and record and record['complete'])
                           or (boundary == 'publish' and target == fixture.BACKEND_CONFIG)):
            failed = True
            raise OSError('interrupted config publication')

    def command(argv):
        nonlocal failed
        if not failed and boundary == 'native-check' and argv[1:] == ['--check-config']:
            failed = True
            raise RuntimeError('native check failed')
        return actual_command(argv)

    monkeypatch.setattr(guest, 'write', write)
    monkeypatch.setattr(guest, 'chown', chown)
    monkeypatch.setattr(guest, 'mv', move)
    monkeypatch.setattr(guest, 'command', command)
    with pytest.raises((OSError, RuntimeError)): fixture.reconcile(guest, payload)
    assert not guest.exists(fixture.TRUST_FILE)
    fixture.reconcile(guest, payload)
    fixture.verify_trusted(guest)
    assert guest.read_file(fixture.BACKEND_CONFIG) == original.replace(b'debdb', b'debdb,file')
    assert not guest.exists(fixture.BACKEND_PENDING)


@pytest.mark.parametrize('field,value', [('mode', 0o666), ('uid', 1000), ('gid', -1), ('gid', 2 ** 32)])
def test_backend_shape_metadata_guards_apply_equally_to_fedora(prepared, field, value):
    guest, payload = prepared
    guest.set_fedora()
    fixture.reconcile(guest, payload)
    record = fixture.verify_trusted(guest)
    record['backend'][field] = value
    with pytest.raises(ValueError): fixture.validate_trusted_shape(record)


def test_native_launchers_upgrade_both_child_catalogues_without_rewriting_existing_files(prepared, monkeypatch):
    guest, payload = prepared
    declaration = fixture.assets.files
    riley_prefix = '/home/onpc-child-riley/.local/share/applications/com.puffyslippers.ONPCTest.'
    # Reproduce the old baseline, whose native launchers existed only for Jordan.
    with monkeypatch.context() as previous:
        previous.setattr(fixture.assets, 'files', lambda accounts: {
            path: spec for path, spec in declaration(accounts).items()
            if not path.startswith(riley_prefix)})
        fixture.reconcile(guest, payload)
    before = copy.deepcopy(guest.nodes)
    fixture.reconcile(guest, payload)
    for path, node in before.items():
        if path not in (fixture.RECORD, fixture.TRUST_RECORD):
            assert guest.nodes[path] == node
    accounts = fixture.accounts(guest)
    for role in ('child', 'other'):
        for asset in fixture.assets.ASSETS:
            path = accounts[role].pw_dir + '/.local/share/applications/' + fixture.assets.desktop_id(asset[0])
            assert guest.read_file(path) == fixture.assets.desktop_entry(asset).encode()
            fixture.regular(guest, path, accounts[role].pw_uid, accounts[role].pw_gid, 0o644)
    after = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    fixture.verify(guest)
    assert guest.nodes == after and guest.writes == []


@pytest.mark.parametrize('boundary', ['write', 'chown', 'rename', 'record'])
def test_interrupted_placement_retries_only_owned_work(prepared, monkeypatch, boundary):
    guest, payload = prepared
    actual_write, actual_move = guest.write, guest.mv
    actual_chown = guest.chown
    failed = False
    def write(path, data):
        nonlocal failed
        if not failed and boundary == 'write' and path.endswith('.onpc-baseline-new'):
            failed = True
            actual_write(path, data[:3])
            raise OSError('interrupted')
        actual_write(path, data)
    def chown(uid, gid, path):
        nonlocal failed
        actual_chown(uid, gid, path)
        if not failed and boundary == 'chown' and uid != 0 and path.endswith('.onpc-baseline-new'):
            failed = True
            raise OSError('interrupted')
    def move(source, target):
        nonlocal failed
        if not failed and boundary == 'rename' and source.endswith('.onpc-baseline-new'):
            failed = True
            raise OSError('interrupted')
        actual_move(source, target)
        if not failed and boundary == 'record' and source.endswith('.onpc-baseline-new'):
            failed = True
            raise OSError('interrupted')
    monkeypatch.setattr(guest, 'write', write)
    monkeypatch.setattr(guest, 'mv', move)
    monkeypatch.setattr(guest, 'chown', chown)
    with pytest.raises(OSError): fixture.reconcile(guest, payload)
    fixture.reconcile(guest, payload)
    fixture.verify(guest)
    assert not any(path.endswith('.onpc-baseline-new') for path in guest.nodes)


@pytest.mark.parametrize('fault', ['collision', 'link', 'hardlink', 'owner', 'mode', 'parent', 'bytes'])
def test_refuses_foreign_or_tampered_inputs_before_any_write(prepared, fault):
    guest, payload = prepared
    path = fixture.assets.PREFIX + '/Exact Fixture.AppImage'
    if fault == 'collision':
        guest.write(path, b'foreign')
        guest.chown(1001, 1001, path)
        guest.chmod(0o755, path)
    else:
        fixture.reconcile(guest, payload)
        if fault == 'link': guest.links[path] = '/foreign'
        if fault == 'hardlink': guest.nodes[path][0]['st_nlink'] = 2
        if fault == 'owner': guest.nodes[path][0]['st_uid'] = 999
        if fault == 'mode': guest.chmod(0o777, path)
        if fault == 'parent': guest.links[fixture.assets.PREFIX] = '/foreign'
        if fault == 'bytes': guest.write(path, b'foreign')
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and guest.writes == []


def test_missing_baseline_is_a_read_only_refusal(prepared):
    guest, _ = prepared
    before = copy.deepcopy(guest.nodes)
    with pytest.raises(KeyError): fixture.verify(guest)
    assert guest.nodes == before


def test_folder_renamer_overrides_are_owned_idempotent_and_preserve_folder_state(prepared):
    guest, payload = prepared
    accounts = fixture.accounts(guest)
    for role in ('child', 'other', 'parent'):
        config = accounts[role].pw_dir + '/.config'
        guest.mkdir(config)
        guest.chown(accounts[role].pw_uid, accounts[role].pw_gid, config)
        guest.write(config + '/user-dirs.dirs', b'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n')
        guest.write(config + '/user-dirs.locale', b'en_US')
    before = copy.deepcopy(guest.nodes)
    fixture.reconcile(guest, payload)
    for path, node in before.items():
        assert guest.nodes[path] == node
    declared = fixture.assets.desktop_settings_files(accounts)
    assert len(declared) == 6
    for path, (content, mode, role) in declared.items():
        assert guest.read_file(path) == content
        fixture.regular(guest, path, accounts[role].pw_uid, accounts[role].pw_gid, mode)
        if path.endswith('.desktop'):
            assert b'Hidden=true\n' in content
        else:
            assert path.endswith('/user-dirs-update-gtk.service') and content == b''
    after = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    fixture.verify(guest)
    assert guest.nodes == after and guest.writes == []


@pytest.mark.parametrize('fault', ['collision', 'link', 'hardlink', 'owner', 'parent', 'bytes', 'missing'])
@pytest.mark.parametrize('suffix', ['autostart/user-dirs-update-gtk.desktop',
                                  'systemd/user/user-dirs-update-gtk.service'])
def test_folder_renamer_overrides_refuse_unsafe_or_stale_state_without_writes(prepared, fault, suffix):
    guest, payload = prepared
    path = '/home/onpc-child-jordan/.config/' + suffix
    if fault == 'collision':
        guest.write(path, b'foreign')
        guest.chown(1001, 1001, path)
        guest.chmod(0o644, path)
    else:
        fixture.reconcile(guest, payload)
        if fault == 'link': guest.links[path] = '/foreign'
        if fault == 'hardlink': guest.nodes[path][0]['st_nlink'] = 2
        if fault == 'owner': guest.nodes[path][0]['st_uid'] = 999
        if fault == 'parent': guest.links[str(PurePosixPath(path).parent)] = '/foreign'
        if fault == 'bytes': guest.write(path, b'foreign')
        if fault == 'missing': del guest.nodes[path]
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises((ValueError, KeyError)):
        (fixture.reconcile(guest, payload) if fault == 'collision' else fixture.verify(guest))
    assert guest.nodes == before and guest.writes == []


def test_ubuntu_apt_masks_upgrade_the_owned_inventory_and_repeat_without_writes(prepared, monkeypatch):
    guest, payload = prepared
    with monkeypatch.context() as previous:
        previous.setattr(fixture.assets, 'automatic_update_files', lambda os_id: {})
        fixture.reconcile(guest, payload)
    before = copy.deepcopy(guest.nodes)
    fixture.reconcile(guest, payload)
    expected = {'/etc/systemd/system/' + unit for unit in (
        'apt-daily.timer', 'apt-daily.service',
        'apt-daily-upgrade.timer', 'apt-daily-upgrade.service')}
    assert set(fixture.assets.automatic_update_files('ubuntu')) == expected
    for path in expected:
        assert guest.read_file(path) == b''
        fixture.regular(guest, path, 0, 0, 0o644)
    for path, node in before.items():
        if path not in (fixture.RECORD, fixture.TRUST_RECORD):
            assert guest.nodes[path] == node
    after = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    fixture.verify(guest)
    assert guest.nodes == after and guest.writes == []


def test_fedora_fixture_inventory_does_not_add_ubuntu_apt_controls(prepared):
    guest, payload = prepared
    guest.set_fedora()
    fixture.reconcile(guest, payload)
    fixture.verify(guest)
    assert fixture.assets.automatic_update_files('fedora') == {}
    assert not any(path.startswith('/etc/systemd/system/apt-daily') for path in guest.nodes)


@pytest.mark.parametrize('os_id', ['ubuntu', 'fedora'])
def test_trusted_variants_bind_native_api_exact_payloads_and_baseline_without_changing_untrusted(prepared, monkeypatch, os_id):
    guest, payload = prepared
    if os_id == 'fedora':
        guest.set_fedora()
    commands = []
    actual = guest.command
    monkeypatch.setattr(guest, 'command', lambda argv: (commands.append(argv), actual(argv))[1])
    fixture.reconcile(guest, payload)
    provenance = fixture.verify_trusted(guest)
    assert provenance['native']['os_id'] == os_id
    assert provenance['preparation_script_sha256'] == fixture.prepare_vm.preparation_digest()
    assert provenance['fixture_record_sha256'] == hashlib.sha256(guest.read_file(fixture.RECORD)).hexdigest()
    assert set(provenance['files']) == set(fixture.assets.trusted_file_modes())
    assert len({spec['sha256'] for spec in provenance['files'].values()}) == 5
    for identity, (path, suffix) in fixture.assets.TRUSTED_NATIVE.items():
        assert guest.read_file(path) == payload[identity]
        assert guest.read_file('/usr/share/applications/com.puffyslippers.ONPCTest.' + suffix + '.desktop').count(path.encode()) == 1
    for path, _ in fixture.assets.NATIVE.values():
        assert guest.read_file(path) == payload['mechanical']
        assert path not in fixture.trust_entries(guest.read_file(fixture.TRUST_FILE))
    cli = fixture.native_tool_paths(os_id)['cli']
    trust_commands = [argv for argv in commands if argv[0] == cli and argv[1] == '--file']
    assert trust_commands == [
        [cli, '--file', 'add', path,
         '--trust-file', PurePosixPath(fixture.TRUST_PENDING).name]
        for path in fixture.assets.trusted_file_modes()]
    assert not any('--update' in argv or '--reload-rules' in argv for argv in commands)
    before = copy.deepcopy(guest.nodes)
    commands.clear()
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes
    assert not any(argv[0] == cli and argv[1] == '--file' for argv in commands)


def test_trusted_native_inventory_upgrades_old_baseline_without_rewriting_untrusted_files(prepared, monkeypatch):
    guest, payload = prepared
    declaration = fixture.assets.files
    trusted = {path for path, _ in fixture.assets.TRUSTED_NATIVE.values()}
    trusted.update('/usr/share/applications/com.puffyslippers.ONPCTest.' + suffix + '.desktop'
                   for _, suffix in fixture.assets.TRUSTED_NATIVE.values())
    with monkeypatch.context() as old:
        old.setattr(fixture.assets, 'files', lambda identities: {
            path: spec for path, spec in declaration(identities).items() if path not in trusted})
        old.setattr(fixture, 'preflight_trusted', lambda g: None)
        old.setattr(fixture, 'reconcile_trusted', lambda g, txn: None)
        old.setattr(fixture, 'verify_trusted', lambda *args: None)
        fixture.reconcile(guest, payload)
    before = copy.deepcopy(guest.nodes)
    fixture.reconcile(guest, payload)
    for path, node in before.items():
        if path != fixture.RECORD:
            assert guest.nodes[path] == node
    fixture.verify_trusted(guest)


@pytest.mark.parametrize('interrupted', [False, True])
def test_activity_upgrade_preserves_old_trust_and_controls_and_retries_new_admission(prepared, monkeypatch, interrupted):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    activity_paths = {fixture.assets.ACTIVITY_EXECUTABLE,
                      *(fixture.assets.ACTIVITY_PREFIX + '/' + name for name in fixture.assets.GUI_FILES)}
    files = json.loads(guest.read_file(fixture.RECORD))
    for path in activity_paths:
        del guest.nodes[path]
        del files['files'][path]
    guest.write(fixture.RECORD, json.dumps(files).encode())
    transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
    old = transaction['complete']
    old['files'] = {path: spec for path, spec in old['files'].items() if path not in activity_paths}
    trust = b''.join(line for line in guest.read_file(fixture.TRUST_FILE).splitlines(keepends=True)
                     if line.split()[0].decode() not in activity_paths)
    guest.write(fixture.TRUST_FILE, trust)
    old['fixture_record_sha256'] = hashlib.sha256(guest.read_file(fixture.RECORD)).hexdigest()
    old['trust_file_sha256'] = hashlib.sha256(trust).hexdigest()
    guest.write(fixture.TRUST_RECORD, json.dumps(transaction).encode())
    preserved = {path: copy.deepcopy(guest.nodes[path]) for path in files['files']}
    commands, failed = [], False
    actual = guest.command

    def command(argv):
        nonlocal failed
        commands.append(argv)
        if interrupted and not failed and argv[1:3] == ['--file', 'add']:
            failed = True
            guest.write(fixture.TRUST_PENDING, b'partial native admission')
            raise RuntimeError('interrupted activity admission')
        return actual(argv)

    monkeypatch.setattr(guest, 'command', command)
    if interrupted:
        with pytest.raises(RuntimeError, match='interrupted activity admission'):
            fixture.reconcile(guest, payload)
    fixture.reconcile(guest, payload)
    fixture.verify_trusted(guest)
    assert all(guest.nodes[path] == node for path, node in preserved.items())
    assert all(guest.lstatns(path)['st_uid'] == 0 for path in activity_paths)
    assert all(argv[2] == ('add' if argv[3] in activity_paths else 'update')
               for argv in commands if argv[1:2] == ['--file'])
    assert set(fixture.trust_entries(guest.read_file(fixture.TRUST_FILE))) == set(fixture.assets.trusted_file_modes())


@pytest.mark.parametrize('boundary', ['intent', 'cli-partial', 'cli-finished', 'generated-record', 'publish', 'complete'])
def test_trusted_native_interrupted_generation_resumes_owned_intent(prepared, monkeypatch, boundary):
    guest, payload = prepared
    actual_command, actual_move = guest.command, guest.mv
    failed = False

    def command(argv):
        nonlocal failed
        if not failed and argv[:2] == ['/usr/sbin/fapolicyd-cli', '--file']:
            if boundary == 'cli-partial':
                guest.write(fixture.TRUST_PENDING, b'partial native write')
                failed = True
                raise OSError('interrupted CLI')
            result = actual_command(argv)
            if boundary == 'cli-finished':
                failed = True
                raise OSError('interrupted CLI completion')
            return result
        return actual_command(argv)

    def move(source, target):
        nonlocal failed
        actual_move(source, target)
        if failed:
            return
        if target == fixture.TRUST_RECORD:
            state = json.loads(guest.read_file(target))
            intent = state['pending']
            should_fail = ((boundary == 'intent' and intent and intent['trust_file_sha256'] is None)
                           or (boundary == 'generated-record' and intent and intent['trust_file_sha256'])
                           or (boundary == 'complete' and state['complete'] and not intent))
        else:
            should_fail = boundary == 'publish' and target == fixture.TRUST_FILE
        if should_fail:
            failed = True
            raise OSError('interrupted publication')

    monkeypatch.setattr(guest, 'command', command)
    monkeypatch.setattr(guest, 'mv', move)
    with pytest.raises(OSError):
        fixture.reconcile(guest, payload)
    fixture.reconcile(guest, payload)
    fixture.verify_trusted(guest)
    assert not guest.exists(fixture.TRUST_PENDING)
    assert json.loads(guest.read_file(fixture.TRUST_RECORD))['pending'] is None


@pytest.mark.parametrize('fault', ['trust-collision', 'trust-link', 'trust-hardlink', 'trust-bytes',
                                 'record-link', 'record-foreign', 'staging-foreign', 'tool-owner',
                                 'tool-substitution', 'trusted-bytes', 'trusted-owner'])
def test_trusted_native_refuses_foreign_inputs_before_any_reconciliation_write(prepared, fault):
    guest, payload = prepared
    if fault == 'trust-collision':
        guest.write(fixture.TRUST_FILE, b'foreign trust entry')
    elif fault == 'staging-foreign':
        guest.write(fixture.TRUST_PENDING, b'foreign trust staging')
    else:
        fixture.reconcile(guest, payload)
        if fault == 'trust-link': guest.links[fixture.TRUST_FILE] = '/foreign'
        if fault == 'trust-hardlink': guest.nodes[fixture.TRUST_FILE][0]['st_nlink'] = 2
        if fault == 'trust-bytes': guest.write(fixture.TRUST_FILE, b'foreign trust entry')
        if fault == 'record-link': guest.links[fixture.TRUST_RECORD] = '/foreign'
        if fault == 'record-foreign': guest.write(fixture.TRUST_RECORD, b'{"foreign":true}')
        if fault == 'tool-owner': guest.chown(1000, 1000, '/usr/sbin/fapolicyd-cli')
        if fault == 'tool-substitution': guest.write('/usr/sbin/fapolicyd-cli', b'substituted package tool')
        target = fixture.assets.TRUSTED_NATIVE['trusted-hard'][0]
        if fault == 'trusted-bytes': guest.write(target, b'foreign trusted executable')
        if fault == 'trusted-owner': guest.chown(1000, 1000, target)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError):
        fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('os_id', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('fault', ['owner', 'digest', 'missing-digest', 'duplicate-digest', 'malformed', 'algorithm'])
def test_native_package_identity_refuses_substituted_or_ambiguous_inputs_before_writes(prepared, monkeypatch, os_id, fault):
    guest, payload = prepared
    if os_id == 'fedora':
        guest.set_fedora()
    actual = guest.command

    def command(argv):
        result = actual(argv)
        if fault == 'owner' and argv[1] in ('-S', '-qf'):
            return result.replace('fapolicyd', 'foreign', 1)
        manifest = argv[1] == '--control-show' or (argv[0] == 'rpm' and argv[3].startswith('%{FILEDIGESTALGO}'))
        if manifest:
            if fault == 'digest':
                daemon = fixture.native_tool_paths(os_id)['daemon']
                return result.replace(hashlib.md5(guest.package_payloads[daemon]).hexdigest()
                                      if os_id == 'ubuntu' else hashlib.sha256(guest.package_payloads[daemon]).hexdigest(),
                                      ('f' * 32 if os_id == 'ubuntu' else 'f' * 64))
            if fault == 'missing-digest': return result.splitlines(keepends=True)[0]
            if fault == 'duplicate-digest': return result + result.splitlines(keepends=True)[-1]
            if fault == 'malformed': return result + 'invalid metadata row\n'
            if fault == 'algorithm':
                return result.replace('8\n', '1\n', 1) if os_id == 'fedora' else result.replace('  usr/', '  /usr/')
        return result

    monkeypatch.setattr(guest, 'command', command)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert not guest.writes


def test_owned_trusted_update_changes_only_exact_file_trust_and_keeps_unrelated_state(prepared):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    guest.write('/etc/fapolicyd/trust.d/administrator.trust', b'/administrator 1 ' + b'a' * 64 + b'\n')
    before = copy.deepcopy(guest.nodes)
    fixture.reconcile(guest, payload | {'trusted-hard': b'updated trusted hard fixture'})
    provenance = fixture.verify_trusted(guest)
    target = fixture.assets.TRUSTED_NATIVE['trusted-hard'][0]
    assert provenance['files'][target]['sha256'] == hashlib.sha256(b'updated trusted hard fixture').hexdigest()
    for path, _ in fixture.assets.NATIVE.values():
        assert guest.nodes[path] == before[path]
    path = '/etc/fapolicyd/trust.d/administrator.trust'
    assert guest.nodes[path] == before[path]


@pytest.mark.parametrize('boundary', ['cli-partial', 'published'])
def test_owned_update_retries_with_scoped_native_update_despite_global_add_duplicates(prepared, monkeypatch, boundary):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    actual_command, actual_move = guest.command, guest.mv
    commands = []
    failed = False

    def command(argv):
        nonlocal failed
        commands.append(argv)
        if argv[:2] == ['/usr/sbin/fapolicyd-cli', '--file']:
            assert argv[2] == 'update'
            if not failed and boundary == 'cli-partial':
                guest.write(fixture.TRUST_PENDING, b'partial owned update')
                failed = True
                raise OSError('interrupted update')
        return actual_command(argv)

    def move(source, target):
        nonlocal failed
        actual_move(source, target)
        if not failed and boundary == 'published' and target == fixture.TRUST_FILE:
            failed = True
            raise OSError('interrupted after atomic publication')

    monkeypatch.setattr(guest, 'command', command)
    monkeypatch.setattr(guest, 'mv', move)
    desired = payload | {'trusted-soft': b'new soft trusted fixture'}
    with pytest.raises(OSError): fixture.reconcile(guest, desired)
    fixture.reconcile(guest, desired)
    fixture.verify_trusted(guest)
    assert all(argv[2] == 'update' for argv in commands if argv[:2] == ['/usr/sbin/fapolicyd-cli', '--file'])


@pytest.mark.parametrize('boundary', ['intent', 'cli-partial'])
@pytest.mark.parametrize('existing', [False, True])
def test_double_interruption_preserves_published_identity_across_retry_intent(prepared, monkeypatch, boundary, existing):
    guest, payload = prepared
    if existing:
        fixture.reconcile(guest, payload)
        payload = payload | {'trusted-hard': b'updated trusted fixture before interrupted publication'}
    actual_command, actual_move = guest.command, guest.mv
    failures = 0

    def move(source, target):
        nonlocal failures
        actual_move(source, target)
        if failures == 0 and target == fixture.TRUST_FILE:
            failures = 1
            raise OSError('interrupted after first publication')
        if failures == 1 and boundary == 'intent' and target == fixture.TRUST_RECORD:
            state = json.loads(guest.read_file(target))
            if state['pending'] and state['pending']['trust_file_sha256'] is None:
                failures = 2
                raise OSError('interrupted after retry intent')

    def command(argv):
        nonlocal failures
        if failures == 1 and boundary == 'cli-partial' and argv[:2] == ['/usr/sbin/fapolicyd-cli', '--file']:
            guest.write(fixture.TRUST_PENDING, b'partial second native write')
            failures = 2
            raise OSError('interrupted during retry CLI')
        return actual_command(argv)

    monkeypatch.setattr(guest, 'mv', move)
    monkeypatch.setattr(guest, 'command', command)
    with pytest.raises(OSError, match='first publication'): fixture.reconcile(guest, payload)
    published_digest = guest.checksum('sha256', fixture.TRUST_FILE)
    with pytest.raises(OSError, match='retry'): fixture.reconcile(guest, payload)
    transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
    assert transaction['complete']['trust_file_sha256'] == published_digest
    assert transaction['pending']['trust_file_sha256'] is None
    fixture.reconcile(guest, payload)
    fixture.verify_trusted(guest)
    assert failures == 2 and not guest.exists(fixture.TRUST_PENDING)
    assert json.loads(guest.read_file(fixture.TRUST_RECORD))['pending'] is None


@pytest.mark.parametrize('placement', ['default', 'fragment', 'nested'])
@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('variant', ['trusted-hard', 'command', 'whitespace', 'active-s', 'legacy-s'])
def test_foreign_exact_target_trust_is_refused_and_preserved_before_any_write(prepared, placement, existing, variant):
    guest, payload = prepared
    if existing:
        fixture.reconcile(guest, payload)
    if placement == 'default':
        path = '/etc/fapolicyd/fapolicyd.trust'
    elif placement == 'fragment':
        path = '/etc/fapolicyd/trust.d/administrator.trust'
    else:
        guest.mkdir('/etc/fapolicyd/trust.d/administrator')
        path = '/etc/fapolicyd/trust.d/administrator/nested.trust'
    inventory = fixture.assets.TRUSTED_NATIVE | fixture.assets.NATIVE | {
        'active-s': (fixture.assets.PREFIX + '/Versioned/Lunar Client-3.7.17.AppImage', ''),
        'legacy-s': (fixture.assets.legacy_executable_paths()[0], '')}
    target = inventory[variant][0]
    guest.write(path, f'{target} 123 {"a" * 64}\n'.encode())
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('fault', ['source-binding', 'fixture-binding', 'native-bytes', 'trust-bytes',
                                 'missing-trust', 'pending', 'extra-path', 'aliased-payload', 'metadata'])
def test_trusted_native_readonly_verification_refuses_stale_or_substituted_provenance(prepared, fault):
    guest, payload = prepared
    fixture.reconcile(guest, payload)
    transaction = json.loads(guest.read_file(fixture.TRUST_RECORD))
    record = transaction['complete']
    target = fixture.assets.TRUSTED_NATIVE['trusted-hard'][0]
    if fault == 'source-binding': record['preparation_script_sha256'] = 'f' * 64
    if fault == 'fixture-binding': record['fixture_record_sha256'] = 'f' * 64
    if fault == 'native-bytes': guest.write('/usr/sbin/fapolicyd-cli', b'replaced tool')
    if fault == 'trust-bytes': guest.write(fixture.TRUST_FILE, b'replaced trust file')
    if fault == 'missing-trust': del guest.nodes[fixture.TRUST_FILE]
    if fault == 'pending': transaction['pending'] = copy.deepcopy(record)
    if fault == 'extra-path': record['files']['/foreign'] = record['files'][target]
    if fault == 'aliased-payload':
        record['files'][target]['sha256'] = record['files'][fixture.assets.TRUSTED_NATIVE['trusted-soft'][0]]['sha256']
    if fault == 'metadata': record['files'][target]['uid'] = 1000
    guest.write(fixture.TRUST_RECORD, json.dumps(transaction).encode())
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises((ValueError, KeyError)):
        fixture.verify_trusted(guest)
    assert guest.nodes == before and not guest.writes


@pytest.mark.parametrize('boundary', ['write', 'rename', 'record'])
def test_interrupted_apt_mask_placement_retries_only_its_owned_transaction(prepared, monkeypatch, boundary):
    guest, payload = prepared
    path = '/etc/systemd/system/apt-daily-upgrade.service'
    temporary = path + '.onpc-baseline-new'
    actual_write, actual_move = guest.write, guest.mv
    failed = False

    def write(target, data):
        nonlocal failed
        actual_write(target, data)
        if not failed and boundary == 'write' and target == temporary:
            failed = True
            raise OSError('interrupted owned mask write')

    def move(source, target):
        nonlocal failed
        if not failed and boundary == 'rename' and source == temporary:
            failed = True
            raise OSError('interrupted owned mask rename')
        actual_move(source, target)
        if not failed and boundary == 'record' and source == temporary:
            failed = True
            raise OSError('interrupted owned mask record')

    monkeypatch.setattr(guest, 'write', write)
    monkeypatch.setattr(guest, 'mv', move)
    with pytest.raises(OSError):
        fixture.reconcile(guest, payload)
    fixture.reconcile(guest, payload)
    fixture.verify(guest)
    assert guest.read_file(path) == b''
    fixture.regular(guest, path, 0, 0, 0o644)
    assert not any(path.endswith('.onpc-baseline-new') for path in guest.nodes)


@pytest.mark.parametrize('fault', ['collision', 'link', 'hardlink', 'owner', 'mode', 'parent', 'bytes', 'missing'])
@pytest.mark.parametrize('unit', ['apt-daily.timer', 'apt-daily-upgrade.service'])
def test_apt_masks_refuse_foreign_or_stale_state_without_writes(prepared, fault, unit):
    guest, payload = prepared
    path = '/etc/systemd/system/' + unit
    if fault == 'collision':
        guest.write(path, b'foreign')
        guest.chmod(0o644, path)
    else:
        fixture.reconcile(guest, payload)
        if fault == 'link': guest.links[path] = '/foreign'
        if fault == 'hardlink': guest.nodes[path][0]['st_nlink'] = 2
        if fault == 'owner': guest.nodes[path][0]['st_uid'] = 999
        if fault == 'mode': guest.chmod(0o666, path)
        if fault == 'parent': guest.links[str(PurePosixPath(path).parent)] = '/foreign'
        if fault == 'bytes': guest.write(path, b'foreign')
        if fault == 'missing': del guest.nodes[path]
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises((ValueError, KeyError)):
        (fixture.reconcile(guest, payload) if fault == 'collision' else fixture.verify(guest))
    assert guest.nodes == before and guest.writes == []


def test_console_reconcile_twice_and_runtime_never_repairs():
    guest = Guest()
    guest.write('/etc/login.defs', b'# keep\nLOGIN_TIMEOUT\t60 # stock\nLOGIN_RETRIES 3\n')
    original = guest.read_file('/etc/login.defs')
    with pytest.raises(ValueError, match='login-stale'): console.login_window(guest)
    assert guest.read_file('/etc/login.defs') == original
    assert console.login_window(guest, prepare=True)['login_timeout_seconds'] == 600
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    console.login_window(guest, prepare=True)
    console.login_window(guest)
    assert guest.nodes == before and not guest.writes
    assert guest.read_file('/etc/login.defs') == original.replace(b'\t60 ', b'\t600 ')


def test_baseline_console_getty_is_idempotent_and_test_route_is_read_only():
    guest = Mock()
    guest.is_file.return_value = guest.is_dir.return_value = True
    links = {}
    guest.realpath.side_effect = lambda path: links.get(path, path)
    guest.is_symlink.side_effect = lambda path: path in links
    guest.exists.return_value = False
    guest.ln_s.side_effect = lambda target, path: links.update({path: target})
    with pytest.raises(ValueError): console.getty(guest)
    guest.ln_s.assert_not_called()
    console.getty(guest, prepare=True)
    console.getty(guest, prepare=True)
    console.getty(guest)
    guest.ln_s.assert_called_once()


@pytest.mark.parametrize('original', [
    b'# LOGIN_TIMEOUT 60\nLOGIN_RETRIES 3\n',
    b'LOGIN_RETRIES 3',
])
def test_console_preparation_adds_missing_timeout_and_preserves_existing_bytes(original):
    guest = Guest()
    guest.write('/etc/login.defs', original)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError, match='login-stale'):
        console.login_window(guest)
    assert guest.nodes == before and not guest.writes
    console.login_window(guest, prepare=True)
    desired = original + (b'' if original.endswith(b'\n') else b'\n') + b'LOGIN_TIMEOUT\t600\n'
    assert guest.read_file('/etc/login.defs') == desired
    guest.writes.clear()
    console.login_window(guest, prepare=True)
    console.login_window(guest)
    assert not guest.writes


@pytest.mark.parametrize('original', [
    b'LOGIN_TIMEOUT 60\nLOGIN_TIMEOUT 600\n',
    b'LOGIN_TIMEOUT invalid\n',
    b'#' + b'x' * 65534 + b'\n',
])
def test_console_preparation_refuses_ambiguous_invalid_or_oversized_settings(original):
    guest = Guest()
    guest.write('/etc/login.defs', original)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError):
        console.login_window(guest, prepare=True)
    assert guest.nodes == before and not guest.writes
