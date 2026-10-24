"""Qualify the shared provisioner on clean, watched Ubuntu/Fedora attempts.

This engineering selector does not enable any ordinary fixture consumer. The
unprivileged launcher selects the immutable input before this controller exists.
"""
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
sys.path.insert(0, str(ROOT))

import app_snapshot
from execution import open_source
import online_snapshot
import prepare_vm
from provenance import preflight_source
from qualification_storage import allocate, session
from suite_lease import Suite
import system_runner as system
from vm_transport import Transport
from tools import fixture_execution, fixture_manifest, fixture_provision
from tools.test_storage import authenticated_input
from tests.fixtures import baseline_assets, native_assets
from fixture_snapshot_qualification import policy_rules

TARGETS = prepare_vm.vm_config.fixture_targets()
TRUST = '/etc/fapolicyd/trust.d/onpc-fixture-runtime.trust'
COMPILED = '/etc/fapolicyd/compiled.rules'
COMBINED = ['native', 'activity', 'trusted-hard', 'trusted-soft', 'mechanical']
NATIVE_DIAGNOSTIC = r'''import json,pathlib,subprocess
def command(argv):
 return subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       check=True,timeout=30).stdout.decode()
pid=int(command(['/usr/bin/systemctl','show','fapolicyd.service','--property=MainPID','--value']).strip())
status={}
for line in pathlib.Path('/proc/'+str(pid)+'/status').read_text().splitlines():
 key,_,value=line.partition(':')
 if key in ('Uid','Gid','CapEff'):status[key]=value.strip()
config={}
for line in pathlib.Path('/etc/fapolicyd/fapolicyd.conf').read_text().splitlines():
 key,separator,value=line.partition('=')
 if separator and key.strip() in ('uid','gid','trust'):config[key.strip()]=value.strip()
release=dict(line.split('=',1) for line in pathlib.Path('/etc/os-release').read_text().splitlines() if '=' in line)
package=(['/usr/bin/rpm','-q','fapolicyd'] if release['ID'].strip('"')=='fedora' else
 ['/usr/bin/dpkg-query','-W','-f=${Package} ${Version}\n','fapolicyd'])
print(json.dumps({'pid':pid,'status':status,'config':config,
 'package':command(package).strip()},sort_keys=True))
'''


def selected_target():
    target = prepare_vm.vm_config.selected().name
    system.require(target in TARGETS, 'fixture-provisioning:target-not-qualified')
    return target, TARGETS[target]


def expected_admissions(members, accounts, os_id):
    """Independent finite rule text, without the guest's native policy builder."""
    if os_id != 'fedora' or not any(m['native_action'] in ('native-open', 'native-execute')
                                     for m in members.values()):
        return {}
    by_path = {m['destination']: m for m in members.values()}
    executables = [by_path[native_assets.executable_path(role)]['sha256']
                   for role in ('A', 'H', 'S', 'N')]
    gui = [by_path[native_assets.PREFIX + '/' + name]['sha256']
           for name in native_assets.GUI_FILES]
    for name, digest in zip(native_assets.GUI_FILES, gui):
        system.require(by_path[native_assets.PREFIX + '/Versioned/' + name]['sha256'] == digest,
                       'fixture-provisioning:runtime-alias')
    subject = ','.join(str(uid) for uid in sorted(accounts[role]['uid'] for role in ('child', 'other')))
    return {path: '# Finite reusable fixture admission; inputs remain untrusted.\n' + ''.join(
        f'allow perm={permission} uid={subject} : sha256hash={digest} trust=0\n' for digest in hashes)
        for path, permission, hashes in zip(native_assets.NATIVE_POLICY_PATHS,
                                            ('open', 'execute'), (gui, executables))}


