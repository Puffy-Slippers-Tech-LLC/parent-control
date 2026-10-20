"""Native completion records with real private inodes and no-replace witnesses.

Each bounded probe enters only its own user namespace to observe real root
ownership, creates no mounts, and changes no shared service. Mount completion
is a checked-input fixture here; native-pin tests own actual mount witnesses.
Compiler/probe children are synchronously reaped; launcher owns disk scratch.
"""
from pathlib import Path
import stat
import subprocess

import pytest

from tools import test_storage

ROOT = Path(__file__).resolve().parents[2]
DIGEST = 'a' * 64


@pytest.fixture(scope='module')
def private_initializer_probe(tmp_path_factory):
    """Bounded credential doubles, separate from real single-GID namespaces.

    These model nonzero filesystem groups and SGID inheritance; they do not
    claim actual GDM credential or installed-policy qualification.
    """
    directory = tmp_path_factory.mktemp('private-initializer')
    source, binary = directory / 'probe.c', directory / 'probe'
    source.write_text(r'''
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/fsuid.h>
#include <sys/stat.h>
#include <unistd.h>
static struct stat object;
static uid_t effective_uid, filesystem_uid;
static gid_t effective_gid, filesystem_gid;
static unsigned changes, chowns, chmods, queries;
static const char *fault;
static uid_t uid(void) {return effective_uid;}
static int fsuid(uid_t value) {
    if(value!=(uid_t)-1)exit(3);queries++;return (int)filesystem_uid;
}
static int metadata(int fd,struct stat *out) {
    if(fd!=123)exit(3);
    if(!strcmp(fault,"stat")){errno=EIO;return -1;}
    *out=object;return 0;
}
static int owner(int fd,uid_t uid,gid_t gid) {
    if(fd!=123||uid||gid||chmods)exit(3);
    chowns++;
    if(!strcmp(fault,"chown")){errno=EPERM;return -1;}
    object.st_uid=uid;object.st_gid=gid;object.st_mode&=~06000;
    changes++;return 0;
}
static int permissions(int fd,mode_t mode) {
    if(fd!=123)exit(3);chmods++;
    if(!strcmp(fault,"chmod")){errno=EPERM;return -1;}
    object.st_mode=(object.st_mode&S_IFMT)|mode;changes++;
    if(!strcmp(fault,"replacement"))object.st_ino++;
    if(!strcmp(fault,"group-drift"))object.st_gid=77;
    return 0;
}
#define geteuid uid
#define setfsuid fsuid
#define fstat metadata
#define fchown owner
#define fchmod permissions
#include "kiosk_private_creation.h"
static void require(int value) {if(!value)exit(2);}
int main(int argc,char **argv) {
    require(argc==6);fault=argv[1];
    mode_t mask=(mode_t)strtoul(argv[2],NULL,8), mode=(mode_t)strtoul(argv[3],NULL,8);
    int directory=atoi(argv[4]),root_group=atoi(argv[5]);
    effective_uid=filesystem_uid=0;effective_gid=0;filesystem_gid=42;
    if(!strcmp(fault,"effective-only")){effective_gid=42;filesystem_gid=0;}
    if(!strcmp(fault,"fsuid"))filesystem_uid=42;
    if(!strcmp(fault,"euid"))effective_uid=42;
    object=(struct stat){.st_dev=1,.st_ino=2,.st_uid=0,
        .st_gid=!strcmp(fault,"sgid")?77:filesystem_gid,
        .st_mode=(directory?S_IFDIR:S_IFREG)|(mode&~mask),.st_nlink=directory?2:1};
    if(directory&&!strcmp(fault,"sgid"))object.st_mode|=S_ISGID;
    if(!strcmp(fault,"foreign-uid"))object.st_uid=88;
    if(!strcmp(fault,"hardlink"))object.st_nlink=3;
    if(!strcmp(fault,"symlink"))object.st_mode=S_IFLNK|0777;
    struct stat before=object;uid_t e=effective_uid,f=filesystem_uid;
    gid_t g=effective_gid,h=filesystem_gid;
    int result=kiosk_private_initialize(123,mode,root_group);
    require(effective_uid==e&&filesystem_uid==f&&effective_gid==g&&filesystem_gid==h&&queries<=1);
    int refuse=!strcmp(fault,"fsuid")||!strcmp(fault,"euid")||!strcmp(fault,"foreign-uid")||
        !strcmp(fault,"symlink")||(!directory&&!strcmp(fault,"hardlink"))||!strcmp(fault,"stat");
    if(refuse)require(result&&changes==0&&chowns==0&&chmods==0);
    else if(!strcmp(fault,"chown"))require(result&&chowns==1&&chmods==0&&changes==0);
    else if(!strcmp(fault,"chmod"))require(result&&chowns==(unsigned)root_group&&chmods==1);
    else if(!strcmp(fault,"replacement")||!strcmp(fault,"group-drift"))require(result);
    else require(!result&&object.st_uid==0&&object.st_gid==(root_group?0:before.st_gid)&&
        (object.st_mode&07777)==mode&&chowns==(unsigned)root_group&&chmods==1);
    return 0;
}
''')
    result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                             '-Wno-unused-function', '-Wno-misleading-indentation',
                             '-I', str(ROOT / 'tools'), str(source), '-o', str(binary)],
                            capture_output=True, text=True, timeout=30,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    return binary


