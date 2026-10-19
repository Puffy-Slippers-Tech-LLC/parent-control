"""Native policy controls with private trees and independent kernel-query doubles.

Compiler children and fixture data use launcher scratch. No bus, mount, policy
load or installed PAM operation occurs. Coordinator owns inventory review.
"""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from tools import test_storage

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = 'usr/share/oh-no-parent-control/confinement'
STATE = 'var/lib/oh-no-parent-control/kiosk-confinement.json'
PROFILES = 'sys/kernel/security/apparmor/profiles'


@pytest.fixture(scope='module')
def policy_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-policy-authority')
    source, binary = directory / 'probe.c', directory / 'probe'
    source.write_text(r'''
#define _GNU_SOURCE
#define KIOSK_HOST_PROOF_OWNER getuid()
#define KIOSK_HOST_PROOF_GROUP getgid()
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const char *fault; static unsigned observations;
static int fake_enabled(void) { return strcmp(fault,"disabled")!=0; }
static int fake_enforce(void) { return strcmp(fault,"global-permissive")!=0; }
static unsigned short fake_class(const char *name) { return !strcmp(name,"process")&&strcmp(fault,"missing-class")?1:0; }
static uint32_t fake_perm(unsigned short cls,const char *name) { return cls==1&&!strcmp(name,"ptrace")&&strcmp(fault,"missing-permission")?2:0; }
struct test_decision { uint32_t allowed,decided,auditallow,auditdeny,seqno,flags; };
static int fake_compute(const char *source,const char *target,unsigned short cls,uint32_t perm,struct test_decision *decision) {
    if(strcmp(source,target)||cls!=1||perm!=2)exit(3);
    puts(source); observations++;
    if(!strcmp(fault,"query-failure"))return -1;
    if((!strcmp(fault,"manager-permissive")&&strstr(source,"onpc_kiosk_manager_t"))||
       (!strcmp(fault,"vendor-permissive")&&strstr(source,"policykit_auth_t"))) decision->flags=1;
    return 0;
}
static void *fake_open(const char *name,int flags) { (void)flags;return !strcmp(name,"libselinux.so.1")&&strcmp(fault,"missing-library")?(void*)1:NULL; }
static int fake_close(void *handle) { return handle==(void*)1?0:-1; }
static void *fake_symbol(void *handle,const char *name) {
    if(handle!=(void*)1)return NULL;
    if(!strcmp(fault,"missing-symbol")&&!strcmp(name,"security_compute_av_flags_raw"))return NULL;
    if(!strcmp(name,"is_selinux_enabled"))return (void*)fake_enabled;
    if(!strcmp(name,"security_getenforce"))return (void*)fake_enforce;
    if(!strcmp(name,"string_to_security_class"))return (void*)fake_class;
    if(!strcmp(name,"string_to_av_perm"))return (void*)fake_perm;
    if(!strcmp(name,"security_compute_av_flags_raw"))return (void*)fake_compute;
    return NULL;
}
#define KIOSK_POLICY_DLOPEN fake_open
#define KIOSK_POLICY_DLSYM fake_symbol
#define KIOSK_POLICY_DLCLOSE fake_close
#include "kiosk_policy_authority.h"
static void require(int ok) { if(!ok) {perror("policy-fixture");exit(2);} }
static void replace(int root,const char *path) {
    int fd=openat(root,path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);require(fd>=0);
    struct stat info;require(fstat(fd,&info)==0&&info.st_size>0);
    char *data=malloc((size_t)info.st_size);require(data!=NULL);
    require(read(fd,data,(size_t)info.st_size)==info.st_size&&close(fd)==0);
    require(unlinkat(root,path,0)==0);
    fd=openat(root,path,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,info.st_mode&07777);require(fd>=0);
    require(fchmod(fd,info.st_mode&07777)==0&&write(fd,data,(size_t)info.st_size)==info.st_size&&close(fd)==0);free(data);
}
int main(int argc,char **argv) {
    require(argc==5);fault=argv[3];
    int root=open(argv[1],O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);require(root>=0);
    int usr=openat(root,"usr",O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);require(usr>=0);
    struct kiosk_host_roots roots={.root=root,.usr=usr};
    int cfg=open(argv[2],O_RDONLY|O_NOFOLLOW|O_CLOEXEC);require(cfg>=0);struct stat info;require(fstat(cfg,&info)==0);
    char *bytes=malloc((size_t)info.st_size);require(bytes!=NULL&&read(cfg,bytes,(size_t)info.st_size)==info.st_size&&close(cfg)==0);
    void *crypto=dlopen("libcrypto.so.3",RTLD_NOW|RTLD_LOCAL);require(crypto!=NULL);
    uint64_t now;require(kiosk_host_now(&now)==0);uint64_t deadline=!strcmp(argv[4],"expired")?1:now+5000000ULL;
    struct kiosk_policy_authority policy={0};kiosk_policy_close(&policy);
    int result=kiosk_policy_acquire_until(&policy,&roots,bytes,(size_t)info.st_size,crypto,deadline);
    if(!result) {
        const char *mode=argv[4];
        if(!strcmp(mode,"state-replace"))replace(root,"var/lib/oh-no-parent-control/kiosk-confinement.json");
        if(!strcmp(mode,"config-replace"))replace(usr,"share/oh-no-parent-control/confinement/config.json");
        if(!strcmp(mode,"policy-replace"))replace(usr,!strcmp(policy.backend,"apparmor")?"share/oh-no-parent-control/confinement/onpc-kiosk.apparmor":"share/oh-no-parent-control/confinement/onpc-kiosk.cil");
        if(!strcmp(mode,"host-after-overlay")||!strcmp(mode,"overlay-only")) {
            require(renameat(root,"usr",root,"original-usr")==0&&mkdirat(root,"usr",0755)==0);
            if(!strcmp(mode,"host-after-overlay"))replace(usr,"share/oh-no-parent-control/confinement/config.json");
        }
        if(!strcmp(mode,"late-enforcement"))fault="global-permissive";
        if(!strcmp(mode,"late-apparmor")) {
            const char text[]="onpc-kiosk-manager (complain)\n";
            int fd=openat(root,"sys/kernel/security/apparmor/profiles",O_WRONLY|O_TRUNC|O_CLOEXEC);require(fd>=0);
            require(write(fd,text,sizeof(text)-1)==sizeof(text)-1&&close(fd)==0);
        }
        result=kiosk_policy_recheck_until(&policy,!strcmp(mode,"renewed-deadline")?deadline+1:deadline);
        if(!result)printf("verified %s %zu %zu %u\n",policy.backend,policy.config_size,policy.policy_size,observations);
    }
    kiosk_policy_close(&policy);kiosk_policy_close(&policy);free(bytes);
    require(close(root)==0&&close(usr)==0&&dlclose(crypto)==0);return result?1:0;
}
''')
    result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                             '-I', str(ROOT / 'tools'), str(source), '-ldl', '-o', str(binary)],
                            capture_output=True, text=True, timeout=30,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    return binary