def validate_native_policy(observed, members):
    os_id = observed['platform']['os']
    expected = expected_admissions(members, observed['accounts'], os_id)
    system.require(set(observed['admissions']) == set(expected),
                   'fixture-provisioning:admission-inventory')
    for path, text in expected.items():
        entry = observed['admissions'][path]
        system.require(entry['text'] == text and entry['sha256'] == hashlib.sha256(text.encode()).hexdigest()
                       and entry['length'] == len(text.encode()) and entry['uid'] == 0
                       and entry['gid'] == observed['native_gid'] and entry['mode'] == 0o644
                       and entry['regular'] is True and entry['nlink'] == 1,
                       'fixture-provisioning:exact-native-admission')
    if os_id == 'fedora':
        system.require(observed['selinux_enforcing'] is True, 'fixture-provisioning:selinux-not-enforcing')
        paths = {m['destination'] for m in members.values()} | set(expected)
        if observed['trust_entries']:
            paths.add(TRUST)
        labels = observed['labels']
        system.require(set(labels) == paths and all(
            type(entry) is dict and set(entry) == {'actual', 'expected'}
            and type(entry['actual']) is str and entry['actual'] == entry['expected']
            and re.fullmatch(r'[^:]+:[^:]+:[^:]+:s0(?:[:\-].*)?', entry['actual'])
            for entry in labels.values()), 'fixture-provisioning:selinux-labels')
        compiled = observed['compiled']
        sources = observed['rule_sources']
        system.require(set(expected) <= set(sources) and all(sources[p] == t for p, t in expected.items()),
                       'fixture-provisioning:admission-source')
        text = '## This file is automatically generated from /etc/fapolicyd/rules.d\n' + ''.join(
            line + '\n' for path in sorted(sources) for line in sources[path].splitlines()
            if line and not re.match(r'^\s*#', line))
        system.require(compiled['text'] == text and compiled['sha256'] == hashlib.sha256(text.encode()).hexdigest()
                       and compiled['uid'] == 0 and compiled['gid'] == observed['native_gid']
                       and compiled['mode'] == 0o644 and compiled['regular'] is True
                       and compiled['nlink'] == 1
                       and policy_rules(observed['public_rules'].encode(), numbered=True) == policy_rules(text.encode())
                       and '/usr/sbin/fagenrules: No change' in observed['rules_check'].splitlines(),
                       'fixture-provisioning:compiled-native-policy')
    else:
        system.require(observed['selinux_enforcing'] is None and observed['labels'] == {}
                       and observed['rule_sources'] == {} and observed['compiled'] is None
                       and observed['compiled_previous'] is None and observed['public_rules'] is None
                       and observed['rules_check'] is None,
                       'fixture-provisioning:platform-native-audit')


def selected_members(manifest, subsets, accounts):
    """Expected runtime metadata derived independently of the readiness receipt."""
    result = {}
    for key in fixture_manifest.select(subsets):
        member = deepcopy(manifest['members'][key])
        for role, account in accounts.items():
            member['destination'] = member['destination'].replace('@' + role + '@', account['home'])
        owner = accounts[member['owner']]
        member.update(uid=owner['uid'], gid=owner['gid'])
        result[key] = member
    return result


def validate_readback(observed, manifest, subsets, binding, *, installed):
    """Check actual bytes, ownership, exact native rows and guest attempt identity."""
    system.require(type(observed) is dict and set(observed) == {
        'accounts', 'files', 'unselected_present', 'boot_sha256', 'vm_uuid', 'run',
        'native_rows', 'native_gid', 'native_active', 'trust_entries',
        'vendor_database_sha256', 'preserved', 'staging', 'installed', 'platform',
        'selinux_enforcing', 'labels', 'admissions', 'rule_sources', 'compiled',
        'compiled_previous', 'public_rules', 'rules_check'},
        'fixture-provisioning:audit-schema')
    system.require(observed['platform'] == manifest['inputs']['target'],
                   'fixture-provisioning:platform-identity')
    accounts = fixture_provision.accepted_accounts(observed['accounts'])
    expected = selected_members(manifest, subsets, accounts)
    system.require(set(observed['files']) == set(expected) and not observed['unselected_present']
                   and not observed['staging'] and observed['installed'] is installed,
                   'fixture-provisioning:minimal-runtime')
    for key, member in expected.items():
        value = observed['files'][key]
        system.require(all(value.get(name) == member[name]
                           for name in ('sha256', 'length', 'mode', 'uid', 'gid'))
                       and value.get('nlink') == 1 and value.get('regular') is True,
                       'fixture-provisioning:independent-readback')
        row = (['filedb', member['destination'], str(member['length']), member['sha256']]
               if member['native_action'] == 'trust' else None)
        system.require(observed['native_rows'].get(key) == ([row] if row else []),
                       'fixture-provisioning:exact-native-trust')
    system.require(set(observed['native_rows']) == set(expected),
                   'fixture-provisioning:native-inventory')
    trusted = {member['destination']: {'length': member['length'], 'sha256': member['sha256']}
               for member in expected.values() if member['native_action'] == 'trust'}
    system.require(observed['trust_entries'] == trusted and observed['native_active'] is True,
                   'fixture-provisioning:native-activation')
    trust_file = observed['preserved']['@attempt-trust']
    system.require(trust_file is None if not trusted else trust_file is not None and trust_file['uid'] == 0
                   and trust_file['gid'] == observed['native_gid'] and trust_file['mode'] == 0o600
                   and trust_file['regular'] is True and trust_file['nlink'] == 1,
                   'fixture-provisioning:trust-metadata')
    system.require(all(observed[name] == binding[name] for name in ('boot_sha256', 'vm_uuid', 'run')),
                   'fixture-provisioning:actual-attempt')
    validate_native_policy(observed, expected)
    return expected


def verify_repeat(before, after):
    """Includes inode, nanosecond mtime/ctime and hash; reads may change atime."""
    system.require(before == after, 'fixture-provisioning:repeat-wrote-state')


class RecordingBoundary:
    """Observe the real shared SSH boundary, without replacing any guest action."""
    def __init__(self, transport):
        self.delegate = fixture_provision.SSHBoundary(transport)
        self.actions = []
        self.transfers = []

    def call(self, action, request, payloads=None):
        self.actions.append(action)
        if payloads is not None:
            self.transfers.append({key: {'length': len(data),
                                         'sha256': hashlib.sha256(data).hexdigest()}
                                   for key, data in payloads.items()})
        return self.delegate.call(action, request, payloads)


