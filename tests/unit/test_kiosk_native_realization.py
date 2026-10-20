"""Independent real-mount witnesses for native actual V/I realization.

Each waited probe owns private user/mount namespaces and disposable scratch.
No installed product, service, host mount or ready record is changed.
"""

import hashlib
from pathlib import Path
import subprocess

import pytest

from tools import test_storage


ROOT = Path(__file__).resolve().parents[2]

PREAMBLE = r'''
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <poll.h>
#include <limits.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/wait.h>
#include <sys/socket.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <signal.h>
#include <dirent.h>
#include <sys/xattr.h>
#include "kiosk_private_creation.h"
static void require(int value, const char *stage) {
    if (!value) { fprintf(stderr, "realization-witness:%s:%s\n", stage, strerror(errno)); exit(1); }
}
static void put(const char *path, const char *bytes) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    require(fd >= 0 && write(fd, bytes, strlen(bytes)) == (ssize_t)strlen(bytes) &&
        fchmod(fd, 0644) == 0 && close(fd) == 0, path);
}
static void make_dir(const char *path) { require(mkdir(path, 0755) == 0 && chmod(path, 0755) == 0, path); }
static void put_map(const char *path, const char *bytes) {
    int fd = open(path, O_WRONLY | O_CLOEXEC);
    require(fd >= 0 && write(fd, bytes, strlen(bytes)) == (ssize_t)strlen(bytes) && close(fd) == 0, path);
}
static void private_namespace(void) {
    uid_t uid = getuid(); gid_t gid = getgid(); char map[128];
    require(unshare(CLONE_NEWUSER) == 0, "private-user-namespace");
    put_map("/proc/self/setgroups", "deny");
    snprintf(map, sizeof(map), "0 %lu 1\n", (unsigned long)uid); put_map("/proc/self/uid_map", map);
    snprintf(map, sizeof(map), "0 %lu 1\n", (unsigned long)gid); put_map("/proc/self/gid_map", map);
    require(unshare(CLONE_NEWNS) == 0 && mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) == 0, "private-mounts");
}
struct kiosk_failure { const char *stage, *reason; int error; };
struct kiosk_owned_mount { char *path; unsigned long long id; int live; };
#define KIOSK_VIEW_ROWS 32768U
#define KIOSK_VIEW_BYTES (64U * 1024U * 1024U)
'''

