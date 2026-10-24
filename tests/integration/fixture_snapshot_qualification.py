"""Audit clean snapshots through the maintained watched, exclusive suite owner.

This is infrastructure qualification. Baseline refresh is a separate operation;
this check never prepares a baseline or exercises a customer journey.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import traceback
from collections import Counter
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
sys.path.insert(0, str(ROOT))

import app_snapshot
import baseline_fixtures
import baseline_guest
from execution import open_source
from guest_inputs import Bundle, read
import installed_setup
import online_snapshot
import prepare_vm
from provenance import preflight_source
from qualification_storage import allocate, session
from suite_lease import Suite
import system_runner as system
from tests.fixtures.native_trust import database_row, native_tool_paths
from vm_transport import Transport


def check_input_files(files, allowed):
    """Independently reject payload/source bytes in active AND archived trees."""
    for name in files:
        if name in allowed or name == 'before.json':
            continue
        path = Path(name)
        # Only known installed helper modules may leave bytecode. Fixture
        # bytecode remains a refusal even when its source has been removed.
        if path.parent.name == '__pycache__' and re.fullmatch(
                r'[A-Za-z_][A-Za-z_0-9]*\.cpython-[0-9]+\.pyc', path.name):
            original = str(path.parent.parent / (path.name.split('.')[0] + '.py'))
            if original in allowed:
                continue
        # Installation command records are bounded diagnostics, not inputs.
        if re.fullmatch(r'private/stage-[A-Za-z0-9_]{8}/command-[0-9]{4}(?:-stderr)?\.txt', name):
            continue
        if re.fullmatch(r'private/redaction-identities/[A-Za-z0-9_]{8}\.json', name):
            continue
        raise ValueError('fixture-snapshots:unexpected-input-file')


def runtime_absence():
    """The complete movable legacy declaration, excluding durable settings."""
    from tests.fixtures import baseline_assets, native_assets
    identities = {'system': SimpleNamespace(pw_dir='/')}
    for role, user in (('child', 'onpc-child-riley'), ('other', 'onpc-child-jordan'),
                       ('parent', 'onpc-parent-jamie')):
        identities[role] = SimpleNamespace(pw_dir='/home/' + user)
    movable = set(baseline_assets.native_files(identities)) | set(
        baseline_assets.catalogue_files(identities))
    return sorted(movable | {path + '.onpc-baseline-new' for path in movable} |
                  set(native_assets.NATIVE_POLICY_PATHS) |
                  {baseline_fixtures.TRUST_RECORD, baseline_fixtures.TRUST_PENDING,
                   baseline_fixtures.TRUST_FILE})


TARGETS = prepare_vm.vm_config.fixture_targets()


def preparation_checkout_files(os_id='ubuntu'):
    files = set(prepare_vm.preparation_files(os_id)) | set(prepare_vm.REQUIRED_CHECKOUT_ENTRIES)
    files -= set(prepare_vm.FIXTURE_SOURCE_FILES)
    files.discard('common/oh_no_parent_control_ui/gtk_automation.py')
    files.update(str(Path(account.icon_file).relative_to(prepare_vm.CHECKOUT))
                 for account in prepare_vm.IDENTITIES)
    return sorted(files)


def input_roots(names):
    selected = sorted(name for name in names if name.startswith('onpc-system-input'))
    system.require(all(name == 'onpc-system-input' or re.fullmatch(
        r'onpc-system-input-snapshot-[0-9a-f]{32}-[0-9a-f]{32}', name)
        for name in selected), 'fixture-snapshots:unrecognized-input-tree')
    return ['/var/tmp/' + name for name in selected]


def relative_member(name):
    """libguestfs may retain the root separator in find results."""
    system.require(type(name) is str, 'fixture-snapshots:unsafe-member')
    relative = name.removeprefix('/')
    system.require(relative and '\x00' not in relative and
                   all(part not in ('', '.', '..') for part in relative.split('/')),
                   'fixture-snapshots:unsafe-member')
    return relative


def broker_group(g):
    """Resolve Fedora's fixed broker group from the authenticated baseline DB."""
    path = '/etc/group'
    before = g.lstatns(path)
    system.require(g.realpath(path) == path and stat.S_ISREG(before['st_mode']) and
                   before['st_uid'] == 0 and not before['st_mode'] & 0o022 and
                   before['st_nlink'] == 1 and 0 < before['st_size'] <= 1024 * 1024,
                   'fixture-snapshots:broker-group-database')
    raw = g.read_file(path)
    system.require(type(raw) is bytes and len(raw) == before['st_size'] and
                   before == g.lstatns(path), 'fixture-snapshots:broker-group-database')
    selected = [line.split(':') for line in raw.decode('utf-8').splitlines()
                if line.split(':')[0] == 'wheel']
    system.require(len(selected) == 1 and len(selected[0]) == 4 and
                   re.fullmatch(r'[0-9]{1,10}', selected[0][2]) is not None and
                   0 < int(selected[0][2]) < 2**32 - 1,
                   'fixture-snapshots:broker-group-database')
    return int(selected[0][2])