class LostReply(TimeoutError):
    """Engineering-only transport uncertainty after a completed real action."""


class InterruptedBoundary(RecordingBoundary):
    def call(self, action, request, payloads=None):
        reply = super().call(action, request, payloads)
        if action == 'stage':
            self.interrupted_request = deepcopy(request)
            self.stage_reply = deepcopy(reply)
            raise LostReply('fixture-provisioning:deliberate-lost-stage-reply')
        return reply


# A separate reader: no guest fixture module, provisioner receipt or native
# verifier participates. Only the frozen finite declaration supplies paths.
AUDIT = r'''import grp,hashlib,json,os,pathlib,pwd,re,stat,subprocess,sys
data=json.load(sys.stdin)
release=dict(line.split('=',1) for line in pathlib.Path('/etc/os-release').read_text().splitlines() if '=' in line)
platform={'os':release['ID'].strip('"'),'release':release['VERSION_ID'].strip('"'),'architecture':os.uname().machine}
assert platform in ({'os':'ubuntu','release':'26.04','architecture':'x86_64'},
 {'os':'fedora','release':'44','architecture':'x86_64'}),'audit-platform'
fedora=platform['os']=='fedora'
cli=('/usr/bin' if fedora else '/usr/sbin')+'/fapolicyd-cli'
def command(argv):
 raw=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    check=True,timeout=60).stdout
 assert len(raw)<=33554432,'audit-command-size'
 return raw.decode()
accounts={'system':{'uid':0,'gid':0,'home':'/root'}}
for role,name in (('child','onpc-child-riley'),('other','onpc-child-jordan'),('parent','onpc-parent-jamie')):
 p=pwd.getpwnam(name);accounts[role]={'uid':p.pw_uid,'gid':p.pw_gid,'home':p.pw_dir}
def path_for(member):
 path=member['destination']
 for role,account in accounts.items():path=path.replace('@'+role+'@',account['home'])
 return path
def read(path,text=False):
 p=pathlib.Path(path);assert p.resolve()==p,'audit-path-link'
 signature=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as f:
  s=os.fstat(f.fileno());assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=16777216,'audit-file'
  raw=f.read(16777217);assert len(raw)==s.st_size and signature(os.fstat(f.fileno()))==signature(s),'audit-file-changed'
 assert signature(p.lstat())==signature(s),'audit-file-replaced'
 result={'sha256':hashlib.sha256(raw).hexdigest(),'length':len(raw),'mode':stat.S_IMODE(s.st_mode),
         'uid':s.st_uid,'gid':s.st_gid,'device':s.st_dev,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,
         'ctime_ns':s.st_ctime_ns,'nlink':s.st_nlink,'regular':True}
 if text:result['text']=raw.decode()
 return result
selected=set(data['selected']);files={};unselected=[]
for key,m in data['members'].items():
 path=path_for(m)
 if os.path.lexists(path):
  if key in selected:files[key]=read(path)
  else:unselected.append(key)
for item in data['absences']:assert not os.path.lexists(item['destination']),'required-absence'
native_rows={key:[] for key in selected};by_path={path_for(m):k for k,m in data['members'].items()};vendor=[]
raw=command([cli,'--dump-db']).encode()
assert len(raw)<=33554432,'native-database-size'
for line in raw.decode().splitlines():
 first=line.split(None,1)
 fields=[first[0],*first[1].rsplit(None,2)] if len(first)==2 else []
 if len(fields)==4 and fields[1] in by_path:
  key=by_path[fields[1]]
  if key in selected:native_rows[key].append(fields)
  else:unselected.append('native:'+key)
 else:vendor.append(line)
preserved={}
for root in ('/etc/fapolicyd','/var/lib/oh-no-parent-control/preferences','/var/lib/AccountsService/users'):
 p=pathlib.Path(root)
 if not p.exists():continue
 assert p.resolve()==p and p.is_dir(),'preserved-directory'
 for current,dirs,names in os.walk(p,followlinks=False):
  assert all(not (pathlib.Path(current)/name).is_symlink() for name in dirs),'preserved-link'
  for name in sorted(names):
   path=str(pathlib.Path(current)/name)
   if path=='/etc/fapolicyd/trust.d/onpc-fixture-runtime.trust':continue
   preserved[path]=read(path)
   assert len(preserved)<=4096,'preserved-inventory-size'
trust=pathlib.Path('/etc/fapolicyd/trust.d/onpc-fixture-runtime.trust')
trust_entries={}
if trust.exists():
 files['@trust']=read(str(trust))
 for line in trust.read_text().splitlines():
  if not line.strip() or line.startswith('#'):continue
  fields=line.rsplit(None,2);assert len(fields)==3 and fields[0] not in trust_entries,'native-trust-format'
  trust_entries[fields[0]]={'length':int(fields[1]),'sha256':fields[2]}
active=subprocess.run(['/usr/bin/systemctl','is-active','fapolicyd.service'],stdin=subprocess.DEVNULL,
 stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
marker=json.loads(pathlib.Path('/etc/onpc-system-test.json').read_text())
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_bytes()
admissions={};sources={};compiled=None;previous=None;public=None;check=None;labels={};enforcing=None
if fedora:
 enforcing=command(['/usr/sbin/getenforce'])=='Enforcing\n'
 for name in data['admission_paths']:
  if os.path.lexists(name):admissions[name]=read(name,text=True)
 for path in pathlib.Path('/etc/fapolicyd/rules.d').iterdir():
  assert path.suffix=='.rules','audit-rule-source'
  sources[str(path)]=read(str(path),text=True)['text']
 compiled=read('/etc/fapolicyd/compiled.rules',text=True)
 if os.path.lexists('/etc/fapolicyd/compiled.rules.prev'):
  previous=read('/etc/fapolicyd/compiled.rules.prev',text=True)
 public=command([cli,'--list'])
 check=command(['/usr/sbin/fagenrules','--check'])
 label_paths={path_for(data['members'][key]) for key in files if key!='@trust'}|set(admissions)
 if trust.exists():label_paths.add(str(trust))
 for path in sorted(label_paths):
  labels[path]={'actual':os.getxattr(path,'security.selinux',follow_symlinks=False).rstrip(b'\0').decode(),
                'expected':command(['/usr/sbin/matchpathcon','-n',path]).strip()}
print(json.dumps({'accounts':accounts,'files':files,'unselected_present':sorted(unselected),
 'boot_sha256':hashlib.sha256(boot).hexdigest(),'vm_uuid':pathlib.Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower(),
 'run':marker['run'],'native_rows':native_rows,'native_gid':grp.getgrnam('fapolicyd').gr_gid,
 'native_active':active.returncode==0 and active.stdout==b'active\n','trust_entries':trust_entries,
 'vendor_database_sha256':hashlib.sha256(('\n'.join(sorted(vendor))+'\n').encode()).hexdigest(),
 'preserved':preserved,'staging':sorted(p.name for p in pathlib.Path('/run').iterdir() if p.name.startswith('onpc-fixture-')),
 'installed':pathlib.Path('/usr/lib/oh-no-parent-control').is_dir(),'platform':platform,
 'selinux_enforcing':enforcing,'labels':labels,'admissions':admissions,'rule_sources':sources,
 'compiled':compiled,'compiled_previous':previous,'public_rules':public,'rules_check':check},sort_keys=True))
'''