BODY = r'''
#include <stdarg.h>
static int injected_errno;
static dev_t error_parent_device;
static ino_t error_parent_inode;
static const char *error_name;
static int controlled_openat(int parent, const char *name, int flags, ...) {
    struct stat s;
    if (injected_errno && error_name && !strcmp(name,error_name) && (flags & O_PATH) &&
        fstat(parent,&s)==0 && s.st_dev==error_parent_device && s.st_ino==error_parent_inode) {
        errno=injected_errno; return -1;
    }
    mode_t mode=0;
    if (flags & O_CREAT) { va_list args; va_start(args,flags); mode=(mode_t)va_arg(args,int); va_end(args); }
    return openat(parent,name,flags,mode);
}
#define openat controlled_openat
#include "kiosk_native_realization.h"
#undef openat
static const char digest[] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
static const char sha[] = "@SHA@";
static void identity(const char *path, uint64_t value[8]) {
    struct stat s; require(lstat(path, &s) == 0, "independent-source-stat"); kiosk_preparation_assertion(&s, value);
}
static struct kiosk_pin_target target_for(int parent, const char *name) {
    struct kiosk_pin_target target; struct stat s; int fd = openat(parent, name, O_PATH | O_DIRECTORY | O_CLOEXEC);
    require(fd >= 0 && fstat(parent, &s) == 0 && kiosk_pin_fd_mount(parent, &target.parent_mount) == 0, "target-parent");
    target.parent_device = s.st_dev; target.parent_inode = s.st_ino;
    require(fstat(fd, &s) == 0 && kiosk_pin_fd_mount(fd, &target.mount) == 0, "target-inode");
    target.device = s.st_dev; target.inode = s.st_ino; close(fd); return target;
}
static void content(int root, const char *name, const char *expected) {
    char bytes[128] = {0}; int fd = openat(root, name, O_RDONLY | O_CLOEXEC);
    require(fd >= 0 && read(fd, bytes, sizeof(bytes)-1) == (ssize_t)strlen(expected) && !strcmp(bytes, expected), "actual-mounted-bytes"); close(fd);
}
int main(int argc, char **argv) {
    require(argc == 3 && chdir(argv[2]) == 0, "arguments"); private_namespace();
    const char *mode = argv[1]; uint64_t now; require(kiosk_pin_now(&now) == 0, "clock"); uint64_t deadline = now + 10000000;
    make_dir("host"); make_dir("host/data"); make_dir("host/data/inner"); make_dir("host/data/inner/nested");
    require(mount("tmpfs", "host/data/inner/nested", "tmpfs", 0, "size=1m,mode=0755") == 0, "real-nested-submount");
    put("host/data/inner/nested/leaf", "nested-original"); put("host/extra", "ambient"); make_dir("copies"); put("copies/0", "required");
    make_dir("stage"); require(mount("tmpfs", "stage", "tmpfs", 0, "size=1m,mode=0755") == 0, "fresh-private-tmpfs");
    make_dir("stage/tree"); make_dir("stage/tree/bin"); put("stage/tree/bin/tool", "");
    require(symlink("tool", "stage/tree/bin/tool-link") == 0, "fresh-link");
    make_dir("stage/tree/data"); put("stage/tree/extra", "");
    require(symlink("tool", "host/tool-link") == 0, "source-link"); make_dir("attached");
    struct kiosk_material_spec specs[] = {
        {.path="/usr", .kind="tree", .source_class="skeleton", .role="skeleton"},
        {.path="/usr/bin", .kind="tree", .source_class="skeleton", .role="skeleton"},
        {.path="/usr/bin/tool", .kind="file", .source_class="runtime", .role="data", .sha256=sha, .label="-", .size=8, .mode=0644},
        {.path="/usr/bin/tool-link", .kind="link", .source_class="alias", .role="data", .link="tool"},
    };
    struct kiosk_material_authority authority = {.backend="apparmor", .specs=specs, .count=4, .deadline=deadline};
    strcpy(authority.digest, digest);
    struct kiosk_preparation_row rows[] = {
        {.path="/usr", .kind="tree", .source_class="skeleton", .role="skeleton", .slot=0, .required=1, .spec=&specs[0]},
        {.path="/usr/bin", .kind="tree", .source_class="skeleton", .role="skeleton", .slot=2, .required=1, .spec=&specs[1]},
        {.path="/usr/bin/tool", .kind="file", .source_class="runtime", .role="data", .slot=5, .required=1, .has_source=1, .copied=1, .copy_name="0", .spec=&specs[2]},
        {.path="/usr/bin/tool-link", .kind="link", .link="tool", .source_path="/usr/tool-link", .source_class="alias", .role="data", .slot=8, .required=1, .has_source=1, .spec=&specs[3]},
        {.path="/usr/data", .kind="directory", .source_path="/usr/data", .source_class="ambient", .role="ambient", .slot=12, .has_source=1},
        {.path="/usr/extra", .kind="file", .source_path="/usr/extra", .source_class="ambient", .role="ambient", .slot=16, .has_source=1},
    };
    identity("copies/0", rows[2].copy_identity); identity("host/tool-link", rows[3].assertion);
    identity("host/data", rows[4].assertion); identity("host/extra", rows[5].assertion);
    for (unsigned i=2; i<6; i++) { rows[i].origin[0]=rows[i].assertion[0]; rows[i].origin[1]=rows[i].assertion[1]; }
    rows[2].origin[0]=100; rows[2].origin[1]=200; /* Independent original source, never the copied inode. */
    struct kiosk_preparation_plan plan = {.rows=rows, .count=6, .deadline=deadline, .verified=1};
    struct kiosk_host_roots host = {.root=open(".", O_PATH|O_DIRECTORY|O_CLOEXEC), .usr=open("host", O_PATH|O_DIRECTORY|O_CLOEXEC)};
    int copies=open("copies", O_PATH|O_DIRECTORY|O_CLOEXEC), skeleton=open("stage/tree", O_PATH|O_DIRECTORY|O_CLOEXEC);
    void *crypto=dlopen("libcrypto.so.3", RTLD_NOW|RTLD_LOCAL); require(crypto != NULL, "crypto");
    int fail_bind = 0;
    if (!strcmp(mode,"extra-skeleton")) { put("stage/tree/unexpected", ""); fail_bind=1; }
    if (!strcmp(mode,"wrong-copy")) { require(unlink("copies/0")==0,"replace-copy"); put("copies/0","required"); fail_bind=1; }
    if (!strcmp(mode,"wrong-link")) { require(unlink("stage/tree/bin/tool-link")==0 && symlink("elsewhere","stage/tree/bin/tool-link")==0,"replace-link"); fail_bind=1; }
    if (!strcmp(mode,"changed-content")) { put("copies/0","required-changed"); fail_bind=1; }
    if (!strcmp(mode,"expired")) { deadline=now-1; authority.deadline=plan.deadline=deadline; fail_bind=1; }
    if (!strcmp(mode,"ambient-mask")) { require(chmod("host/data",0777)==0 && chmod("host/extra",0666)==0,"ambient-unsafe"); }
    if (!strcmp(mode,"initial-nested-unsafe")) require(chmod("host/data/inner/nested",0777)==0,"initial-nested-unsafe-metadata");
    if (!strcmp(mode,"initial-intermediate-unsafe")) require(chmod("host/data/inner",0777)==0,"initial-nested-parent-unsafe-metadata");
    if (!strcmp(mode,"initial-replaced-inode")) { require(rename("host/extra","host/original-extra")==0,"retire-initial-ambient"); put("host/extra","replacement"); }
    if (!strncmp(mode,"source-error-",13) || !strcmp(mode,"required-source-error")) {
        injected_errno=!strcmp(mode,"source-error-EACCES") ? EACCES : !strcmp(mode,"source-error-EPERM") ? EPERM :
            !strcmp(mode,"source-error-ESTALE") ? ESTALE : !strcmp(mode,"source-error-ENOENT") ? ENOENT : EIO;
        struct stat parent_info; require(fstat(!strcmp(mode,"required-source-error") ? copies : host.usr,&parent_info)==0,"error-parent");
        error_parent_device=parent_info.st_dev; error_parent_inode=parent_info.st_ino;
        error_name=!strcmp(mode,"required-source-error") ? "0" : "extra";
        fail_bind=!strcmp(mode,"required-source-error");
    }
    if (!strcmp(mode,"safe-ambient-drift")) put("host/extra","changed");
    struct kiosk_native_realization realized; struct kiosk_failure failure={0},cleanup={0};
    int result=kiosk_realization_bind_until(&realized,skeleton,&plan,&authority,&host,-1,copies,NULL,digest,crypto,deadline,&failure);
    if (fail_bind) {
        require(result != 0 && !realized.bound && failure.stage,"refuse-invalid-intent-or-source");
        for (unsigned i=realized.stage_count;i>0;i--) if (realized.stages[i-1].live)
            require(kiosk_detach_owned(realized.stages[i-1].path,realized.stages[i-1].id,&cleanup)==0,"owned-failure-cleanup");
        kiosk_realization_close(&realized); puts("refused"); return 0;
    }
    require(result==0,"native-actual-realization");
    injected_errno=0;
    require(realized.receipt.nodes[2].number[KR_INDEX]==5 && realized.receipt.nodes[2].number[KR_ORIGIN_INO]==200,
        "global-slot-and-original-copy-provenance");
    int masked_directory=!strcmp(mode,"ambient-mask") || !strcmp(mode,"initial-nested-unsafe") || !strcmp(mode,"initial-intermediate-unsafe");
    if (masked_directory) require(realized.receipt.nc==0 && !strcmp(realized.receipt.nodes[4].v[KR_KIND],"empty-directory"),"actual-ambient-directory-narrowing");
    else {
        require(realized.receipt.nc==1 && !strcmp(realized.receipt.coverage[0].v[KC_PATH],"/usr/data/inner/nested"),"independent-real-submount-receipt");
        content(skeleton,"data/inner/nested/leaf","nested-original");
    }
    if (!strcmp(mode,"initial-replaced-inode") || !strcmp(mode,"safe-ambient-drift") || !strncmp(mode,"source-error-",13))
        require(!strcmp(realized.receipt.nodes[5].v[KR_KIND],"absent") && access("stage/tree/extra",F_OK)!=0,
            "initial-local-omission-never-binds-replacement");
    char marker_bytes[256]; snprintf(marker_bytes,sizeof(marker_bytes),"M=%s\nV=%s\n",digest,realized.receipt.digest);
    put("stage/tree/retained-view",marker_bytes); require(chmod("stage/tree/retained-view",0444)==0,"marker-seal");
    int marker=open("stage/tree/retained-view",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if (!strcmp(mode,"wrong-marker")) marker_bytes[0]='x';
    result=kiosk_realization_marker_until(&realized,"/usr/retained-view",marker,marker_bytes,strlen(marker_bytes),deadline,&failure);
    if (!strcmp(mode,"wrong-marker")) { require(result!=0 && !realized.marker_verified,"marker-byte-refusal"); puts("refused"); return 0; }
    require(result==0,"native-marker-independent-verification"); close(marker);
    if (!strcmp(mode,"missing-recursive")) {
        require(umount2("stage/tree/data/inner/nested",MNT_DETACH)==0,"remove-real-nested-mount");
    }
    int parent=open(".",O_PATH|O_DIRECTORY|O_CLOEXEC); struct kiosk_pin_target target=target_for(parent,"attached");
    struct kiosk_source_pin pin={.fd=-1,.parent=-1,.worker=-1};
    result=kiosk_realization_attach_until(&realized,&pin,parent,"attached",&target,deadline,&failure);
    if (!strcmp(mode,"missing-recursive")) { require(result!=0 && !pin.verified,"missing-submount-independent-refusal"); puts("refused"); return 0; }
    require(result==0 && pin.verified,"strict-recursive-readonly-attachment");
    content(pin.fd,"bin/tool","required");
    if (!masked_directory) content(pin.fd,"data/inner/nested/leaf","nested-original");
    int writable=open("attached/bin/tool",O_WRONLY|O_CLOEXEC); require(writable<0 && errno==EROFS,"actual-required-readonly");
    if (!masked_directory) { writable=open("attached/data/inner/nested/leaf",O_WRONLY|O_CLOEXEC); require(writable<0 && errno==EROFS,"actual-nested-readonly"); }
    char absolute[PATH_MAX]; require(realpath("stage",absolute)!=NULL,"stage-path");
    struct kiosk_owned_mount stages[16]; stages[0]=(struct kiosk_owned_mount){.path=absolute,.live=1};
    require(kiosk_mount_id(absolute,&stages[0].id)==0,"stage-identity");
    for (unsigned i=0;i<realized.stage_count;i++) stages[i+1]=realized.stages[i];
    require(kiosk_pin_finish_until(&pin,stages,realized.stage_count+1,realized.entries,realized.entry_count,deadline,&failure)==0,
        "identity-owned-staging-detach-and-recheck");
    unsigned char ambient[32768]={0};
    for (unsigned i=0;i<realized.entry_count;i++) ambient[i]=!strncmp(realized.entries[i].relative,"data",4) || !strcmp(realized.entries[i].relative,"extra");
    require(kiosk_realization_verify_source_until(pin.fd,&realized.receipt,&authority,"/usr/retained-view",realized.entries,
        realized.entry_count,ambient,crypto,deadline,&failure)==0,"full-actual-retained-source-closure");
    content(pin.fd,"bin/tool","required");
    if (!strncmp(mode,"gate-",5)) {
        struct stat manager_root, manager_link, manager_file, current;
        require(fstat(pin.fd,&manager_root)==0 && fstatat(pin.fd,"bin/tool-link",&manager_link,AT_SYMLINK_NOFOLLOW)==0 &&
            fstatat(pin.fd,"bin/tool",&manager_file,AT_SYMLINK_NOFOLLOW)==0,"independent-manager-before");
        make_dir("gate-stage"); require(mount("tmpfs","gate-stage","tmpfs",0,"size=1m,mode=0755")==0,"fresh-gate-tmpfs");
        make_dir("gate-stage/tree"); make_dir("gate-stage/tree/bin"); put("gate-stage/tree/bin/tool","");
        require(symlink("tool","gate-stage/tree/bin/tool-link")==0,"fresh-gate-link");
        make_dir("gate-stage/tree/data"); put("gate-stage/tree/extra","");
        for (unsigned i=0;i<6;i++) {
            const struct kiosk_receipt_row *v=&realized.receipt.nodes[i];
            rows[i].copied=0; rows[i].copy_name=NULL; rows[i].source_path=rows[i].path; rows[i].has_source=1;
            rows[i].origin[0]=v->number[KR_ORIGIN_DEV]; rows[i].origin[1]=v->number[KR_ORIGIN_INO];
            int source=kiosk_pin_open(pin.fd,kiosk_realization_relative(rows[i].path));
            require(source>=0 && fstat(source,&current)==0,"independent-gate-source-stat"); close(source);
            kiosk_preparation_assertion(&current,rows[i].assertion);
        }
        if (!strcmp(mode,"gate-ambient-loss")) require(chmod("host/data",0777)==0 && chmod("host/extra",0666)==0,"late-gate-ambient-loss");
        if (!strcmp(mode,"gate-nested-unsafe")) require(chmod("host/data/inner/nested",0777)==0,"same-origin-nested-unsafe");
        if (!strcmp(mode,"gate-nested-foreign")) require(mount("tmpfs","attached/data/inner/nested","tmpfs",0,"size=1m,mode=0755")==0,"foreign-real-submount");
        if (!strcmp(mode,"gate-source-foreign")) { put("foreign-extra","foreign"); require(mount("foreign-extra","attached/extra",NULL,MS_BIND,NULL)==0,"retained-foreign-file"); }
        if (!strcmp(mode,"gate-required-unsafe")) require(chmod("copies/0",0666)==0,"required-remains-strict");
        if (!strcmp(mode,"gate-safe-drift")) put("host/extra","changed-after-selected-assertion");
        if (!strcmp(mode,"gate-source-error")) {
            injected_errno=ESTALE; error_name="extra"; error_parent_device=manager_root.st_dev; error_parent_inode=manager_root.st_ino;
        }
        int gate_root=open("gate-stage/tree",O_PATH|O_DIRECTORY|O_CLOEXEC);
        struct kiosk_native_realization invocation;
        int gate_result=kiosk_realization_bind_until(&invocation,gate_root,&plan,&authority,&host,pin.fd,-1,&realized.receipt,
            digest,crypto,deadline,&failure);
        injected_errno=0;
        if (!strcmp(mode,"gate-nested-foreign") || !strcmp(mode,"gate-source-foreign") || !strcmp(mode,"gate-required-unsafe") || !strcmp(mode,"gate-safe-drift")) {
            require(gate_result!=0 && !invocation.bound,"foreign-or-required-never-narrows");
            puts("refused"); return 0;
        }
        require(gate_result==0,"native-actual-I-from-actual-V");
        require(!strcmp(invocation.receipt.kind,"I") && !strcmp(invocation.receipt.source,realized.receipt.digest) &&
            invocation.receipt.nodes[2].number[KR_INDEX]==5 && invocation.receipt.nodes[2].number[KR_ORIGIN_INO]==200,
            "I-binds-V-slots-and-original-provenance");
        if (!strcmp(mode,"gate-ambient-loss")) require(!strcmp(invocation.receipt.nodes[4].v[KR_KIND],"empty-directory") &&
            !strcmp(invocation.receipt.nodes[5].v[KR_KIND],"absent") && !invocation.receipt.nc,"I-only-ambient-narrowing");
        else if (!strcmp(mode,"gate-nested-unsafe")) require(!strcmp(invocation.receipt.nodes[4].v[KR_KIND],"empty-directory") &&
            !invocation.receipt.nc,"unsafe-nested-owner-masked-in-I");
        else require(invocation.receipt.nc==1,"I-retains-real-recursive-coverage");
        if (!strcmp(mode,"gate-source-error")) require(!strcmp(invocation.receipt.nodes[5].v[KR_KIND],"absent"),"retained-final-local-error-narrows-I");
        require(fstat(pin.fd,&current)==0 && current.st_ino==manager_root.st_ino && current.st_dev==manager_root.st_dev &&
            fstatat(pin.fd,"bin/tool-link",&current,AT_SYMLINK_NOFOLLOW)==0 && current.st_ino==manager_link.st_ino &&
            fstatat(pin.fd,"bin/tool",&current,AT_SYMLINK_NOFOLLOW)==0 && current.st_ino==manager_file.st_ino,
            "fresh-I-leaves-manager-dentries-unchanged");
        content(pin.fd,"bin/tool","required"); content(pin.fd,"data/inner/nested/leaf","nested-original");
        for (unsigned i=invocation.stage_count;i>0;i--) if (invocation.stages[i-1].live)
            require(kiosk_detach_owned(invocation.stages[i-1].path,invocation.stages[i-1].id,&cleanup)==0,"owned-gate-bind-cleanup");
        require(umount2("gate-stage",MNT_DETACH)==0,"owned-gate-stage-cleanup");
        kiosk_realization_close(&invocation); close(gate_root);
    }
    require(kiosk_pin_release(&pin,0,&cleanup)==0,"owned-attachment-release");
    kiosk_realization_close(&realized); close(parent); close(skeleton); close(copies); close(host.root); close(host.usr); dlclose(crypto);
    puts("verified"); return 0;
}
'''


