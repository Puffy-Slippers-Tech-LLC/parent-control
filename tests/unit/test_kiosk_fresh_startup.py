"""Complete native fresh-manager transaction in private kernel namespaces.

The production child, authorities, binder and publisher consume real private
files and mounts. Only account/PAM/MAC policy and the root-name mapping are
fixture boundaries. No installed path, service or host mount is changed.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import test_storage


ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = '/usr/share/oh-no-parent-control/confinement'


# This is an executable preparation child, not a replacement coordinator. It
# calls the same serve(), required_material(), InitialPreparation() and channel
# owners as the installed helper with independently opened private host files.
HELPER = r'''
import copy, hashlib, importlib.util, json, os, socket, sys, traceback
from types import SimpleNamespace
from pathlib import Path
base = Path(@BASE@)
diagnostic_open = os.open
def report_error(kind, error, tb):
    fd = diagnostic_open(str(base / 'helper-error'), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, ('fresh-python-error:' + kind.__name__ + ':' + str(error) + '\n').encode())
        try:
            os.write(fd, ''.join(traceback.format_exception(kind, error, tb)).encode())
        except BaseException as diagnostic_error:
            os.write(fd, ('traceback-error:' + type(diagnostic_error).__name__ + ':' + str(diagnostic_error) + '\n').encode())
    finally:
        os.close(fd)
sys.excepthook = report_error
with open(base / 'helper-started', 'x') as report:
    json.dump(dict(pid=os.getpid(), deadline=int(sys.argv[4]),
                   lock=os.fstat(4).st_ino, lease=os.fstat(5).st_ino), report)
sys.path.insert(0, @TOOLS@)
import kiosk_confinement as c
import kiosk_preparation_service as service
import kiosk_preparation_input as channel_input
import fcntl
host = base / 'host'
raw_open, raw_readlink = os.open, os.readlink
raw_fstat, raw_stat = os.fstat, os.stat
channel_identity = channel_input._identity
def observed_identity(fd, regular):
    try:
        return channel_identity(fd, regular)
    except BaseException:
        info = raw_fstat(fd)
        with open('/proc/self/fdinfo/' + str(fd)) as stream:
            kernel = stream.read()
        try:
            seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
        except OSError as error:
            seals = 'error:' + str(error)
        record = diagnostic_open(str(base / 'helper-error'), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(record, ('identity-failure:fd=' + str(fd) + ' regular=' + str(regular) +
                             ' seals=' + str(seals) + ' mode=' + oct(info.st_mode) +
                             ' links=' + str(info.st_nlink) + '\n' + kernel).encode())
        finally:
            os.close(record)
        raise
channel_input._identity = observed_identity
path_open, path_stat, path_lstat = Path.open, Path.stat, Path.lstat
path_exists, path_islink, path_iterdir = Path.exists, Path.is_symlink, Path.iterdir
def physical(path):
    p = Path(path)
    return host / str(p).lstrip('/') if p == Path('/usr') or Path('/usr') in p.parents else p
def logical(path):
    return Path('/') / path.relative_to(host) if host in path.parents else path
Path.open = lambda p, *a, **kw: path_open(physical(p), *a, **kw)
Path.stat = lambda p, **kw: path_stat(physical(p), **kw)
Path.lstat = lambda p: path_lstat(physical(p))
Path.exists = lambda p, **kw: path_exists(physical(p), **kw)
Path.is_symlink = lambda p: path_islink(physical(p))
Path.iterdir = lambda p: iter(logical(q) for q in path_iterdir(physical(p)))
os.open = lambda p, *a, **kw: raw_open(physical(p) if isinstance(p, (str, Path)) and str(p).startswith('/') else p, *a, **kw)
os.readlink = lambda p, *a, **kw: raw_readlink(physical(p) if p else p, *a, **kw)
# Root-name translation includes the launcher-owned ancestors; their modes and
# IDs are fixture boundaries, while every member beneath host/runtime keeps
# its real complete kernel metadata.
def metadata(info, path):
    if path == base or path in base.parents:
        fields = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        fields.update(st_uid=0, st_gid=0, st_mode=info.st_mode & ~0o7022)
        return SimpleNamespace(**fields)
    return info
def stat_path(path, *, dir_fd=None, follow_symlinks=True):
    actual = physical(path)
    if dir_fd is not None:
        actual = Path(raw_readlink('/proc/self/fd/' + str(dir_fd))) / str(path)
    return metadata(raw_stat(physical(path), dir_fd=dir_fd, follow_symlinks=follow_symlinks), actual)
os.stat = stat_path
os.fstat = lambda fd: metadata(raw_fstat(fd), Path(raw_readlink('/proc/self/fd/' + str(fd))))
Path.lstat = lambda p: metadata(path_lstat(physical(p)), physical(p))
Path.stat = lambda p, **kw: metadata(path_stat(physical(p), **kw), physical(p))
trusted = c.trusted
c.trusted = lambda p, **kw: logical(trusted(physical(p), **kw))
runtime_open = c.runtime_open
c.runtime_open = lambda p, **kw: runtime_open(physical(p), **kw)
c.RUNTIME = base / 'runtime'
config_bytes = (host / @CONFIG@).read_bytes()
config = json.loads(config_bytes)
policy_bytes = (host / @POLICY@).read_bytes()
c.runtime_input_specs = lambda distribution: copy.deepcopy(config['runtime_inputs'])
c.enforcing = lambda cfg: None
attestation = ' '.join(hashlib.sha256(x).hexdigest() for x in (config_bytes, policy_bytes)) + '\n'
def measure(role, deadline_ns):
    service._before(deadline_ns)
    snapshot = c.required_material(config_bytes, policy_bytes, attestation)
    return snapshot, config_bytes, b'ONPC-KIOSK-ACCOUNT\t1\t4242\t4242\t1\n4242\n'
production_measure = service.measure
service.measure = measure
mode = (base / 'mode').read_text()
if mode in ('measurement-config-refusal', 'measurement-policy-refusal', 'measurement-helper-refusal',
            'measurement-production-healthy', 'measurement-attestation-refusal'):
    service.measure = production_measure
    service._account = lambda deadline: b'ONPC-KIOSK-ACCOUNT\t1\t4242\t4242\t1\n4242\n'
    spec = importlib.util.spec_from_file_location('private_policy_integration',
        Path(@TOOLS@).parent / 'packaging/kiosk_confinement.py')
    integration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(integration)
    saved_policy = json.loads((host / 'var/lib/oh-no-parent-control/kiosk-confinement.json').read_text())
    if mode in ('measurement-config-refusal', 'measurement-policy-refusal'):
        saved_policy['loaded_' + ('config' if mode == 'measurement-config-refusal' else 'policy') + '_sha256'] = '0' * 64
    # Integration-command/account/MAC boundaries remain finite doubles. Execute
    # the real service measure -> required_material -> preserved_inventory path.
    def integration_verify(args, **kwargs):
        assert args == ['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'verify']
        assert kwargs['env'] == c.ENV and kwargs['check'] and kwargs['capture_output'] and kwargs['text']
        assert 0 < kwargs['timeout'] <= 5
        (base / 'measurement-command').write_text(mode)
        try:
            digests = integration.verify_policy(saved_policy)
        except ValueError as error:
            assert error.args == ('policy-load-incomplete-reconfigure-required',)
            (base / 'measurement-attestation').write_text('actual-policy-digest-refusal')
            raise service.subprocess.CalledProcessError(1, args, stderr='private attestation detail') from error
        return SimpleNamespace(stdout='invalid attestation\n' if mode == 'measurement-attestation-refusal' else ' '.join(digests) + '\n')
    service.subprocess.run = integration_verify
    if mode == 'measurement-helper-refusal':
        inventory = c.preserved_inventory
        def invalid_inventory(config):
            (base / 'measurement-inventory').write_text('real-preserved-inventory')
            return inventory(dict(config, preserved_executables=[dict(
                path='/usr/bin/ambient', mode=0o644, label=None)]))
        c.preserved_inventory = invalid_inventory
if mode == 'helper-exit':
    sys.exit(17)
if mode == 'helper-timeout':
    import signal
    while True: signal.pause()
if mode in ('helper-order', 'helper-identity'):
    import array
    deadline = int(sys.argv[4])
    snapshot, configuration, account = measure('manager', deadline)
    with service._record(service.receipt.material_canonical(snapshot['record']), deadline) as material_fd, \
            service._record(configuration, deadline) as config_fd, service._record(account, deadline) as account_fd:
        fds = [material_fd, config_fd, account_fd]
        packet = bytearray(channel_input._phase_packet(1, 'manager', 'apparmor',
                           bytes.fromhex(snapshot['digest']), bytes(32), fds, deadline))
        # Change exactly one checked property of an otherwise valid transfer.
        packet[8 if mode == 'helper-order' else 96 + 15] ^= 2 if mode == 'helper-order' else 1
        socket.socket(fileno=3).sendmsg([packet], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', fds))])
    sys.exit(0)
if mode in ('result-malformed', 'ticket-parent', 'ticket-malformed', 'copy-replacement', 'source-replacement', 'required-drift', 'ambient-narrow'):
    original = service._canonical
    def canonical(record, deadline_ns):
        if isinstance(record, dict) and record.get('role') == 'manager':
            if mode == 'ticket-malformed':
                return b'{}'
            if mode == 'ticket-parent':
                record['ticket']['parent'][1] += 1
            elif mode == 'result-malformed':
                record['plan'] = {}
        return original(record, deadline_ns)
    service._canonical = canonical
if mode in ('helper-result-exit', 'copy-replacement', 'source-replacement', 'required-drift', 'ambient-narrow',
            'selection-lock-replaced', 'selection-lease-replaced'):
    detached = c.InitialPreparation.detach
    def detach(attempt):
        # Mutate after the real Python owner successfully transfers its ticket.
        # Native finish() must reap this child before consuming the change.
        ticket = detached(attempt)
        if mode == 'helper-result-exit':
            sys.exit(17)
        if mode.startswith('selection-'):
            name = 'lock' if mode == 'selection-lock-replaced' else 'lease'
            p = base / name
            p.rename(base / ('original-' + name))
            p.write_bytes(b'foreign-lock')
            p.chmod(0o600)
            return ticket
        if mode == 'copy-replacement':
            p = c.RUNTIME / ticket['name'] / 'native-0'
            original_bytes = p.read_bytes()
            p.rename(p.with_name('displaced-copy'))
            p.write_bytes(original_bytes)
            p.chmod(0o755)
            foreign = raw_stat(p)
            original = ticket['members']['native-0']
            (base / 'fault-copy').write_text(ticket['name'] + '/native-0 ' +
                ' '.join(map(str, (foreign.st_dev, foreign.st_ino, *original))))
        elif mode in ('source-replacement', 'required-drift'):
            p = physical('/usr/bin/native')
            if mode == 'source-replacement':
                original_bytes = p.read_bytes()
                p.rename(p.with_name('displaced-native'))
                p.write_bytes(original_bytes)
                p.chmod(0o755)
            else:
                p.write_bytes(b'\x7fELFchanged-required')
        else:
            physical('/usr/bin/ambient').chmod(0o666)
        return ticket
    c.InitialPreparation.detach = detach
encode_result = service._canonical
def capture_result(record, deadline_ns):
    data = encode_result(record, deadline_ns)
    with open(base / 'helper-result.json', 'wb') as output:
        output.write(data)
    return data
service._canonical = capture_result
with socket.socket(fileno=int(sys.argv[3])) as channel:
    service.serve(channel, role=sys.argv[2], deadline_ns=int(sys.argv[4]))
'''


NATIVE = r'''
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <dirent.h>
#include <dlfcn.h>
#include <limits.h>
#include <linux/capability.h>
#include <pwd.h>
#include <sched.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/wait.h>
#include <syslog.h>
#include <time.h>
#include <unistd.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>
#include <security/pam_ext.h>
static const char *base, *mode;
static unsigned environment_calls, mac_calls, ready_commits;
static int final_fd_baseline;
static int original_source=-1, partial_write;
static struct stat original_nested;
static struct stat original_target_info;
static struct statx original_target_mount;
static const char *origin_paths[]={"/usr/bin/native","/usr/bin/script","/usr/bin/ambient",
    "/usr/bin/ambient-tree","/usr/share/oh-no-parent-control/confinement/config.json",
    "/usr/share/oh-no-parent-control/confinement/onpc-kiosk.apparmor"};
static struct stat original_origins[sizeof(origin_paths)/sizeof(*origin_paths)];
static uint64_t transaction_deadline;
static struct stat caller_objects[4096];
static unsigned char caller_fds[4096];
static unsigned selinux_order;
static unsigned fault_hits, contention_checks, writer_barriers, cleanup_hits;
static void contend(void);
static void writer_barrier(const char *phase) {
    char prefix[64];snprintf(prefix,sizeof(prefix),"writer-%s-",phase);
    if(strncmp(mode,prefix,strlen(prefix)) || writer_barriers) return;
    writer_barriers++;contend();
}
static int ready_expected(void) {
    return !strcmp(mode,"healthy") || !strcmp(mode,"measurement-production-healthy") || !strcmp(mode,"ambient-narrow") || !strcmp(mode,"concurrent-writers") ||
        !strncmp(mode,"writer-",7) ||
        !strcmp(mode,"mac-failure") || !strcmp(mode,"mac-cleanup-cut") || !strcmp(mode,"mac-readback") || !strcmp(mode,"mac-deadline") ||
        !strcmp(mode,"environment-failure") || !strcmp(mode,"post-attach-required-drift") ||
        !strncmp(mode,"ready-",6) || !strncmp(mode,"premac-",7) || !strcmp(mode,"generation-three");
}
static void require(int ok, const char *stage) {
    if (!ok) { fprintf(stderr,"fresh-witness:%s:%s\n",stage,strerror(errno)); exit(2); }
}
static void fixture_syslog(const pam_handle_t *p,int priority,const char *format,...) {
    (void)p;(void)priority;va_list a;va_start(a,format);vfprintf(stderr,format,a);fputc('\n',stderr);va_end(a);
}
static void unpack_required(void) {
    char before[19],after[19];
    require(pread(original_source,before,sizeof(before),0)==(ssize_t)sizeof(before) &&
        !memcmp(before,"\177ELF/usr/bin/native",sizeof(before)),"independent-original-required-before-unpack");
    /* Distribution unpack does not acquire either cooperating-writer lock. */
    require(pwrite(original_source,"X",1,4)==1 && fsync(original_source)==0 &&
        pread(original_source,after,sizeof(after),0)==(ssize_t)sizeof(after) && after[4]=='X' &&
        memcmp(before,after,sizeof(before)),"unlocked-original-required-unpack");fault_hits++;
}
static ssize_t fixture_recvmsg(int channel,struct msghdr *message,int flags) {
    ssize_t result=recvmsg(channel,message,flags);int saved=errno;
    if(result>0 && message->msg_iovlen==1 && message->msg_iov[0].iov_len>=9 &&
        !memcmp(message->msg_iov[0].iov_base,"ONPCPRE2",8) &&
        ((unsigned char *)message->msg_iov[0].iov_base)[8]==1) {
        /* A real completed measurement is waiting for native authority checks;
         * the preparation child cannot select or publish until its reply. */
        writer_barrier("measurement");
        if(!strcmp(mode,"measurement-required-drift") && !fault_hits) unpack_required();
    }
    errno=saved;return result;
}
/* Only the capability API boundary is doubled for these finite controls.
 * Ordinary complete transactions below still use the real caller syscalls. */
static unsigned capability_get_calls, capability_set_calls, capability_ambient_calls;
static int capability_ambient;
static struct __user_cap_data_struct capability_state[2], capability_original[2];
static int capability_model(void) {return !strncmp(mode,"capabilities-",13);}
static void capability_begin(void) {
    capability_get_calls=capability_set_calls=capability_ambient_calls=0;
    capability_state[0]=(struct __user_cap_data_struct){.effective=0x12345678U,.permitted=0xffffffffU,.inheritable=0x10U};
    capability_state[1]=(struct __user_cap_data_struct){.effective=0x40U,.permitted=0x148U,.inheritable=8U};
    capability_ambient=1;
    if(!strcmp(mode,"capabilities-zero")){capability_state[0].inheritable=capability_state[1].inheritable=0;capability_ambient=0;}
    memcpy(capability_original,capability_state,sizeof(capability_original));
}
static long fixture_capget(struct __user_cap_header_struct *header,struct __user_cap_data_struct *data) {
    capability_get_calls++;
    require(header->version==_LINUX_CAPABILITY_VERSION_3 && header->pid==0,"capget-only-current-task-v3");
    if(!capability_model())return syscall(SYS_capget,header,data);
    if((capability_get_calls==1 && !strcmp(mode,"capabilities-get-before")) ||
        (capability_get_calls==2 && !strcmp(mode,"capabilities-get-after"))){errno=EIO;return -1;}
    memcpy(data,capability_state,sizeof(capability_state));
    if(capability_get_calls==2) {
        if(!strcmp(mode,"capabilities-inheritable-drift"))data[1].inheritable=8U;
        if(!strcmp(mode,"capabilities-effective-drift"))data[1].effective^=1U;
        if(!strcmp(mode,"capabilities-permitted-drift"))data[0].permitted^=1U;
    }
    return 0;
}
static long fixture_capset(struct __user_cap_header_struct *header,const struct __user_cap_data_struct *data) {
    capability_set_calls++;
    require(header->version==_LINUX_CAPABILITY_VERSION_3 && header->pid==0,"capset-only-current-task-v3");
    if(!capability_model())return syscall(SYS_capset,header,data);
    for(unsigned i=0;i<2;i++)require(!data[i].inheritable && data[i].effective==capability_original[i].effective &&
        data[i].permitted==capability_original[i].permitted,"capset-clears-only-inheritable-preserves-executor-authority");
    if(!strcmp(mode,"capabilities-set")){errno=EPERM;return -1;}
    memcpy(capability_state,data,sizeof(capability_state));return 0;
}
static int fixture_ambient_clear(void) {
    capability_ambient_calls++;
    if(!capability_model())return prctl(PR_CAP_AMBIENT,PR_CAP_AMBIENT_CLEAR_ALL,0,0,0);
    if(!strcmp(mode,"capabilities-ambient")){errno=EPERM;return -1;}
    capability_ambient=0;return 0;
}
static void capability_expect(int result) {
    int positive=!strcmp(mode,"capabilities-inherited") || !strcmp(mode,"capabilities-zero");
    require((result==0)==positive,"capability-clear-result");
    unsigned gets=!strcmp(mode,"capabilities-expired")?0:
        (!strcmp(mode,"capabilities-get-before") || !strcmp(mode,"capabilities-set") || !strcmp(mode,"capabilities-ambient"))?1:2;
    unsigned sets=gets && strcmp(mode,"capabilities-get-before");
    unsigned ambient=sets && strcmp(mode,"capabilities-set");
    require(capability_get_calls==gets && capability_set_calls==sets && capability_ambient_calls==ambient,
        "bounded-capability-syscall-order-and-failure-cut");
    for(unsigned i=0;i<2;i++)require(capability_state[i].effective==capability_original[i].effective &&
        capability_state[i].permitted==capability_original[i].permitted,"unchanged-effective-permitted-authority");
    if(positive)require(!capability_state[0].inheritable && !capability_state[1].inheritable && !capability_ambient,
        "all-inheritable-words-and-ambient-cleared");
}
static uint64_t actual_bounding_set(void) {
    uint64_t mask=0;
    for(unsigned i=0;i<64;i++){
        int value=prctl(PR_CAPBSET_READ,i,0,0,0);
        if(value<0){require(errno==EINVAL && i>0,"bounded-capability-read");break;}
        require(value==0 || value==1,"bounding-set-bit");if(value)mask|=1ULL<<i;
    }
    return mask;
}
static unsigned descriptors(void) {
    DIR *d=opendir("/proc/self/fd"); require(d!=NULL,"fd-census");
    unsigned n=0; struct dirent *e;
    while((e=readdir(d))) if(strcmp(e->d_name,".") && strcmp(e->d_name,"..")) n++;
    closedir(d); return n;
}
static const char *map(const char *path, char out[PATH_MAX]) {
    if (!strcmp(path,"/")) snprintf(out,PATH_MAX,"%s/host",base);
    else if (!strncmp(path,"/run/oh-no-parent-control",strlen("/run/oh-no-parent-control"))) {
        if (!strcmp(path,"/run/oh-no-parent-control-confinement.lock")) snprintf(out,PATH_MAX,"%s/lock",base);
        else if (!strcmp(path,"/run/oh-no-parent-control-kiosk-admission.lock")) snprintf(out,PATH_MAX,"%s/lease",base);
        else snprintf(out,PATH_MAX,"%s/runtime%s",base,path+strlen("/run/oh-no-parent-control-confinement"));
    } else if ((!strncmp(path,"/usr",4) || !strncmp(path,"/var",4)) && (!path[4] || path[4]=='/')) snprintf(out,PATH_MAX,"%s/host%s",base,path);
    else return path;
    return out;
}
static int fixture_open(const char *p,int flags,...) {
    mode_t permission=0; if(flags&O_CREAT) {va_list a;va_start(a,flags);permission=va_arg(a,int);va_end(a);}
    char out[PATH_MAX]; return open(map(p,out),flags,permission);
}
static int fixture_lstat(const char *p,struct stat *s) {char out[PATH_MAX];return lstat(map(p,out),s);}
static int fixture_mkdir(const char *p,mode_t m) {char out[PATH_MAX];return mkdir(map(p,out),m);}
static int fixture_statx(int fd,const char *p,int flags,unsigned mask,struct statx *s) {
    char out[PATH_MAX];return statx(fd,p[0]=='/'?map(p,out):p,flags,mask,s);
}
static int fixture_mount(const char *source,const char *target,const char *type,unsigned long flags,const void *data) {
    if(!strcmp(mode,"bind-cut") && (flags&MS_BIND) && !fault_hits++) {errno=EIO;return -1;}
    if(flags&MS_BIND) {
        writer_barrier("bind");
        if(!strcmp(mode,"bind-required-drift") && !fault_hits) {
            char named[PATH_MAX];ssize_t length=readlink(source,named,sizeof(named)-1);
            if(length>0) {
                named[length]=0;const char *leaf=strrchr(named,'/');
                if(leaf && !strcmp(leaf+1,"native-0")) {
                    char bytes[19];int fd=open(source,O_RDONLY|O_CLOEXEC);
                    require(fd>=0 && pread(fd,bytes,sizeof(bytes),0)==(ssize_t)sizeof(bytes) &&
                        !memcmp(bytes,"\177ELF/usr/bin/native",sizeof(bytes)),"independent-bind-copy-before-unpack");
                    unpack_required();memset(bytes,0,sizeof(bytes));
                    require(pread(fd,bytes,sizeof(bytes),0)==(ssize_t)sizeof(bytes) &&
                        !memcmp(bytes,"\177ELF/usr/bin/native",sizeof(bytes)) && close(fd)==0,
                        "independent-bind-copy-survives-original-host-unpack");
                }
            }
        }
    }
    char out[PATH_MAX];int result=mount(source,!strcmp(target,"/")?target:map(target,out),type,flags,data);
    if(!result && (flags&MS_BIND) && !strcmp(mode,"ambient-bind-undo-cleanup-cut") && !fault_hits) {
        char named[PATH_MAX],ambient[PATH_MAX];ssize_t length=readlink(source,named,sizeof(named)-1);
        snprintf(ambient,sizeof(ambient),"%s/host/usr/bin/ambient",base);
        if(length>0) {
            named[length]=0;
            if(!strcmp(named,ambient)) {
                struct stat before,after,mounted;char mounted_path[PATH_MAX];
                ssize_t mounted_length=readlink(target,mounted_path,sizeof(mounted_path)-1);
                require(mounted_length>0,"independent-mounted-ambient-target-path");mounted_path[mounted_length]=0;
                require(lstat(ambient,&before)==0 && stat(mounted_path,&mounted)==0 &&
                    before.st_dev==original_origins[2].st_dev && before.st_ino==original_origins[2].st_ino &&
                    mounted.st_dev==before.st_dev && mounted.st_ino==before.st_ino &&
                    (before.st_mode&0777)==0644,"real-ambient-bind-precedes-same-origin-trust-drift");
                require(chmod(ambient,0666)==0 && lstat(ambient,&after)==0 &&
                    after.st_dev==before.st_dev && after.st_ino==before.st_ino &&
                    (after.st_mode&0777)==0666,"late-ambient-trust-drift-preserves-original-inode");
                fault_hits++;
            }
        }
    }
    return result;
}
static int fixture_umount(const char *target,int flags) {
    if(!strcmp(mode,"publication-cleanup-cut") && fault_hits && !cleanup_hits++) {errno=EBUSY;return -1;}
    if(!strcmp(mode,"mac-cleanup-cut") && mac_calls && !cleanup_hits++) {errno=EBUSY;return -1;}
    if(!strcmp(mode,"ambient-bind-undo-cleanup-cut") && fault_hits && !cleanup_hits++) {errno=EBUSY;return -1;}
    if(!strcmp(mode,"staging-detach-cut") && !fault_hits++) {errno=EIO;return -1;}
    char out[PATH_MAX];return umount2(map(target,out),flags);
}
static int fixture_open_tree(int fd,const char *path,unsigned flags) {
    if(!strcmp(mode,"clone-cut") && !fault_hits++) {errno=EIO;return -1;}
    return open_tree(fd,path,flags);
}
static int fixture_move_mount(int from,const char *source,int to,const char *target,unsigned flags) {
    if(!strcmp(mode,"attachment-cut") && !fault_hits++) {errno=EIO;return -1;}
    return move_mount(from,source,to,target,flags);
}
static int fixture_mount_setattr(int fd,const char *path,unsigned flags,struct mount_attr *attr,size_t size) {
    if(!strcmp(mode,"readonly-cut") && !fault_hits++) {errno=EIO;return -1;}
    return mount_setattr(fd,path,flags,attr,size);
}
static int fixture_unshare(int flags) {
    int result=unshare(flags);
    if(!result && flags==CLONE_NEWNS) {
        /* Cloning a mount namespace changes its mount IDs. Observe the new
         * namespace's original target before production attaches anything. */
        char target[PATH_MAX];snprintf(target,sizeof(target),"%s/host/usr",base);struct stat info;
        require(lstat(target,&info)==0 && info.st_dev==original_target_info.st_dev &&
            info.st_ino==original_target_info.st_ino && info.st_mode==original_target_info.st_mode &&
            info.st_uid==original_target_info.st_uid && info.st_gid==original_target_info.st_gid,
            "independent-namespace-original-target-identity");
        require(statx(AT_FDCWD,target,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&original_target_mount)==0,
            "independent-namespace-original-target-mount");
    }
    return result;
}
static int fixture_fstat(int fd,struct stat *s) {
    int r=fstat(fd,s);
    /* The real /dev/null belongs to the outer root, outside this user map. */
    if(!r && S_ISCHR(s->st_mode) && s->st_rdev==makedev(1,3)) s->st_uid=0;
    return r;
}
static int fixture_execve(const char *path,char *const argv[],char *const env[]) {
    char error_path[PATH_MAX];snprintf(error_path,sizeof(error_path),"%s/helper-error",base);
    int diagnostic=open(error_path,O_WRONLY|O_CREAT|O_APPEND|O_CLOEXEC,0600);
    if(diagnostic>=0) {dup2(diagnostic,STDERR_FILENO);close(diagnostic);}
    int result=execve(path,argv,env);
    dprintf(STDERR_FILENO,"fixture-execve:%s\n",strerror(errno));return result;
}
static int fixture_account(const char *name,struct passwd *p,char *bytes,size_t size,struct passwd **out) {
    (void)bytes;(void)size;
    require(!strcmp(name,"oh-no-parent-control-kiosk"),"account-name");
    memset(p,0,sizeof(*p));p->pw_uid=p->pw_gid=4242;*out=p;return 0;
}
static int fixture_environment(pam_handle_t *p,const char *value) {
    (void)p; require(!strcmp(value,"SYSTEMD_UNIT_PATH=/usr/share/oh-no-parent-control/confinement/user-units:"),"manager-environment");
    require(ready_commits==1 && !mac_calls,"ready-before-environment-before-MAC");
    environment_calls++;
    if(!strcmp(mode,"concurrent-writers")) contend();
    if(!strncmp(mode,"premac-",7)) {
        const char *name=!strcmp(mode,"premac-lock-replaced")?"lock":"lease";
        char path[PATH_MAX],saved[PATH_MAX];snprintf(path,sizeof(path),"%s/%s",base,name);
        snprintf(saved,sizeof(saved),"%s/original-%s",base,name);
        require(rename(path,saved)==0,"premac-displace-owned-lock");
        int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
        require(fd>=0 && write(fd,"foreign-lock",12)==12 && close(fd)==0,"premac-foreign-lock");fault_hits++;
    }
    return !strcmp(mode,"environment-failure")?PAM_SESSION_ERR:PAM_SUCCESS;
}
static int fixture_user(pam_handle_t *p,const char **name,const char *prompt) {
    (void)p;(void)prompt;*name="oh-no-parent-control-kiosk";return PAM_SUCCESS;
}
static int fixture_item(const pam_handle_t *p,int item,const void **value) {
    (void)p;require(item==PAM_SERVICE,"PAM-service-item");*value="systemd-user";return PAM_SUCCESS;
}
static int profile(const char *name) {
    require(!strcmp(name,"onpc-kiosk-manager"),"final-profile");mac_calls++;
    require(ready_commits==1 && environment_calls==1,"ready-before-security-transition");
    require((int)descriptors()==final_fd_baseline,"all-setup-fds-closed-before-MAC");
    for(int fd=0;fd<4096;fd++) {
        struct stat info;int exists=fstat(fd,&info)==0;
        require(exists==(int)caller_fds[fd],"exact-setup-FD-set-before-MAC");
        if(exists) require(info.st_dev==caller_objects[fd].st_dev && info.st_ino==caller_objects[fd].st_ino &&
            info.st_mode==caller_objects[fd].st_mode,"borrowed-FD-identities-before-MAC");
    }
    if(!strcmp(mode,"mac-deadline")) {
        struct timespec end={.tv_sec=(time_t)(transaction_deadline/1000000),.tv_nsec=(long)(transaction_deadline%1000000)*1000+1000};
        if(end.tv_nsec>=1000000000) {end.tv_sec++;end.tv_nsec-=1000000000;}
        require(clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&end,NULL)==0,"original-deadline-expires-in-final-MAC");
    }
    if(!strcmp(mode,"mac-failure") || !strcmp(mode,"mac-cleanup-cut")) {
        fault_hits++;errno=EACCES;return -1;
    }return 0;
}
static int get_profile(char **label,char **enforce) {
    *label=strdup("onpc-kiosk-manager\0enforce");
    /* Both values share the allocation, as libapparmor documents. */
    *label=realloc(*label,32);strcpy(*label,!strcmp(mode,"mac-readback")?"wrong-profile":"onpc-kiosk-manager");strcpy(*label+19,"enforce");*enforce=*label+19;return 1;
}
static int selinux_enabled(void) {return !strcmp(mode,"selinux-disabled")?0:1;}
static int apparmor_fixture_backend(void) {return 0;}
static int selinux_enforcing(void) {return !strcmp(mode,"selinux-permissive")?0:1;}
static int selinux_setexec(const char *context) {
    if(strstr(mode,"selinux-gate")) {
        require(context && !strcmp(context,"system_u:system_r:onpc_kiosk_gate_t:s0") && selinux_order++==0,
            "SELinux-gate-pending-context");
        return !strcmp(mode,"selinux-gate-transition")?-1:0;
    }
    require(!context && selinux_order++==0,"SELinux-clear-pending-before-current");return 0;
}
static int selinux_getexec(char **context) {
    require(strstr(mode,"selinux-gate") && selinux_order++==1,"SELinux-gate-pending-readback");
    *context=strdup(!strcmp(mode,"selinux-gate-readback")?"system_u:system_r:wrong_t:s0":"system_u:system_r:onpc_kiosk_gate_t:s0");return 0;
}
static int selinux_setcurrent(const char *context) {
    require(!strcmp(context,"system_u:system_r:onpc_kiosk_manager_pam_t:s0") && selinux_order++==1,"SELinux-manager-PAM-domain");
    return !strcmp(mode,"selinux-transition")?-1:0;
}
static int selinux_getcurrent(char **context) {
    require(selinux_order++==2,"SELinux-independent-current-readback");
    *context=strdup(!strcmp(mode,"selinux-readback")?"system_u:system_r:wrong_t:s0":"system_u:system_r:onpc_kiosk_manager_pam_t:s0");return 0;
}
static void *fixture_dlopen(const char *path,int flags) {
    if(!strcmp(path,"libapparmor.so.1")) return (void *)1;
    if(!strncmp(mode,"selinux-",8) && !strcmp(path,"libselinux.so.1")) return (void *)2;
    if(!strcmp(path,"libselinux.so.1")) return (void *)3;
    return dlopen(path,flags);
}
static void *fixture_dlsym(void *handle,const char *symbol) {
    if(handle==(void *)1) {
        if(!strcmp(symbol,"aa_change_profile")) return (void *)profile;
        if(!strcmp(symbol,"aa_getcon")) return (void *)get_profile;
        return NULL;
    }
    if(handle==(void *)2) {
        if(!strcmp(mode,"selinux-symbol") && !strcmp(symbol,"getcon_raw")) return NULL;
        if(!strcmp(mode,"selinux-gate-symbol") && !strcmp(symbol,"getexeccon_raw")) return NULL;
        if(!strcmp(symbol,"is_selinux_enabled")) return (void *)selinux_enabled;
        if(!strcmp(symbol,"security_getenforce")) return (void *)selinux_enforcing;
        if(!strcmp(symbol,"setexeccon_raw")) return (void *)selinux_setexec;
        if(!strcmp(symbol,"getexeccon_raw")) return (void *)selinux_getexec;
        if(!strcmp(symbol,"setcon_raw")) return (void *)selinux_setcurrent;
        if(!strcmp(symbol,"getcon_raw")) return (void *)selinux_getcurrent;
        if(!strcmp(symbol,"freecon")) return (void *)free;
        return NULL;
    }
    if(handle==(void *)3) return !strcmp(symbol,"is_selinux_enabled")?(void *)apparmor_fixture_backend:NULL;
    return dlsym(handle,symbol);
}
static int fixture_dlclose(void *handle) {return handle==(void *)1 || handle==(void *)2 || handle==(void *)3?0:dlclose(handle);}
static int fixture_rename(int a,const char *from,int b,const char *to,unsigned flags) {
    if(!strcmp(from,"ready.pending")) {
        struct stat s;require(fstatat(a,"material.json",&s,AT_SYMLINK_NOFOLLOW)==0 &&
            fstatat(a,"view",&s,AT_SYMLINK_NOFOLLOW)==0 && fstatat(a,"pins",&s,AT_SYMLINK_NOFOLLOW)==0 &&
            fstatat(a,"runtime.json",&s,AT_SYMLINK_NOFOLLOW)==0,"ready-after-complete-records");
        if(!strcmp(mode,"publication-cut") || !strcmp(mode,"publication-cleanup-cut")) {
            fault_hits++;errno=EIO;return -1;
        }
        if(!strcmp(mode,"post-attach-required-drift")) {
            char source[PATH_MAX],bytes[32]={0};snprintf(source,sizeof(source),"%s/host/usr/bin/native",base);
            int selected=open(source,O_RDONLY|O_CLOEXEC);
            require(selected>=0 && read(selected,bytes,sizeof(bytes))==19 && !memcmp(bytes,"\177ELF/usr/bin/native",19),"private-copy-before-host-drift");close(selected);
            unpack_required();
            selected=open(source,O_RDONLY|O_CLOEXEC);memset(bytes,0,sizeof(bytes));
            require(selected>=0 && read(selected,bytes,sizeof(bytes))==19 && !memcmp(bytes,"\177ELF/usr/bin/native",19),"private-copy-survives-original-host-drift");close(selected);
        }
        int r=renameat2(a,from,b,to,flags);if(!r)ready_commits++;
        if(!r) writer_barrier("final");
        if(!r && (!strcmp(mode,"ready-lock-replaced") || !strcmp(mode,"ready-lease-replaced"))) {
            const char *name=!strcmp(mode,"ready-lock-replaced")?"lock":"lease";
            char path[PATH_MAX],saved[PATH_MAX];snprintf(path,sizeof(path),"%s/%s",base,name);
            snprintf(saved,sizeof(saved),"%s/original-%s",base,name);
            require(rename(path,saved)==0,"ready-displace-owned-lock");
            int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
            require(fd>=0 && write(fd,"foreign-lock",12)==12 && close(fd)==0,"ready-foreign-lock");fault_hits++;
        }
        if(!r && (!strcmp(mode,"ready-material-replaced") || !strcmp(mode,"ready-view-replaced") ||
            !strcmp(mode,"ready-pins-replaced"))) {
            const char *name=!strcmp(mode,"ready-material-replaced")?"material.json":
                !strcmp(mode,"ready-view-replaced")?"view":"pins";
            struct stat original,foreign;require(fstatat(a,name,&original,AT_SYMLINK_NOFOLLOW)==0,
                "independent-original-publication-identity");
            int owner=open(base,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
            require(owner>=0 && renameat(a,name,owner,"displaced-record")==0,"displace-owned-completed-record-outside-publication");
            int input=openat(owner,"displaced-record",O_RDONLY|O_CLOEXEC);
            int output=openat(a,name,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);char bytes[4096];ssize_t n;
            require(input>=0 && output>=0,"foreign-completed-record-open");
            while((n=read(input,bytes,sizeof(bytes)))>0) require(write(output,bytes,(size_t)n)==n,"foreign-identical-record-bytes");
            require(n==0 && fstat(output,&foreign)==0 && foreign.st_ino!=original.st_ino &&
                close(input)==0 && close(output)==0 && close(owner)==0,"independent-foreign-record-identity");
            char witness[PATH_MAX];snprintf(witness,sizeof(witness),"%s/record-identities",base);
            FILE *record=fopen(witness,"w");require(record && fprintf(record,"%s %llu %llu %llu %llu\n",name,
                (unsigned long long)original.st_dev,(unsigned long long)original.st_ino,
                (unsigned long long)foreign.st_dev,(unsigned long long)foreign.st_ino)>0 && fclose(record)==0,
                "record-publication-identities");fault_hits++;
        }
        if(!r && !strcmp(mode,"ready-account-drift")) {
            char path[PATH_MAX];snprintf(path,sizeof(path),"%s/host/var/lib/oh-no-parent-control/package-created-kiosk-uid",base);
            int fd=open(path,O_WRONLY|O_CLOEXEC);require(fd>=0 && pwrite(fd,"4243",4,0)==4 && close(fd)==0,
                "post-ready-independent-original-account-drift");fault_hits++;
        }
        return r;
    }
    if(strlen(to)==64 && !strcmp(mode,"generation-rename-cut")) {fault_hits++;errno=EIO;return -1;}
    return renameat2(a,from,b,to,flags);
}
static int fixture_fsync(int fd) {
    char proc[64],name[PATH_MAX];snprintf(proc,sizeof(proc),"/proc/self/fd/%d",fd);
    ssize_t n=readlink(proc,name,sizeof(name)-1);
    if(n>0) {
        name[n]=0;const char *leaf=strrchr(name,'/');leaf=leaf?leaf+1:name;
        const char *record=!strcmp(mode,"material-fsync-cut")?"material.json":
            !strcmp(mode,"view-fsync-cut")?"view":!strcmp(mode,"pins-fsync-cut")?"pins":
            !strcmp(mode,"pending-fsync-cut")?"ready.pending":NULL;
        if(!fault_hits && ((record && !strcmp(leaf,record)) ||
            (!strcmp(mode,"ready-durability-cut") && ready_commits && strlen(leaf)==64) ||
            (!strcmp(mode,"generation-durability-cut") && !strcmp(leaf,"runtime")))) {
            /* The runtime directory is fsynced only after its atomic rename;
             * each one-shot fault allows explicit recovery to prove cleanup. */
            fault_hits++;errno=EIO;return -1;
        }
    }return fsync(fd);
}
static ssize_t fixture_write(int fd,const void *data,size_t size) {
    if(!strcmp(mode,"publication-partial")) {
        char proc[64],name[PATH_MAX];snprintf(proc,sizeof(proc),"/proc/self/fd/%d",fd);
        ssize_t n=readlink(proc,name,sizeof(name)-1);if(n>0) {
            name[n]=0;size_t length=(size_t)n;
            if(length>5 && !strcmp(name+length-5,"/view")) {
                if(partial_write++) {errno=EIO;return -1;}
                return write(fd,data,size>1?size/2:size);
            }
        }
    }return write(fd,data,size);
}
#define KIOSK_ACCOUNT_NAME "oh-no-parent-control-kiosk"
#define KIOSK_CONFINEMENT_PREPARE @HELPER@
#define KIOSK_FRESH_CAPGET fixture_capget
#define KIOSK_FRESH_CAPSET fixture_capset
#define KIOSK_FRESH_AMBIENT_CLEAR fixture_ambient_clear
#define open fixture_open
#define lstat fixture_lstat
#define mkdir fixture_mkdir
#define statx(...) fixture_statx(__VA_ARGS__)
#define mount fixture_mount
#define umount2 fixture_umount
#define unshare fixture_unshare
#define fstat fixture_fstat
#define execve fixture_execve
#define getpwnam_r fixture_account
#define pam_putenv fixture_environment
#define pam_get_user fixture_user
#define pam_get_item fixture_item
#define dlopen fixture_dlopen
#define dlsym fixture_dlsym
#define dlclose fixture_dlclose
#define renameat2 fixture_rename
#define write fixture_write
#define fsync fixture_fsync
#define open_tree fixture_open_tree
#define move_mount fixture_move_mount
#define mount_setattr fixture_mount_setattr
#define recvmsg fixture_recvmsg
#define pam_syslog fixture_syslog
#include "kiosk_confinement.h"
#undef pam_syslog
#include "kiosk_fresh_startup.h"
#undef open
#undef lstat
#undef mkdir
#undef statx
#undef mount
#undef umount2
#undef unshare
#undef fstat
#undef execve
#undef getpwnam_r
#undef pam_putenv
#undef pam_get_user
#undef pam_get_item
#undef dlopen
#undef dlsym
#undef dlclose
#undef renameat2
#undef write
#undef fsync
#undef open_tree
#undef move_mount
#undef mount_setattr
#undef recvmsg
static void contend(void) {
    char path[PATH_MAX];snprintf(path,sizeof(path),"%s/lock",base);
    int lock=open(path,O_RDWR|O_CLOEXEC);snprintf(path,sizeof(path),"%s/lease",base);
    int lease=open(path,O_RDWR|O_CLOEXEC);
    require(lock>=0 && lease>=0,"independent-competing-lock-open");
    unsigned before=descriptors();int all=!strcmp(mode,"concurrent-writers");
    if(all || strstr(mode,"-admission")) {
        struct kiosk_fresh_startup other;kiosk_fresh_startup_init(&other);
        require(kiosk_fresh_startup_until(&other,NULL,lock,lease,transaction_deadline)!=0 &&
            other.deadline==transaction_deadline && other.stage && !strcmp(other.stage,"identity") &&
            !other.child.started && !other.ready && !other.armed &&
            kiosk_fresh_close(&other)==0 && descriptors()==before,
            "competing-full-admission-refuses-before-helper-or-publication");contention_checks++;
    }
    /* These are real independent open-description lock probes at the writer
     * barriers, not execution of public configuration or removal workflows. */
    if(all || strstr(mode,"-configuration")) {
        require(flock(lock,LOCK_EX|LOCK_NB)!=0 && (errno==EAGAIN || errno==EWOULDBLOCK),
            "configuration-writer-refused-by-original-preparation-lock");contention_checks++;
    }
    if(all || strstr(mode,"-loader")) {
        require(flock(lease,LOCK_EX|LOCK_NB)!=0 && (errno==EAGAIN || errno==EWOULDBLOCK),
            "loader-removal-writer-refused-by-original-admission-lease");contention_checks++;
    }
    require(descriptors()==before,"competing-writer-preserves-descriptors");
    require(close(lock)==0 && close(lease)==0,"competing-descriptors-close");
}
static void mapfile(const char *path,const char *text) {
    int fd=open(path,O_WRONLY|O_CLOEXEC);require(fd>=0 && write(fd,text,strlen(text))==(ssize_t)strlen(text) && close(fd)==0,"user-map");
}
static void namespaces(void) {
    char text[128];uid_t uid=getuid();gid_t gid=getgid();require(unshare(CLONE_NEWUSER)==0,"private-user-namespace");
    mapfile("/proc/self/setgroups","deny");snprintf(text,sizeof(text),"0 %lu 1\n",(unsigned long)uid);mapfile("/proc/self/uid_map",text);
    snprintf(text,sizeof(text),"0 %lu 1\n",(unsigned long)gid);mapfile("/proc/self/gid_map",text);
    require(unshare(CLONE_NEWNS)==0 && mount(NULL,"/",NULL,MS_REC|MS_PRIVATE,NULL)==0,"private-mount-namespace");
}
static void actual_bytes(const char *name,const char *expected) {
    char path[PATH_MAX],bytes[256]={0};snprintf(path,sizeof(path),"%s/host/usr/%s",base,name);
    int fd=open(path,O_RDONLY|O_CLOEXEC);require(fd>=0 && read(fd,bytes,sizeof(bytes)-1)==(ssize_t)strlen(expected) &&
        !strcmp(bytes,expected),"independent-actual-source-bytes");close(fd);
    fd=open(path,O_WRONLY|O_CLOEXEC);require(fd<0 && errno==EROFS,"independent-actual-readonly");
}
static unsigned actual_walk(const char *logical) {
    const char *allowed[]={"/usr","/usr/bin","/usr/bin/ambient","/usr/bin/ambient-tree",
        "/usr/bin/ambient-tree/nested","/usr/bin/ambient-tree/nested/leaf",
        "/usr/bin/native","/usr/bin/script","/usr/share","/usr/share/oh-no-parent-control",
        "/usr/share/oh-no-parent-control/confinement",
        "/usr/share/oh-no-parent-control/confinement/config.json",
        "/usr/share/oh-no-parent-control/confinement/onpc-kiosk.apparmor",
        "/usr/share/oh-no-parent-control/confinement/retained-view"};
    unsigned i;for(i=0;i<sizeof(allowed)/sizeof(*allowed);i++) if(!strcmp(logical,allowed[i])) break;
    require(i<sizeof(allowed)/sizeof(*allowed),"independent-no-extra-mounted-source");
    char physical[PATH_MAX];snprintf(physical,sizeof(physical),"%s/host%s",base,logical);
    struct stat info;require(lstat(physical,&info)==0 && (S_ISDIR(info.st_mode) || S_ISREG(info.st_mode)),"independent-actual-entry-kind");
    if(!S_ISDIR(info.st_mode)) return 1;
    DIR *d=opendir(physical);require(d!=NULL,"independent-tree-enumeration");unsigned count=1;struct dirent *e;
    while((e=readdir(d))) {
        if(!strcmp(e->d_name,".") || !strcmp(e->d_name,"..")) continue;
        char child[PATH_MAX];require(snprintf(child,sizeof(child),"%s/%s",logical,e->d_name)<PATH_MAX,"independent-tree-bound");
        count+=actual_walk(child);
    }
    require(closedir(d)==0,"independent-tree-close");return count;
}
static void independent_coverage(const struct kiosk_fresh_startup *s) {
    const char *expected[]={"/usr","/usr/bin","/usr/bin/ambient","/usr/bin/ambient-tree",
        "/usr/bin/native","/usr/bin/script","/usr/share","/usr/share/oh-no-parent-control",
        "/usr/share/oh-no-parent-control/confinement",
        "/usr/share/oh-no-parent-control/confinement/config.json",
        "/usr/share/oh-no-parent-control/confinement/onpc-kiosk.apparmor"};
    require(s->realized.receipt.nn==sizeof(expected)/sizeof(*expected),"exact-actual-node-domain");
    require(actual_walk("/usr")==(!strcmp(mode,"ambient-narrow")?13U:14U),"independent-complete-actual-tree-coverage");
    for(unsigned i=0;i<s->realized.receipt.nn;i++) {
        const struct kiosk_receipt_row *n=s->realized.receipt.nodes+i;unsigned j;
        for(j=0;j<sizeof(expected)/sizeof(*expected);j++) if(!strcmp(expected[j],n->v[KR_PATH])) break;
        require(j<sizeof(expected)/sizeof(*expected),"no-unexpected-actual-source");
        for(unsigned origin=0;origin<sizeof(origin_paths)/sizeof(*origin_paths);origin++)
            if(!strcmp(n->v[KR_PATH],origin_paths[origin]))
                require(n->number[KR_ORIGIN_DEV]==(uint64_t)original_origins[origin].st_dev &&
                    n->number[KR_ORIGIN_INO]==(uint64_t)original_origins[origin].st_ino,
                    "independent-original-host-source-provenance");
        char path[PATH_MAX];snprintf(path,sizeof(path),"%s/host%s",base,n->v[KR_PATH]);struct stat info;
        if(!strcmp(n->v[KR_KIND],"absent")) {require(lstat(path,&info)!=0 && errno==ENOENT,"actual-source-absent");continue;}
        require(lstat(path,&info)==0 && (uint64_t)info.st_dev==n->number[KR_DEV] &&
            (uint64_t)info.st_ino==n->number[KR_INO] && (uint64_t)info.st_mode==n->number[KR_MODE],"independent-every-mounted-inode");
        if(!strcmp(n->v[KR_CLASS],"native") || !strcmp(n->v[KR_CLASS],"runtime") || !strcmp(n->v[KR_CLASS],"payload"))
            require(n->number[KR_INO]!=n->number[KR_ORIGIN_INO] || n->number[KR_DEV]!=n->number[KR_ORIGIN_DEV],"independent-copy-inode-separation");
    }
    require(s->realized.receipt.nc==1,"exact-real-recursive-mount-domain");
    const struct kiosk_receipt_row *c=s->realized.receipt.coverage;
    require(!strcmp(c->v[KC_PATH],"/usr/bin/ambient-tree/nested") &&
        c->number[KC_ORIGIN_DEV]==(uint64_t)original_nested.st_dev &&
        c->number[KC_ORIGIN_INO]==(uint64_t)original_nested.st_ino,"independent-nested-source-provenance");
    char path[PATH_MAX],parent[PATH_MAX];snprintf(path,sizeof(path),"%s/host/usr/bin/ambient-tree/nested",base);
    snprintf(parent,sizeof(parent),"%s/host/usr/bin/ambient-tree",base);struct stat info;struct statx child_mount,parent_mount;
    require(lstat(path,&info)==0 && (uint64_t)info.st_dev==c->number[KC_DEV] && (uint64_t)info.st_ino==c->number[KC_INO] &&
        statx(AT_FDCWD,path,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&child_mount)==0 &&
        statx(AT_FDCWD,parent,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&parent_mount)==0 &&
        child_mount.stx_mnt_id!=parent_mount.stx_mnt_id,"independent-real-nested-mount");
}
static void completion_boundary(const struct kiosk_fresh_startup *s) {
    /* Assert the actual transaction stop, independently of the injected API's
     * return. In particular, a committed ready rename survives later refusal. */
    const char *publication[]={"publication-cut","publication-cleanup-cut","publication-partial",
        "material-fsync-cut","view-fsync-cut","pins-fsync-cut","pending-fsync-cut",
        "generation-rename-cut","generation-durability-cut","ready-durability-cut","generation-four"};
    const char *expected=NULL;
    for(unsigned i=0;i<sizeof(publication)/sizeof(*publication);i++)
        if(!strcmp(mode,publication[i])) expected="publication";
    if(!strcmp(mode,"bind-cut") || !strcmp(mode,"ambient-bind-undo-cleanup-cut")) expected="realization";
    if(!strcmp(mode,"clone-cut") || !strcmp(mode,"attachment-cut") || !strcmp(mode,"readonly-cut")) expected="attachment";
    if(!strcmp(mode,"staging-detach-cut")) expected="staging";
    if(!strcmp(mode,"environment-failure")) expected="environment";
    if(!strcmp(mode,"mac-failure") || !strcmp(mode,"mac-cleanup-cut") || !strcmp(mode,"mac-readback") || !strcmp(mode,"mac-deadline")) expected="mac";
    if(expected) require(s->stage && !strcmp(s->stage,expected),"exact-completion-refusal-stage");
    if(expected && strcmp(expected,"mac") && strcmp(expected,"environment"))
        require(!environment_calls && !mac_calls,"publication-or-mount-refusal-prevents-environment-and-MAC");
    if(expected && !strcmp(expected,"publication"))
        require(s->ready==!strcmp(mode,"ready-durability-cut"),"atomic-ready-commit-is-completion-boundary");
}
int main(int argc,char **argv) {
    require(argc==3,"arguments");mode=argv[1];base=argv[2];
    if(capability_model()) {
        capability_begin();uint64_t now;require(kiosk_pin_now(&now)==0,"capability-clock");
        uint64_t bounding=actual_bounding_set();unsigned before=descriptors();
        int result=kiosk_fresh_capabilities_until(!strcmp(mode,"capabilities-expired")?now-1:now+1000000);
        capability_expect(result);
        require(actual_bounding_set()==bounding && descriptors()==before,"unchanged-bounding-set-and-descriptors");
        puts("capabilities verified");return 0;
    }
    if(!strncmp(mode,"selinux-",8)) {
        unsigned before=descriptors();struct kiosk_fresh_mac mac;
        int gate=strstr(mode,"selinux-gate")!=NULL;
        int result=gate?kiosk_gate_mac_preload(&mac,"selinux"):kiosk_fresh_mac_preload(&mac,"selinux");
        if(!result) result=kiosk_fresh_mac_apply(&mac);
        require((result==0)==(!strcmp(mode,"selinux-healthy") || !strcmp(mode,"selinux-gate-healthy")),"SELinux-final-transition-result");
        if(!strcmp(mode,"selinux-healthy")) require(selinux_order==3,"SELinux-all-security-observations");
        if(!strcmp(mode,"selinux-gate-healthy")) require(selinux_order==2,"SELinux-gate-only-pending-context");
        if(mac.library) fixture_dlclose(mac.library);
        require(descriptors()==before,"SELinux-preload-descriptor-balance");puts("mac verified");return 0;
    }
    namespaces();
    char path[PATH_MAX];snprintf(path,sizeof(path),"%s/host/usr/bin/ambient-tree/nested",base);
    require(mount("tmpfs",path,"tmpfs",0,"size=1m,mode=0755")==0,"private-nested-source");
    char leaf[PATH_MAX];snprintf(leaf,sizeof(leaf),"%s/leaf",path);
    int fd=open(leaf,O_WRONLY|O_CREAT|O_CLOEXEC,0644);require(fd>=0 && write(fd,"nested-source",13)==13 && fchmod(fd,0644)==0 && close(fd)==0,"nested-bytes");
    require(lstat(path,&original_nested)==0,"independent-original-nested-source");
    char lockpath[PATH_MAX],leasepath[PATH_MAX];snprintf(lockpath,sizeof(lockpath),"%s/lock",base);snprintf(leasepath,sizeof(leasepath),"%s/lease",base);
    int lock=open(lockpath,O_RDWR|O_CLOEXEC),lease=open(leasepath,O_RDWR|O_CLOEXEC);
    require(lock>=0 && lease>=0 && flock(lock,LOCK_EX|LOCK_NB)==0 && flock(lease,LOCK_SH|LOCK_NB)==0,"private-locks");
    snprintf(path,sizeof(path),"%s/host/usr/bin/native",base);original_source=open(path,O_RDWR|O_CLOEXEC);
    require(original_source>=0,"independent-original-host-descriptor");
    char original_usr[PATH_MAX];snprintf(original_usr,sizeof(original_usr),"%s/host/usr",base);
    require(lstat(original_usr,&original_target_info)==0 &&
        statx(AT_FDCWD,original_usr,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&original_target_mount)==0,"independent-original-target-mount");
    for(unsigned origin=0;origin<sizeof(origin_paths)/sizeof(*origin_paths);origin++) {
        snprintf(path,sizeof(path),"%s/host%s",base,origin_paths[origin]);
        require(lstat(path,&original_origins[origin])==0,"capture-original-host-source-before-attachment");
    }
    final_fd_baseline=(int)descriptors();
    for(int caller=0;caller<4096;caller++) caller_fds[caller]=fstat(caller,&caller_objects[caller])==0;
    struct kiosk_fresh_startup startup;kiosk_fresh_startup_init(&startup);
    uint64_t now;require(kiosk_pin_now(&now)==0,"clock");
    uint64_t deadline=!strcmp(mode,"expired")?now-1:now+(!strcmp(mode,"helper-timeout")?250000:!strcmp(mode,"mac-deadline")?2000000:10000000);
    transaction_deadline=deadline;
    int result=kiosk_fresh_startup_until(&startup,NULL,lock,lease,deadline);
    require(startup.deadline==deadline &&
        kiosk_fresh_startup_until(&startup,NULL,lock,lease,deadline+1000000)!=0 && startup.deadline==deadline,
        "original-deadline-and-single-attempt");
    int positive=!strcmp(mode,"healthy") || !strcmp(mode,"measurement-production-healthy") || !strcmp(mode,"ambient-narrow") ||
        !strcmp(mode,"concurrent-writers") || !strncmp(mode,"writer-",7) || !strcmp(mode,"generation-three");
    if((result==0)!=positive) fprintf(stderr,"fresh-result mode=%s result=%d stage=%s child-started=%d reaped=%d phase=%u pidfd=%d channel=%d\n",mode,result,startup.stage?startup.stage:"-",
        startup.child.started,startup.child.reaped,startup.child.phase,startup.child.pidfd,startup.child.channel);
    require((result==0)==positive,"complete-transaction-result");
    completion_boundary(&startup);
    struct kiosk_failure primary=startup.failure, cleanup=startup.cleanup_failure;
    if(!strcmp(mode,"measurement-config-refusal") || !strcmp(mode,"measurement-policy-refusal") ||
        !strcmp(mode,"measurement-helper-refusal") || !strcmp(mode,"measurement-attestation-refusal")) {
        const char *cause=!strcmp(mode,"measurement-helper-refusal")?"unexpected-preserved-executable":
            !strcmp(mode,"measurement-attestation-refusal")?"policy-snapshot-not-attested":"attestation-command-failed";
        require(startup.stage && !strcmp(startup.stage,"measurement") && primary.stage &&
            !strcmp(primary.stage,"measurement") && !strcmp(primary.reason,cause) && primary.error==-1 &&
            !startup.measurement.count && !startup.ticket_adopted && !startup.ready && !ready_commits && !mac_calls,
            "checked-measurement-refusal-before-native-authority-or-material-selection");
        struct kiosk_view diagnostic={0};diagnostic.failure=primary;
        kiosk_native_diagnostic(NULL,&diagnostic,"manager");
    }
    if(!strcmp(mode,"publication-cleanup-cut")) {
        require(fault_hits==1 && cleanup_hits==1 && !startup.recovered && startup.pin.attached &&
            startup.pin.parent>=0 && kiosk_fresh_close(&startup)!=0,
            "failed-detach-retains-exact-attachment-owner");
        require(primary.stage && !strcmp(primary.stage,"publication") && !strcmp(primary.reason,"refused") &&
            cleanup.stage && !strcmp(cleanup.stage,"pin") && !strcmp(cleanup.reason,"detach") && cleanup.error==EBUSY,
            "independent-primary-publication-and-cleanup-detach-failures");
    }
    if(!strcmp(mode,"mac-cleanup-cut")) {
        struct statx attached;
        require(fault_hits==1 && cleanup_hits==1 && mac_calls==1 && startup.ready && ready_commits==1 &&
            !startup.recovered && !startup.armed && startup.view.cloned && !startup.pin.attached &&
            statx(AT_FDCWD,original_usr,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&attached)==0 &&
            attached.stx_mnt_id==startup.view.clone_id && kiosk_fresh_close(&startup)!=0,
            "post-closure-failed-detach-retains-exact-view-owner");
        fprintf(stderr,"mac-cleanup primary=%s/%s/%d common=%s/%s/%d view=%s/%s/%d\n",
            primary.stage?primary.stage:"-",primary.reason?primary.reason:"-",primary.error,
            cleanup.stage?cleanup.stage:"-",cleanup.reason?cleanup.reason:"-",cleanup.error,
            startup.view.cleanup_failure.stage?startup.view.cleanup_failure.stage:"-",
            startup.view.cleanup_failure.reason?startup.view.cleanup_failure.reason:"-",startup.view.cleanup_failure.error);
        require(primary.stage && !strcmp(primary.stage,"mac") && !strcmp(primary.reason,"refused") &&
            cleanup.stage && !strcmp(cleanup.stage,"detach") && !strcmp(cleanup.reason,"detach") && cleanup.error==EBUSY &&
            startup.view.cleanup_failure.stage && !strcmp(startup.view.cleanup_failure.stage,"detach") &&
            !strcmp(startup.view.cleanup_failure.reason,"detach") && startup.view.cleanup_failure.error==EBUSY,
            "independent-primary-MAC-and-post-closure-cleanup-detach-failures");
    }
    if(!strcmp(mode,"ambient-bind-undo-cleanup-cut")) {
        require(fault_hits==1 && cleanup_hits>=2 && startup.recovered && !startup.ready &&
            !ready_commits && !environment_calls && !mac_calls,
            "late-ambient-bind-undo-failure-recovered-without-admission");
        fprintf(stderr,"ambient-undo primary=%s/%s/%d common=%s/%s/%d realization=%s/%s/%d\n",
            primary.stage?primary.stage:"-",primary.reason?primary.reason:"-",primary.error,
            cleanup.stage?cleanup.stage:"-",cleanup.reason?cleanup.reason:"-",cleanup.error,
            startup.realized.cleanup_failure.stage?startup.realized.cleanup_failure.stage:"-",
            startup.realized.cleanup_failure.reason?startup.realized.cleanup_failure.reason:"-",
            startup.realized.cleanup_failure.error);
        require(primary.stage && !strcmp(primary.stage,"realization") && !strcmp(primary.reason,"identity") &&
            cleanup.stage && !strcmp(cleanup.stage,"detach") && !strcmp(cleanup.reason,"detach") && cleanup.error==EBUSY &&
            startup.realized.cleanup_failure.stage && !strcmp(startup.realized.cleanup_failure.stage,"detach") &&
            !strcmp(startup.realized.cleanup_failure.reason,"detach") && startup.realized.cleanup_failure.error==EBUSY,
            "successful-recovery-preserves-primary-and-native-bind-undo-cleanup-failures");
    }
    if(!strcmp(mode,"concurrent-writers")) require(contention_checks==3,"all-competing-production-writers-observed");
    if(!strncmp(mode,"writer-",7)) require(writer_barriers==1 && contention_checks==1,
        "exact-independent-writer-at-requested-composition-barrier");
    if(!strcmp(mode,"measurement-required-drift")) require(fault_hits==1 && startup.stage &&
        !strcmp(startup.stage,"authority") && !startup.ticket_adopted && !startup.ready,
        "measurement-unpack-refuses-at-independent-host-authority");
    if(!strcmp(mode,"bind-required-drift")) require(fault_hits==1 && startup.stage &&
        !strcmp(startup.stage,"publication") && startup.realized.bound && !startup.ready && !ready_commits,
        "bind-unpack-refuses-at-original-host-prepublication-proof");
    if(!strcmp(mode,"post-attach-required-drift")) require(fault_hits==1 && startup.stage &&
        !strcmp(startup.stage,"final-proof") && startup.ready && ready_commits==1,
        "final-unpack-refuses-after-preserving-completed-publication");
    if(!strcmp(mode,"selection-lock-replaced") || !strcmp(mode,"selection-lease-replaced"))
        require(startup.stage && !strcmp(startup.stage,"copy-ticket") && !startup.ready && !ready_commits,
            "selection-replaced-lock-refuses-before-scratch-adoption-or-publication");
    if(!strcmp(mode,"ready-lock-replaced") || !strcmp(mode,"ready-lease-replaced"))
        require(startup.stage && !strcmp(startup.stage,"final-proof") && startup.ready && ready_commits==1,
            "ready-replaced-lock-refuses-before-environment-or-MAC");
    if(!strcmp(mode,"premac-lock-replaced") || !strcmp(mode,"premac-lease-replaced"))
        require(startup.stage && !strcmp(startup.stage,"lock") && startup.ready && ready_commits==1,
            "premac-replaced-lock-refuses-after-setup-closure-before-MAC");
    if(strstr(mode,"-cut") && strcmp(mode,"publication-cut")) require(fault_hits>0,"requested-failure-boundary-observed");
    if(!positive) require(!startup.armed && startup.failure.stage && (mac_calls==0)==
        (strcmp(mode,"mac-failure") && strcmp(mode,"mac-cleanup-cut") && strcmp(mode,"mac-readback") && strcmp(mode,"mac-deadline")),
        "primary-refusal-keeps-MAC-boundary-closed");
    if(!strcmp(mode,"ticket-parent") || !strcmp(mode,"ticket-malformed")) {
        require(startup.transferred_scratch && !startup.ticket_adopted && startup.child.reaped &&
            startup.child.pidfd<0 && startup.child.channel<0 && startup.response.count==2 &&
            descriptors()>(unsigned)final_fd_baseline,
            "ambiguous-ticket-retains-exact-owner");
        require(kiosk_pin_now(&now)==0 && kiosk_fresh_recover_until(&startup,now+5000000)!=0 &&
            kiosk_fresh_close(&startup)!=0 && !ready_commits && !mac_calls,"ambiguous-ticket-no-sweep-or-admission");
        siginfo_t remaining={0};errno=0;
        require(waitid(P_ALL,0,&remaining,WEXITED|WNOHANG|__WALL)<0 && errno==ECHILD,
            "ambiguous-ticket-child-independently-reaped");
        require(startup.deadline==deadline && startup.failure.stage==primary.stage &&
            startup.failure.reason==primary.reason && startup.failure.error==primary.error &&
            startup.cleanup_failure.stage==cleanup.stage && startup.cleanup_failure.reason==cleanup.reason &&
            startup.cleanup_failure.error==cleanup.error,"ambiguous-ticket-preserves-separate-first-failures");
        /* The enclosing fixture owns this entire private process namespace;
         * process exit releases its unresolved test FDs, never a host object. */
        puts("retained");return 0;
    }
    if(positive) {
        require(capability_get_calls==2 && capability_set_calls==1 && capability_ambient_calls==1,
            "production-fresh-cut-uses-shared-capability-clear");
        independent_coverage(&startup);
        struct statx actual_mount;require(statx(AT_FDCWD,original_usr,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&actual_mount)==0 &&
            actual_mount.stx_mnt_id!=original_target_mount.stx_mnt_id,"independent-actual-root-attachment");
        snprintf(path,sizeof(path),"%s/host/usr/forbidden-write",base);
        require(mkdir(path,0755)!=0 && errno==EROFS,"independent-actual-root-readonly");
        actual_bytes("bin/native","\177ELF/usr/bin/native");
        actual_bytes("bin/script","#!/usr/bin/python3\n");
        actual_bytes("bin/ambient-tree/nested/leaf","nested-source");
        snprintf(path,sizeof(path),"%s/host/usr/bin/ambient",base);
        if(!strcmp(mode,"ambient-narrow")) require(access(path,F_OK)!=0,"safe-ambient-omission");
        else actual_bytes("bin/ambient","ambient-original");
        require(mac_calls==1 && startup.armed,"security-transition-complete");
    }
    if(!strcmp(mode,"copy-replacement")) {
        /* Restore only this fixture's recorded original inode, before asking
         * the production recovery owner to retry its exact ticket proof. */
        snprintf(path,sizeof(path),"%s/fault-copy",base);char relative[128]={0};unsigned long long foreign_dev,foreign_ino,owned_dev,owned_ino;
        FILE *record=fopen(path,"r");require(record && fscanf(record,"%127s %llu %llu %llu %llu",relative,&foreign_dev,&foreign_ino,&owned_dev,&owned_ino)==5 && fclose(record)==0,"recorded-copy-restoration");
        require(!strncmp(relative,".runtime-",9) && strstr(relative,"/native-")!=NULL,"recorded-copy-name");
        snprintf(path,sizeof(path),"%s/runtime/%s",base,relative);
        char displaced[PATH_MAX];strcpy(displaced,path);strcpy(strrchr(displaced,'/')+1,"displaced-copy");
        struct stat foreign,owned;require(lstat(path,&foreign)==0 && lstat(displaced,&owned)==0 &&
            (uint64_t)foreign.st_dev==foreign_dev && (uint64_t)foreign.st_ino==foreign_ino && foreign.st_nlink==1 &&
            (uint64_t)owned.st_dev==owned_dev && (uint64_t)owned.st_ino==owned_ino && owned.st_nlink==1,"exact-owned-copy-restoration-identities");
        require(unlink(path)==0 && rename(displaced,path)==0,"restore-owned-copy-inode");
    }
    if(!positive) require(kiosk_pin_now(&now)==0 && kiosk_fresh_recover_until(&startup,now+5000000)==0,"owned-failed-attempt-recovery");
    require(startup.deadline==deadline && startup.failure.stage==primary.stage &&
        startup.failure.reason==primary.reason && startup.failure.error==primary.error &&
        startup.cleanup_failure.stage==cleanup.stage && startup.cleanup_failure.reason==cleanup.reason &&
        startup.cleanup_failure.error==cleanup.error,"recovery-preserves-deadline-and-separate-first-failures");
    require(!startup.child.started || (startup.child.reaped && startup.child.pidfd<0 && startup.child.channel<0),
        "bounded-preparation-child-reaped-and-channel-closed");
    siginfo_t remaining={0};errno=0;
    require(waitid(P_ALL,0,&remaining,WEXITED|WNOHANG|__WALL)<0 && errno==ECHILD,
        "independent-no-unreaped-owned-child");
    require(!startup.pin.attached && startup.pin.worker<0 && !startup.view.mounted,
        "no-owned-worker-or-writable-staging-alias-survives");
    for(unsigned i=0;i<startup.realized.stage_count;i++)
        require(!startup.realized.stages[i].live,"every-owned-staging-mount-detached");
    if(!positive) {
        struct statx restored;struct stat info;require(statx(AT_FDCWD,original_usr,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&restored)==0 &&
            restored.stx_mnt_id==original_target_mount.stx_mnt_id && lstat(original_usr,&info)==0 &&
            info.st_dev==original_target_info.st_dev && info.st_ino==original_target_info.st_ino &&
            info.st_mode==original_target_info.st_mode && info.st_uid==original_target_info.st_uid &&
            info.st_gid==original_target_info.st_gid,"independent-refusal-detaches-only-invocation");
    }
    require(kiosk_fresh_close(&startup)==0,"setup-close");
    require((int)descriptors()==final_fd_baseline,"exact-descriptor-balance");
    for(int caller=0;caller<4096;caller++) {
        struct stat info;int exists=fstat(caller,&info)==0;
        require(exists==(int)caller_fds[caller],"exact-caller-FD-set-after-close");
        if(exists) require(info.st_dev==caller_objects[caller].st_dev && info.st_ino==caller_objects[caller].st_ino &&
            info.st_mode==caller_objects[caller].st_mode,"borrowed-FD-identities-after-close");
    }
    require(ready_commits==(unsigned)ready_expected(),"publication-boundary");
    close(original_source);close(lock);close(lease);puts("verified");return 0;
}
'''


def _put(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


@pytest.fixture
def fresh_scene(tmp_path):
    host = tmp_path / 'host'
    config = dict(backend='apparmor', domains=['manager'], apparmor_profiles=['onpc-kiosk-manager'],
                  executables=[dict(role='service', paths=['/usr/bin/native'])],
                  preserved_executables=[], reserved_directories=[],
                  runtime_inputs={'/usr/bin/script': dict(kind='file', role='script')})
    config_bytes = json.dumps(config, sort_keys=True).encode()
    policy = b'private-attested-policy\n'
    files = {'usr/bin/native': (b'\x7fELF/usr/bin/native', 0o755),
             'usr/bin/script': (b'#!/usr/bin/python3\n', 0o755),
             'usr/bin/ambient': (b'ambient-original', 0o644),
             PAYLOAD.lstrip('/') + '/config.json': (config_bytes, 0o644),
             PAYLOAD.lstrip('/') + '/onpc-kiosk.apparmor': (policy, 0o644),
             'var/lib/oh-no-parent-control/package-created-kiosk-uid': (b'4242\n', 0o600),
             'sys/kernel/security/apparmor/profiles': (b'onpc-kiosk-manager (enforce)\n', 0o644)}
    state = dict(schema=1, backend='apparmor', pam={'gdm-password': {}, 'systemd-user': {}},
                 loaded_config_sha256=hashlib.sha256(config_bytes).hexdigest(),
                 loaded_policy_sha256=hashlib.sha256(policy).hexdigest())
    files['var/lib/oh-no-parent-control/kiosk-confinement.json'] = (json.dumps(state).encode(), 0o600)
    for name, (data, mode) in files.items():
        _put(host / name, data, mode)
    (host / 'usr/bin/ambient-tree/nested').mkdir(parents=True)
    for path in [host, *host.rglob('*')]:
        if path.is_dir():
            path.chmod(0o755)
    (tmp_path / 'runtime').mkdir(mode=0o700)
    for name in ('lock', 'lease'):
        _put(tmp_path / name, b'owned-lock', 0o600)
    helper = tmp_path / 'helper'
    helper_text = '#!' + sys.executable + '\n' + HELPER
    for key, value in {'@TOOLS@': str(ROOT / 'tools'), '@BASE@': str(tmp_path),
                       '@CONFIG@': PAYLOAD.lstrip('/') + '/config.json',
                       '@POLICY@': PAYLOAD.lstrip('/') + '/onpc-kiosk.apparmor'}.items():
        helper_text = helper_text.replace(key, repr(value))
    helper.write_text(helper_text)
    helper.chmod(0o755)
    source = tmp_path / 'fresh.c'
    source.write_text(NATIVE.replace('@HELPER@', json.dumps(str(helper))))
    binary = tmp_path / 'fresh'
    compiled = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-function',
                               '-Wno-format-truncation', '-I', str(ROOT / 'tools'),
                               str(source), '-ldl', '-lpam', '-o', str(binary)],
                              capture_output=True, text=True, timeout=30,
                              pass_fds=test_storage.scratch_descriptors())
    assert compiled.returncode == 0, compiled.stderr
    binary.chmod(0o755)
    return tmp_path, binary


@pytest.mark.parametrize('mode', [
    'healthy', 'ambient-narrow', 'helper-exit', 'helper-result-exit', 'helper-timeout', 'helper-order',
    'measurement-config-refusal', 'measurement-policy-refusal', 'measurement-helper-refusal',
    'measurement-attestation-refusal', 'measurement-production-healthy',
    'helper-identity', 'result-malformed', 'ticket-parent', 'ticket-malformed', 'copy-replacement', 'source-replacement',
    'required-drift', 'measurement-required-drift', 'bind-required-drift', 'post-attach-required-drift', 'publication-cut',
    'publication-cleanup-cut',
    'publication-partial', 'expired', 'environment-failure', 'mac-failure', 'mac-cleanup-cut', 'mac-readback', 'mac-deadline',
    'concurrent-writers', 'selection-lock-replaced', 'selection-lease-replaced',
    'writer-measurement-admission', 'writer-measurement-configuration', 'writer-measurement-loader',
    'writer-bind-admission', 'writer-bind-configuration', 'writer-bind-loader',
    'writer-final-admission', 'writer-final-configuration', 'writer-final-loader',
    'ready-lock-replaced', 'ready-lease-replaced', 'premac-lock-replaced', 'premac-lease-replaced',
    'material-fsync-cut', 'view-fsync-cut', 'pins-fsync-cut', 'pending-fsync-cut',
    'generation-rename-cut', 'generation-durability-cut', 'ready-durability-cut',
    'bind-cut', 'ambient-bind-undo-cleanup-cut', 'clone-cut', 'readonly-cut', 'attachment-cut', 'staging-detach-cut',
    'generation-three', 'generation-four',
    'ready-material-replaced', 'ready-view-replaced', 'ready-pins-replaced', 'ready-account-drift',
])
def test_complete_native_fresh_manager_transaction(fresh_scene, mode):
    directory, binary = fresh_scene
    (directory / 'mode').write_text(mode)
    borrowed = {name: (directory / name).stat() for name in ('lock', 'lease')}
    retained_generations = {}
    prior_count = 3 if mode == 'generation-three' else 4 if mode == 'generation-four' else 0
    if (mode.startswith('writer-') or mode == 'concurrent-writers' or
            mode in ('measurement-required-drift', 'bind-required-drift', 'post-attach-required-drift') or
            mode.endswith(('-lock-replaced', '-lease-replaced'))):
        prior_count = 1
    if prior_count:
        for index in range(prior_count):
            generation = directory / 'runtime' / f'{index:064x}'
            generation.mkdir(mode=0o700)
            _put(generation / 'foreign-record', b'previous-generation', 0o600)
            retained_generations[generation.name] = (generation.stat(), (generation / 'foreign-record').stat())
    completed = subprocess.run([str(binary), mode, str(directory)],
                               capture_output=True, text=True, timeout=20,
                               pass_fds=test_storage.scratch_descriptors())
    helper_error = directory / 'helper-error'
    helper_started = directory / 'helper-started'
    helper_result = directory / 'helper-result.json'
    result_summary = 'not-produced'
    if helper_result.exists():
        record = json.loads(helper_result.read_text())
        plan = record.get('plan', {})
        result_summary = json.dumps(dict(ticket=record.get('ticket'), native=plan.get('native'),
            sources={path: {key: value for key, value in source.items()
                            if key in ('kind', 'path', 'name', 'source_class', 'required', 'assertion', 'copy_identity')}
                     for path, source in plan.get('sources', {}).items()}), sort_keys=True)[:6000]
    assert completed.returncode == 0, (
        f'returncode={completed.returncode}\nstdout:{completed.stdout}\nstderr:{completed.stderr}\n'
        'helper-error:' + (helper_error.read_text() if helper_error.exists() else '') + '\n'
        'helper-started:' + (helper_started.read_text() if helper_started.exists() else 'helper-not-entered') + '\n'
        'helper-result:' + result_summary)
    assert completed.stdout == ('retained\n' if mode in ('ticket-parent', 'ticket-malformed') else 'verified\n')
    for name, original in borrowed.items():
        displaced = directory / ('original-' + name)
        selected = displaced if displaced.exists() else directory / name
        assert selected.read_bytes() == b'owned-lock'
        assert (selected.stat().st_dev, selected.stat().st_ino) == (original.st_dev, original.st_ino)
        if displaced.exists():
            # Replacement names are foreign to the production cleanup owner.
            assert (directory / name).read_bytes() == b'foreign-lock'
            assert (directory / name).stat().st_ino != original.st_ino
    if mode != 'expired':
        started = json.loads(helper_started.read_text())
        assert started['pid'] > 0
        assert started['lock'] == borrowed['lock'].st_ino
        assert started['lease'] == borrowed['lease'].st_ino
        assert started['deadline'] > 0
    else:
        assert not helper_started.exists()
    for name, (root_identity, member_identity) in retained_generations.items():
        generation = directory / 'runtime' / name
        assert {p.name for p in generation.iterdir()} == {'foreign-record'}
        assert (generation / 'foreign-record').read_bytes() == b'previous-generation'
        assert (generation.stat().st_dev, generation.stat().st_ino) == (root_identity.st_dev, root_identity.st_ino)
        actual = (generation / 'foreign-record').stat()
        assert (actual.st_dev, actual.st_ino) == (member_identity.st_dev, member_identity.st_ino)
    generations = [path for path in (directory / 'runtime').iterdir()
                   if len(path.name) == 64 and path.name not in retained_generations]
    if mode in ('measurement-config-refusal', 'measurement-policy-refusal', 'measurement-helper-refusal',
                'measurement-attestation-refusal', 'measurement-production-healthy'):
        assert (directory / 'measurement-command').read_text() == mode
        if mode.endswith('-refusal'):
            reason = ('unexpected-preserved-executable' if mode == 'measurement-helper-refusal' else
                      'policy-snapshot-not-attested' if mode == 'measurement-attestation-refusal' else 'attestation-command-failed')
            assert completed.stderr.splitlines() == [
                f'onpc.pam kiosk native-view outcome=denied role=manager stage=measurement reason={reason} errno=-1']
            assert not helper_result.exists()
        if mode == 'measurement-helper-refusal':
            assert (directory / 'measurement-inventory').read_text() == 'real-preserved-inventory'
        if mode in ('measurement-config-refusal', 'measurement-policy-refusal'):
            assert (directory / 'measurement-attestation').read_text() == 'actual-policy-digest-refusal'
    if mode.startswith('writer-') or mode in ('healthy', 'measurement-production-healthy', 'ambient-narrow', 'environment-failure', 'mac-failure', 'mac-cleanup-cut', 'mac-readback', 'mac-deadline',
                'post-attach-required-drift', 'concurrent-writers', 'ready-lock-replaced', 'ready-lease-replaced',
                'premac-lock-replaced', 'premac-lease-replaced', 'ready-durability-cut', 'generation-three',
                'ready-material-replaced', 'ready-view-replaced', 'ready-pins-replaced', 'ready-account-drift'):
        assert len(generations) == 1
        names = {path.name for path in generations[0].iterdir()}
        expected_names = {'material.json', 'view', 'pins', 'runtime.json', 'ready', 'native-0', '0', '1', '2'}
        if mode in ('ready-material-replaced', 'ready-view-replaced', 'ready-pins-replaced'):
            name, original_dev, original_ino, foreign_dev, foreign_ino = (directory / 'record-identities').read_text().split()
            owned, foreign = directory / 'displaced-record', generations[0] / name
            assert owned.read_bytes() == foreign.read_bytes()
            assert (owned.stat().st_dev, owned.stat().st_ino) == (int(original_dev), int(original_ino))
            assert (foreign.stat().st_dev, foreign.stat().st_ino) == (int(foreign_dev), int(foreign_ino))
        assert names == expected_names
        assert (generations[0] / 'native-0').read_bytes() == b'\x7fELF/usr/bin/native'
        assert { (generations[0] / str(index)).read_bytes() for index in range(3)} == {
            (directory / 'host/usr/bin/script').read_bytes(),
            (directory / ('host' + PAYLOAD) / 'config.json').read_bytes(),
            (directory / ('host' + PAYLOAD) / 'onpc-kiosk.apparmor').read_bytes()}
        ready = (generations[0] / 'ready').read_bytes().split(b'\t')
        assert ready[:2] == [b'ONPC-KIOSK-READY', b'2']
        assert ready[3].decode() == generations[0].name
        assert ready[4].decode() == hashlib.sha256((generations[0] / 'pins').read_bytes()).hexdigest()
        assert list(map(int, ready[6:8])) == [generations[0].stat().st_dev, generations[0].stat().st_ino]
        assert b'ONPC-KIOSK-RECEIPT\t2\tV\t' in (generations[0] / 'view').read_bytes()
    elif mode in ('ticket-parent', 'ticket-malformed'):
        assert not generations
        scratch = [path for path in (directory / 'runtime').iterdir() if path.name.startswith('.runtime-')]
        assert len(scratch) == 1
        assert (scratch[0] / 'runtime.json').is_file()
        assert (scratch[0] / 'native-0').read_bytes() == b'\x7fELF/usr/bin/native'
        assert not (scratch[0] / 'ready').exists()
    else:
        assert not generations
        assert not any(path.name.startswith('.runtime-')
                       for path in (directory / 'runtime').iterdir())


@pytest.mark.parametrize('mode', ['selinux-healthy', 'selinux-disabled', 'selinux-permissive',
                                'selinux-symbol', 'selinux-transition', 'selinux-readback',
                                'selinux-gate-healthy', 'selinux-gate-symbol',
                                'selinux-gate-transition', 'selinux-gate-readback'])
def test_native_fresh_selinux_security_transition(fresh_scene, mode):
    directory, binary = fresh_scene
    completed = subprocess.run([str(binary), mode, str(directory)],
                               capture_output=True, text=True, timeout=5,
                               pass_fds=test_storage.scratch_descriptors())
    assert completed.returncode == 0, (completed.returncode, completed.stdout, completed.stderr)
    assert completed.stdout == 'mac verified\n'


@pytest.mark.parametrize('mode', ['inherited', 'zero', 'get-before', 'set', 'ambient', 'get-after',
                                 'inheritable-drift', 'effective-drift', 'permitted-drift', 'expired'])
def test_native_admission_clears_only_inheritable_and_ambient_capabilities(fresh_scene, mode):
    directory, binary = fresh_scene
    completed = subprocess.run([str(binary), 'capabilities-' + mode, str(directory)],
                               capture_output=True, text=True, timeout=5,
                               pass_fds=test_storage.scratch_descriptors())
    assert completed.returncode == 0, (completed.returncode, completed.stdout, completed.stderr)
    assert completed.stdout == 'capabilities verified\n'