def audit(transport, manifest, subsets):
    raw = transport.call(['/usr/bin/python3', '-I', '-c', AUDIT],
        input=system.baseline.encode({'members': manifest['members'],
             'selected': list(fixture_manifest.select(subsets)), 'absences': manifest['absences'],
             'admission_paths': list(native_assets.NATIVE_POLICY_PATHS)}),
        timeout=120, attempts=1)
    system.require(type(raw) is bytes and len(raw) <= 2 * 1024 * 1024,
                   'fixture-provisioning:audit-size')
    value = json.loads(raw)
    # Trust metadata is part of the independent repeat comparison but is not
    # one of the manifest's selected payload members.
    trust = value['files'].pop('@trust', None)
    value['preserved']['@attempt-trust'] = trust
    return value


def unchanged_policy(before, after):
    ignored = {'@attempt-trust'}
    if after['admissions']:
        # The new finite admissions were independently proved by readback.
        # Only their two exact sources and compiler outputs may change; vendor
        # and product sources (including other files with similar names) stay pinned.
        system.require(not before['admissions'] and set(after['admissions']) == set(native_assets.NATIVE_POLICY_PATHS),
                       'fixture-provisioning:unexpected-policy-transition')
        previous = after['compiled_previous']
        system.require(previous is not None and previous['sha256'] == before['compiled']['sha256']
                       and previous['text'] == before['compiled']['text'] and previous['uid'] == 0
                       and previous['gid'] in (0, after['native_gid']) and previous['mode'] in (0o640, 0o644)
                       and previous['regular'] is True and previous['nlink'] == 1,
                       'fixture-provisioning:compiled-previous-preservation')
        ignored.update((*native_assets.NATIVE_POLICY_PATHS, COMPILED, COMPILED + '.prev'))
    original = {key: value for key, value in before['preserved'].items() if key not in ignored}
    current = {key: value for key, value in after['preserved'].items() if key not in ignored}
    system.require(original == current and before['vendor_database_sha256'] == after['vendor_database_sha256'],
                   'fixture-provisioning:unrelated-native-or-product-state-changed')