@pytest.fixture(scope='module')
def native_realization(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-native-realization')
    source, binary = directory / 'realization.c', directory / 'realization'
    header = (ROOT / 'tools/kiosk_confinement.h').read_text()
    helpers = header[header.index('static void\nkiosk_failure('):header.index('static void\nkiosk_native_diagnostic(')]
    paths = header[header.index('static int\nkiosk_mount_id('):header.index('static int\nkiosk_label(')]
    labels = header[header.index('static int\nkiosk_label('):header.index('/* Open parents separately.')]
    parents = header[header.index('static int\nkiosk_parent('):header.index('static int\nkiosk_absolute_parent(')]
    primitives = header[header.index('#include <sys/statvfs.h>', header.index('kiosk_absolute_parent')):
                        header.index('static int\ncleanup_kiosk_view(')]
    source.write_text(PREAMBLE + helpers + paths + labels + parents + primitives +
                      BODY.replace('@SHA@', hashlib.sha256(b'required').hexdigest()))
    compiled = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-I', str(ROOT / 'tools'), str(source), '-o', str(binary), '-ldl'],
                              capture_output=True, text=True, timeout=30, pass_fds=test_storage.scratch_descriptors())
    assert compiled.returncode == 0, compiled.stderr
    return binary


@pytest.mark.parametrize('mode', ['positive', 'ambient-mask', 'initial-nested-unsafe', 'initial-intermediate-unsafe', 'initial-replaced-inode',
                                 'source-error-EACCES', 'source-error-EPERM', 'source-error-EIO', 'source-error-ESTALE', 'source-error-ENOENT',
                                 'required-source-error', 'gate-positive', 'gate-ambient-loss', 'gate-nested-unsafe',
                                 'gate-nested-foreign', 'gate-source-foreign', 'gate-required-unsafe', 'gate-safe-drift', 'gate-source-error', 'extra-skeleton', 'wrong-copy', 'wrong-link',
                                 'changed-content', 'expired', 'safe-ambient-drift', 'wrong-marker', 'missing-recursive'])
def test_actual_native_realization(native_realization, tmp_path, mode):
    result = subprocess.run([str(native_realization), mode, str(tmp_path)], capture_output=True, text=True,
                            timeout=15, pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stdout + result.stderr
    verified = (mode in ('positive', 'ambient-mask', 'initial-nested-unsafe', 'initial-intermediate-unsafe', 'initial-replaced-inode', 'safe-ambient-drift', 'gate-positive', 'gate-ambient-loss',
                        'gate-nested-unsafe', 'gate-source-error') or mode.startswith('source-error-'))
    assert result.stdout.strip() == ('verified' if verified else 'refused')
