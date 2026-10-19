"""Real, private Linux mount witnesses for the unwired retained-pin primitives.

The compiler and probe are bounded, waited children; each probe creates its own
user/mount namespaces. An unavailable namespace capability is a failure, never
an acceptance skip or a reason to use host mount authority.
"""

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
static void require(int value, const char *stage) {
    if (!value) { fprintf(stderr, "pin-witness:%s:%s\n", stage, strerror(errno)); exit(1); }
}
static void put(const char *path, const char *bytes) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    require(fd >= 0 && write(fd, bytes, strlen(bytes)) == (ssize_t) strlen(bytes), path);
    require(close(fd) == 0, "write-close");
}
static void private_namespace(void) {
    uid_t uid = getuid(); gid_t gid = getgid(); char map[128];
    require(unshare(CLONE_NEWUSER) == 0, "private-user-namespace-unavailable");
    put("/proc/self/setgroups", "deny");
    snprintf(map, sizeof(map), "0 %lu 1\n", (unsigned long) uid);
    put("/proc/self/uid_map", map);
    snprintf(map, sizeof(map), "0 %lu 1\n", (unsigned long) gid);
    put("/proc/self/gid_map", map);
    require(unshare(CLONE_NEWNS) == 0, "private-mount-namespace-unavailable");
    require(mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) == 0, "private-propagation");
}
static const char *probe_mode;
static int transaction_elapsed;
static unsigned clone_calls, transaction_clock_calls, expire_at, deferred_waits, move_calls, stage_detaches, ready_renames;
static int fixture_pin_clock(clockid_t clock, struct timespec *value) {
    int result = clock_gettime(clock, value);
    transaction_clock_calls++;
    if (expire_at && transaction_clock_calls >= expire_at) transaction_elapsed = 1;
    if (result == 0 && transaction_elapsed) value->tv_sec += 120;
    return result;
}
#define KIOSK_PIN_CLOCK_GETTIME fixture_pin_clock
static int fault(const char *name) {
    if (probe_mode && strcmp(probe_mode, name) == 0) { errno = EIO; return 1; } return 0;
}
static int fixture_open_tree(int fd, const char *path, unsigned flags) {
    clone_calls++;
    if (probe_mode && strcmp(probe_mode, "deadline-after-clone") == 0) transaction_elapsed = 1;
    if (probe_mode && (!strcmp(probe_mode, "worker-timeout") || !strcmp(probe_mode, "worker-deadline"))) for (;;) pause();
    return fault("clone-error") ? -1 : open_tree(fd, path, flags);
}
static int fixture_poll(struct pollfd *fds, nfds_t count, int timeout) {
    if (probe_mode && !strcmp(probe_mode, "worker-deadline")) { transaction_elapsed = 1; return 0; }
    return poll(fds, count, timeout);
}
static int fixture_waitid(idtype_t type, id_t id, siginfo_t *info, int options) {
    if (probe_mode && !strcmp(probe_mode, "worker-deadline") && transaction_elapsed) {
        memset(info, 0, sizeof(*info)); deferred_waits++; return 0;
    }
    return waitid(type, id, info, options);
}
static int fixture_setns(int fd, int type) { return fault("worker-error") ? -1 : setns(fd, type); }
static ssize_t fixture_sendmsg(int socket, const struct msghdr *message, int flags) {
    if (probe_mode && (strcmp(probe_mode, "worker-malformed") == 0 || strcmp(probe_mode, "worker-cleanup-error") == 0)) {
        struct msghdr malformed = *message; malformed.msg_control = NULL; malformed.msg_controllen = 0;
        return sendmsg(socket, &malformed, flags);
    }
    return sendmsg(socket, message, flags);
}
static long fixture_pidfd_send_signal(int fd, int signal, const void *info, unsigned flags) {
    if (fault("worker-cleanup-error")) return -1;
    return syscall(SYS_pidfd_send_signal, fd, signal, info, flags);
}
static int fixture_move_mount(int source, const char *from, int target, const char *to, unsigned flags) {
    move_calls++;
    int result = fault("attach-error") ? -1 : move_mount(source, from, target, to, flags);
    if (result == 0 && probe_mode && !strcmp(probe_mode, "attach-deadline-after-move")) transaction_elapsed = 1;
    return result;
}
static int fixture_mount_setattr(int fd, const char *path, unsigned flags, struct mount_attr *attr, size_t size) {
    return ((flags & AT_EMPTY_PATH) && fault("readonly-error")) ? -1 : mount_setattr(fd, path, flags, attr, size);
}
static int fixture_umount(const char *path, int flags) {
    if (probe_mode && strcmp(probe_mode, "detach-error") == 0 && strstr(path, "/stage")) { errno = EIO; return -1; }
    if (fault("cleanup-error")) return -1;
    int result = umount2(path, flags);
    if (result == 0 && strstr(path, "/stage")) {
        stage_detaches++;
        if (probe_mode && !strcmp(probe_mode, "finish-deadline-after-detach")) transaction_elapsed = 1;
    }
    return result;
}
static ssize_t fixture_write(int fd, const void *bytes, size_t size) {
    if (fault("publish-cleanup-error")) return -1;
    ssize_t result = fault("write-error") ? -1 : write(fd, bytes, size);
    if (result > 0 && probe_mode && !strcmp(probe_mode, "publish-deadline-after-write")) transaction_elapsed = 1;
    return result;
}
static int fixture_unlinkat(int fd, const char *path, int flags) {
    return fault("publish-cleanup-error") ? -1 : unlinkat(fd, path, flags);
}
static int fixture_fsync(int fd) {
    int result = fault("fsync-error") ? -1 : fsync(fd);
    if (result == 0 && probe_mode && !strcmp(probe_mode, "publish-deadline-before-rename")) transaction_elapsed = 1;
    return result;
}
static int fixture_rename(int from, const char *source, int to, const char *target, unsigned flags) {
    if (probe_mode && strcmp(probe_mode, "before-ready-cut") == 0) _exit(73);
    if (fault("rename-error")) return -1;
    int result = renameat2(from, source, to, target, flags);
    if (result == 0) ready_renames++;
    if (result == 0 && probe_mode && !strcmp(probe_mode, "publish-deadline-after-ready")) transaction_elapsed = 1;
    if (result == 0 && probe_mode && strcmp(probe_mode, "after-ready-cut") == 0) _exit(74);
    return result;
}
static unsigned descriptors(void) {
    DIR *directory = opendir("/proc/self/fd"); require(directory != NULL, "descriptor-count");
    unsigned count = 0; struct dirent *entry;
    while ((entry = readdir(directory)) != NULL)
        if (strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) count++;
    closedir(directory); return count;
}
'''


@pytest.fixture(scope='module')
def native_pin(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-pin-native')
    source = directory / 'pin.c'
    binary = directory / 'pin'
    header = (ROOT / 'tools/kiosk_confinement.h').read_text()
    helpers = header[header.index('static void\nkiosk_failure('):header.index('static void\nkiosk_native_diagnostic(')]
    paths = header[header.index('static int\nkiosk_mount_id('):header.index('static int\nkiosk_label(')]
    labels = header[header.index('static int\nkiosk_label('):header.index('/* Open parents separately.')]
    parents = header[header.index('static int\nkiosk_parent('):header.index('static int\nkiosk_absolute_parent(')]
    primitives = header[header.index('#include <sys/statvfs.h>', header.index('kiosk_absolute_parent')):
                        header.index('static int\ncleanup_kiosk_view(')]
    for actual, controlled in [('open_tree(', 'fixture_open_tree('), ('move_mount(', 'fixture_move_mount('),
                               ('mount_setattr(', 'fixture_mount_setattr('), ('umount2(', 'fixture_umount('),
                               ('write(', 'fixture_write('), ('fsync(', 'fixture_fsync('), ('renameat2(', 'fixture_rename('),
                               ('unlinkat(', 'fixture_unlinkat('), ('setns(', 'fixture_setns('), ('sendmsg(', 'fixture_sendmsg(')]:
        primitives = primitives.replace(actual, controlled)
    primitives = primitives.replace('syscall(SYS_pidfd_send_signal, ', 'fixture_pidfd_send_signal(')
    primitives = primitives.replace('poll(', 'fixture_poll(').replace('waitid(', 'fixture_waitid(')
    source.write_text(PREAMBLE + r'''