def _encode(value):
    return json.dumps(value, sort_keys=True).encode() + b'\n'


@pytest.fixture
def policy_case(tmp_path):
    root = tmp_path / 'host'
    root.mkdir(mode=0o755)
    return dict(root=root, directory=tmp_path, backend='apparmor',
                config=dict(backend='apparmor', domains=['manager', 'manager-pam'],
                            apparmor_profiles=['onpc-kiosk-manager', 'onpc-kiosk-gate'],
                            preserved_executables=[{'role': 'polkit'}]),
                policy=b'independently attested policy\n',
                state_extra={}, profiles=b'onpc-kiosk-manager (enforce)\nonpc-kiosk-gate (enforce)\n')


def _write(case):
    config = _encode(case['config'])
    state = dict(schema=1, backend=case['backend'], admission_protocol=1,
                 pam={'gdm-password': {}, 'systemd-user': {}},
                 loaded_config_sha256=hashlib.sha256(config).hexdigest(),
                 loaded_policy_sha256=hashlib.sha256(case['policy']).hexdigest())
    state.update(case['state_extra'])
    values = {STATE: _encode(state), PAYLOAD + '/config.json': config,
              PAYLOAD + ('/onpc-kiosk.apparmor' if case['backend'] == 'apparmor' else '/onpc-kiosk.cil'): case['policy'],
              PROFILES: case['profiles']}
    for name, data in values.items():
        path = case['root'] / name
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in path.parents:
            if parent == case['root']:
                break
            parent.chmod(0o755)
        path.write_bytes(data)
        path.chmod(0o600 if name == STATE else 0o644)
    expected = case['directory'] / 'expected-config'
    expected.write_bytes(config)
    return expected