@system.observed('Auditing fixture-free baseline runtime and retained source trees')
def audit_baseline(suite, allowed):
    lease = suite.lease
    os_id = TARGETS[suite.source.domain.name()]
    system.require(lease.capture.state['guest'].get('fixture_boundary') == 'clean',
                   'fixture-snapshots:clean-baseline-required')
    with system.mounted_guest(suite.guestfs, lease, readonly=True) as g:
        baseline_fixtures.verify_clean(g)
        native_previous = None
        broker_gid = None
        if os_id == 'ubuntu':
            baseline_fixtures.verify_native_rules(g)
            policy_paths = (baseline_fixtures.NATIVE_RULES_FILE, baseline_fixtures.NATIVE_RULES_RECORD)
        else:
            baseline_fixtures.verify_native_policy_sources(
                g, baseline_fixtures.fixture_accounts(g), include_native_policy=False)
            broker_gid = broker_group(g)
            native_previous = baseline_fixtures.verify_clean_compiled(g)
            policy_paths = ['/etc/fapolicyd/rules.d/' + relative_member(name)
                            for name in g.find('/etc/fapolicyd/rules.d')]
            prepare_vm.selinux_policy(g.read_file('/etc/selinux/config').decode('utf-8'))
        native_policy = {}
        for path in policy_paths:
            info = g.lstatns(path)
            native_policy[path] = {'sha256': g.checksum('sha256', path),
                'mode': stat.S_IMODE(info['st_mode']), 'uid': info['st_uid'], 'gid': info['st_gid']}
        baseline_guest.verify_clean_sources(g)
        checkout = baseline_guest.STAGE + '/checkout'
        checkout_files = []
        for name in g.find(checkout):
            relative = relative_member(name)
            path = checkout + '/' + relative
            info = g.lstatns(path)
            system.require(not g.is_symlink(path) and
                           (stat.S_ISDIR(info['st_mode']) or stat.S_ISREG(info['st_mode'])),
                           'fixture-snapshots:unsafe-retained-checkout')
            if stat.S_ISREG(info['st_mode']):
                checkout_files.append(relative)
        system.require(set(checkout_files) == set(preparation_checkout_files(os_id)),
                       'fixture-snapshots:unexpected-retained-source')
        roots = input_roots(g.ls('/var/tmp'))
        inventories = {}
        for root in roots:
            system.require(g.is_dir(root) and not g.is_symlink(root),
                           'fixture-snapshots:unsafe-input-tree')
            files = []
            for name in g.find(root):
                relative = relative_member(name)
                path = root + '/' + relative
                info = g.lstatns(path)
                system.require(not g.is_symlink(path) and
                               (stat.S_ISDIR(info['st_mode']) or
                                stat.S_ISREG(info['st_mode'])),
                               'fixture-snapshots:unsafe-input-tree')
                if stat.S_ISREG(info['st_mode']):
                    files.append(relative)
            check_input_files(files, allowed)
            inventories[root] = sorted(files)
        for path in runtime_absence():
            system.require(not g.exists(path) and not g.is_symlink(path),
                           'fixture-snapshots:runtime-fixture-retained')
    return {'runtime_absent': True, 'native_policy': native_policy,
            'native_previous': native_previous,
            'broker_gid': broker_gid,
            'retained_checkout_files': sorted(checkout_files),
            'input_trees': inventories}


LIVE_AUDIT = '''import hashlib,json,os,pathlib,stat,sys
data=json.load(sys.stdin)
for name in data['absent']:
 assert not os.path.lexists(name),'runtime-fixture-retained'
checkout=pathlib.Path('/var/lib/onpc-baseline-preparation/checkout')
for name in data['fixture_sources']:
 assert not os.path.lexists(checkout/name),'retained-fixture-source'
retained=[]
for current,dirs,names in os.walk(checkout,followlinks=False):
 for name in dirs+names:
  path=pathlib.Path(current)/name
  info=path.lstat()
  assert not stat.S_ISLNK(info.st_mode),'unsafe-retained-checkout'
  assert stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode),'unsafe-retained-checkout'
  if stat.S_ISREG(info.st_mode): retained.append(path.relative_to(checkout).as_posix())
assert sorted(retained)==data['checkout_files'],'unexpected-retained-source'
trees={}
for root in sorted(pathlib.Path('/var/tmp').iterdir()):
 if not root.name.startswith('onpc-system-input'): continue
 assert not root.is_symlink() and root.is_dir(),'unsafe-input-tree'
 files=[]
 for current,dirs,names in os.walk(root,followlinks=False):
  for name in dirs+names:
   path=pathlib.Path(current)/name
   info=path.lstat()
   assert not stat.S_ISLNK(info.st_mode),'unsafe-input-tree'
   assert stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode),'unsafe-input-tree'
   if stat.S_ISREG(info.st_mode): files.append(path.relative_to(root).as_posix())
   assert len(files)<=8192,'oversized-input-tree'
 trees[root.name]=sorted(files)
active=pathlib.Path('/var/tmp/onpc-system-input')
for name,digest in data['expected'].items():
 path=active/name
 assert not path.is_symlink() and path.is_file(),'missing-installation-input'
 with path.open('rb') as stream:
  assert hashlib.file_digest(stream,'sha256').hexdigest()==digest,'capture-input-bytes-changed'
print(json.dumps({'trees':trees,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()}))
'''