@pytest.mark.parametrize('group', ['filesystem-only', 'effective-only', 'sgid'])
@pytest.mark.parametrize('mask', ['0000', '0022', '0077', '0777'])
@pytest.mark.parametrize('mode,directory', [('0600', '0'), ('0444', '0'), ('0700', '1')])
def test_private_initializer_ignores_group_inheritance_and_mask(
        private_initializer_probe, group, mask, mode, directory):
    result = subprocess.run([str(private_initializer_probe), group, mask, mode, directory, '1'],
                            capture_output=True, text=True, timeout=5,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('fault', ['fsuid', 'euid', 'foreign-uid', 'hardlink', 'symlink',
                                  'stat', 'chown', 'chmod', 'replacement', 'group-drift'])
def test_private_initializer_refuses_unsupported_or_failed_initialization(private_initializer_probe, fault):
    result = subprocess.run([str(private_initializer_probe), fault, '0777', '0600', '0', '1'],
                            capture_output=True, text=True, timeout=5,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr


def test_private_initializer_can_preserve_existing_per_object_group_policy(private_initializer_probe):
    result = subprocess.run([str(private_initializer_probe), 'filesystem-only', '0777', '0600', '0', '0'],
                            capture_output=True, text=True, timeout=5,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope='module')
def publication_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-publication')
    source, binary = directory / 'probe.c', directory / 'probe'
    header = (ROOT / 'tools/kiosk_confinement.h').read_text()
    paths = header[header.index('static int\nkiosk_trusted_stat('):header.index('static int\nkiosk_below(')]
    labels = header[header.index('static int\nkiosk_label('):header.index('/* Open parents separately.')]
    types = header[header.index('struct kiosk_pin_entry {'):header.index('static int\nkiosk_pin_reap_worker_until(')]
    mount_id = header[header.index('static int\nkiosk_pin_fd_mount('):header.index('static int\nkiosk_pin_attached_topology_until(')]
    same = header[header.index('static int\nkiosk_pin_same_stat('):header.index('static int\nkiosk_pin_open(')]
    source.write_text(r'''
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <limits.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/xattr.h>
#include <dirent.h>
#include "kiosk_private_creation.h"
#include "kiosk_view_receipt.h"
#define KIOSK_VIEW_ROWS 32768U
#define KIOSK_VIEW_BYTES (64U * 1024U * 1024U)
static const char *mode;static int elapsed,armed,unlinks;
static void require(int ok) {if(!ok){perror("publication-fixture");exit(2);}}
static int test_clock(clockid_t clock,struct timespec *value) {
    int result=clock_gettime(clock,value);if(!result&&elapsed)value->tv_sec+=120;return result;
}
#define KIOSK_PIN_CLOCK_GETTIME test_clock
static void put(const char *path,const char *bytes) {
    int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0600);require(fd>=0);
    require(write(fd,bytes,strlen(bytes))==(ssize_t)strlen(bytes)&&close(fd)==0);
}
static void own_namespace(void) {
    uid_t uid=getuid();gid_t gid=getgid();char mapping[128];
    require(unshare(CLONE_NEWUSER)==0);
    put("/proc/self/setgroups","deny");
    snprintf(mapping,sizeof(mapping),"0 %lu 1\n",(unsigned long)uid);put("/proc/self/uid_map",mapping);
    snprintf(mapping,sizeof(mapping),"0 %lu 1\n",(unsigned long)gid);put("/proc/self/gid_map",mapping);
}
static int test_rename(int from,const char *a,int to,const char *b,unsigned flags) {
    if(armed&&!strcmp(b,"ready")&&!strcmp(mode,"ready-before")){errno=EIO;return -1;}
    int result=renameat2(from,a,to,b,flags);
    if(!result&&armed&&!strcmp(b,"ready")&&!strcmp(mode,"ready-after"))elapsed=1;
    return result;
}
static int test_unlink(int root,const char *name,int flags) {
    if(armed&&!strcmp(mode,"cleanup-cut")&&++unlinks==2){errno=EIO;return -1;}
    return unlinkat(root,name,flags);
}
''' + paths + labels + types + mount_id + same + r'''
#define renameat2 test_rename
#define unlinkat test_unlink
#include "kiosk_view_publication.h"
#undef renameat2
#undef unlinkat
static const char digest[]="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
static int exists(int root,const char *name) {struct stat info;return fstatat(root,name,&info,AT_SYMLINK_NOFOLLOW)==0;}
static void replace(int root,const char *name) {
    require(renameat(root,name,root,"old-member")==0);
    int fd=openat(root,name,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);require(fd>=0);
    require(write(fd,"foreign-token",13)==13&&close(fd)==0);
}
int main(int argc,char **argv) {
    require(argc==3);mode=argv[2];require(chdir(argv[1])==0);own_namespace();
    uint64_t now;require(kiosk_pin_now(&now)==0);uint64_t deadline=now+5000000ULL;
    if(!strncmp(mode,"ready-parse",11)) {
        int fd=open("input",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);require(fd>=0);
        char *bytes;size_t size;require(kiosk_publication_read(fd,&bytes,&size,deadline)==0&&close(fd)==0);
        struct kiosk_publication_ready_record ready;
        int result=kiosk_publication_ready_parse(&ready,bytes,size,!strcmp(mode,"ready-parse-expired")?1:deadline);
        if(!result)printf("parsed %s %llu %llu %llu %llu\n",ready.boot,
             (unsigned long long)ready.root_inode,(unsigned long long)ready.source_inode,
             (unsigned long long)ready.marker_inode,(unsigned long long)ready.publisher);
        free(bytes);return result?1:0;
    }
    if(!strncmp(mode,"parse",5)) {
        int fd=open("input",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);require(fd>=0);
        char *bytes;size_t size;require(kiosk_publication_read(fd,&bytes,&size,deadline)==0&&close(fd)==0);
        struct kiosk_publication_inventory inventory;
        int result=kiosk_publication_inventory_parse(&inventory,bytes,size,!strcmp(mode,"parse-expired")?1:deadline);
        if(!result) {
            printf("entries %u\n",inventory.count);char *encoded;size_t count;
            require(kiosk_publication_inventory_encode(inventory.entries,inventory.count,&encoded,&count,deadline)==0);
            require(count==size&&!memcmp(encoded,bytes,size));free(encoded);
        }
        kiosk_publication_inventory_close(&inventory);free(bytes);return result?1:0;
    }
    require(mkdir("store",0700)==0&&mkdir("store/scratch",0700)==0);
    int parent=open("store",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    int root=open("store/scratch",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);require(parent>=0&&root>=0);
    struct kiosk_publication publication;
    require(kiosk_publication_open_until(&publication,parent,root,"scratch",NULL,0,deadline)==0);
    mode_t caller_mask=umask(!strcmp(mode,"private-0777")?0777:0022);
    require(kiosk_publication_write(&publication,"material","material-token",14,0)==0);
    require(kiosk_publication_write(&publication,"copies","copy-token",10,0)==0);
    if(!strcmp(mode,"private-0777")) {
        struct stat info;
        require(fstatat(root,"material",&info,AT_SYMLINK_NOFOLLOW)==0&&
            info.st_uid==0&&info.st_gid==0&&(info.st_mode&07777)==0600);
        require(fstatat(root,"copies",&info,AT_SYMLINK_NOFOLLOW)==0&&
            info.st_uid==0&&info.st_gid==0&&(info.st_mode&07777)==0600);
        require(umask(0777)==0777);umask(caller_mask);
        require(kiosk_publication_abort_until(&publication,deadline)==0);
        kiosk_publication_close(&publication);require(close(root)==0&&close(parent)==0);return 0;
    }
    umask(caller_mask);
    int result=0;
    if(!strcmp(mode,"foreign-member")) {
        int fd=openat(root,"foreign",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);require(fd>=0&&close(fd)==0);
        result=kiosk_publication_abort_until(&publication,deadline);
        require(exists(root,"material")&&exists(root,"copies")&&exists(root,"foreign"));
    } else if(!strcmp(mode,"replace-member")) {
        replace(root,"material");result=kiosk_publication_abort_until(&publication,deadline);
        require(exists(root,"material")&&exists(root,"copies")&&exists(root,"old-member"));
    } else if(!strcmp(mode,"hardlink-member")) {
        require(linkat(root,"material",parent,"external",0)==0);
        result=kiosk_publication_abort_until(&publication,deadline);
        require(exists(root,"material")&&exists(root,"copies")&&exists(parent,"external"));
    } else if(!strcmp(mode,"replace-root")) {
        require(renameat(parent,"scratch",parent,"original")==0&&mkdirat(parent,"scratch",0700)==0);
        result=kiosk_publication_abort_until(&publication,deadline);
        require(exists(root,"material")&&exists(root,"copies")&&exists(parent,"scratch"));
    } else if(!strcmp(mode,"no-replace")) {
        require(mkdirat(parent,digest,0700)==0);result=kiosk_publication_rename_until(&publication,digest);
        struct stat checked;require(fstatat(parent,digest,&checked,AT_SYMLINK_NOFOLLOW)==0&&exists(parent,"scratch"));
    } else if(!strcmp(mode,"generation-limit")) {
        char name[65];memset(name,'b',64);name[64]=0;
        for(unsigned i=0;i<4;i++){name[0]=(char)('0'+i);require(mkdirat(parent,name,0700)==0);}
        result=kiosk_publication_rename_until(&publication,digest);require(exists(parent,"scratch"));
    } else if(!strcmp(mode,"duplicate-write")) {
        struct stat before,after;require(fstatat(root,"material",&before,AT_SYMLINK_NOFOLLOW)==0);
        result=kiosk_publication_write(&publication,"material","replacement",11,0);
        require(fstatat(root,"material",&after,AT_SYMLINK_NOFOLLOW)==0&&before.st_ino==after.st_ino);
    } else if(!strcmp(mode,"cleanup-cut")) {
        armed=1;require(kiosk_publication_abort_until(&publication,deadline)!=0);armed=0;
        result=kiosk_publication_abort_until(&publication,deadline);
        require(!result&&!exists(parent,"scratch"));
    } else if(!strcmp(mode,"abort")) {
        result=kiosk_publication_abort_until(&publication,deadline);require(!result&&!exists(parent,"scratch"));
    } else {
        require(kiosk_publication_rename_until(&publication,digest)==0);
        require(mkdir("view",0755)==0);int view=open("view",O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);require(view>=0);
        put("marker","marker-token");struct stat marker;require(stat("marker",&marker)==0);
        struct kiosk_source_pin pin={.fd=view,.parent=-1,.worker=-1,.attached=1,.verified=1,.complete=1,.attached_id=987};
        if(!strcmp(mode,"incomplete"))pin.complete=0;
        if(!strcmp(mode,"unverified"))pin.verified=0;
        if(!strcmp(mode,"unattached"))pin.attached=0;
        if(!strcmp(mode,"worker"))pin.worker=42;
        armed=1;result=kiosk_publication_ready_until(&publication,&pin,digest,digest,digest,
             "01234567-89ab-cdef-0123-456789abcdef",&marker,0);armed=0;elapsed=0;
        printf("ready %d pending %d complete %d\n",exists(root,"ready"),exists(root,"ready.pending"),publication.ready);
        if(!strcmp(mode,"ready-before")) {
            require(result&&exists(root,"ready.pending")&&!exists(root,"ready"));
            require(kiosk_publication_abort_until(&publication,deadline)==0&&!exists(parent,digest));
        } else if(!strcmp(mode,"ready-after")) {
            require(result&&exists(root,"ready")&&publication.ready);
            require(kiosk_publication_abort_until(&publication,deadline)!=0&&exists(parent,digest));
        } else if(!strcmp(mode,"complete")) {
            require(!result&&exists(root,"ready")&&publication.ready);
            int ready_fd=openat(root,"ready",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);require(ready_fd>=0);
            char *bytes;size_t size;require(kiosk_publication_read(ready_fd,&bytes,&size,deadline)==0&&close(ready_fd)==0);
            struct kiosk_publication_ready_record ready;struct stat actual_view;
            require(kiosk_publication_ready_parse(&ready,bytes,size,deadline)==0&&fstat(view,&actual_view)==0);
            require(ready.root_device==(uint64_t)publication.root_info.st_dev&&ready.root_inode==(uint64_t)publication.root_info.st_ino&&
                    ready.source_device==(uint64_t)actual_view.st_dev&&ready.source_inode==(uint64_t)actual_view.st_ino&&
                    ready.marker_device==(uint64_t)marker.st_dev&&ready.marker_inode==(uint64_t)marker.st_ino&&
                    ready.attachment==pin.attached_id&&ready.publisher==(uint64_t)getpid());free(bytes);
            require(kiosk_publication_abort_until(&publication,deadline)!=0);
            require(kiosk_publication_write(&publication,"late","late",4,0)!=0);
        }
        require(close(view)==0);
    }
    kiosk_publication_close(&publication);kiosk_publication_close(&publication);
    require(close(root)==0&&close(parent)==0);return result?1:0;
}
''')
    result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                             '-Wno-unused-function', '-O2', '-I', str(ROOT / 'tools'),
                             str(source), '-ldl', '-o', str(binary)],
                            capture_output=True, text=True, timeout=30,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    return binary


def _run(probe, tmp_path, mode):
    return subprocess.run([str(probe), str(tmp_path), mode], capture_output=True,
                          text=True, timeout=10,
                          pass_fds=test_storage.scratch_descriptors())


@pytest.mark.parametrize('mode', ['abort', 'complete', 'cleanup-cut', 'private-0777'])
def test_publication_complete_or_owned_cleanup(publication_probe, tmp_path, mode):
    result = _run(publication_probe, tmp_path, mode)
    assert result.returncode == 0, result.stderr
    if mode == 'complete':
        root = tmp_path / 'store' / DIGEST
        assert {item.name for item in root.iterdir()} == {'material', 'copies', 'ready'}
        fields = (root / 'ready').read_text().rstrip('\n').split('\t')
        assert fields[:6] == ['ONPC-KIOSK-READY', '2', DIGEST, DIGEST, DIGEST,
                              '01234567-89ab-cdef-0123-456789abcdef']
        assert int(fields[7]) == root.stat().st_ino
        assert int(fields[9]) == (tmp_path / 'view').stat().st_ino
        assert int(fields[11]) == (tmp_path / 'marker').stat().st_ino


@pytest.mark.parametrize('mode', ['foreign-member', 'replace-member', 'hardlink-member',
    'replace-root', 'no-replace', 'generation-limit', 'duplicate-write', 'incomplete',
    'unverified', 'unattached', 'worker', 'ready-before', 'ready-after'])
def test_publication_refuses_without_adopting_or_deleting_foreign_objects(publication_probe, tmp_path, mode):
    result = _run(publication_probe, tmp_path, mode)
    assert result.returncode == 1, result.stderr
    if mode == 'replace-member':
        assert (tmp_path / 'store/scratch/material').read_bytes() == b'foreign-token'


def _inventory():
    return ('ONPC-KIOSK-PINS\t1\n'
            f'P\t-\t1\t10\t{stat.S_IFDIR | 0o755}\t0\t0\t0\t1\n'
            f'P\tbin\t1\t11\t{stat.S_IFDIR | 0o755}\t0\t0\t0\t0\n'
            f'P\tbin/tool\t1\t12\t{stat.S_IFREG | 0o755}\t0\t0\t1\t1\n').encode()


def test_inventory_roundtrip_has_closed_realization_rows(publication_probe, tmp_path):
    (tmp_path / 'input').write_bytes(_inventory())
    result = _run(publication_probe, tmp_path, 'parse')
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'entries 3\n'


@pytest.mark.parametrize('mutation', ['header', 'newline', 'nul', 'parent', 'order',
                                     'duplicate', 'unsafe', 'root', 'extra', 'expired'])
def test_inventory_rejects_malformed_or_expired_records(publication_probe, tmp_path, mutation):
    data = _inventory()
    if mutation == 'header':
        data = data.replace(b'PINS\t1', b'PINS\t9')
    elif mutation == 'newline':
        data = data[:-1]
    elif mutation == 'nul':
        data += b'\0\n'
    elif mutation == 'parent':
        data = data.replace(b'\t0\t0\t1\t1\n', b'\t0\t0\t0\t1\n')
    elif mutation == 'order':
        rows = data.splitlines(keepends=True)
        data = b''.join([rows[0], rows[1], rows[3], rows[2]])
    elif mutation == 'duplicate':
        data += data.splitlines(keepends=True)[-1]
    elif mutation == 'unsafe':
        data = data.replace(str(stat.S_IFREG | 0o755).encode(), str(stat.S_IFREG | 0o775).encode())
    elif mutation == 'root':
        data = data.replace(b'P\t-\t', b'P\troot\t', 1)
    elif mutation == 'extra':
        data = data.replace(b'P\tbin\t', b'P\tbin\textra\t')
    (tmp_path / 'input').write_bytes(data)
    result = _run(publication_probe, tmp_path, 'parse-expired' if mutation == 'expired' else 'parse')
    assert result.returncode == 1, result.stderr


def _ready_fields():
    return ['ONPC-KIOSK-READY', '2', DIGEST, 'b' * 64, 'c' * 64,
            '01234567-89ab-cdef-0123-456789abcdef', '0', '10', '1', '20', '2', '30', '40', '50']


def test_ready_parser_accepts_exact_canonical_record(publication_probe, tmp_path):
    (tmp_path / 'input').write_bytes(('\t'.join(_ready_fields()) + '\n').encode())
    result = _run(publication_probe, tmp_path, 'ready-parse')
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'parsed 01234567-89ab-cdef-0123-456789abcdef 10 20 30 50\n'


@pytest.mark.parametrize('mutation', ['header', 'version', 'extra-field', 'truncated',
    'newline', 'nul', 'control', 'boot-missing-dash', 'boot-extra-dash', 'boot-uppercase',
    'material', 'leading-zero', 'signed', 'overflow', 'root-zero', 'source-zero',
    'marker-zero', 'attachment-zero', 'publisher-zero', 'publisher-overflow', 'expired'])
def test_ready_parser_rejects_ambiguous_or_incomplete_records(publication_probe, tmp_path, mutation):
    fields = _ready_fields()
    edits = {'header': (0, 'ONPC-OTHER'), 'version': (1, '1'),
             'control': (5, '01234567-89ab-cdef-0123-456789abcde\r'),
             'boot-missing-dash': (5, '01234567089ab-cdef-0123-456789abcdef'),
             'boot-extra-dash': (5, '-1234567-89ab-cdef-0123-456789abcdef'),
             'boot-uppercase': (5, '01234567-89AB-cdef-0123-456789abcdef'),
             'material': (2, 'a' * 63), 'leading-zero': (7, '010'), 'signed': (8, '+1'),
             'overflow': (6, str(2**64)), 'root-zero': (7, '0'), 'source-zero': (9, '0'),
             'marker-zero': (11, '0'), 'attachment-zero': (12, '0'), 'publisher-zero': (13, '0'),
             'publisher-overflow': (13, str(2**31))}
    if mutation in edits:
        index, text = edits[mutation]
        fields[index] = text
    data = ('\t'.join(fields) + '\n').encode()
    if mutation == 'extra-field':
        data = data[:-1] + b'\textra\n'
    elif mutation == 'truncated':
        data = data[:-1]
    elif mutation == 'newline':
        data += b'\n'
    elif mutation == 'nul':
        data = data[:-1] + b'\0\n'
    (tmp_path / 'input').write_bytes(data)
    result = _run(publication_probe, tmp_path, 'ready-parse-expired' if mutation == 'expired' else 'ready-parse')
    assert result.returncode == 1, result.stderr