struct kiosk_failure { const char *stage, *reason; int error; };
struct kiosk_owned_mount { char *path; unsigned long long id; int live; };
#define KIOSK_VIEW_ROWS 32768U
#define KIOSK_VIEW_BYTES (64U * 1024U * 1024U)
''' + helpers + paths + labels + parents + primitives + r'''
static const char digest[] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
static const char *names[] = {"", "bin", "bin/copy", "bin/vendor", "data"};
static void content(int root, const char *relative, const char *expected) {
    int fd = openat(root, relative, O_RDONLY | O_CLOEXEC); char bytes[128] = {0};
    require(fd >= 0 && read(fd, bytes, sizeof(bytes) - 1) == (ssize_t) strlen(expected) &&
        strcmp(bytes, expected) == 0, "original-content"); close(fd);
}
static void setup_source(void) {
    require(mkdir("stage", 0755) == 0, "stage-directory");
    require(mount("tmpfs", "stage", "tmpfs", 0, "size=1m,mode=0755") == 0, "private-tmpfs");
    require(mkdir("stage/bin", 0755) == 0 && mkdir("stage/data", 0755) == 0, "skeleton");
    put("stage/bin/copy", "original-copy"); put("stage/bin/vendor", "");
    require(mount("vendor", "stage/bin/vendor", NULL, MS_BIND, NULL) == 0, "vendor-bind");
    require(mount("ambient", "stage/data", NULL, MS_BIND | MS_REC, NULL) == 0, "directory-bind");
    struct mount_attr readonly = {.attr_set = MOUNT_ATTR_RDONLY};
    require(mount_setattr(AT_FDCWD, "stage", AT_RECURSIVE, &readonly, sizeof(readonly)) == 0, "source-readonly");
}
static void entries_for(int root, struct kiosk_pin_entry entries[5]) {
    for (unsigned i = 0; i < 5; i++) {
        int fd = kiosk_pin_open(root, names[i]); struct stat info;
        require(fd >= 0 && fstat(fd, &info) == 0, "receipt-independent-inode"); close(fd);
        entries[i] = (struct kiosk_pin_entry) {.relative = names[i], .device = info.st_dev,
            .inode = info.st_ino, .mode = info.st_mode, .uid = info.st_uid, .gid = info.st_gid,
            .parent = (i == 2 || i == 3) ? 1U : 0U, .mountpoint = i == 0 || i == 3 || i == 4};
    }
}
static struct kiosk_pin_target target_for(int parent, const char *name) {
    struct kiosk_pin_target ticket; struct stat info;
    int fd = openat(parent, name, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    require(fd >= 0 && fstat(fd, &info) == 0, "target-ticket");
    ticket.device = info.st_dev; ticket.inode = info.st_ino;
    require(kiosk_pin_fd_mount(fd, &ticket.mount) == 0 && fstat(parent, &info) == 0, "target-ticket-mount");
    ticket.parent_device = info.st_dev; ticket.parent_inode = info.st_ino;
    require(kiosk_pin_fd_mount(parent, &ticket.parent_mount) == 0, "target-parent-ticket"); close(fd); return ticket;
}
static void send_sources(int socket) {
    int fds[3] = {open("stage", O_PATH | O_DIRECTORY | O_CLOEXEC), open("/proc/self/mountinfo", O_RDONLY | O_CLOEXEC),
        open("/proc/self/ns/mnt", O_RDONLY | O_CLOEXEC)};
    require(fds[0] >= 0 && fds[1] >= 0 && fds[2] >= 0, "owner-source-descriptors");
    char control[CMSG_SPACE(sizeof(fds))] = {0}, data = 'r'; struct iovec io = {&data, 1};
    struct msghdr message = {.msg_iov = &io, .msg_iovlen = 1, .msg_control = control, .msg_controllen = sizeof(control)};
    struct cmsghdr *cmsg = CMSG_FIRSTHDR(&message); cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type = SCM_RIGHTS; cmsg->cmsg_len = CMSG_LEN(sizeof(fds)); memcpy(CMSG_DATA(cmsg), fds, sizeof(fds));
    require(sendmsg(socket, &message, 0) == 1, "owner-send"); close(fds[0]); close(fds[1]); close(fds[2]);
    /* EOF also releases the child if the probing parent fails. */
    require(read(socket, &data, 1) >= 0, "owner-barrier");
    require(umount2("stage", MNT_DETACH) == 0, "owner-staging-detach"); close(socket); _exit(0);
}
static void receive_sources(int socket, int fds[3]) {
    char control[CMSG_SPACE(3 * sizeof(int))] = {0}, data; struct iovec io = {&data, 1};
    struct msghdr message = {.msg_iov = &io, .msg_iovlen = 1, .msg_control = control, .msg_controllen = sizeof(control)};
    require(recvmsg(socket, &message, MSG_CMSG_CLOEXEC) == 1 && !(message.msg_flags & MSG_CTRUNC), "source-receive");
    struct cmsghdr *cmsg = CMSG_FIRSTHDR(&message);
    require(cmsg != NULL && cmsg->cmsg_type == SCM_RIGHTS && cmsg->cmsg_len == CMSG_LEN(3 * sizeof(int)), "source-rights");
    memcpy(fds, CMSG_DATA(cmsg), 3 * sizeof(int));
}
static void caller_identity(struct stat identities[3]) {
    const char *paths[] = {"/proc/self/ns/mnt", "/", "."};
    for (unsigned i = 0; i < 3; i++) {
        int fd = open(paths[i], O_PATH | O_CLOEXEC);
        require(fd >= 0 && fstat(fd, &identities[i]) == 0, "caller-identity"); close(fd);
    }
}
int main(int argc, char **argv) {
    require(argc == 3, "arguments");
    private_namespace();
    require(chdir(argv[2]) == 0, "private-directory");
    const char *mode = argv[1];
    probe_mode = mode;
    unsigned baseline = descriptors();
    if (strcmp(mode, "capability") == 0) {
        require(mkdir("stage", 0755) == 0, "stage-directory");
        require(mount("tmpfs", "stage", "tmpfs", 0, "size=1m,mode=0755") == 0, "private-tmpfs");
        require(umount2("stage", MNT_DETACH) == 0, "private-detach");
        puts("private-mount-capability:verified"); return 0;
    }
    put("vendor", "original-vendor"); put("host-script", "original-copy");
    require(mkdir("ambient", 0755) == 0 && mkdir("attached", 0755) == 0 && mkdir("publication", 0700) == 0,
            "host-inputs"); put("ambient/leaf", "original-data");
    struct stat original_caller[3], observed_caller[3]; caller_identity(original_caller);
    int fds[3], sockets[2] = {-1, -1}; pid_t owner = -1;
    if (strcmp(mode, "lifetime") == 0 || strcmp(mode, "worker-error") == 0 || strcmp(mode, "worker-timeout") == 0 ||
        strcmp(mode, "worker-deadline") == 0 ||
        strcmp(mode, "worker-malformed") == 0 || strcmp(mode, "wrong-namespace") == 0 || strcmp(mode, "worker-cleanup-error") == 0) {
        require(socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, sockets) == 0, "owner-socket");
        owner = fork(); require(owner >= 0, "owner-fork");
        if (owner == 0) {
            close(sockets[0]); require(prctl(PR_SET_PDEATHSIG, SIGKILL) == 0 && getppid() != 1, "owner-lifetime");
            require(unshare(CLONE_NEWNS) == 0, "owner-namespace"); setup_source(); send_sources(sockets[1]);
        }
        close(sockets[1]); receive_sources(sockets[0], fds);
    } else {
        setup_source(); fds[0] = open("stage", O_PATH | O_DIRECTORY | O_CLOEXEC);
        fds[1] = open("/proc/self/mountinfo", O_RDONLY | O_CLOEXEC);
        fds[2] = open("/proc/self/ns/mnt", O_RDONLY | O_CLOEXEC);
    }
    require(fds[0] >= 0 && fds[1] >= 0 && fds[2] >= 0, "source-descriptors");
    if (strcmp(mode, "wrong-namespace") == 0) {
        close(fds[2]); fds[2] = open("/proc/self/ns/mnt", O_RDONLY | O_CLOEXEC);
    }
    struct stat source_ns; require(fstat(fds[2], &source_ns) == 0, "native-source-namespace");
    struct kiosk_pin_namespace source_namespace = {.fd = fds[2], .device = source_ns.st_dev, .inode = source_ns.st_ino};
    struct kiosk_pin_entry entries[5]; entries_for(fds[0], entries);
    struct kiosk_source_pin pin = {.fd = -1, .parent = -1, .worker = -1}; struct kiosk_failure failure = {0}, cleanup = {0};
    char source_path[PATH_MAX]; require(snprintf(source_path, sizeof(source_path), "%s/stage", argv[2]) < PATH_MAX, "source-path");
    if (strcmp(mode, "wrong-root") == 0) entries[0].inode++;
    if (strcmp(mode, "wrong-owner") == 0) entries[3].uid = 1;
    if (strcmp(mode, "unsafe-source") == 0) require(chmod("vendor", 0666) == 0, "actual-unsafe-source");
    if (strcmp(mode, "placeholder") == 0) { close(fds[0]); fds[0] = open("attached", O_PATH | O_DIRECTORY | O_CLOEXEC); }
    if (strcmp(mode, "extra-mount") == 0) {
        struct mount_attr writable = {.attr_clr = MOUNT_ATTR_RDONLY};
        require(mount_setattr(AT_FDCWD, "stage", 0, &writable, sizeof(writable)) == 0, "extra-enable");
        require(mkdir("stage/extra", 0755) == 0 && mount("ambient", "stage/extra", NULL, MS_BIND, NULL) == 0, "extra-mount");
        struct mount_attr readonly = {.attr_set = MOUNT_ATTR_RDONLY};
        require(mount_setattr(AT_FDCWD, "stage", AT_RECURSIVE, &readonly, sizeof(readonly)) == 0, "extra-readonly");
    }
    if (strcmp(mode, "missing-recursive") == 0) {
        int shallow = open_tree(fds[0], "", OPEN_TREE_CLONE | AT_EMPTY_PATH | OPEN_TREE_CLOEXEC);
        require(shallow >= 0, "shallow-clone");
        require(kiosk_pin_coverage(shallow, entries, 5, 1, &failure) != 0, "missing-recursive-refused"); close(shallow);
        close(fds[0]); close(fds[1]); close(fds[2]); puts("missing-recursive:refused"); return 0;
    }
    if (strncmp(mode, "deadline-", 9) == 0) {
        uint64_t now; require(kiosk_pin_now(&now) == 0, "transaction-clock");
        uint64_t deadline = strcmp(mode, "deadline-before-clone") == 0 ? now : now + 60000000U;
        int acquired;
        if (!strcmp(mode, "deadline-coverage-walk") || !strcmp(mode, "deadline-topology-walk")) {
            expire_at = transaction_clock_calls + 3;
            if (!strcmp(mode, "deadline-coverage-walk"))
                acquired = kiosk_pin_coverage_policy_until(fds[0], entries, 5, NULL, 1, deadline, &failure);
            else {
                unsigned long long id; require(kiosk_pin_fd_mount(fds[0], &id) == 0, "walk-mount-witness");
                acquired = kiosk_pin_topology_until(fds[1], id, source_path, entries, 5, deadline, &failure);
            }
            require(transaction_clock_calls == expire_at && clone_calls == 0, "mid-walk-deadline-stopped-work");
        } else acquired = kiosk_pin_acquire_policy_until(&pin, fds[0], fds[1], source_path,
            &source_namespace, entries, 5, NULL, deadline, &failure, &cleanup);
        require(acquired != 0 && pin.fd == -1 && pin.worker == -1 && failure.stage != NULL,
            "expired-transaction-refused");
        require(clone_calls == (strcmp(mode, "deadline-after-clone") == 0 ? 1U : 0U),
            "exact-clone-boundary-witness");
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0 && cleanup.stage == NULL, "deadline-owned-release");
        content(fds[0], "bin/vendor", "original-vendor");
        close(fds[0]); close(fds[1]); close(fds[2]);
        require(descriptors() == baseline, "deadline-fd-balance");
        printf("%s:refused\n", mode); return 0;
    }
    if (strncmp(mode, "provenance-", 11) == 0) {
        unsigned char ambient[5] = {0, 0, 0, 0, 1};
        int positive = strcmp(mode, "provenance-ambient-directory") == 0 ||
            strcmp(mode, "provenance-ambient-file") == 0;
        if (strcmp(mode, "provenance-ambient-file") == 0) {
            ambient[3] = 1;
            require(chmod("vendor", 0666) == 0, "ambient-file-unsafe");
        } else require(chmod("ambient", 0777) == 0, "ambient-directory-unsafe");
        if (strcmp(mode, "provenance-required") == 0) ambient[4] = 0;
        if (strcmp(mode, "provenance-root") == 0) ambient[0] = 1;
        if (strcmp(mode, "provenance-ancestor") == 0) ambient[1] = 1;
        if (strcmp(mode, "provenance-unknown") == 0) ambient[4] = 2;
        if (strcmp(mode, "provenance-foreign") == 0) entries[4].inode++;
        struct kiosk_failure strict = {0};
        require(kiosk_pin_coverage(fds[0], entries, 5, 1, &strict) != 0,
            "unsafe-source-still-refuses-strict-attachment");
        int acquired = kiosk_pin_acquire_policy(&pin, fds[0], fds[1], source_path,
            &source_namespace, entries, 5, ambient, &failure, &cleanup);
        require(positive ? acquired == 0 : acquired != 0, "retained-provenance-policy");
        if (positive) {
            struct stat observed;
            require(fstatat(pin.fd, "data", &observed, AT_SYMLINK_NOFOLLOW) == 0 &&
                observed.st_dev == entries[4].device && observed.st_ino == entries[4].inode,
                "original-ambient-inode");
            content(pin.fd, "data/leaf", "original-data");
            require(kiosk_pin_coverage(pin.fd, entries, 5, 1, &strict) != 0,
                "unsafe-clone-has-no-invocation-bind-authority");
            int parent = open(".", O_PATH | O_DIRECTORY | O_CLOEXEC);
            require(parent >= 0, "provenance-staging-parent");
            struct kiosk_pin_target ticket = target_for(parent, "attached");
            uint64_t deadline;
            require(kiosk_pin_now(&deadline) == 0, "provenance-staging-clock"); deadline += 60000000U;
            require(kiosk_pin_attach_until(&pin, parent, "attached", &ticket, entries, 5, deadline, &strict) != 0 &&
                !pin.attached, "strict-attachment-refuses-unsafe-provenance");
            require(kiosk_pin_attach_policy_until(&pin, parent, "attached", &ticket, entries, 5, ambient,
                deadline, &failure) == 0 && pin.verified, "explicit-ambient-staging-attachment");
            struct kiosk_owned_mount stage = {.path = source_path, .live = 1};
            require(kiosk_mount_id(stage.path, &stage.id) == 0, "provenance-stage-witness");
            require(kiosk_pin_finish_until(&pin, &stage, 1, entries, 5, deadline, &failure) != 0 &&
                !pin.complete && !stage.live, "ambient-staging-never-authorizes-completion");
            close(parent);
        }
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "provenance-release");
        close(fds[0]); close(fds[1]); close(fds[2]);
        require(descriptors() == baseline, "provenance-fd-balance");
        printf("%s:verified\n", mode); return 0;
    }
    uint64_t transaction_deadline;
    require(kiosk_pin_now(&transaction_deadline) == 0 && transaction_deadline < UINT64_MAX - 60000000U,
        "original-transaction-deadline");
    transaction_deadline += 60000000U;
    int acquired = kiosk_pin_acquire_policy_until(&pin, fds[0], fds[1], source_path, &source_namespace,
        entries, 5, NULL, transaction_deadline, &failure, &cleanup);
    caller_identity(observed_caller);
    for (unsigned i = 0; i < 3; i++) require(original_caller[i].st_dev == observed_caller[i].st_dev &&
        original_caller[i].st_ino == observed_caller[i].st_ino, "caller-namespace-root-cwd-preserved");
    if (strcmp(mode, "worker-error") == 0 || strcmp(mode, "worker-timeout") == 0 ||
        strcmp(mode, "worker-deadline") == 0 ||
        strcmp(mode, "worker-malformed") == 0 || strcmp(mode, "wrong-namespace") == 0 || strcmp(mode, "worker-cleanup-error") == 0) {
        require(acquired != 0 && pin.fd == -1 && failure.stage != NULL, "crossnamespace-refusal");
        if (strcmp(mode, "worker-cleanup-error") == 0 || strcmp(mode, "worker-deadline") == 0 ||
            (strcmp(mode, "worker-timeout") == 0 && pin.worker >= 0)) {
            require(pin.worker >= 0 && cleanup.stage != NULL, "worker-cleanup-identity-retained");
            if (!strcmp(mode, "worker-deadline")) require(deferred_waits == 1 && cleanup.error == ETIMEDOUT,
                "cleanup-does-not-renew-expired-transaction");
            require(kiosk_pin_acquire(&pin, fds[0], fds[1], source_path, &source_namespace, entries, 5, &failure, &cleanup) != 0,
                "unreaped-worker-refuses-reuse");
            probe_mode = "recovery";
            transaction_elapsed = 0;
            require(kiosk_pin_release(&pin, 0, &cleanup) == 0 && pin.worker == -1, "worker-cleanup-owned-retry");
        } else require(pin.worker == -1 && cleanup.stage == NULL, "clone-worker-cleaned");
        close(fds[0]); close(fds[1]); close(fds[2]); int status;
        require(waitpid(owner, &status, WNOHANG) == 0, "source-owner-not-signalled");
        require(write(sockets[0], "x", 1) == 1, "source-owner-release"); close(sockets[0]);
        require(waitpid(owner, &status, 0) == owner && WIFEXITED(status) && WEXITSTATUS(status) == 0, "source-owner-reaped");
        require(waitpid(-1, &status, WNOHANG | __WALL) == -1 && errno == ECHILD, "clone-worker-reaped");
        require(descriptors() == baseline, "crossnamespace-failure-fd-balance"); printf("%s:refused\n", mode); return 0;
    }
    if (strcmp(mode, "wrong-root") == 0 || strcmp(mode, "wrong-owner") == 0 ||
        strcmp(mode, "placeholder") == 0 || strcmp(mode, "extra-mount") == 0 ||
        strcmp(mode, "unsafe-source") == 0 || strcmp(mode, "clone-error") == 0) {
        require(acquired != 0 && pin.fd == -1 && failure.stage != NULL, "source-refused");
        close(fds[0]); close(fds[1]); close(fds[2]); printf("%s:refused\n", mode); return 0;
    }
    if (acquired != 0) fprintf(stderr, "native-cause:%s:%s:%d\n", failure.stage, failure.reason, failure.error);
    require(acquired == 0 && (fcntl(pin.fd, F_GETFD) & FD_CLOEXEC), "pin-acquired");
    close(fds[0]); close(fds[1]); close(fds[2]);
    if (owner > 0) {
        require(write(sockets[0], "x", 1) == 1, "owner-release"); close(sockets[0]); int status;
        require(waitpid(owner, &status, 0) == owner && WIFEXITED(status) && WEXITSTATUS(status) == 0, "owner-reaped");
        require(unlink("vendor") == 0 && rename("ambient", "retired") == 0, "host-unlink-rename");
        put("vendor", "replacement-vendor"); require(mkdir("ambient", 0755) == 0, "host-directory-replacement");
        put("ambient/leaf", "replacement-data"); put("host-script", "replacement-script");
        content(pin.fd, "bin/copy", "original-copy"); content(pin.fd, "bin/vendor", "original-vendor"); content(pin.fd, "data/leaf", "original-data");
        struct stat vendor; require(fstatat(pin.fd, "bin/vendor", &vendor, 0) == 0 &&
            vendor.st_ino == entries[3].inode && vendor.st_nlink == 0, "original-unlinked-vendor-inode");
    }
    int parent = open(".", O_PATH | O_DIRECTORY | O_CLOEXEC); require(parent >= 0, "target-parent");
    struct kiosk_pin_target ticket = target_for(parent, "attached");
    if (strcmp(mode, "target-replaced") == 0) {
        require(rename("attached", "old-target") == 0 && mkdir("attached", 0755) == 0, "target-replace");
        require(kiosk_pin_attach(&pin, parent, "attached", &ticket, entries, 5, &failure) != 0 && !pin.attached, "target-refused");
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "unattached-release"); close(parent); puts("target-replaced:refused"); return 0;
    }
    if (strncmp(mode, "attach-deadline-", 16) == 0 && strcmp(mode, "attach-deadline-topology")) {
        if (!strcmp(mode, "attach-deadline-expired")) transaction_elapsed = 1;
        if (!strcmp(mode, "attach-deadline-coverage")) expire_at = transaction_clock_calls + 4;
        require(kiosk_pin_attach_until(&pin, parent, "attached", &ticket, entries, 5,
            transaction_deadline, &failure) != 0 && !pin.verified && !pin.complete && failure.stage != NULL,
            "original-attachment-deadline-refused");
        require(move_calls == (!strcmp(mode, "attach-deadline-after-move") ? 1U : 0U),
            "attachment-mutation-boundary");
        require(pin.attached == (!strcmp(mode, "attach-deadline-after-move") ? 1 : 0), "attachment-owned-state");
        content(pin.fd, "bin/vendor", "original-vendor");
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "attachment-deadline-owned-release"); close(parent);
        require(access("publication/ready", F_OK) != 0 && descriptors() == baseline, "attachment-deadline-no-publication");
        printf("%s:verified\n", mode); return 0;
    }
    int attached_result = !strcmp(mode, "transaction-complete") ?
        kiosk_pin_attach_until(&pin, parent, "attached", &ticket, entries, 5, transaction_deadline, &failure) :
        kiosk_pin_attach(&pin, parent, "attached", &ticket, entries, 5, &failure);
    if (strcmp(mode, "attach-error") == 0 || strcmp(mode, "readonly-error") == 0) {
        require(attached_result != 0 && failure.stage != NULL && !pin.complete, "attachment-failure");
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "attachment-failure-cleanup"); close(parent);
        require(descriptors() == baseline, "attachment-failure-fd-balance"); printf("%s:verified\n", mode); return 0;
    }
    require(attached_result == 0, "pin-attached");
    if (!strcmp(mode, "attach-deadline-topology")) {
        int attached = open("attached", O_PATH | O_DIRECTORY | O_CLOEXEC);
        require(attached >= 0, "deadline-attached-witness");
        expire_at = transaction_clock_calls + 3;
        require(kiosk_pin_attached_topology_until(attached, entries, 5, transaction_deadline, &failure) != 0 &&
            transaction_clock_calls == expire_at && move_calls == 1, "attached-topology-original-deadline");
        close(attached);
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "topology-deadline-owned-release"); close(parent);
        require(descriptors() == baseline, "topology-deadline-fd-balance"); printf("%s:verified\n", mode); return 0;
    }
    if (strcmp(mode, "lifetime") == 0) {
        /* The source owner's namespace is gone; this new attachment owns the
         * original recursive sources even after the clone descriptor closes. */
        close(pin.fd); pin.fd = -1;
        int attached = open("attached", O_PATH | O_DIRECTORY | O_CLOEXEC); require(attached >= 0, "lifetime-attachment");
        content(attached, "bin/copy", "original-copy"); content(attached, "bin/vendor", "original-vendor"); content(attached, "data/leaf", "original-data");
        int writefd = open("attached/bin/copy", O_WRONLY | O_CLOEXEC); require(writefd < 0 && errno == EROFS, "attachment-readonly");
        close(attached); require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "lifetime-owned-detach"); close(parent);
        puts("lifetime:verified"); return 0;
    }
    struct kiosk_owned_mount stages[3]; const char *relative_stages[] = {"stage", "stage/bin/vendor", "stage/data"};
    for (unsigned i = 0; i < 3; i++) {
        char path[PATH_MAX]; require(snprintf(path, sizeof(path), "%s/%s", argv[2], relative_stages[i]) < PATH_MAX, "stage-path");
        stages[i].path = strdup(path); stages[i].live = 1;
        require(stages[i].path != NULL && kiosk_mount_id(path, &stages[i].id) == 0, "stage-record");
    }
    if (strncmp(mode, "finish-deadline-", 16) == 0) {
        if (!strcmp(mode, "finish-deadline-expired")) transaction_elapsed = 1;
        if (!strcmp(mode, "finish-deadline-staging")) expire_at = transaction_clock_calls + 10;
        require(kiosk_pin_finish_until(&pin, stages, 3, entries, 5, transaction_deadline, &failure) != 0 &&
            !pin.complete && failure.stage != NULL, "original-completion-deadline-refused");
        require(stage_detaches == (!strcmp(mode, "finish-deadline-after-detach") ? 1U : 0U),
            "completion-mutation-boundary");
        require(stages[0].live && stages[1].live &&
            stages[2].live == (!strcmp(mode, "finish-deadline-after-detach") ? 0 : 1), "exact-staging-ownership");
        content(pin.fd, "bin/vendor", "original-vendor");
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0 && access("publication/ready", F_OK) != 0,
            "completion-deadline-owned-release");
    } else if (strcmp(mode, "incomplete") == 0 || strcmp(mode, "false-detach") == 0 || strcmp(mode, "foreign-stage") == 0) {
        if (strcmp(mode, "false-detach") == 0 || strcmp(mode, "foreign-stage") == 0) {
            if (strcmp(mode, "foreign-stage") == 0)
                require(mount("tmpfs", "stage", "tmpfs", 0, "size=1m") == 0, "foreign-staging-alias");
            for (unsigned i = 0; i < 3; i++) stages[i].live = 0;
            require(kiosk_pin_finish(&pin, stages, 3, entries, 5, &failure) != 0 && !pin.complete, "false-detach-refused");
        }
        struct kiosk_pin_target publication = target_for(parent, "publication");
        require(kiosk_pin_publish(&pin, parent, "publication", &publication, digest, entries, 5, 0, &failure, &cleanup) != 0,
            "incomplete-publication-refused");
        require(access("publication/ready", F_OK) != 0 && kiosk_pin_release(&pin, 1, &cleanup) != 0, "incomplete-not-retained");
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "incomplete-owned-detach");
    } else if (strcmp(mode, "detach-error") == 0 || strcmp(mode, "cleanup-error") == 0) {
        require(kiosk_pin_finish(&pin, stages, 3, entries, 5, &failure) != 0 && !pin.complete && failure.stage != NULL,
            "staging-failure-denied");
        if (strcmp(mode, "cleanup-error") == 0)
            require(kiosk_pin_release(&pin, 0, &cleanup) != 0 && cleanup.stage != NULL, "separate-cleanup-failure");
        probe_mode = "recovery";
        require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "staging-failure-owned-cleanup");
        require(access("publication/ready", F_OK) != 0, "staging-failure-no-ready");
    } else if (strcmp(mode, "cleanup-replaced") == 0) {
        require(mount("tmpfs", "attached", "tmpfs", 0, "size=1m") == 0, "foreign-overmount");
        unsigned long long foreign; require(kiosk_mount_id("attached", &foreign) == 0 && foreign != pin.attached_id, "foreign-id");
        require(kiosk_pin_release(&pin, 0, &cleanup) != 0 && pin.parent >= 0 && cleanup.stage != NULL, "foreign-detach-refused");
        unsigned long long after; require(kiosk_mount_id("attached", &after) == 0 && after == foreign, "foreign-survives");
        require(umount2("attached", MNT_DETACH) == 0 && kiosk_pin_release(&pin, 0, &cleanup) == 0, "owned-cleanup-retry");
    } else {
        require((!strcmp(mode, "transaction-complete") ?
            kiosk_pin_finish_until(&pin, stages, 3, entries, 5, transaction_deadline, &failure) :
            kiosk_pin_finish(&pin, stages, 3, entries, 5, &failure)) == 0 && pin.complete, "native-completion");
        struct kiosk_pin_target publication = target_for(parent, "publication");
        if (strncmp(mode, "publish-deadline-", 17) == 0) {
            if (!strcmp(mode, "publish-deadline-expired")) transaction_elapsed = 1;
            if (!strcmp(mode, "publish-deadline-coverage")) expire_at = transaction_clock_calls + 4;
            require(kiosk_pin_publish_until(&pin, parent, "publication", &publication, digest, entries, 5, 0,
                transaction_deadline, &failure, &cleanup) != 0 && !pin.published && failure.stage != NULL,
                "original-publication-deadline-refused");
            int after_ready = !strcmp(mode, "publish-deadline-after-ready");
            require(ready_renames == (unsigned) after_ready && (access("publication/ready", F_OK) == 0) == after_ready &&
                access("publication/ready.pending", F_OK) != 0 && cleanup.stage == NULL,
                "exact-expired-publication-boundary");
            content(pin.fd, "bin/vendor", "original-vendor");
        } else if (strcmp(mode, "publish-cleanup-error") == 0) {
            require(kiosk_pin_publish(&pin, parent, "publication", &publication, digest, entries, 5, 0, &failure, &cleanup) != 0 &&
                !pin.published && failure.stage != NULL && cleanup.stage != NULL, "separate-publication-cleanup-error");
            require(access("publication/ready", F_OK) != 0 && access("publication/ready.pending", F_OK) == 0,
                "failed-cleanup-remains-incomplete");
        } else if (strcmp(mode, "write-error") == 0 || strcmp(mode, "fsync-error") == 0 || strcmp(mode, "rename-error") == 0 ||
            strcmp(mode, "label-error") == 0) {
            require(kiosk_pin_publish(&pin, parent, "publication", &publication, digest, entries, 5,
                strcmp(mode, "label-error") == 0, &failure, &cleanup) != 0 && !pin.published,
                "publication-error-denied");
            require(access("publication/ready", F_OK) != 0 && access("publication/ready.pending", F_OK) != 0,
                "publication-error-cleaned");
        } else if (strcmp(mode, "interrupted-publication") == 0) {
            put("publication/ready.pending", "interrupted-native-attempt");
            require(chmod("publication/ready.pending", 0600) == 0, "pending-mode");
            require(kiosk_pin_publish(&pin, parent, "publication", &publication, digest, entries, 5, 0, &failure, &cleanup) != 0 &&
                !pin.published && access("publication/ready", F_OK) != 0, "pending-not-adopted");
        } else if (strcmp(mode, "publication-replaced") == 0) {
            require(rename("publication", "old-publication") == 0 && mkdir("publication", 0700) == 0, "publication-replace");
            require(kiosk_pin_publish(&pin, parent, "publication", &publication, digest, entries, 5, 0, &failure, &cleanup) != 0 && !pin.published,
                "publication-identity-refused");
        } else {
            require((!strcmp(mode, "transaction-complete") ?
                kiosk_pin_publish_until(&pin, parent, "publication", &publication, digest, entries, 5, 0,
                    transaction_deadline, &failure, &cleanup) :
                kiosk_pin_publish(&pin, parent, "publication", &publication, digest, entries, 5, 0, &failure, &cleanup)) == 0 && pin.published,
                "native-ready-publication");
            struct stat ready; require(lstat("publication/ready", &ready) == 0 && ready.st_nlink == 1 &&
                (ready.st_mode & 07777) == 0600 && ready.st_uid == 0, "native-ready-identity");
            require(access("publication/ready.pending", F_OK) != 0, "atomic-pending-absent");
            require(kiosk_pin_release(&pin, 1, &cleanup) == 0, "close-setup-descriptors");
            int attached = open("attached", O_PATH | O_DIRECTORY | O_CLOEXEC); require(attached >= 0, "completed-attachment");
            content(attached, "bin/copy", "original-copy"); close(attached);
            require(umount2("attached", MNT_DETACH) == 0, "completed-owned-detach");
        }
        if (pin.fd >= 0) require(kiosk_pin_release(&pin, 0, &cleanup) == 0, "publication-failure-detach");
    }
    for (unsigned i = 0; i < 3; i++) free(stages[i].path);
    close(parent); require(descriptors() == baseline, "native-fd-balance"); printf("%s:verified\n", mode);
    return 0;
}
''')
    result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', str(source), '-o', str(binary)],
                            capture_output=True, text=True, timeout=30,
                            pass_fds=test_storage.scratch_descriptors())
    if result.returncode != 0:
        pytest.fail(result.stderr, pytrace=False)
    return binary


def test_private_mount_capability(native_pin, tmp_path):
    result = subprocess.run([str(native_pin), 'capability', str(tmp_path)],
                            capture_output=True, text=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'private-mount-capability:verified\n'


@pytest.mark.parametrize('mode', [
    'lifetime', 'complete', 'incomplete', 'false-detach', 'cleanup-replaced',
    'interrupted-publication', 'publication-replaced',
    'attach-error', 'readonly-error', 'detach-error', 'cleanup-error', 'write-error', 'fsync-error', 'rename-error', 'label-error',
    'publish-cleanup-error',
    'foreign-stage',
])
def test_native_pin_mounted_lifetime_and_publication(native_pin, tmp_path, mode):
    result = subprocess.run([str(native_pin), mode, str(tmp_path)],
                            capture_output=True, text=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    assert result.stdout == f'{mode}:verified\n'


@pytest.mark.parametrize('mode', [
    'transaction-complete', 'attach-deadline-expired', 'attach-deadline-coverage',
    'attach-deadline-after-move', 'attach-deadline-topology',
    'finish-deadline-expired', 'finish-deadline-staging', 'finish-deadline-after-detach',
    'publish-deadline-expired', 'publish-deadline-coverage', 'publish-deadline-after-write',
    'publish-deadline-before-rename', 'publish-deadline-after-ready',
])
def test_native_pin_attachment_completion_publication_share_original_deadline(native_pin, tmp_path, mode):
    result = subprocess.run([str(native_pin), mode, str(tmp_path)],
                            capture_output=True, text=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    assert result.stdout == f'{mode}:verified\n'


@pytest.mark.parametrize('mode', [
    'wrong-root', 'wrong-owner', 'placeholder', 'extra-mount', 'missing-recursive', 'target-replaced', 'unsafe-source', 'clone-error',
    'worker-error', 'worker-timeout', 'worker-malformed', 'wrong-namespace', 'worker-cleanup-error',
    'worker-deadline', 'deadline-before-clone', 'deadline-after-clone', 'deadline-coverage-walk', 'deadline-topology-walk',
])
def test_native_pin_refuses_wrong_source_and_coverage(native_pin, tmp_path, mode):
    result = subprocess.run([str(native_pin), mode, str(tmp_path)],
                            capture_output=True, text=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    assert result.stdout == f'{mode}:refused\n'


@pytest.mark.parametrize(('mode', 'status', 'ready'), [('before-ready-cut', 73, False), ('after-ready-cut', 74, True)])
def test_native_pin_crash_at_atomic_ready_boundary(native_pin, tmp_path, mode, status, ready):
    result = subprocess.run([str(native_pin), mode, str(tmp_path)], capture_output=True, text=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == status, result.stderr
    assert (tmp_path / 'publication/ready').exists() is ready
    assert (tmp_path / 'publication/ready.pending').exists() is (not ready)
    record = (tmp_path / 'publication' / ('ready' if ready else 'ready.pending')).read_text()
    assert record.startswith('ONPC-PIN-READY 1\nreceipt 0123456789abcdef')


@pytest.mark.parametrize('mode', [
    'provenance-ambient-directory', 'provenance-ambient-file', 'provenance-required',
    'provenance-root', 'provenance-ancestor', 'provenance-unknown', 'provenance-foreign',
])
def test_retained_provenance_separates_clone_identity_from_ambient_bind_trust(native_pin, tmp_path, mode):
    result = subprocess.run([str(native_pin), mode, str(tmp_path)], capture_output=True, text=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    assert result.stdout == f'{mode}:verified\n'