@system.observed('Auditing the restored online app capture and archived inputs')
def audit_online(transport, allowed, expected, os_id='ubuntu'):
    fixture_sources = [*prepare_vm.FIXTURE_SOURCE_FILES,
                       'common/oh_no_parent_control_ui/gtk_automation.py']
    raw = transport.call(['/usr/bin/python3', '-I', '-c', LIVE_AUDIT],
        input=system.baseline.encode({'absent': runtime_absence(),
                                     'fixture_sources': fixture_sources,
                                     'checkout_files': preparation_checkout_files(os_id),
                                     'expected': expected}), timeout=120)
    system.require(len(raw) <= 1024 * 1024, 'fixture-snapshots:oversized-audit')
    value = json.loads(raw)
    system.require(set(value) == {'trees', 'boot_id'} and
                   re.fullmatch(r'[0-9a-f-]{36}', value['boot_id']) is not None,
                   'fixture-snapshots:audit-schema')
    roots = input_roots(value['trees'])
    system.require('/var/tmp/onpc-system-input' in roots,
                   'fixture-snapshots:missing-installation-input')
    for files in value['trees'].values():
        check_input_files(files, allowed)
    return value


def baseline_transport(suite, directory):
    """Boot the restored baseline with only the shared observation SSH input."""
    observation = directory / 'baseline-observation'
    (observation / 'input').mkdir(parents=True, mode=0o700)
    (observation / 'input/selected-inputs.json').write_bytes(system.baseline.encode({
        'schema_version': 1, 'scope': 'fixture-snapshot-qualification'}))
    host_key = system.bootstrap(suite.commands, suite.lease, observation, suite.guestfs,
                                observation_only=True, environment_only=True)
    suite.lease.start()
    hostname = system.address(suite.source)
    (observation / 'known-hosts').write_text(f'{hostname} {host_key}\n')
    transport = Transport({'directory': str(observation), 'hostname': hostname,
        'domain_uuid': suite.source.uuid, 'domain_id': suite.lease.view.domain_id,
        'run': suite.lease.state['run']}, suite.commands,
        guard=lambda _: suite.lease.guard(), lease=suite.lease)
    transport.probe_ready()
    return transport


def native_rows(raw, absent, product_paths, os_id='ubuntu'):
    """Separate package-owned product rows from the preserved vendor database."""
    system.require(type(raw) is bytes and 0 < len(raw) <= 32 * 1024 * 1024,
                   'fixture-snapshots:native-database-size')
    vendor, product = Counter(), Counter()
    for line in raw.decode('utf-8').splitlines():
        fields = database_row(line)
        backend = 'rpmdb' if os_id == 'fedora' else 'debdb'
        system.require(fields is not None and fields[0] in (backend, 'filedb') and
                       fields[2].isdecimal() and re.fullmatch(r'[0-9a-f]{64}', fields[3]) is not None,
                       'fixture-snapshots:native-database-row')
        path = fields[1]
        system.require(path not in absent, 'fixture-snapshots:native-fixture-trust-retained')
        (product if path in product_paths else vendor)[line] += 1
    system.require(vendor, 'fixture-snapshots:vendor-trust-missing')
    return vendor, product


@system.observed('Checking live native service and database readiness')
def audit_native(transport, absent, product_paths=(), native_policy=None, os_id='ubuntu',
                 product_policy=None, native_previous=None):
    policy_evidence = {}
    if native_policy is not None:
        # Verify the actual restored policy source and ownership receipt without
        # importing preparation code or changing compiler/service state.
        raw = transport.call(['/usr/bin/python3', '-I', '-c', NATIVE_POLICY_AUDIT],
            input=system.baseline.encode({'os_id': os_id, 'files': native_policy,
                                         'product': product_policy or {},
                                         'previous': native_previous}),
            timeout=30, attempts=1)
        if os_id == 'fedora':
            system.require(type(raw) is bytes and len(raw) <= 2 * 1024 * 1024,
                           'fixture-snapshots:native-policy-size')
            policy_evidence = json.loads(raw)
            system.require(set(policy_evidence) == {
                'compiled_rules', 'compiled_sha256', 'compiled_previous'},
                           'fixture-snapshots:native-policy-schema')
            listed = transport.call([native_tool_paths(os_id)['cli'], '--list'],
                                    timeout=30, attempts=1)
            system.require(policy_rules(listed, numbered=True) ==
                           policy_rules(policy_evidence.pop('compiled_rules').encode()),
                           'fixture-snapshots:native-policy-list-changed')
            policy_evidence['compiled_and_public_rule_list_match_sources'] = True
    if os_id == 'fedora':
        enforcing = transport.call(['/usr/sbin/getenforce'],
                                    timeout=30, attempts=1)
        system.require(enforcing == b'Enforcing\n', 'fixture-snapshots:selinux-not-enforcing')
    active = transport.call(['/usr/bin/systemctl', 'is-active', 'fapolicyd.service'],
                            timeout=30, attempts=1)
    system.require(active == b'active\n', 'fixture-snapshots:native-service-inactive')
    raw = transport.call([native_tool_paths(os_id)['cli'], '--dump-db'], timeout=60, attempts=1)
    vendor, product = native_rows(raw, absent, product_paths, os_id)
    digest = hashlib.sha256('\n'.join(sorted(vendor.elements())).encode()).hexdigest()
    return {'service_active': True, 'database_readable': True,
            'vendor_rows': sum(vendor.values()), 'vendor_sha256': digest,
            'product_rows': sum(product.values()),
            'native_policy_preserved': native_policy is not None,
            'os_id': os_id, 'selinux_enforcing': os_id == 'fedora',
            **policy_evidence}, vendor