def _run(probe, case, *, mode='unchanged', fault='none', mutate=None):
    expected = _write(case)
    if mutate:
        mutate(case['root'], expected)
    return subprocess.run([str(probe), str(case['root']), str(expected), fault, mode],
                          capture_output=True, text=True, timeout=10,
                          pass_fds=test_storage.scratch_descriptors())


@pytest.mark.parametrize('mode', ['unchanged', 'overlay-only'])
def test_apparmor_authority_uses_original_anchors(policy_probe, policy_case, mode):
    result = _run(policy_probe, policy_case, mode=mode)
    assert result.returncode == 0, result.stderr
    assert 'verified apparmor' in result.stdout


@pytest.mark.parametrize('mode', ['state-replace', 'config-replace', 'policy-replace',
                                 'host-after-overlay', 'late-apparmor', 'renewed-deadline', 'expired'])
def test_final_policy_proof_refuses_drift(policy_probe, policy_case, mode):
    assert _run(policy_probe, policy_case, mode=mode).returncode == 1


@pytest.mark.parametrize('field,value', [('schema', 2), ('backend', 'selinux'),
    ('loaded_config_sha256', '0' * 64), ('loaded_policy_sha256', 'f' * 64),
    ('pam', {'gdm-password': {}})])
def test_native_attestation_rejects_wrong_state(policy_probe, policy_case, field, value):
    policy_case['state_extra'][field] = value
    assert _run(policy_probe, policy_case).returncode == 1


@pytest.mark.parametrize('profiles', [b'onpc-kiosk-manager (enforce)\n',
    b'onpc-kiosk-manager (complain)\nonpc-kiosk-gate (enforce)\n',
    b'prefix-onpc-kiosk-manager (enforce)\nonpc-kiosk-gate (enforce)\n',
    b'onpc-kiosk-manager (enforce) trailing\nonpc-kiosk-gate (enforce)\n'])
def test_enforcement_requires_each_exact_apparmor_profile(policy_probe, policy_case, profiles):
    policy_case['profiles'] = profiles
    assert _run(policy_probe, policy_case).returncode == 1


def _selinux(case):
    case['backend'] = case['config']['backend'] = 'selinux'
    case['config'].pop('apparmor_profiles')


def test_selinux_queries_all_domains_and_vendor_helper(policy_probe, policy_case):
    _selinux(policy_case)
    result = _run(policy_probe, policy_case)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        'system_u:system_r:onpc_kiosk_manager_t:s0',
        'system_u:system_r:onpc_kiosk_manager_pam_t:s0',
        'system_u:system_r:policykit_auth_t:s0'] * 2 + [
            f'verified selinux {len(_encode(policy_case["config"]))} {len(policy_case["policy"])} 6']


@pytest.mark.parametrize('fault', ['disabled', 'global-permissive', 'manager-permissive',
    'vendor-permissive', 'missing-class', 'missing-permission', 'query-failure',
    'missing-library', 'missing-symbol'])
def test_selinux_enforcement_fails_closed(policy_probe, policy_case, fault):
    _selinux(policy_case)
    assert _run(policy_probe, policy_case, fault=fault).returncode == 1


def test_final_selinux_enforcement_is_repeated(policy_probe, policy_case):
    _selinux(policy_case)
    assert _run(policy_probe, policy_case, mode='late-enforcement').returncode == 1


@pytest.mark.parametrize('change', ['state-mode', 'state-hardlink', 'config-link',
                                    'config-unsafe-parent', 'config-expected-mismatch'])
def test_policy_paths_and_named_state_are_private(policy_probe, policy_case, change):
    def mutate(root, expected):
        if change == 'state-mode':
            (root / STATE).chmod(0o644)
        elif change == 'state-hardlink':
            (root / (STATE + '.other')).hardlink_to(root / STATE)
        elif change == 'config-link':
            target = root / (PAYLOAD + '/config.json')
            moved = target.with_suffix('.original')
            target.rename(moved)
            target.symlink_to(moved.name)
        elif change == 'config-unsafe-parent':
            (root / PAYLOAD).chmod(0o775)
        else:
            expected.write_bytes(b'{"backend":"changed"}\n')
    assert _run(policy_probe, policy_case, mutate=mutate).returncode == 1