def runtime_witnesses(transport, members, accounts, os_id, *, only=None):
    """Use the existing recorded Popen/termination owner for each runtime family."""
    from tests.fixtures import build_test_applications as processes
    source = ('from __future__ import annotations\n'
              'import errno,json,os,pwd,select,signal,subprocess,sys\nfrom pathlib import Path\n'
              'READY_MARKER="ONPC_TEST_APPLICATION_READY"\n')
    for name in ('FixtureError', '_log', '_preexec_for_uid', 'launch_native', '_read_readiness', 'terminate'):
        source += inspect.getsource(getattr(processes, name)) + '\n'
    source += '''data=json.load(sys.stdin)
for path in data['paths']:
 process=launch_native(Path(path),data['uid'])
 terminate(process)
 assert process.returncode==0,'runtime-witness-exit'
for path in data['denied']:
 try:
  process=launch_native(Path(path),data['uid'])
 except PermissionError as error:
  assert error.errno in (errno.EACCES,errno.EPERM),'runtime-control-error'
 else:
  terminate(process)
  raise AssertionError('untrusted-control-executed')
print(json.dumps({'paths':data['paths'],'denied':data['denied'],'ready':True}))
'''
    paths = {member['destination'] for member in members.values() if member['mode'] == 0o755}
    witnesses = [path for path in (*(native_assets.executable_path(role) for role in ('A', 'H', 'S', 'N')),
        native_assets.ACTIVITY_EXECUTABLE,
        *(value[0] for value in native_assets.TRUSTED_NATIVE.values()), baseline_assets.MECHANICAL)
        if path in paths]
    # Fedora's stock 90-deny-execute precedes the product's 99 fallback.
    # Mechanical remains trust=0 and has no finite fixture admission.
    denied = [baseline_assets.MECHANICAL] if os_id == 'fedora' and baseline_assets.MECHANICAL in paths else []
    witnesses = [path for path in witnesses if path not in denied]
    if only is not None:
        system.require(type(only) is tuple and only and set(only) <= set(witnesses),
                       'fixture-provisioning:invalid-runtime-witness')
        witnesses = list(only)
    system.require(witnesses, 'fixture-provisioning:no-runtime-witness')
    value = json.loads(transport.call(['/usr/bin/python3', '-I', '-c', source],
        input=system.baseline.encode({'paths': witnesses, 'denied': denied, 'uid': accounts['child']['uid']}),
        timeout=120, attempts=1))
    system.require(value == {'paths': witnesses, 'denied': denied, 'ready': True}, 'fixture-provisioning:runtime-witness')
    return {'allowed': witnesses, 'denied_untrusted': denied}


def register_staging(directory, lease, attempt_id, path):
    system.require(re.fullmatch(r'/run/onpc-fixture-[0-9a-f]{64}', path) is not None,
                   'fixture-provisioning:staging-path')
    # The existing retained attempt allocation records intent before reserve.
    # This is evidence for its sole snapshot recovery owner, not a second journal.
    target = directory / 'fixture-staging-intent.json'
    with target.open('xb') as stream:
        stream.write(system.baseline.encode({'run': lease.state['run'],
            'vm_uuid': lease.state['domain_uuid'], 'attempt_id': attempt_id, 'staging': path}))
        stream.flush()
        os.fsync(stream.fileno())