def policy_rules(raw, *, numbered=False):
    """The public CLI lists the rules file; it is not a daemon generation probe."""
    system.require(type(raw) is bytes and 0 < len(raw) <= 2 * 1024 * 1024,
                   'fixture-snapshots:native-policy-size')
    lines = []
    for line in raw.decode('utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if numbered:
            line = re.sub(r'^[0-9]+[.:]\s+', '', line)
            # The packaged CLI prefixes variable definitions rather than
            # numbering them; they are not policy decisions.
            line = re.sub(r'^->\s+(?=%)', '', line)
        if not line or line.startswith('%'):
            continue
        system.require(re.match(r'(allow|deny)(_(audit|log|syslog))?\s', line) is not None,
                       'fixture-snapshots:native-policy-rule')
        lines.append(' '.join(line.split()))
    system.require(lines, 'fixture-snapshots:native-policy-rules-empty')
    return lines


NATIVE_POLICY_AUDIT = '''import grp,hashlib,json,os,pathlib,re,stat,sys
data=json.load(sys.stdin)
assert set(data)=={'os_id','files','product','previous'} and data['os_id'] in ('ubuntu','fedora'),'native-policy-platform'
prior=data['previous']
assert prior is None or (type(prior) is dict and set(prior)=={'sha256','mode','uid','gid'} and type(prior['sha256']) is str and re.fullmatch('[0-9a-f]{64}',prior['sha256']) and prior['uid']==0 and prior['mode'] in (0o640,0o644)),'native-policy-previous-proof'
expected=dict(data['files'])
optional={'/etc/fapolicyd/rules.d/01-oh-no-parent-control-deny.rules','/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules'}
required={'/etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules','/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules'}
if data['product']:
 assert data['os_id']=='fedora' and set(data['product'])==optional|required,'native-policy-product-inventory'
 native_gid=data['product']['/etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules']['gid']
 broker_groups=[entry.gr_gid for entry in grp.getgrall() if entry.gr_name=='wheel']
 assert len(broker_groups)==1 and type(broker_groups[0]) is int and 0<broker_groups[0]<2**32-1,'native-policy-broker-group'
 broker_gid=broker_groups[0]
 assert type(native_gid) is int and native_gid>0 and all(data['product'][name]['gid']==native_gid for name in required),'native-policy-product-group'
 for name in optional:
  assert data['product'][name]['gid']==[broker_gid,native_gid],f"native-policy-product-group path={name} expected={[broker_gid,native_gid]} received={data['product'][name]['gid']}"
 expected.update({name:spec for name,spec in data['product'].items() if name not in optional or os.path.lexists(name)})
if data['os_id']=='ubuntu':
 assert set(expected)=={'/etc/fapolicyd/rules.d/95-allow-open.rules','/var/lib/onpc-baseline-native-rules.json'},'native-policy-inventory'
else:
 root=pathlib.Path('/etc/fapolicyd/rules.d')
 assert root.resolve()==root and root.is_dir(),'native-policy-link'
 assert 0<len(expected)<=128 and {str(path) for path in root.iterdir()}==set(expected),'native-policy-inventory'
 assert all(pathlib.Path(name).parent==root for name in expected),'native-policy-inventory'
 assert not os.path.lexists('/etc/fapolicyd/fapolicyd.rules'),'native-policy-legacy'
 assert not os.path.lexists('/var/lib/onpc-baseline-native-rules.json'),'native-policy-foreign-receipt'
contents={}
for name,spec in expected.items():
 path=pathlib.Path(name)
 assert path.resolve()==path,'native-policy-link'
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
  before=os.fstat(stream.fileno())
  assert stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=2*1024*1024,'native-policy-file'
  raw=stream.read(2*1024*1024+1)
  after=os.fstat(stream.fileno())
  signature=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  assert signature(before)==signature(after)==signature(path.lstat()),'native-policy-changed'
  if type(spec['gid']) is list:
   assert name in optional and before.st_gid in spec['gid'],f"native-policy-product-group path={name} actual_gid={before.st_gid} expected_gids={spec['gid']}"
   spec=spec|{'gid':before.st_gid}
  actual={'sha256':hashlib.sha256(raw).hexdigest(),'mode':stat.S_IMODE(before.st_mode),'uid':before.st_uid,'gid':before.st_gid}
  assert actual==spec,f"native-policy-substituted path={name} actual={actual} expected={spec}"
  contents[name]=raw
if data['os_id']=='fedora':
 native_gids={spec['gid'] for spec in data['files'].values()}
 assert len(native_gids)==1,'native-policy-compiled-group'
 native_gid=next(iter(native_gids))
 def read_compiled(name,category):
  path=pathlib.Path(name)
  assert path.resolve()==path,'native-policy-'+category+'-link'
  with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
   info=os.fstat(stream.fileno())
   groups=(0,native_gid) if category=='previous' else (native_gid,)
   modes=(0o640,0o644) if category=='previous' else (0o644,)
   assert stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==0 and info.st_gid in groups and stat.S_IMODE(info.st_mode) in modes and info.st_size<=2*1024*1024,'native-policy-'+category+'-file'
   raw=stream.read(2*1024*1024+1)
   assert signature(info)==signature(os.fstat(stream.fileno()))==signature(path.lstat()),'native-policy-'+category+'-changed'
  return raw,{'sha256':hashlib.sha256(raw).hexdigest(),'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid}
 def compiled_output(names):
  header=b'## This file is automatically generated from /etc/fapolicyd/rules.d\\n'
  lines=[line for name in sorted(names) for line in contents[name].splitlines() if line and not re.match(rb'^\\s*#',line)]
  return header+b''.join(line+b'\\n' for line in lines)
 raw,_=read_compiled('/etc/fapolicyd/compiled.rules','compiled')
 assert raw==compiled_output(contents),'native-policy-compiled-substituted'
 previous=None
 if os.path.lexists('/etc/fapolicyd/compiled.rules.prev'):
  backup,previous=read_compiled('/etc/fapolicyd/compiled.rules.prev','previous')
  assert backup in (compiled_output(data['files']),compiled_output(contents)) or (prior is not None and hashlib.sha256(backup).hexdigest()==prior['sha256']),'native-policy-previous-substituted'
 print(json.dumps({'compiled_rules':raw.decode('utf-8'),'compiled_sha256':hashlib.sha256(raw).hexdigest(),'compiled_previous':previous}))
'''


def installed_product_paths(assets):
    manifest = json.loads((assets / 'installed-files.json').read_bytes())
    system.require(type(manifest) is list and all(type(entry) is dict and
                   type(entry.get('path')) is str and entry['path'].startswith('/')
                   for entry in manifest), 'fixture-snapshots:product-manifest')
    return {entry['path'] for entry in manifest}


def installed_product_policy(assets, commands, native_gid, broker_gid):
    """Bind Fedora's required canary and fallback to the authenticated RPM.

    The two generated units may be absent or contain only their empty-policy
    header. This qualification installs no customer policy or fixture admission.
    """
    sources = {'/usr/share/oh-no-parent-control/' + name for name in (
        '00-oh-no-parent-control-canary.rules', '99-oh-no-parent-control-allow.rules')}
    system.require(type(native_gid) is int and native_gid > 0,
                   'fixture-snapshots:product-policy-group')
    system.require(type(broker_gid) is int and 0 < broker_gid < 2**32 - 1,
                   'fixture-snapshots:product-policy-broker-group')
    manifest = json.loads((assets / 'installed-files.json').read_bytes())
    system.require(type(manifest) is list and all(type(entry) is dict for entry in manifest),
                   'fixture-snapshots:product-policy-manifest')
    for source in sources:
        selected = [entry for entry in manifest if entry.get('path') == source]
        system.require(len(selected) == 1 and selected[0].get('kind') == 'file'
                       and selected[0].get('mode') == 0o644,
                       'fixture-snapshots:product-policy-manifest')
    raw = commands.run(['rpm', '-qp', '--queryformat',
        '%{FILEDIGESTALGO}\n[%{FILENAMES}\t%{FILEDIGESTS}\t%{FILEMODES}\t%{FILEUSERNAME}\t%{FILEGROUPNAME}\n]',
        str(assets / 'package.rpm')], merge_stderr=False)
    system.require(type(raw) is bytes and 0 < len(raw) <= 8 * 1024 * 1024,
                   'fixture-snapshots:product-policy-package')
    algorithm, *rows = raw.decode('utf-8').splitlines()
    selected = [row.split('\t') for row in rows if row.split('\t')[0] in sources]
    system.require(algorithm == '8' and len(selected) == len(sources) and
                   {row[0] for row in selected} == sources and all(len(row) == 5 for row in selected),
                   'fixture-snapshots:product-policy-package')
    digests = {}
    for source, digest, mode, owner, group in selected:
        system.require(re.fullmatch(r'[0-9a-f]{64}', digest) is not None and
                       mode == str(stat.S_IFREG | 0o644) and owner == group == 'root',
                       'fixture-snapshots:product-policy-package')
        digests[source.rsplit('/', 1)[1]] = digest
    root = '/etc/fapolicyd/rules.d/'
    header = hashlib.sha256(b'# Generated by Oh No! Parent Control. Do not edit.\n').hexdigest()
    # Native tmpfiles owns both packaged rules' group after reboot. Broker atomic
    # replacements inherit the broker's wheel group; unchanged units retain the native
    # group from boot. Both derive from authenticated writers, never observation.
    return {root + name: {'sha256': sha, 'mode': 0o644, 'uid': 0,
                         'gid': native_gid if name in digests else [broker_gid, native_gid]}
            for name, sha in (digests | {'01-oh-no-parent-control-deny.rules': header,
                                        '89-oh-no-parent-control.rules': header}).items()}


def package_inventory(transport, os_id='ubuntu'):
    if os_id == 'fedora':
        # RPM permits several installed versions of one name/architecture.
        # Bind exact installed instances, including epochs, rather than lose
        # installonly packages in a name-keyed dictionary.
        command = ['/usr/bin/rpm', '-qa', '--queryformat',
            r'%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\tinstalled\n']
    else:
        command = ['/usr/bin/dpkg-query', '-W',
            r'-f=${binary:Package}\t${Version}\t${db:Status-Status}\n']
    raw = transport.call(command, timeout=60, attempts=1)
    system.require(type(raw) is bytes and len(raw) <= 4 * 1024 * 1024,
                   'fixture-snapshots:package-inventory-size')
    packages = {}
    for line in raw.decode().splitlines():
        fields = line.split('\t')
        system.require(len(fields) == 3 and fields[2] in ('installed', 'config-files', 'not-installed'),
                       'fixture-snapshots:package-inventory')
        name, version, status = fields
        if status != 'installed':
            continue
        pattern = (r'[A-Za-z0-9][A-Za-z0-9+._:~()^-]*' if os_id == 'fedora'
                   else r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?')
        version_pattern = (r'[A-Za-z0-9.+:~_^-]+' if os_id == 'fedora'
                           else r'[A-Za-z0-9.+:~_-]+')
        system.require(re.fullmatch(pattern, name) is not None
                       and re.fullmatch(version_pattern, version) is not None
                       and name not in packages, 'fixture-snapshots:package-inventory')
        packages[name] = version
    system.require(packages and len(packages) <= 8192, 'fixture-snapshots:package-inventory')
    return packages


def verify_vendor_preservation(transport, before, after, packages_before, packages_after,
                               os_id='ubuntu'):
    """Preserve every original row; authenticate additions from installed packages.

    The public installer may add its declared native dependencies. Their files
    are vendor-owned, separate from the product's installation manifest.
    """
    system.require(not (before - after), 'fixture-snapshots:vendor-trust-changed')
    system.require(set(packages_before) <= set(packages_after),
                   'fixture-snapshots:vendor-package-removed')
    changed = {name: version for name, version in packages_after.items()
               if packages_before.get(name) != version}
    system.require(len(changed) <= 256, 'fixture-snapshots:package-change-inventory')
    additions = after - before
    paths = set()
    if changed:
        command = (['/usr/bin/rpm', '-ql', '--', *sorted(changed)] if os_id == 'fedora' else
                   ['/usr/bin/dpkg-query', '-L', *sorted(changed)])
        raw = transport.call(command,
                             timeout=60, attempts=1)
        system.require(type(raw) is bytes and len(raw) <= 8 * 1024 * 1024,
                       'fixture-snapshots:package-file-inventory-size')
        for path in raw.decode().splitlines():
            # Native multi-package listings separate package blocks with an
            # empty line. It is formatting, never a trusted file path.
            if path in ('', '/', '/.'):
                continue
            system.require(path.startswith('/') and '\x00' not in path
                           and all(part not in ('', '.', '..') for part in path[1:].split('/')),
                           'fixture-snapshots:package-file-inventory')
            paths.add(path)
    for line in additions:
        source, rest = line.split(None, 1)
        path = rest.rsplit(None, 2)[0]
        system.require(source == ('rpmdb' if os_id == 'fedora' else 'debdb') and path in paths,
                       'fixture-snapshots:unowned-vendor-trust-added')
    return {'original_vendor_rows_preserved': True,
            'original_vendor_rows': sum(before.values()),
            'additional_vendor_rows': sum(additions.values()),
            'installed_or_updated_packages': changed}


def changed_bundle(bundle, sources):
    frozen = {bundle.sources[target]: data for target, data in bundle.files.items()}
    for source in sources:
        if source in frozen:
            frozen[source] += b'\n# fixture snapshot qualification mutation\n'
            if source == 'tests/fixtures/native_assets.py':
                frozen[source] += b'\nASSETS = ()\n'
    return Bundle(bundle.root, [(source, target) for target, source in bundle.sources.items()],
                  frozen=frozen)


def changed_product(directory, assets, commands, os_id='ubuntu'):
    """Repack changed actual product bytes; never install or execute the copy."""
    if os_id == 'fedora':
        # RPM content identity deliberately covers every archive byte. Probe
        # that conservative contract using a changed private actual archive,
        # without inventing a valid rebuilt RPM or installing this invalid copy.
        private = directory / 'identity-product'
        private.mkdir(mode=0o700)
        changed = private / 'assets'
        changed.mkdir(mode=0o700)
        original = assets / 'package.rpm'
        system.require(not original.is_symlink() and original.is_file(),
                       'fixture-snapshots:unsafe-product-copy')
        data = original.read_bytes()
        system.require(len(data) > 1, 'fixture-snapshots:product-mutation-target')
        (changed / 'package.rpm').write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        return changed
    target = '/usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/duration.py'
    manifest = json.loads((assets / 'installed-files.json').read_bytes())
    system.require(sum(entry.get('path') == target and entry.get('kind') == 'file'
                       for entry in manifest) == 1,
                   'fixture-snapshots:product-mutation-target')
    private = directory / 'identity-product'
    private.mkdir(mode=0o700)
    unpacked = private / 'unpacked'
    commands.run(['dpkg-deb', '--raw-extract', str(assets / 'package.deb'), str(unpacked)],
                 timeout=120)
    path = unpacked / target.removeprefix('/')
    system.require(path.resolve() == path, 'fixture-snapshots:unsafe-product-copy')
    info = path.lstat()
    system.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                   'fixture-snapshots:unsafe-product-copy')
    path.write_bytes(path.read_bytes() + b'\n# snapshot product-byte qualification\n')
    changed = private / 'assets'
    changed.mkdir(mode=0o700)
    commands.run(['dpkg-deb', '--build', str(unpacked), str(changed / 'package.deb')],
                 timeout=240)
    return changed


@system.observed('Qualifying snapshot identity boundaries with private source copies')
def qualify_identities(directory, lease, assets, bundle, xml):
    """Use actual changed source bytes; never edit the live checkout or package."""
    checkout = directory / 'identity-checkout'
    checkout.mkdir(mode=0o700)
    os_id = TARGETS[lease.source.domain.name()]
    files = set(prepare_vm.preparation_files(os_id)) | set(prepare_vm.FIXTURE_SOURCE_FILES)
    for relative in sorted(files):
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(read(ROOT, relative))
    original = prepare_vm.preparation_digest(checkout, os_id=os_id)
    system.require(original == lease.capture.state['script_digest'],
                   'fixture-snapshots:preparation-source-changed')
    for relative in prepare_vm.FIXTURE_SOURCE_FILES:
        path = checkout / relative
        path.write_bytes(path.read_bytes() + b'\n# fixture-only mutation\n')
    shared = checkout / 'tests/integration/baseline_fixtures.py'
    original_shared = shared.read_bytes()
    fixture_body = b'def build_payload():\n'
    system.require(original_shared.count(fixture_body) == 1,
                   'fixture-snapshots:fixture-mutation-target')
    shared.write_bytes(original_shared.replace(fixture_body, fixture_body +
        b"    raise RuntimeError('fixture-only changed builder')\n"))
    system.require(prepare_vm.preparation_digest(checkout, os_id=os_id) == original,
                   'fixture-snapshots:fixture-invalidates-baseline')
    guard = b"raise ValueError('baseline:fixtures-' + category + '; run tools/prepare-vm')"
    shared_bytes = shared.read_bytes()
    system.require(shared_bytes.count(guard) == 1, 'fixture-snapshots:lifecycle-mutation-target')
    shared.write_bytes(shared_bytes.replace(guard,
        b"raise ValueError('changed shared guard:' + category)"))
    system.require(prepare_vm.preparation_digest(checkout, os_id=os_id) != original,
                   'fixture-snapshots:lifecycle-does-not-invalidate')
    shared.write_bytes(original_shared)
    dependency = checkout / 'tests/integration/guest_test_dependencies.py'
    dependency.write_bytes(dependency.read_bytes() + b'\n# dependency mutation\n')
    system.require(prepare_vm.preparation_digest(checkout, os_id=os_id) != original,
                   'fixture-snapshots:dependency-does-not-invalidate')
    expected = app_snapshot.input_identity(lease, assets, bundle, lease.commands)
    changed = changed_bundle(bundle, prepare_vm.FIXTURE_SOURCE_FILES)
    system.require(app_snapshot.input_identity(lease, assets, changed, lease.commands) == expected
                   and app_snapshot.matches(xml, expected),
                   'fixture-snapshots:fixture-invalidates-app')
    recipe = changed_bundle(bundle, ('tests/integration/guest_install_recipe.py',))
    system.require(app_snapshot.mismatch(xml, app_snapshot.input_identity(
        lease, assets, recipe, lease.commands)) == 'installation recipe changed',
        'fixture-snapshots:recipe-does-not-invalidate')
    # DEB normalizes delivery metadata and therefore needs a real file change;
    # RPM deliberately binds its entire archive. Neither probe is installed.
    product = changed_product(directory, assets, lease.commands, os_id)
    system.require(app_snapshot.mismatch(xml, app_snapshot.input_identity(
        lease, product, bundle, lease.commands)) == 'package contents changed',
                   'fixture-snapshots:product-content-does-not-invalidate')
    baseline = json.loads(expected)
    baseline['baseline_sha256'] = hashlib.sha256(baseline['baseline_sha256'].encode()).hexdigest()
    system.require(app_snapshot.mismatch(xml, json.dumps(baseline)) == 'baseline changed',
                   'fixture-snapshots:dependency-baseline-does-not-invalidate-app')
    return {'fixture_source_mutations_preserve_baseline_and_app_identity': True,
            'dependency_source_mutation_invalidates_baseline': True,
            'shared_lifecycle_source_mutation_invalidates_baseline': True,
            'recipe_source_mutation_invalidates_app': True,
            'changed_product_package_bytes_invalidate_app': True,
            'product_package_mutation_method': ('private-rpm-archive-byte' if os_id == 'fedora'
                                                else 'repacked-deb-product-file'),
            'changed_baseline_identity_invalidates_app': True,
            'mutated_fixture_sources': list(prepare_vm.FIXTURE_SOURCE_FILES)}


def qualify(directory, assets):
    suite = Suite(open_source)
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite.commands.directory = private
    result = {}
    try:
        system.stage_assets(system.artifact_source(assets), directory / 'assets', suite.commands)
        assets = directory / 'assets'
        provenance = preflight_source(assets)
        bundle = suite.input_bundle(ROOT)
        lean = installed_setup.snapshot_inputs(bundle)
        target = prepare_vm.vm_config.selected().name
        system.require(target in TARGETS, 'fixture-snapshots:target-not-qualified')
        os_id = TARGETS[target]
        allowed = set(lean.files) | {'package.' + ('rpm' if os_id == 'fedora' else 'deb'), 'installed-files.json',
                                   'selected-inputs.json', 'transfer-sha256.json'}
        product_paths = installed_product_paths(assets)
        source, _, lease = suite.acquire(system.RunLedger())
        system.require(source.domain.name() == target,
                       'fixture-snapshots:target-not-qualified')
        with lease:
            lease.prepare()
            result['baseline'] = audit_baseline(suite, allowed)
            product_policy = None
            if os_id == 'fedora':
                groups = {spec['gid'] for spec in result['baseline']['native_policy'].values()}
                system.require(len(groups) == 1, 'fixture-snapshots:native-policy-group')
                product_policy = installed_product_policy(
                    assets, suite.commands, groups.pop(), result['baseline']['broker_gid'])
            baseline = baseline_transport(suite, directory)
            result['baseline']['native'], vendor = audit_native(
                baseline, set(runtime_absence()), product_paths, result['baseline']['native_policy'],
                os_id, None, result['baseline'].get('native_previous'))
            packages_before = package_inventory(baseline, os_id)
            system.require(result['baseline']['native']['product_rows'] == 0,
                           'fixture-snapshots:baseline-product-trust')
            lease.stop()
            created = suite.prepare_installed(directory, assets,
                {'schema_version': 1, 'scope': 'fixture-snapshot-qualification',
                 'source_sha256': provenance['source_sha256']},
                root=ROOT, overwrite=True, mode='online')
            system.require(created and lease.installed_online,
                           'fixture-snapshots:online-capture-not-created')
            xml = lease.installed_xml
            result['identities'] = qualify_identities(directory, lease, assets, bundle, xml)
            record = online_snapshot.load(source, lease.installed_name, xml)
            system.require(record is not None, 'fixture-snapshots:credentials-missing')
            # Reset the just-created guest, then read the actual saved memory
            # capture through the ordinary credential and ownership checks.
            lease.stop()
            lease.prepare()
            hostname = online_snapshot.restore(lease, record)
            transport = online_snapshot.saved_transport(lease, directory, record, hostname)
            captured = directory / 'suite-setup/input'
            expected = {name: system.baseline.digest(captured / name) for name in allowed}
            result['online_app'] = audit_online(transport, allowed, expected, os_id)
            result['online_app']['native'], app_vendor = audit_native(
                transport, set(runtime_absence()), product_paths, result['baseline']['native_policy'],
                os_id, product_policy, result['baseline'].get('native_previous'))
            result['vendor_preservation'] = verify_vendor_preservation(
                transport, vendor, app_vendor, packages_before, package_inventory(transport, os_id), os_id)
            result['online_app']['snapshot'] = lease.installed_name
            result['online_app']['snapshot_sha256'] = hashlib.sha256(xml.encode()).hexdigest()
            result['baseline_sha256'] = lease.state['baseline_sha256']
            result['target'] = target
            result['os_id'] = os_id
    except BaseException:
        (private / 'controller-error.txt').write_text(traceback.format_exc())
        raise
    finally:
        suite.close()
    result['owned_baseline_restoration_verified'] = True
    return result


def main(*, assets):
    directory = None
    try:
        system.require(os.geteuid() == 0, 'fixture-snapshots:root-required')
        system.require(prepare_vm.vm_config.selected().name in TARGETS,
                       'fixture-snapshots:target-not-qualified')
        os.umask(0o077)
        with session():
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-snapshots-'))
            result = qualify(directory, assets)
            (directory / 'result.json').write_bytes(system.baseline.encode(result))
        print('fixture-snapshots: passed; evidence=' + str(directory), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print('fixture-snapshots: ' + system.error_category(error), file=sys.stderr, flush=True)
        if directory is not None:
            print('fixture-snapshots: evidence=' + str(directory), file=sys.stderr, flush=True)
        return 1