def baseline_transport(suite, directory):
    (directory / 'input').mkdir(mode=0o700)
    (directory / 'input/selected-inputs.json').write_bytes(system.baseline.encode({
        'schema_version': 1, 'scope': 'fixture-provisioning-engineering'}))
    host_key = system.bootstrap(suite.commands, suite.lease, directory, suite.guestfs,
                               observation_only=True, environment_only=True)
    suite.lease.start()
    hostname = system.address(suite.source)
    (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
    transport = Transport({'directory': str(directory), 'hostname': hostname,
        'domain_uuid': suite.source.uuid, 'domain_id': suite.lease.view.domain_id,
        'run': suite.lease.state['run']}, suite.commands, guard=lambda _: suite.lease.guard(), lease=suite.lease)
    transport.probe_ready()
    return transport


def installed_transport(suite, directory, assets):
    lease = suite.lease
    package = assets / ('package.' + system.package_format(lease.capture.state['guest']))
    name = app_snapshot.snapshot_name(system.package_version(suite.commands, package))
    system.require(name in suite.source.domain.snapshotListNames(0),
                   'fixture-provisioning:app-snapshot-missing; run tools/prepare-appsnapshot')
    xml = suite.source.domain.snapshotLookupByName(name, 0).getXMLDesc(0)
    expected = app_snapshot.input_identity(lease, assets, suite.input_bundle(ROOT), suite.commands)
    system.require(app_snapshot.matches(xml, expected) and app_snapshot.mode_mismatch(xml, 'online') is None,
                   'fixture-provisioning:app-snapshot-stale; run tools/prepare-appsnapshot')
    system.require(online_snapshot.load(suite.source, name, xml) is not None,
                   'fixture-provisioning:app-credentials-missing')
    lease.installed_name, lease.installed_xml = name, xml
    (directory / 'input').mkdir(mode=0o700)
    # Existing online rebind reads these host identities; no product/fixture
    # payload is uploaded by this qualification before the provisioner runs.
    shutil.copyfile(package, directory / 'input' / package.name)
    (directory / 'input/selected-inputs.json').write_bytes(system.baseline.encode({
        'schema_version': 1, 'scope': 'fixture-provisioning-engineering'}))
    lease.online_pending = True
    host_key = online_snapshot.stage(suite.commands, lease, directory)
    lease.start()
    hostname = system.address(suite.source)
    (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
    transport = Transport({'directory': str(directory), 'hostname': hostname,
        'domain_uuid': suite.source.uuid, 'domain_id': lease.view.domain_id,
        'run': lease.state['run']}, suite.commands, guard=lambda _: lease.guard(), lease=lease)
    transport.probe_ready()
    return transport


def successful_attempt(suite, directory, selection, manifest, subsets, *, installed):
    attempt_id = directory.name
    transport = (installed_transport(suite, directory, directory.parent / 'assets')
                 if installed else baseline_transport(suite, directory))
    fixture_provision.Provisioner(suite.lease, transport,
        register_staging=lambda path: register_staging(
            directory, suite.lease, attempt_id, path)).wait_environment()
    before = audit(transport, manifest, subsets)
    system.require(not before['files'] and not before['unselected_present'] and not before['staging']
                   and before['preserved']['@attempt-trust'] is None,
                   'fixture-provisioning:capture-not-clean')
    boundary = RecordingBoundary(transport)
    controller = fixture_provision.Provisioner(suite.lease, transport, boundary=boundary,
        register_staging=lambda path: register_staging(directory, suite.lease, attempt_id, path))
    try:
        readiness = controller.provision(selection, subsets, attempt_id=attempt_id)
    except Exception:
        # Preserve an independent read-only observation before the sole VM
        # owner restores this terminal attempt. Never retry provisioning.
        try:
            (directory / 'failure-audit.json').write_bytes(
                system.baseline.encode(audit(transport, manifest, subsets)))
        except Exception:
            (directory / 'failure-audit-error.txt').write_text(traceback.format_exc())
        try:
            journal = transport.call(['/usr/bin/journalctl', '--unit', 'fapolicyd.service',
                '--boot', '--no-pager', '--lines', '80', '--output', 'short-monotonic'],
                timeout=30, attempts=1)
            system.require(type(journal) is bytes and len(journal) <= 256 * 1024,
                           'fixture-provisioning:diagnostic-size')
            (directory / 'failure-native-journal.txt').write_bytes(journal)
        except Exception:
            (directory / 'failure-native-journal-error.txt').write_text(traceback.format_exc())
        try:
            diagnostic = transport.call(['/usr/bin/python3', '-I', '-c', NATIVE_DIAGNOSTIC],
                                        timeout=60, attempts=1)
            system.require(type(diagnostic) is bytes and len(diagnostic) <= 16384,
                           'fixture-provisioning:diagnostic-size')
            (directory / 'failure-native-status.json').write_bytes(diagnostic)
        except Exception:
            (directory / 'failure-native-status-error.txt').write_text(traceback.format_exc())
        raise
    system.require(readiness.binding['attempt_id'] == attempt_id
                   and all(readiness.binding[name] == before[name]
                           for name in ('boot_sha256', 'vm_uuid', 'run')),
                   'fixture-provisioning:attempt-binding')
    observed = audit(transport, manifest, subsets)
    members = validate_readback(observed, manifest, subsets, readiness.binding, installed=installed)
    unchanged_policy(before, observed)
    expected_transfer = {key: {field: member[field] for field in ('length', 'sha256')}
                         for key, member in members.items()}
    system.require(boundary.transfers == [expected_transfer]
                   and boundary.actions == ['inspect', 'preflight', 'reserve', 'stage', 'place',
                                            'activate', 'readback', 'witness', 'clean'],
                   'fixture-provisioning:nonminimal-transfer')
    controller.require_ready(readiness)
    witnesses = runtime_witnesses(transport, members, observed['accounts'], observed['platform']['os'])
    first = audit(transport, manifest, subsets)
    start = len(boundary.actions)
    repeated = controller.provision(selection, subsets, attempt_id=attempt_id)
    system.require(repeated == readiness and boundary.actions[start:] == [
        'inspect', 'preflight', 'readback', 'witness'] and boundary.transfers == [expected_transfer],
        'fixture-provisioning:repeat-transfer')
    final = audit(transport, manifest, subsets)
    verify_repeat(first, final)
    controller.require_ready(repeated)
    unchanged_policy(before, final)
    return {'binding': readiness.binding, 'readback': final, 'runtime_witnesses': witnesses,
            'untrusted_runtime_controls': [member['destination'] for member in members.values()
                if member['native_action'] == 'native-execute' and member['destination'] in witnesses['allowed']],
            'first_transfer': expected_transfer, 'repeat_without_writes': True}


def require_terminal(controller):
    system.require(controller.failed and controller._receipt is None,
                   'fixture-provisioning:failed-receipt')
    try:
        controller.require_ready(None)
    except ValueError as error:
        system.require(str(error) == 'fixture-provision:terminal-attempt',
                       'fixture-provisioning:failed-input-boundary')
    else:
        raise ValueError('fixture-provisioning:failed-attempt-released-input')


STAGING_AUDIT = r'''import hashlib,json,os,pathlib,stat,sys
data=json.load(sys.stdin);path=pathlib.Path(data['staging'])
assert path.resolve()==path,'stage-link'
fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
try:
 info=os.fstat(fd)
 assert stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==0 and stat.S_IMODE(info.st_mode)==0o700,'stage-metadata'
 assert [info.st_dev,info.st_ino]==data['stage_identity'] and set(os.listdir(fd))==set(data['members']),'stage-inventory'
 for key,m in data['members'].items():
  with os.fdopen(os.open(key,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd),'rb') as stream:
   before=os.fstat(stream.fileno());raw=stream.read(8388609);after=os.fstat(stream.fileno())
   signature=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
   assert signature(before)==signature(after)==signature(os.stat(key,dir_fd=fd,follow_symlinks=False)) and stat.S_ISREG(before.st_mode) and before.st_nlink==1,'stage-file'
   assert before.st_uid==before.st_gid==0 and stat.S_IMODE(before.st_mode)==0o600,'stage-owner'
   assert [before.st_dev,before.st_ino]==data['stage_files'][key],'stage-file-identity'
   assert len(raw)==m['length'] and hashlib.sha256(raw).hexdigest()==m['sha256'],'stage-bytes'
 print(json.dumps({'staging':str(path),'selected':sorted(data['members']),'retained':True}))
finally:os.close(fd)
'''


def interrupted_attempt(suite, directory, selection, manifest):
    """Lose a reply after real SSH staging; the VM owner alone recovers it."""
    subsets = ['trusted-hard']
    transport = baseline_transport(suite, directory)
    controller = fixture_provision.Provisioner(suite.lease, transport,
        register_staging=lambda path: register_staging(directory, suite.lease, directory.name, path))
    controller.wait_environment()
    before = audit(transport, manifest, subsets)
    system.require(not before['files'] and not before['unselected_present'] and not before['staging']
                   and before['preserved']['@attempt-trust'] is None and not before['admissions'],
                   'fixture-provisioning:capture-not-clean')
    boundary = InterruptedBoundary(transport)
    controller = fixture_provision.Provisioner(suite.lease, transport, boundary=boundary,
        register_staging=lambda path: register_staging(directory, suite.lease, directory.name, path))
    try:
        controller.provision(selection, subsets, attempt_id=directory.name)
    except LostReply:
        require_terminal(controller)
    else:
        raise ValueError('fixture-provisioning:interruption-not-exercised')
    request = boundary.interrupted_request
    expected = selected_members(manifest, subsets, before['accounts'])
    transfer = {key: {field: member[field] for field in ('length', 'sha256')} for key, member in expected.items()}
    system.require(boundary.actions == ['inspect', 'preflight', 'reserve', 'stage']
                   and boundary.transfers == [transfer], 'fixture-provisioning:interruption-boundary')
    after = audit(transport, manifest, subsets)
    system.require(after['staging'] == [Path(request['staging']).name],
                   'fixture-provisioning:interrupted-staging-missing')
    verify_repeat(before, {**after, 'staging': []})
    proof = json.loads(transport.call(['/usr/bin/python3', '-I', '-c', STAGING_AUDIT],
        input=system.baseline.encode({'staging': request['staging'], 'stage_identity': request['stage_identity'],
            'stage_files': boundary.stage_reply['identities'], 'members': expected}), timeout=60, attempts=1))
    system.require(proof == {'staging': request['staging'], 'selected': sorted(expected), 'retained': True},
                   'fixture-provisioning:interrupted-stage-proof')
    # A replacement facade shares the terminal generation and cannot release input.
    replacement = fixture_provision.Provisioner(suite.lease, transport, boundary=boundary,
        register_staging=lambda _: (_ for _ in ()).throw(AssertionError('terminal mutation')))
    require_terminal(replacement)
    system.require(boundary.actions == ['inspect', 'preflight', 'reserve', 'stage'],
                   'fixture-provisioning:interruption-retried')
    return {'binding': request['binding'], 'staging_retained_for_vm_recovery': proof,
            'terminal_attempt': True, 'scenario_input_released': False, 'readback': after}


def foreign_attempt(suite, directory, selection, manifest):
    transport = baseline_transport(suite, directory)
    fixture_provision.Provisioner(suite.lease, transport,
        register_staging=lambda path: register_staging(
            directory, suite.lease, directory.name, path)).wait_environment()
    subsets = ['trusted-hard']
    before = audit(transport, manifest, subsets)
    path = native_assets.TRUSTED_NATIVE['trusted-hard'][0]
    # A deliberate engineering collision in this disposable owned attempt.
    program = '''import os,pathlib,sys
p=pathlib.Path(sys.argv[1]);assert not os.path.lexists(p)
p.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o755)
with os.fdopen(fd,'wb') as f:f.write(b'foreign qualification control\\n')
os.chmod(p,0o755)
'''
    transport.call(['/usr/bin/python3', '-I', '-c', program, path], attempts=1)
    foreign = audit(transport, manifest, subsets)
    boundary = RecordingBoundary(transport)
    controller = fixture_provision.Provisioner(suite.lease, transport, boundary=boundary,
        register_staging=lambda stage: register_staging(directory, suite.lease, directory.name, stage))
    try:
        controller.provision(selection, subsets, attempt_id=directory.name)
    except Exception:
        system.require(controller.failed and controller._receipt is None
                       and boundary.actions == ['inspect', 'preflight'] and not boundary.transfers,
                       'fixture-provisioning:foreign-refusal-boundary')
    else:
        raise ValueError('fixture-provisioning:foreign-destination-accepted')
    try:
        controller.require_ready(None)
    except ValueError as error:
        system.require(str(error) == 'fixture-provision:terminal-attempt',
                       'fixture-provisioning:failed-input-boundary')
    else:
        raise ValueError('fixture-provisioning:failed-attempt-released-input')
    after = audit(transport, manifest, subsets)
    verify_repeat(foreign, after)
    unchanged_policy(before, after)
    return {'foreign_destination_preserved': True, 'scenario_input_released': False,
            'terminal_attempt': True, 'actual_boot_sha256': after['boot_sha256']}


def qualify(directory, assets, selection):
    selection = fixture_execution.Selection.from_record(selection)
    # pkexec has a separate privileged retention owner. Keep the existing
    # authenticated caller read pin until VM recovery and suite.close finish;
    # it excludes retirement even if the unprivileged coordinator disappears.
    with authenticated_input(selection.record()):
        return _qualify_pinned(directory, assets, selection.record())


def _qualify_pinned(directory, assets, selection):
    # Every immutable source read and its compatibility refusal precedes acquire.
    selection = fixture_execution.Selection.from_record(selection)
    target, os_id = selected_target()
    system.require(selection.target == os_id, 'fixture-provisioning:input-target')
    manifest = fixture_execution.verify(selection)
    fixture_provision.authenticated_bundle(selection)
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite = Suite(open_source)
    result = {'target': target, 'selection': selection.record(), 'attempts': {}}
    try:
        suite.commands.directory = private
        system.stage_assets(system.artifact_source(assets), directory / 'assets', suite.commands)
        preflight_source(directory / 'assets')
        suite.input_bundle(ROOT)
        source, _, lease = suite.acquire(system.RunLedger())
        system.require(source.domain.name() == target, 'fixture-provisioning:target-not-qualified')
        with lease:
            system.require(system.package_format(lease.capture.state['guest']) ==
                           ('rpm' if os_id == 'fedora' else 'deb'),
                           'fixture-provisioning:target-not-qualified')
            system.require(lease.capture.state['guest'].get('fixture_boundary') == 'clean',
                           'fixture-provisioning:clean-baseline-required')
            cases = [('foreign', None, False), ('interrupted', None, False),
                     ('fresh-minimal', ['trusted-hard'], False),
                     ('installed-union', COMBINED, True)]
            for number, (name, subsets, installed) in enumerate(cases):
                if number:
                    lease.stop()
                    fixture_provision.reset_after_restore(lease)
                    if name == 'fresh-minimal':
                        result['attempts']['interrupted']['owned_restoration_verified_before_fresh_attempt'] = True
                lease.prepare()
                attempt_directory = directory / name
                attempt_directory.mkdir(mode=0o700)
                result['attempts'][name] = (interrupted_attempt(suite, attempt_directory, selection, manifest)
                    if name == 'interrupted' else foreign_attempt(suite, attempt_directory, selection, manifest)
                    if subsets is None else successful_attempt(suite, attempt_directory, selection,
                                                               manifest, subsets, installed=installed))
                (directory / 'attempt-results.json').write_bytes(system.baseline.encode(result))
            attempts = result['attempts']
            foreign_boot = attempts['foreign']['actual_boot_sha256']
            minimal = attempts['fresh-minimal']['binding']
            union = attempts['installed-union']['binding']
            interrupted = attempts['interrupted']['binding']
            system.require(len({foreign_boot, interrupted['boot_sha256'], minimal['boot_sha256'], union['boot_sha256']}) == 4
                           and len({interrupted['attempt_id'], minimal['attempt_id'], union['attempt_id']}) == 3,
                           'fixture-provisioning:fresh-attempt-required')
            fixture_execution.verify(selection)
    except BaseException:
        (private / 'controller-error.txt').write_text(traceback.format_exc())
        raise
    finally:
        suite.close()
    result['owned_baseline_restoration_verified'] = True
    return result


def main(*, assets, selection):
    directory = None
    try:
        system.require(os.geteuid() == 0, 'fixture-provisioning:root-required')
        selected_target()
        os.umask(0o077)
        with session():
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-provisioning-'))
            result = qualify(directory, assets, selection)
            (directory / 'result.json').write_bytes(system.baseline.encode(result))
        print('fixture-provisioning: passed; evidence=' + str(directory), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        if directory is not None:
            (directory / 'controller-error.txt').write_text(traceback.format_exc())
        print('fixture-provisioning: ' + system.error_category(error), file=sys.stderr, flush=True)
        if directory is not None:
            print('fixture-provisioning: evidence=' + str(directory), file=sys.stderr, flush=True)
        return 1
