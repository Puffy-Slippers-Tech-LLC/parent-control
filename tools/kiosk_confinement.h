/* Called in the PAM executor, never in its preparation subprocess. */
#include <dlfcn.h>
#include <limits.h>
#include <sched.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <dirent.h>
#include <stdint.h>
#include <sys/statfs.h>
#include <sys/statvfs.h>
#include <sys/xattr.h>
#include "kiosk_private_creation.h"

#ifndef KIOSK_CONFINEMENT_PREPARE
#define KIOSK_CONFINEMENT_PREPARE "/usr/libexec/oh-no-parent-control-kiosk-confinement"
#endif
#define KIOSK_CONFINEMENT_LOCK "/run/oh-no-parent-control-confinement.lock"
#define KIOSK_CONFINEMENT_RUNTIME "/run/oh-no-parent-control-confinement"
#define KIOSK_CONFINEMENT_VIEW KIOSK_CONFINEMENT_RUNTIME "/native-view"
#define KIOSK_CONFINEMENT_BINDINGS KIOSK_CONFINEMENT_VIEW "/bindings"
#define KIOSK_VIEW_ROWS 32768U
#define KIOSK_VIEW_BYTES (64U * 1024U * 1024U)
#ifndef KIOSK_ADMISSION_LOCK
#define KIOSK_ADMISSION_LOCK "/run/oh-no-parent-control-kiosk-admission.lock"
#endif
#ifndef KIOSK_ADMISSION_DISABLED
#define KIOSK_ADMISSION_DISABLED "/var/lib/oh-no-parent-control/kiosk-confinement-removing"
#endif
#ifndef KIOSK_ADMISSION_LOCK_OWNER
#define KIOSK_ADMISSION_LOCK_OWNER 0
#endif
#define KIOSK_ADMISSION_DATA "oh-no-parent-control.kiosk-admission"

/* Locking an unlinked/replaced inode does not serialize the named lifecycle
 * boundary. Check the exact private named object after locking and again at
 * the admission decision; never repair or unlink a substituted lock. */
static int
kiosk_lock_identity(int fd, const char *path, uid_t owner)
{
    struct stat opened, named;
    return fd >= 0 && fstat(fd, &opened) == 0 && lstat(path, &named) == 0 &&
        S_ISREG(opened.st_mode) && S_ISREG(named.st_mode) &&
        opened.st_uid == owner && named.st_uid == owner &&
        (opened.st_mode & 07777) == 0600 && (named.st_mode & 07777) == 0600 &&
        opened.st_nlink == 1 && named.st_nlink == 1 &&
        opened.st_dev == named.st_dev && opened.st_ino == named.st_ino ? 0 : -1;
}

static int
kiosk_admission_current(int fd)
{
    struct stat barrier;
    return kiosk_lock_identity(fd, KIOSK_ADMISSION_LOCK, KIOSK_ADMISSION_LOCK_OWNER) == 0 &&
        lstat(KIOSK_ADMISSION_DISABLED, &barrier) != 0 && errno == ENOENT ? 0 : -1;
}

static void
release_kiosk_admission(pam_handle_t *pamh, void *data, int status)
{
    int *fd = data;
    (void) pamh;
    (void) status;
    close(*fd);
    free(fd);
}

/* A lease spans the entire PAM handle, including the trusted root worker's
 * interval between returning from open_session and setting UID/exec. Forked
 * PAM lifecycle children inherit the same open-file description. Never unlink
 * this inode: removal takes its exclusive lock before scanning processes. */
static int
kiosk_admission(pam_handle_t *pamh, const char *username)
{
    const void *existing = NULL;
    struct stat info, path_info;
    int *fd, result;
    if (strcmp(username, KIOSK_ACCOUNT_NAME) != 0)
        return PAM_SUCCESS;
    result = pam_get_data(pamh, KIOSK_ADMISSION_DATA, &existing);
    if (result == PAM_SUCCESS && existing != NULL) {
        if (kiosk_admission_current(*(const int *) existing) == 0)
            return PAM_SUCCESS;
        pam_syslog(pamh, LOG_ERR,
                   "onpc.pam kiosk admission outcome=denied stage=removal-barrier");
        return PAM_PERM_DENIED;
    }
    if (result != PAM_NO_MODULE_DATA && result != PAM_SUCCESS)
        return result;
    fd = malloc(sizeof(*fd));
    if (fd == NULL)
        return PAM_BUF_ERR;
    *fd = kiosk_private_lock_open(KIOSK_ADMISSION_LOCK, KIOSK_ADMISSION_LOCK_OWNER, O_NONBLOCK);
    if (*fd < 0 || fstat(*fd, &info) != 0 || !S_ISREG(info.st_mode) ||
        info.st_uid != KIOSK_ADMISSION_LOCK_OWNER || (info.st_mode & 07777) != 0600 ||
        info.st_nlink != 1 || flock(*fd, LOCK_SH | LOCK_NB) != 0 ||
        lstat(KIOSK_ADMISSION_LOCK, &path_info) != 0 ||
        path_info.st_dev != info.st_dev || path_info.st_ino != info.st_ino ||
        lstat(KIOSK_ADMISSION_DISABLED, &path_info) == 0 || errno != ENOENT) {
        if (*fd >= 0)
            close(*fd);
        free(fd);
        pam_syslog(pamh, LOG_ERR,
                   "onpc.pam kiosk admission outcome=denied stage=removal-barrier");
        return PAM_PERM_DENIED;
    }
    result = pam_set_data(pamh, KIOSK_ADMISSION_DATA, fd, release_kiosk_admission);
    if (result != PAM_SUCCESS)
        release_kiosk_admission(pamh, fd, result);
    return result;
}

static int
kiosk_admission_fd(pam_handle_t *pamh)
{
    const void *data = NULL;
    return pam_get_data(pamh, KIOSK_ADMISSION_DATA, &data) == PAM_SUCCESS && data != NULL
        ? *(const int *) data : -1;
}

static inline int
prepare_kiosk_confinement(const char *role, int lock_fd, int admission_fd)
{
    char *const args[] = {(char *) KIOSK_CONFINEMENT_PREPARE, (char *) role, NULL};
    char *const env[] = {(char *) "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                        (char *) "LC_ALL=C", NULL};
    struct timespec start, now, pause = {0, 10000000};
    pid_t child, waited;
    int status;
    if (clock_gettime(CLOCK_MONOTONIC, &start) != 0)
        return -1;
    child = fork();
    if (child == 0) {
        if (fcntl(lock_fd, F_DUPFD, STDERR_FILENO + 1) < 0 ||
            fcntl(admission_fd, F_DUPFD, STDERR_FILENO + 1) < 0)
            _exit(127);
        execve(KIOSK_CONFINEMENT_PREPARE, args, env);
        _exit(127);
    }
    if (child < 0)
        return -1;
    for (;;) {
        waited = waitpid(child, &status, WNOHANG);
        if (waited == child)
            return WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
        if (waited < 0 && errno != EINTR)
            return -1;
        if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 || now.tv_sec - start.tv_sec >= 60) {
            kill(child, SIGKILL);
            do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
            return -1;
        }
        nanosleep(&pause, NULL);
    }
}

/* The namespace, filesystem and every mount below it belong to this one PAM
 * invocation. A pathname is never sufficient authority to detach a mount. */
struct kiosk_owned_mount {
    char *path;
    unsigned long long id;
    int live;
};

/* Closed, invocation-local diagnostics. A validation failure has no syscall
 * errno; only an immediately observed failed syscall supplies one. */
struct kiosk_failure {
    const char *stage, *reason;
    int error;
};

struct kiosk_view {
    int root, selinux, mounted, cloned;
    dev_t namespace_device;
    ino_t namespace_inode;
    unsigned long long root_id, clone_id;
    struct kiosk_owned_mount *mounts;
    unsigned count;
    struct kiosk_failure failure, cleanup_failure;
};

static void
kiosk_failure(struct kiosk_failure *failure, const char *stage, const char *reason, int error)
{
    if (failure->stage == NULL) {
        failure->stage = stage;
        failure->reason = reason;
        failure->error = error > 0 && error <= 4095 ? error : -1;
    }
}

/* The boolean argument must describe just the preceding syscall, never a
 * compound syscall/metadata comparison. Success does not inspect errno. */
static int
kiosk_os_failure(struct kiosk_failure *failure, const char *stage, const char *reason, int failed)
{
    if (failed)
        kiosk_failure(failure, stage, reason, errno);
    return failed;
}

static void
kiosk_native_diagnostic(pam_handle_t *pamh, const struct kiosk_view *view, const char *role)
{
    int saved_errno = errno;
    const struct kiosk_failure *failures[] = {&view->failure, &view->cleanup_failure};
    for (unsigned i = 0; i < 2; i++)
        if (failures[i]->stage != NULL)
            pam_syslog(pamh, LOG_ERR,
                       "onpc.pam kiosk native-view outcome=%s role=%s stage=%s reason=%s errno=%d",
                       i == 0 ? "denied" : "cleanup-failed", role,
                       failures[i]->stage, failures[i]->reason, failures[i]->error);
    errno = saved_errno;
}

struct kiosk_record {
    char *storage, *key, *v[6];
};

struct kiosk_protocol {
    struct kiosk_record *roots, *nodes, *proofs, *binds;
    unsigned nr, nn, np, nb;
    char generation[PATH_MAX], backend[16], role[16], resolved[PATH_MAX];
};

static int
kiosk_mount_id(const char *path, unsigned long long *id)
{
    struct statx info;
    if (statx(AT_FDCWD, path, AT_SYMLINK_NOFOLLOW, STATX_MNT_ID, &info) != 0 ||
        !(info.stx_mask & STATX_MNT_ID))
        return -1;
    *id = info.stx_mnt_id;
    return 0;
}

static int
kiosk_trusted_stat(const struct stat *info, int kind)
{
    return info->st_uid == 0 && (S_ISLNK(info->st_mode) || !(info->st_mode & 022)) &&
        (kind == 0 || (info->st_mode & S_IFMT) == (mode_t) kind);
}

/* Canonical protocol paths never contain empty, dot or dot-dot components.
 * Symlink text is a distinct field and is normalized only by proof walking. */
static int
kiosk_path(const char *path, int absolute)
{
    const char *part = path;
    size_t length = strlen(path);
    if (!length || length >= PATH_MAX || (absolute ? path[0] != '/' : path[0] == '/'))
        return 0;
    if (absolute && strcmp(path, "/") == 0)
        return 1;
    if (absolute)
        part++;
    while (*part) {
        const char *end = strchr(part, '/');
        size_t n = end == NULL ? strlen(part) : (size_t) (end - part);
        if (!n || (n == 1 && part[0] == '.') ||
            (n == 2 && part[0] == '.' && part[1] == '.'))
            return 0;
        for (size_t i = 0; i < n; i++)
            if ((unsigned char) part[i] < 32 || part[i] == 127)
                return 0;
        if (end == NULL)
            return 1;
        part = end + 1;
    }
    return 0;
}

static int
kiosk_below(const char *path, const char *root)
{
    size_t n = strlen(root);
    return strncmp(path, root, n) == 0 && path[n] == '/' && path[n + 1] != '\0';
}

static int
kiosk_label(int fd, const char *path, int link, int selinux)
{
    char label[128], descriptor[64];
    ssize_t n;
    if (!selinux)
        return 0;
    if (link)
        n = lgetxattr(path, "security.selinux", label, sizeof(label));
    else {
        snprintf(descriptor, sizeof(descriptor), "/proc/self/fd/%d", fd);
        n = getxattr(descriptor, "security.selinux", label, sizeof(label));
    }
    return n == (ssize_t) sizeof("system_u:object_r:onpc_kiosk_runtime_t:s0") &&
        memcmp(label, "system_u:object_r:onpc_kiosk_runtime_t:s0", (size_t) n) == 0 ? 0 : -1;
}

/* Open parents separately. Only the final component may later be classified as
 * an ambient omission; failures here are always admission failures. */
static int
kiosk_parent(int root, const char *relative, char name[PATH_MAX])
{
    char buffer[PATH_MAX], *part, *next;
    struct stat info;
    int current, child;
    if (!kiosk_path(relative, 0) || (current = fcntl(root, F_DUPFD_CLOEXEC, STDERR_FILENO + 1)) < 0)
        return -1;
    strcpy(buffer, relative);
    part = buffer;
    while ((next = strchr(part, '/')) != NULL) {
        *next++ = '\0';
        child = openat(current, part, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (child < 0 || fstat(child, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR)) {
            if (child >= 0)
                close(child);
            close(current);
            return -1;
        }
        close(current);
        current = child;
        part = next;
    }
    strcpy(name, part);
    return current;
}

static int
kiosk_absolute_parent(const char *path, char name[PATH_MAX])
{
    struct stat info;
    int root, parent;
    if (!kiosk_path(path, 1) || strcmp(path, "/") == 0)
        return -1;
    root = open("/", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (root < 0 || fstat(root, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR)) {
        if (root >= 0)
            close(root);
        return -1;
    }
    parent = kiosk_parent(root, path + 1, name);
    close(root);
    return parent;
}

#include <sys/statvfs.h>
#include <sys/socket.h>
#include <sys/prctl.h>
#include <poll.h>
#include <linux/sched.h>
#include <sys/syscall.h>
#include <time.h>

/* Retained-source primitives. The production coordinator supplies independently
 * checked manager, receipt and final-proof authority, including every
 * skeleton ancestor and mounted source; these records never authorize a host
 * pathname or establish manager liveness. Inode/type/mount coverage here is
 * additional to the role-specific content, capability and label checks. */
struct kiosk_pin_entry {
    const char *relative;
    dev_t device;
    ino_t inode;
    mode_t mode;
    uid_t uid;
    gid_t gid;
    unsigned parent, mountpoint;
};

struct kiosk_source_pin {
    /* Initialize all three descriptor fields to -1. A refused worker cleanup
     * retains its pidfd here until release proves reaping; no scratch recovery
     * or publication is permitted while that owned child remains unresolved. */
    int fd, parent, worker;
    char name[PATH_MAX];
    dev_t namespace_device;
    ino_t namespace_inode;
    unsigned long long attached_id;
    int attached, verified, complete, published;
};

struct kiosk_pin_target {
    dev_t parent_device, device;
    ino_t parent_inode, inode;
    unsigned long long parent_mount, mount;
};

struct kiosk_pin_namespace {
    int fd;
    dev_t device;
    ino_t inode;
};

#ifndef KIOSK_PIN_CLOCK_GETTIME
#define KIOSK_PIN_CLOCK_GETTIME clock_gettime
#endif

static int
kiosk_pin_now(uint64_t *now)
{
    struct timespec value;
    if (KIOSK_PIN_CLOCK_GETTIME(CLOCK_MONOTONIC, &value) != 0 || value.tv_sec < 0 ||
        (uint64_t) value.tv_sec > (UINT64_MAX - 999999U) / 1000000U)
        return -1;
    *now = (uint64_t) value.tv_sec * 1000000U + (uint64_t) value.tv_nsec / 1000U;
    return 0;
}

static int
kiosk_pin_before(uint64_t deadline)
{
    uint64_t now;
    return deadline && kiosk_pin_now(&now) == 0 && now < deadline ? 0 : -1;
}

static int
kiosk_pin_reap_worker_until(int pidfd, uint64_t deadline, struct kiosk_failure *failure)
{
    if (syscall(SYS_pidfd_send_signal, pidfd, SIGKILL, NULL, 0) != 0 && errno != ESRCH) {
        kiosk_failure(failure, "pin", "clone-cleanup", errno);
        return -1;
    }
    for (;;) {
        siginfo_t observed = {0};
        int waited = waitid(P_PIDFD, (id_t) pidfd, &observed, WEXITED | WNOHANG | __WCLONE);
        if ((waited == 0 && observed.si_pid != 0) || (waited < 0 && errno == ECHILD)) return 0;
        if (waited < 0 && errno != EINTR) { kiosk_failure(failure, "pin", "clone-cleanup", errno); return -1; }
        if (kiosk_pin_before(deadline) != 0) {
            kiosk_failure(failure, "pin", "clone-cleanup", ETIMEDOUT); return -1;
        }
        struct timespec pause = {.tv_nsec = 1000000}; nanosleep(&pause, NULL);
    }
}

/* Explicit standalone recovery may wait for its already-recorded worker.
 * Admission uses _until and retains an unresolved pidfd on deadline expiry;
 * recovery never supplies admission credit or renews the failed transaction. */
static int
kiosk_pin_reap_worker(int pidfd, struct kiosk_failure *failure)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 5000000U) return -1;
    return kiosk_pin_reap_worker_until(pidfd, now + 5000000U, failure);
}

/* An ordinary attached source must belong to open_tree's calling namespace.
 * Use a bounded native child to enter the already-proven source namespace;
 * the PAM caller's namespace/root/cwd never change. The child performs only
 * syscall wrappers and stack operations after fork, including on failure: PAM
 * may be multithreaded, so no allocator, stdio, parser, logger or exec is legal
 * there. Parent owns all source/topology/receipt validation before and after.
 * Existing trusted bootstrap permission is mandatory; setns denial is final.
 */
static int
kiosk_pin_clone_worker(int checked_usr, const struct kiosk_pin_namespace *source, uint64_t transaction_deadline,
                       int *pending_worker, struct kiosk_failure *failure, struct kiosk_failure *cleanup_failure)
{
    struct stat initial, current, source_info;
    struct statfs filesystem;
    uint64_t start, now, deadline;
    int ns = -1, sockets[2] = {-1, -1}, clone = -1, result = -1, received = -1, child_pidfd = -1;
    pid_t child = -1, caller = getpid();
    int reaped = 0;
    if (kiosk_pin_now(&start) != 0 || start > UINT64_MAX - 5000000U ||
        !transaction_deadline || start >= transaction_deadline)
        goto done;
    deadline = start + 5000000U;
    if (transaction_deadline < deadline) deadline = transaction_deadline;
    if (source == NULL || source->fd < 0 || fstat(source->fd, &source_info) != 0 ||
        source_info.st_dev != source->device || source_info.st_ino != source->inode ||
        fstatfs(source->fd, &filesystem) != 0 || filesystem.f_type != 0x6e736673 ||
        (fcntl(source->fd, F_GETFL) & O_PATH) ||
        (ns = open("/proc/self/ns/mnt", O_RDONLY | O_CLOEXEC)) < 0 || fstat(ns, &initial) != 0)
        goto done;
    if (source->device == initial.st_dev && source->inode == initial.st_ino) {
        clone = open_tree(checked_usr, "", OPEN_TREE_CLONE | AT_RECURSIVE | AT_EMPTY_PATH | OPEN_TREE_CLOEXEC);
        if (clone < 0) kiosk_failure(failure, "pin", "clone", errno);
        int current_ns = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
        int unchanged = current_ns >= 0 && fstat(current_ns, &current) == 0 &&
            current.st_dev == initial.st_dev && current.st_ino == initial.st_ino &&
            fstat(source->fd, &source_info) == 0 && source_info.st_dev == source->device && source_info.st_ino == source->inode;
        if (current_ns >= 0) close(current_ns);
        if (!unchanged || kiosk_pin_before(deadline) != 0) goto done;
        result = clone;
        clone = -1;
        goto done;
    }
    if (kiosk_pin_before(deadline) != 0 || socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, sockets) != 0)
        goto done;
    /* Atomically obtain identity before the child can exit or another PAM
     * thread can reap it. No numeric-PID signalling fallback is permitted.
     * A private clone child avoids ordinary SIGCHLD reapers; pidfd identity
     * still protects against an unrelated __WALL reaper. */
    struct clone_args arguments = {.flags = CLONE_PIDFD | CLONE_CLEAR_SIGHAND, .pidfd = (uintptr_t) &child_pidfd};
    child = (pid_t) syscall(SYS_clone3, &arguments, sizeof(arguments));
    if (child == 0) {
        int error = 0, local = -1, observed = -1;
        struct stat info;
        close(sockets[0]);
        if (prctl(PR_SET_PDEATHSIG, SIGKILL) != 0 || getppid() != caller)
            _exit(1);
        if (setns(source->fd, CLONE_NEWNS) != 0) error = errno;
        if (!error) {
            observed = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
            if (observed < 0 || fstat(observed, &info) != 0) error = errno;
            else if (info.st_dev != source->device || info.st_ino != source->inode) error = ESTALE;
            if (observed >= 0) close(observed);
        }
        if (!error) {
            local = open_tree(checked_usr, "", OPEN_TREE_CLONE | AT_RECURSIVE | AT_EMPTY_PATH | OPEN_TREE_CLOEXEC);
            if (local < 0) error = errno;
        }
        char control[CMSG_SPACE(sizeof(local))] = {0};
        struct iovec io = {.iov_base = &error, .iov_len = sizeof(error)};
        struct msghdr message = {.msg_iov = &io, .msg_iovlen = 1};
        if (local >= 0) {
            message.msg_control = control;
            message.msg_controllen = sizeof(control);
            struct cmsghdr *cmsg = CMSG_FIRSTHDR(&message);
            cmsg->cmsg_level = SOL_SOCKET; cmsg->cmsg_type = SCM_RIGHTS;
            cmsg->cmsg_len = CMSG_LEN(sizeof(local));
            /* Avoid libc memcpy after fork: the ancillary payload is one int. */
            *(int *) CMSG_DATA(cmsg) = local;
        }
        ssize_t sent = sendmsg(sockets[1], &message, MSG_NOSIGNAL);
        if (local >= 0) close(local);
        close(sockets[1]);
        _exit(sent == (ssize_t) sizeof(error) ? 0 : 1);
    }
    if (child < 0)
        goto done;
    close(sockets[1]); sockets[1] = -1;
    for (;;) {
        if (kiosk_pin_now(&now) != 0)
            goto done;
        if (now >= deadline) { kiosk_failure(failure, "pin", "clone-timeout", ETIMEDOUT); goto done; }
        struct pollfd channel = {.fd = sockets[0], .events = POLLIN};
        int ready = poll(&channel, 1, (int) ((deadline - now + 999U) / 1000U));
        if (ready < 0 && errno == EINTR) continue;
        if (ready <= 0) { kiosk_failure(failure, "pin", "clone-timeout", ready == 0 ? ETIMEDOUT : errno); goto done; }
        break;
    }
    int error = -1;
    char control[CMSG_SPACE(sizeof(int))] = {0};
    struct iovec io = {.iov_base = &error, .iov_len = sizeof(error)};
    struct msghdr message = {.msg_iov = &io, .msg_iovlen = 1, .msg_control = control, .msg_controllen = sizeof(control)};
    ssize_t bytes = recvmsg(sockets[0], &message, MSG_CMSG_CLOEXEC | MSG_DONTWAIT);
    unsigned descriptors = 0;
    int ancillary_valid = 1;
    for (struct cmsghdr *cmsg = CMSG_FIRSTHDR(&message); cmsg != NULL; cmsg = CMSG_NXTHDR(&message, cmsg)) {
        if (cmsg->cmsg_level != SOL_SOCKET || cmsg->cmsg_type != SCM_RIGHTS || cmsg->cmsg_len < CMSG_LEN(0)) {
            ancillary_valid = 0;
            continue;
        }
        size_t length = cmsg->cmsg_len - CMSG_LEN(0);
        if (length % sizeof(int) != 0) ancillary_valid = 0;
        int *fds = (int *) CMSG_DATA(cmsg);
        for (size_t i = 0; i < length / sizeof(int); i++) {
            descriptors++;
            if (received < 0) received = fds[i];
            else close(fds[i]);
        }
    }
    if (bytes != (ssize_t) sizeof(error) || (message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) || !ancillary_valid ||
        (error == 0 ? descriptors != 1 : descriptors != 0))
        goto done;
    if (error != 0) { kiosk_failure(failure, "pin", "clone-worker", error); goto done; }
    /* Reap this exact private child with the same absolute deadline; never
     * trust a successful message alone or adopt another thread's reaping. */
    siginfo_t exit_info = {0};
    for (;;) {
        int waited = waitid(P_PIDFD, (id_t) child_pidfd, &exit_info, WEXITED | WNOHANG | __WCLONE);
        if (waited == 0 && exit_info.si_pid != 0) { reaped = 1; break; }
        if (waited < 0 && errno != EINTR) { if (errno == ECHILD) reaped = 1; goto done; }
        if (kiosk_pin_before(deadline) != 0)
            goto done;
        struct timespec pause = {.tv_nsec = 1000000}; nanosleep(&pause, NULL);
    }
    if (exit_info.si_code != CLD_EXITED || exit_info.si_status != 0 ||
        fstat(source->fd, &source_info) != 0 || source_info.st_dev != source->device || source_info.st_ino != source->inode)
        goto done;
    int current_ns = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
    int unchanged = current_ns >= 0 && fstat(current_ns, &current) == 0 &&
        current.st_dev == initial.st_dev && current.st_ino == initial.st_ino;
    if (current_ns >= 0) close(current_ns);
    int descriptor_flags = fcntl(received, F_GETFD);
    if (!unchanged || descriptor_flags < 0 || !(descriptor_flags & FD_CLOEXEC) ||
        kiosk_pin_before(deadline) != 0)
        goto done;
    result = received; received = -1;
done:
    if (child > 0 && child_pidfd >= 0 && !reaped) {
        /* Only the atomically acquired child pidfd is signalled. Source
         * manager and reused numeric PIDs are never recovery targets. */
        if (kiosk_pin_reap_worker_until(child_pidfd, deadline, cleanup_failure) != 0) {
            *pending_worker = child_pidfd;
            child_pidfd = -1;
        }
    }
    if (sockets[0] >= 0) close(sockets[0]);
    if (sockets[1] >= 0) close(sockets[1]);
    if (received >= 0) close(received);
    if (clone >= 0) close(clone);
    if (ns >= 0) close(ns);
    if (child_pidfd >= 0) close(child_pidfd);
    if (result < 0) kiosk_failure(failure, "pin", "clone", -1);
    return result;
}

struct kiosk_pin_mount_row {
    unsigned long long id, parent;
    char *path;
    int readonly, within;
};

static int
kiosk_pin_decode_mountpath(char *encoded)
{
    size_t n = strlen(encoded), out = 0;
    for (size_t i = 0; i < n; i++) {
        if (encoded[i] == '\\') {
            if (i + 3 >= n || (strncmp(encoded + i, "\\040", 4) != 0 &&
                strncmp(encoded + i, "\\011", 4) != 0 && strncmp(encoded + i, "\\012", 4) != 0 &&
                strncmp(encoded + i, "\\134", 4) != 0))
                return -1;
            encoded[out++] = (char) ((encoded[i + 1] - '0') * 64 +
                (encoded[i + 2] - '0') * 8 + encoded[i + 3] - '0');
            i += 3;
        } else encoded[out++] = encoded[i];
    }
    encoded[out] = '\0';
    return kiosk_path(encoded, 1) ? 0 : -1;
}

static int
kiosk_pin_mount_compare(const void *a, const void *b)
{
    const struct kiosk_pin_mount_row *left = a, *right = b;
    return left->id < right->id ? -1 : left->id != right->id;
}

/* mountinfo must be opened natively through the checked manager proc object;
 * a helper-generated text file is never topology evidence. Detached trees have
 * no mountinfo pathname: source topology is checked around recursive cloning,
 * and the actual clone topology is checked again upon private attachment. */
static int
kiosk_pin_topology_until(int mountinfo, unsigned long long root, const char *root_path,
                   const struct kiosk_pin_entry *entries, unsigned entry_count,
                   uint64_t deadline, struct kiosk_failure *failure)
{
    struct statfs filesystem;
    struct kiosk_pin_mount_row *rows = NULL;
    FILE *stream = NULL;
    char *line = NULL;
    size_t capacity = 0, bytes = 0;
    unsigned count = 0, expected = 0, observed = 0;
    unsigned *chain = NULL;
    int result = -1, fd = -1;
    if (kiosk_pin_before(deadline) != 0 ||
        !kiosk_path(root_path, 1) || entries == NULL || !entry_count || entry_count > KIOSK_VIEW_ROWS ||
        fstatfs(mountinfo, &filesystem) != 0 || filesystem.f_type != 0x9fa0 ||
        (fd = fcntl(mountinfo, F_DUPFD_CLOEXEC, STDERR_FILENO + 1)) < 0 || lseek(fd, 0, SEEK_SET) != 0 ||
        (stream = fdopen(fd, "r")) == NULL)
        goto done;
    fd = -1;
    rows = calloc(KIOSK_VIEW_ROWS, sizeof(*rows));
    if (rows == NULL)
        goto done;
    ssize_t length;
    while ((length = getline(&line, &capacity, stream)) >= 0) {
        char encoded[PATH_MAX], options[256], tail;
        struct kiosk_pin_mount_row *row;
        if (kiosk_pin_before(deadline) != 0 ||
            count == KIOSK_VIEW_ROWS || length == 0 || length > 3 * PATH_MAX ||
            line[length - 1] != '\n' || (bytes += (size_t) length) > KIOSK_VIEW_BYTES ||
            memchr(line, '\0', (size_t) length) != NULL || strstr(line, " - ") == NULL)
            goto done;
        row = &rows[count];
        if (sscanf(line, "%llu %llu %*s %*s %4095s %255s%c", &row->id, &row->parent,
                   encoded, options, &tail) != 5 || row->id == 0 || row->parent == row->id || tail != ' ')
            goto done;
        if (kiosk_pin_decode_mountpath(encoded) != 0 || (row->path = strdup(encoded)) == NULL)
            goto done;
        row->readonly = strcmp(options, "ro") == 0 || strncmp(options, "ro,", 3) == 0;
        count++;
    }
    if (ferror(stream) || count == 0)
        goto done;
    qsort(rows, count, sizeof(*rows), kiosk_pin_mount_compare);
    for (unsigned i = 1; i < count; i++)
        if (rows[i - 1].id == rows[i].id)
            goto done;
    struct kiosk_pin_mount_row key = {.id = root};
    struct kiosk_pin_mount_row *root_row = bsearch(&key, rows, count, sizeof(*rows), kiosk_pin_mount_compare);
    if (root_row == NULL || strcmp(root_row->path, root_path) != 0 ||
        (chain = calloc(count, sizeof(*chain))) == NULL)
        goto done;
    root_row->within = 1;
    for (unsigned i = 0; i < entry_count; i++)
        expected += entries[i].mountpoint != 0;
    for (unsigned i = 0; i < count; i++) {
        if (kiosk_pin_before(deadline) != 0) goto done;
        struct kiosk_pin_mount_row *row = &rows[i], *ancestor = row;
        unsigned depth = 0;
        while (ancestor != NULL && ancestor->within == 0) {
            if (kiosk_pin_before(deadline) != 0) goto done;
            ancestor->within = 3;
            chain[depth++] = (unsigned) (ancestor - rows);
            key.id = ancestor->parent;
            ancestor = bsearch(&key, rows, count, sizeof(*rows), kiosk_pin_mount_compare);
        }
        if (ancestor != NULL && ancestor->within == 3)
            goto done;
        int within = ancestor == NULL ? 2 : ancestor->within;
        for (unsigned j = 0; j < depth; j++) rows[chain[j]].within = within;
        if (row->within != 1)
            continue;
        if (!row->readonly)
            goto done;
        const char *relative = row->path + strlen(root_path);
        if (row->id == root)
            relative = "";
        else if (!kiosk_below(row->path, root_path))
            goto done;
        else relative++;
        unsigned low = 0, high = entry_count;
        while (low < high) {
            unsigned mid = low + (high - low) / 2;
            if (strcmp(entries[mid].relative, relative) < 0) low = mid + 1;
            else high = mid;
        }
        if (low == entry_count || strcmp(entries[low].relative, relative) != 0 || !entries[low].mountpoint)
            goto done;
        observed++;
    }
    if (observed != expected || kiosk_pin_before(deadline) != 0)
        goto done;
    result = 0;
done:
    if (stream != NULL) fclose(stream);
    if (fd >= 0) close(fd);
    free(line);
    free(chain);
    if (rows != NULL) {
        for (unsigned i = 0; i < count; i++) free(rows[i].path);
        free(rows);
    }
    if (result != 0) kiosk_failure(failure, "pin", "topology", -1);
    return result;
}

static inline int
kiosk_pin_topology(int mountinfo, unsigned long long root, const char *root_path,
                   const struct kiosk_pin_entry *entries, unsigned entry_count,
                   struct kiosk_failure *failure)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 60000000U) return -1;
    return kiosk_pin_topology_until(mountinfo, root, root_path, entries, entry_count,
        now + 60000000U, failure);
}

static int
kiosk_pin_fd_mount(int fd, unsigned long long *id)
{
    struct statx info;
    if (statx(fd, "", AT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW, STATX_MNT_ID, &info) != 0 ||
        !(info.stx_mask & STATX_MNT_ID))
        return -1;
    *id = info.stx_mnt_id;
    return 0;
}

static int
kiosk_pin_attached_topology_until(int root, const struct kiosk_pin_entry *entries, unsigned count,
                                uint64_t deadline, struct kiosk_failure *failure)
{
    char descriptor[64], path[PATH_MAX];
    unsigned long long id;
    if (kiosk_pin_before(deadline) != 0) return -1;
    snprintf(descriptor, sizeof(descriptor), "/proc/self/fd/%d", root);
    ssize_t length = readlink(descriptor, path, sizeof(path) - 1);
    if (length <= 0 || length >= (ssize_t) sizeof(path) - 1 || kiosk_pin_fd_mount(root, &id) != 0)
        return -1;
    path[length] = '\0';
    int mountinfo = open("/proc/self/mountinfo", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    int result = mountinfo < 0 ? -1 : kiosk_pin_topology_until(mountinfo, id, path, entries, count, deadline, failure);
    if (mountinfo >= 0) close(mountinfo);
    return result;
}

static inline int
kiosk_pin_attached_topology(int root, const struct kiosk_pin_entry *entries, unsigned count,
                            struct kiosk_failure *failure)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 60000000U) return -1;
    return kiosk_pin_attached_topology_until(root, entries, count, now + 60000000U, failure);
}

static int
kiosk_pin_same_stat(const struct stat *a, const struct stat *b)
{
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino &&
        a->st_size == b->st_size && a->st_mode == b->st_mode &&
        a->st_uid == b->st_uid && a->st_gid == b->st_gid &&
        a->st_mtim.tv_sec == b->st_mtim.tv_sec && a->st_mtim.tv_nsec == b->st_mtim.tv_nsec &&
        a->st_ctim.tv_sec == b->st_ctim.tv_sec && a->st_ctim.tv_nsec == b->st_ctim.tv_nsec;
}

static int
kiosk_pin_open(int root, const char *relative)
{
    char name[PATH_MAX];
    if (relative[0] == '\0')
        return fcntl(root, F_DUPFD_CLOEXEC, STDERR_FILENO + 1);
    int parent = kiosk_parent(root, relative, name);
    int fd = parent < 0 ? -1 : openat(parent, name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
    if (parent >= 0)
        close(parent);
    return fd;
}

/* A mount boundary is checked independently of inode equality: a bind may
 * contain the same inode as its covered placeholder. Parent closure means a
 * missing recursive submount cannot be mistaken for an ordinary source. Mount
 * IDs are local observations and never receipt/hash inputs. */
static int
kiosk_pin_provenance_open(int root, const char *relative)
{
    char path[PATH_MAX], *part, *next;
    if (relative[0] != '\0' && !kiosk_path(relative, 0))
        return -1;
    int current = fcntl(root, F_DUPFD_CLOEXEC, STDERR_FILENO + 1);
    if (current < 0 || relative[0] == '\0')
        return current;
    strcpy(path, relative);
    for (part = path; part != NULL; part = next) {
        next = strchr(part, '/');
        if (next != NULL) *next++ = '\0';
        int child = openat(current, part, O_PATH | O_NOFOLLOW | O_CLOEXEC |
                           (next != NULL ? O_DIRECTORY : 0));
        close(current);
        if (child < 0) return -1;
        current = child;
    }
    return current;
}

/* A retained source may have become unsafe since V was published. Clone its
 * original inode/topology without granting it bind authority; selection may
 * then omit/mask only explicitly ambient sources in a fresh invocation. The
 * caller derives this vector from the attested required closure, never from a
 * receipt's ambient claim. Required ancestors cannot be relaxed. NULL preserves
 * the original strict primitive used for a newly realized/attached view. */
static int
kiosk_pin_coverage_policy_until(int root, const struct kiosk_pin_entry *entries, unsigned count,
                         const unsigned char *ambient, int readonly, uint64_t deadline,
                         struct kiosk_failure *failure)
{
    unsigned long long *ids = NULL;
    int result = -1;
    if (kiosk_pin_before(deadline) != 0 || entries == NULL || count == 0 || count > KIOSK_VIEW_ROWS ||
        entries[0].relative == NULL || entries[0].relative[0] != '\0' ||
        entries[0].parent != 0 || entries[0].mountpoint != 1 || !S_ISDIR(entries[0].mode) ||
        (ids = calloc(count, sizeof(*ids))) == NULL)
        goto done;
    for (unsigned i = 0; i < count; i++) {
        if (kiosk_pin_before(deadline) != 0) goto done;
        const struct kiosk_pin_entry *entry = &entries[i];
        struct stat info;
        struct statfs filesystem;
        if (entry->relative == NULL || entry->mountpoint > 1 || entry->uid != 0 ||
            (entry->mode & 022) || (!S_ISREG(entry->mode) && !S_ISDIR(entry->mode)))
            goto done;
        if (ambient != NULL && (ambient[i] > 1 || (i == 0 && ambient[i])))
            goto done;
        if (i != 0) {
            if (!kiosk_path(entry->relative, 0) || entry->parent >= i ||
                !S_ISDIR(entries[entry->parent].mode))
                goto done;
            const char *slash = strrchr(entry->relative, '/');
            size_t length = slash == NULL ? 0 : (size_t) (slash - entry->relative);
            const char *parent = entries[entry->parent].relative;
            if (strlen(parent) != length || strncmp(parent, entry->relative, length) != 0)
                goto done;
            if (ambient != NULL && ambient[entry->parent] && !ambient[i])
                goto done;
            if (strcmp(entries[i - 1].relative, entry->relative) >= 0)
                goto done;
        }
        int fd = ambient == NULL ? kiosk_pin_open(root, entry->relative) :
            kiosk_pin_provenance_open(root, entry->relative);
        int valid = fd >= 0 && fstat(fd, &info) == 0 &&
            info.st_dev == entry->device && info.st_ino == entry->inode &&
            (ambient != NULL && ambient[i] ?
             (info.st_mode & S_IFMT) == (entry->mode & S_IFMT) :
             (info.st_mode == entry->mode && info.st_uid == entry->uid && info.st_gid == entry->gid &&
              (!S_ISREG(info.st_mode) || info.st_nlink <= 1))) &&
            kiosk_pin_fd_mount(fd, &ids[i]) == 0 &&
            (!readonly || (fstatfs(fd, &filesystem) == 0 && (filesystem.f_flags & ST_RDONLY)));
        if (fd >= 0)
            close(fd);
        if (!valid || (i != 0 &&
            ((ids[i] != ids[entry->parent]) != (entry->mountpoint != 0))))
            goto done;
    }
    if (kiosk_pin_before(deadline) == 0) result = 0;
done:
    free(ids);
    if (result != 0)
        kiosk_failure(failure, "pin", readonly ? "readonly" : "coverage", -1);
    return result;
}

static int
kiosk_pin_coverage_policy(int root, const struct kiosk_pin_entry *entries, unsigned count,
                         const unsigned char *ambient, int readonly, struct kiosk_failure *failure)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 60000000U) return -1;
    return kiosk_pin_coverage_policy_until(root, entries, count, ambient, readonly,
        now + 60000000U, failure);
}

static inline int
kiosk_pin_coverage(int root, const struct kiosk_pin_entry *entries, unsigned count,
                   int readonly, struct kiosk_failure *failure)
{
    return kiosk_pin_coverage_policy(root, entries, count, NULL, readonly, failure);
}

static inline int
kiosk_pin_acquire_policy_until(struct kiosk_source_pin *pin, int checked_usr, int mountinfo, const char *mount_path,
                         const struct kiosk_pin_namespace *source_namespace,
                         const struct kiosk_pin_entry *entries, unsigned count, const unsigned char *ambient,
                         uint64_t transaction_deadline,
                         struct kiosk_failure *failure, struct kiosk_failure *cleanup_failure)
{
    struct stat before, after;
    unsigned long long source_id, current_id, clone_id;
    int clone = -1;
    if (kiosk_pin_before(transaction_deadline) != 0 ||
        pin->fd != -1 || pin->parent != -1 || pin->worker != -1 || pin->attached || pin->verified || pin->complete ||
        fstat(checked_usr, &before) != 0 || !kiosk_trusted_stat(&before, S_IFDIR) ||
        kiosk_pin_fd_mount(checked_usr, &source_id) != 0 ||
        kiosk_pin_coverage_policy_until(checked_usr, entries, count, ambient, 1, transaction_deadline, failure) != 0 ||
        kiosk_pin_topology_until(mountinfo, source_id, mount_path, entries, count, transaction_deadline, failure) != 0)
        goto denied;
    clone = kiosk_pin_clone_worker(checked_usr, source_namespace, transaction_deadline,
                                    &pin->worker, failure, cleanup_failure);
    if (kiosk_os_failure(failure, "pin", "clone", clone < 0))
        goto denied;
    if (fstat(checked_usr, &after) != 0 || !kiosk_pin_same_stat(&before, &after) ||
        kiosk_pin_fd_mount(checked_usr, &current_id) != 0 || source_id != current_id ||
        kiosk_pin_fd_mount(clone, &clone_id) != 0 || clone_id == source_id ||
        kiosk_pin_coverage_policy_until(clone, entries, count, ambient, 1, transaction_deadline, failure) != 0 ||
        kiosk_pin_coverage_policy_until(checked_usr, entries, count, ambient, 1, transaction_deadline, failure) != 0 ||
        kiosk_pin_topology_until(mountinfo, source_id, mount_path, entries, count, transaction_deadline, failure) != 0 ||
        kiosk_pin_before(transaction_deadline) != 0)
        goto denied;
    pin->fd = clone;
    return 0;
denied:
    if (clone >= 0)
        close(clone); /* An unattached open_tree clone releases all references. */
    kiosk_failure(failure, "pin", "identity", -1);
    return -1;
}

/* Standalone primitive callers keep a finite budget. Composed admission must
 * use _until with the original transaction deadline, never restart this clock
 * after manager acquisition, receipt parsing or preparation. */
static inline int
kiosk_pin_acquire_policy(struct kiosk_source_pin *pin, int checked_usr, int mountinfo, const char *mount_path,
                         const struct kiosk_pin_namespace *source_namespace,
                         const struct kiosk_pin_entry *entries, unsigned count, const unsigned char *ambient,
                         struct kiosk_failure *failure, struct kiosk_failure *cleanup_failure)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 60000000U) {
        kiosk_failure(failure, "pin", "identity", -1);
        return -1;
    }
    return kiosk_pin_acquire_policy_until(pin, checked_usr, mountinfo, mount_path, source_namespace,
        entries, count, ambient, now + 60000000U, failure, cleanup_failure);
}

static inline int
kiosk_pin_acquire(struct kiosk_source_pin *pin, int checked_usr, int mountinfo, const char *mount_path,
                  const struct kiosk_pin_namespace *source_namespace,
                  const struct kiosk_pin_entry *entries, unsigned count,
                  struct kiosk_failure *failure, struct kiosk_failure *cleanup_failure)
{
    return kiosk_pin_acquire_policy(pin, checked_usr, mountinfo, mount_path, source_namespace,
                                    entries, count, NULL, failure, cleanup_failure);
}

/* Only an independently owned fresh invocation target is legal here. Native
 * composition must check that ownership before calling; no source dentry is
 * ever modified. Parent/name are retained for identity-owned failure cleanup.
 * A non-NULL ambient vector permits only a retained-source staging projection
 * whose provenance was independently acquired; it grants no invocation binding
 * or completion authority. Completed views are always validated strictly. */
static inline int
kiosk_pin_attach_policy_until(struct kiosk_source_pin *pin, int owned_parent, const char *name,
                 const struct kiosk_pin_target *expected,
                 const struct kiosk_pin_entry *entries, unsigned count, const unsigned char *ambient,
                 uint64_t deadline,
                 struct kiosk_failure *failure)
{
    struct stat info, parent_info, namespace_info;
    struct mount_attr readonly = {.attr_set = MOUNT_ATTR_RDONLY};
    unsigned long long previous;
    int target = -1, attached = -1, ns = -1, result = -1;
    if (kiosk_pin_before(deadline) != 0 ||
        pin->fd < 0 || pin->parent != -1 || pin->attached || expected == NULL || !kiosk_path(name, 0) ||
        strchr(name, '/') != NULL ||
        kiosk_pin_coverage_policy_until(pin->fd, entries, count, ambient, 1, deadline, failure) != 0)
        goto done;
    ns = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
    target = openat(owned_parent, name, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    unsigned long long parent_id;
    if (ns < 0 || fstat(ns, &namespace_info) != 0 || target < 0 ||
        fstat(owned_parent, &parent_info) != 0 || !kiosk_trusted_stat(&parent_info, S_IFDIR) ||
        parent_info.st_dev != expected->parent_device || parent_info.st_ino != expected->parent_inode ||
        kiosk_pin_fd_mount(owned_parent, &parent_id) != 0 || parent_id != expected->parent_mount ||
        fstat(target, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR) ||
        info.st_dev != expected->device || info.st_ino != expected->inode ||
        kiosk_pin_fd_mount(target, &previous) != 0 || previous != expected->mount ||
        (pin->parent = fcntl(owned_parent, F_DUPFD_CLOEXEC, STDERR_FILENO + 1)) < 0)
        goto done;
    strcpy(pin->name, name);
    pin->namespace_device = namespace_info.st_dev;
    pin->namespace_inode = namespace_info.st_ino;
    /* Record the detached clone ID before move_mount so even an immediate
     * post-attach inspection failure leaves identity-owned cleanup authority. */
    if (kiosk_pin_fd_mount(pin->fd, &pin->attached_id) != 0 || pin->attached_id == previous)
        goto done;
    if (kiosk_pin_before(deadline) != 0 || kiosk_os_failure(failure, "pin", "attach",
        move_mount(pin->fd, "", target, "", MOVE_MOUNT_F_EMPTY_PATH | MOVE_MOUNT_T_EMPTY_PATH) != 0))
        goto done;
    pin->attached = 1;
    attached = openat(pin->parent, pin->name, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    unsigned long long actual;
    if (kiosk_pin_before(deadline) != 0 ||
        attached < 0 || kiosk_pin_fd_mount(attached, &actual) != 0 || actual != pin->attached_id ||
        kiosk_os_failure(failure, "pin", "readonly",
            mount_setattr(attached, "", AT_EMPTY_PATH | AT_RECURSIVE, &readonly, sizeof(readonly)) != 0) ||
        kiosk_pin_coverage_policy_until(attached, entries, count, ambient, 1, deadline, failure) != 0 ||
        kiosk_pin_attached_topology_until(attached, entries, count, deadline, failure) != 0 ||
        kiosk_pin_before(deadline) != 0)
        goto done;
    pin->verified = 1;
    result = 0;
done:
    if (target >= 0) close(target);
    if (attached >= 0) close(attached);
    if (ns >= 0) close(ns);
    if (result != 0) kiosk_failure(failure, "pin", "identity", -1);
    return result;
}

static inline int
kiosk_pin_attach_until(struct kiosk_source_pin *pin, int owned_parent, const char *name,
                 const struct kiosk_pin_target *expected,
                 const struct kiosk_pin_entry *entries, unsigned count,
                 uint64_t deadline, struct kiosk_failure *failure)
{
    return kiosk_pin_attach_policy_until(pin, owned_parent, name, expected, entries, count,
        NULL, deadline, failure);
}

static inline int
kiosk_pin_attach(struct kiosk_source_pin *pin, int owned_parent, const char *name,
                 const struct kiosk_pin_target *expected,
                 const struct kiosk_pin_entry *entries, unsigned count,
                 struct kiosk_failure *failure)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 60000000U) return -1;
    return kiosk_pin_attach_until(pin, owned_parent, name, expected, entries, count,
        now + 60000000U, failure);
}

/* keep_attachment is valid only after the caller's attach/read-only/staging
 * detach/publication transaction succeeds. Closing setup descriptors then
 * leaves the attached tree owning its mount references. Failure cleanup never
 * detaches a foreign namespace, parent or replacement mount. */
static inline int
kiosk_pin_release(struct kiosk_source_pin *pin, int keep_attachment, struct kiosk_failure *failure)
{
    int result = 0;
    if (keep_attachment && (!pin->attached || !pin->verified || !pin->complete || !pin->published || pin->worker >= 0)) {
        kiosk_failure(failure, "pin", "incomplete", -1);
        return -1;
    }
    if (pin->worker >= 0) {
        if (kiosk_pin_reap_worker(pin->worker, failure) != 0)
            result = -1;
        else { close(pin->worker); pin->worker = -1; }
    }
    if (pin->attached && !keep_attachment) {
        struct stat info;
        unsigned long long id;
        char path[PATH_MAX + 64];
        int ns = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
        int fd = pin->parent < 0 ? -1 : openat(pin->parent, pin->name,
            O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (ns < 0 || fstat(ns, &info) != 0 || info.st_dev != pin->namespace_device ||
            info.st_ino != pin->namespace_inode || fd < 0 ||
            kiosk_pin_fd_mount(fd, &id) != 0 || id != pin->attached_id ||
            snprintf(path, sizeof(path), "/proc/self/fd/%d/%s", pin->parent, pin->name) >= (int) sizeof(path)) {
            kiosk_failure(failure, "pin", "detach-identity", -1);
            result = -1;
        } else if (kiosk_os_failure(failure, "pin", "detach", umount2(path, MNT_DETACH) != 0)) {
            result = -1;
        } else {
            pin->attached = 0;
            pin->verified = pin->complete = pin->published = 0;
        }
        if (fd >= 0) close(fd);
        if (ns >= 0) close(ns);
    }
    if (pin->fd >= 0) { close(pin->fd); pin->fd = -1; }
    /* Retain parent identity on a refused detach so an owned retry is possible. */
    if (result == 0 && pin->parent >= 0) { close(pin->parent); pin->parent = -1; }
    return result;
}

static int
kiosk_detach_owned(const char *path, unsigned long long expected, struct kiosk_failure *failure)
{
    unsigned long long actual;
    /* mount-id absence and identity mismatch are validation failures, not
     * necessarily failed syscalls from which errno can be inferred. */
    if (kiosk_mount_id(path, &actual) != 0 || actual != expected) {
        kiosk_failure(failure, "detach", "identity", -1);
        return -1;
    }
    if (kiosk_os_failure(failure, "detach", "detach", umount2(path, MNT_DETACH) != 0))
        return -1;
    return 0;
}

/* Complete only a verified attachment after every native identity-recorded
 * staging alias is detached. This is the native publication boundary; the
 * eventual receipt publisher must require it and still verify its own selected
 * record/marker identities. It grants no manager/admission proof. */
static int
kiosk_pin_stage_absent(const struct kiosk_owned_mount *stage)
{
    struct statx info;
    if (statx(AT_FDCWD, stage->path, AT_SYMLINK_NOFOLLOW, STATX_MNT_ID, &info) != 0)
        return errno == ENOENT;
    return (info.stx_mask & STATX_MNT_ID) && info.stx_mnt_id != stage->id;
}

static int
kiosk_pin_path_compare(const void *a, const void *b)
{
    return strcmp(*(const char *const *) a, *(const char *const *) b);
}

/* An absent original ID is insufficient: a foreign replacement mount or a
 * surviving alias below that path must also deny completion, without detaching
 * it. Compare actual native mountinfo against all detached staging roots. */
static int
kiosk_pin_staging_clear_until(const struct kiosk_owned_mount *stages, unsigned count, uint64_t deadline)
{
    if (kiosk_pin_before(deadline) != 0 || stages == NULL || count == 0 || count > KIOSK_VIEW_ROWS)
        return -1;
    char **paths = calloc(count, sizeof(*paths));
    FILE *stream = fopen("/proc/self/mountinfo", "re");
    char *line = NULL;
    size_t capacity = 0, bytes = 0;
    unsigned roots = 0, rows = 0;
    int result = -1;
    if (paths == NULL || stream == NULL)
        goto done;
    for (unsigned i = 0; i < count; i++) {
        if (kiosk_pin_before(deadline) != 0) goto done;
        if (!stages[i].live) paths[roots++] = stages[i].path;
    }
    qsort(paths, roots, sizeof(*paths), kiosk_pin_path_compare);
    ssize_t length;
    while ((length = getline(&line, &capacity, stream)) >= 0) {
        char path[PATH_MAX];
        if (kiosk_pin_before(deadline) != 0 ||
            ++rows > KIOSK_VIEW_ROWS || length == 0 || length > 3 * PATH_MAX || line[length - 1] != '\n' ||
            (bytes += (size_t) length) > KIOSK_VIEW_BYTES || memchr(line, '\0', (size_t) length) != NULL ||
            strstr(line, " - ") == NULL || sscanf(line, "%*s %*s %*s %*s %4095s", path) != 1 ||
            kiosk_pin_decode_mountpath(path) != 0)
            goto done;
        for (;;) {
            if (kiosk_pin_before(deadline) != 0) goto done;
            char *key = path;
            if (bsearch(&key, paths, roots, sizeof(*paths), kiosk_pin_path_compare) != NULL)
                goto done;
            char *slash = strrchr(path, '/');
            if (slash == path) break;
            *slash = '\0';
        }
    }
    if (ferror(stream) || kiosk_pin_before(deadline) != 0)
        goto done;
    result = 0;
done:
    free(paths);
    free(line);
    if (stream != NULL) fclose(stream);
    return result;
}

static inline int
kiosk_pin_staging_clear(const struct kiosk_owned_mount *stages, unsigned count)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 60000000U) return -1;
    return kiosk_pin_staging_clear_until(stages, count, now + 60000000U);
}

static inline int
kiosk_pin_finish_until(struct kiosk_source_pin *pin, struct kiosk_owned_mount *stages, unsigned count,
                 const struct kiosk_pin_entry *entries, unsigned entry_count,
                 uint64_t deadline, struct kiosk_failure *failure)
{
    struct stat info;
    int ns = -1, attached = -1, result = -1;
    unsigned long long id;
    if (kiosk_pin_before(deadline) != 0 ||
        !pin->attached || !pin->verified || pin->complete || pin->fd < 0 || pin->parent < 0 ||
        stages == NULL || count == 0 || count > KIOSK_VIEW_ROWS)
        goto done;
    ns = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
    if (ns < 0 || fstat(ns, &info) != 0 || info.st_dev != pin->namespace_device ||
        info.st_ino != pin->namespace_inode)
        goto done;
    /* Validate the complete cleanup inventory before the first mutation. */
    for (unsigned i = 0; i < count; i++)
        if (kiosk_pin_before(deadline) != 0 || stages[i].path == NULL || !kiosk_path(stages[i].path, 1) ||
            stages[i].id == 0 || stages[i].id == pin->attached_id ||
            (stages[i].live ? (kiosk_mount_id(stages[i].path, &id) != 0 || id != stages[i].id) :
             !kiosk_pin_stage_absent(&stages[i])))
            goto done;
    if (kiosk_pin_staging_clear_until(stages, count, deadline) != 0)
        goto done;
    for (unsigned i = count; i > 0; i--) {
        if (kiosk_pin_before(deadline) != 0) goto done;
        if (stages[i - 1].live) {
            if (kiosk_detach_owned(stages[i - 1].path, stages[i - 1].id, failure) != 0)
                goto done;
            stages[i - 1].live = 0;
        }
    }
    for (unsigned i = 0; i < count; i++)
        if (kiosk_pin_before(deadline) != 0 || stages[i].live || !kiosk_pin_stage_absent(&stages[i]))
            goto done;
    if (kiosk_pin_staging_clear_until(stages, count, deadline) != 0)
        goto done;
    attached = openat(pin->parent, pin->name, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (attached < 0 || kiosk_pin_fd_mount(attached, &id) != 0 || id != pin->attached_id ||
        kiosk_pin_coverage_policy_until(attached, entries, entry_count, NULL, 1, deadline, failure) != 0 ||
        kiosk_pin_attached_topology_until(attached, entries, entry_count, deadline, failure) != 0 ||
        kiosk_pin_before(deadline) != 0)
        goto done;
    pin->complete = 1;
    result = 0;
done:
    if (ns >= 0) close(ns);
    if (attached >= 0) close(attached);
    if (result != 0) kiosk_failure(failure, "pin", "incomplete", -1);
    return result;
}

static inline int
kiosk_pin_finish(struct kiosk_source_pin *pin, struct kiosk_owned_mount *stages, unsigned count,
                 const struct kiosk_pin_entry *entries, unsigned entry_count,
                 struct kiosk_failure *failure)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 60000000U) return -1;
    return kiosk_pin_finish_until(pin, stages, count, entries, entry_count, now + 60000000U, failure);
}

/* Atomic, no-replace publication of a native completion witness. The opaque
 * receipt hash is the future closed V/I protocol's selected identity; this
 * primitive cannot select/parse that protocol or admit a manager. A leftover
 * pending or ready file is never reused. After ready, 006 still requires the
 * independently verified live view, policy and final MAC before admission. */
static inline int
kiosk_pin_publish_until(struct kiosk_source_pin *pin, int owned_parent, const char *name,
                  const struct kiosk_pin_target *expected, const char *receipt,
                  const struct kiosk_pin_entry *entries, unsigned count,
                  int selinux, uint64_t deadline,
                  struct kiosk_failure *failure, struct kiosk_failure *cleanup_failure)
{
    struct stat parent_info, root_info, named, pending_info, attached_info, namespace_info;
    unsigned long long id;
    int root = -1, pending = -1, attached = -1, ns = -1, result = -1, created = 0, renamed = 0;
    char record[512];
    if (kiosk_pin_before(deadline) != 0 ||
        !pin->complete || !pin->verified || !pin->attached || pin->published || expected == NULL ||
        receipt == NULL || strnlen(receipt, 65) != 64 || !kiosk_path(name, 0) || strchr(name, '/') != NULL)
        goto done;
    for (unsigned i = 0; i < 64; i++)
        if (!((receipt[i] >= '0' && receipt[i] <= '9') || (receipt[i] >= 'a' && receipt[i] <= 'f')))
            goto done;
    ns = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
    root = openat(owned_parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    attached = openat(pin->parent, pin->name, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (ns < 0 || fstat(ns, &namespace_info) != 0 || namespace_info.st_dev != pin->namespace_device ||
        namespace_info.st_ino != pin->namespace_inode || root < 0 || attached < 0 ||
        fstat(owned_parent, &parent_info) != 0 || !kiosk_trusted_stat(&parent_info, S_IFDIR) ||
        parent_info.st_dev != expected->parent_device || parent_info.st_ino != expected->parent_inode ||
        kiosk_pin_fd_mount(owned_parent, &id) != 0 || id != expected->parent_mount ||
        fstat(root, &root_info) != 0 || !kiosk_trusted_stat(&root_info, S_IFDIR) ||
        (root_info.st_mode & 07777) != 0700 || root_info.st_dev != expected->device ||
        root_info.st_ino != expected->inode || kiosk_pin_fd_mount(root, &id) != 0 || id != expected->mount ||
        kiosk_label(root, NULL, 0, selinux) != 0 ||
        kiosk_pin_fd_mount(attached, &id) != 0 || id != pin->attached_id ||
        fstat(attached, &attached_info) != 0 ||
        kiosk_pin_coverage_policy_until(attached, entries, count, NULL, 1, deadline, failure) != 0 ||
        kiosk_pin_attached_topology_until(attached, entries, count, deadline, failure) != 0)
        goto done;
    int scan = fcntl(root, F_DUPFD_CLOEXEC, STDERR_FILENO + 1);
    DIR *directory = scan < 0 ? NULL : fdopendir(scan);
    if (directory == NULL) { if (scan >= 0) close(scan); goto done; }
    struct dirent *entry;
    int empty = 1;
    errno = 0;
    while ((entry = readdir(directory)) != NULL) {
        if (kiosk_pin_before(deadline) != 0) { empty = 0; break; }
        if (strcmp(entry->d_name, ".") != 0 && strcmp(entry->d_name, "..") != 0) { empty = 0; break; }
    }
    int valid = errno == 0 && empty && kiosk_pin_before(deadline) == 0;
    closedir(directory);
    if (!valid)
        goto done;
    pending = openat(root, "ready.pending", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (pending < 0)
        goto done;
    created = 1;
    if (fstat(pending, &pending_info) != 0 ||
        fstatat(root, "ready.pending", &named, AT_SYMLINK_NOFOLLOW) != 0 ||
        named.st_dev != pending_info.st_dev || named.st_ino != pending_info.st_ino ||
        kiosk_pin_fd_mount(pending, &id) != 0 || id != expected->mount ||
        kiosk_private_initialize(pending, 0600, 1) != 0 || fstat(pending, &pending_info) != 0 ||
        !kiosk_trusted_stat(&pending_info, S_IFREG) || (pending_info.st_mode & 07777) != 0600 ||
        pending_info.st_nlink != 1 || kiosk_label(pending, NULL, 0, selinux) != 0)
        goto done;
    int length = snprintf(record, sizeof(record),
        "ONPC-PIN-READY 1\nreceipt %s\nsource %llu %llu\nattachment %llu\npublisher %lu\n",
        receipt, (unsigned long long) attached_info.st_dev, (unsigned long long) attached_info.st_ino,
        pin->attached_id, (unsigned long) getpid());
    if (length <= 0 || length >= (int) sizeof(record))
        goto done;
    size_t offset = 0;
    while (offset < (size_t) length) {
        if (kiosk_pin_before(deadline) != 0) goto done;
        ssize_t written = write(pending, record + offset, (size_t) length - offset);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) goto done;
        offset += (size_t) written;
    }
    if (kiosk_pin_before(deadline) != 0 || fsync(pending) != 0 ||
        kiosk_pin_before(deadline) != 0 || fstatat(root, "ready.pending", &named, AT_SYMLINK_NOFOLLOW) != 0 ||
        named.st_dev != pending_info.st_dev || named.st_ino != pending_info.st_ino || named.st_nlink != 1 ||
        fstatat(owned_parent, name, &named, AT_SYMLINK_NOFOLLOW) != 0 ||
        named.st_dev != root_info.st_dev || named.st_ino != root_info.st_ino || kiosk_pin_before(deadline) != 0 ||
        renameat2(root, "ready.pending", root, "ready", RENAME_NOREPLACE) != 0)
        goto done;
    renamed = 1;
    if (kiosk_pin_before(deadline) != 0 || fsync(root) != 0 || fstatat(root, "ready", &named, AT_SYMLINK_NOFOLLOW) != 0 ||
        named.st_dev != pending_info.st_dev || named.st_ino != pending_info.st_ino || named.st_nlink != 1 ||
        named.st_size != length || (named.st_mode & 07777) != 0600 || named.st_uid != 0 ||
        kiosk_label(pending, NULL, 0, selinux) != 0 || kiosk_label(root, NULL, 0, selinux) != 0 ||
        fstatat(owned_parent, name, &named, AT_SYMLINK_NOFOLLOW) != 0 ||
        named.st_dev != root_info.st_dev || named.st_ino != root_info.st_ino || kiosk_pin_before(deadline) != 0)
        goto done;
    pin->published = 1;
    result = 0;
done:
    if (result != 0 && created && !renamed && pending >= 0 &&
        fstat(pending, &pending_info) == 0 && fstatat(root, "ready.pending", &named, AT_SYMLINK_NOFOLLOW) == 0 &&
        named.st_dev == pending_info.st_dev && named.st_ino == pending_info.st_ino && named.st_nlink == 1)
        (void) kiosk_os_failure(cleanup_failure, "pin", "publication-cleanup", unlinkat(root, "ready.pending", 0) != 0);
    if (pending >= 0) close(pending);
    if (root >= 0) close(root);
    if (attached >= 0) close(attached);
    if (ns >= 0) close(ns);
    if (result != 0) kiosk_failure(failure, "pin", "publication", -1);
    return result;
}

/* Convenience wrappers are standalone only. Composed callers pass the same
 * original absolute deadline through attachment, completion and publication. */
static inline int
kiosk_pin_publish(struct kiosk_source_pin *pin, int owned_parent, const char *name,
                  const struct kiosk_pin_target *expected, const char *receipt,
                  const struct kiosk_pin_entry *entries, unsigned count,
                  int selinux, struct kiosk_failure *failure, struct kiosk_failure *cleanup_failure)
{
    uint64_t now;
    if (kiosk_pin_now(&now) != 0 || now > UINT64_MAX - 60000000U) return -1;
    return kiosk_pin_publish_until(pin, owned_parent, name, expected, receipt, entries, count,
        selinux, now + 60000000U, failure, cleanup_failure);
}

static int
cleanup_kiosk_view(struct kiosk_view *view, int keep_clone)
{
    int result = 0;
    if (view->mounted || view->cloned) {
        struct stat namespace_info;
        int ns = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
        int matches = ns >= 0 && fstat(ns, &namespace_info) == 0 &&
            namespace_info.st_dev == view->namespace_device && namespace_info.st_ino == view->namespace_inode;
        if (ns >= 0)
            close(ns);
        if (!matches) {
            kiosk_failure(&view->cleanup_failure, "detach", "namespace", -1);
            if (view->root >= 0) {
                close(view->root);
                view->root = -1;
            }
            return -1;
        }
    }
    if (!keep_clone && view->cloned) {
        if (kiosk_detach_owned("/usr", view->clone_id, &view->cleanup_failure) != 0)
            result = -1;
        else
            view->cloned = 0;
    }
    for (unsigned i = view->count; i > 0; i--) {
        struct kiosk_owned_mount *item = &view->mounts[i - 1];
        if (item->live) {
            if (kiosk_detach_owned(item->path, item->id, &view->cleanup_failure) != 0)
                result = -1;
            else
                item->live = 0;
        }
    }
    /* Never hide an unsuccessful subordinate detach under a root detach. */
    if (result == 0 && view->mounted) {
        if (kiosk_detach_owned(KIOSK_CONFINEMENT_VIEW, view->root_id, &view->cleanup_failure) != 0)
            result = -1;
        else
            view->mounted = 0;
    }
    if (view->root >= 0) {
        close(view->root);
        view->root = -1;
    }
    if (result == 0) {
        for (unsigned i = 0; i < view->count; i++)
            free(view->mounts[i].path);
        free(view->mounts);
        view->mounts = NULL;
        view->count = 0;
    }
    return result;
}

static int
kiosk_tmpfs_context(unsigned long long mount_id)
{
    FILE *stream = fopen("/proc/self/mountinfo", "re");
    char line[PATH_MAX * 4];
    int result = -1;
    if (stream == NULL)
        return -1;
    while (fgets(line, sizeof(line), stream) != NULL) {
        unsigned long long id;
        char *separator;
        if (strchr(line, '\n') == NULL)
            break;
        if (sscanf(line, "%llu", &id) != 1 || id != mount_id)
            continue;
        separator = strstr(line, " - tmpfs ");
        if (separator == NULL)
            break;
        /* SELinux's show_options reports filesystem and root-inode mount
         * contexts independently. The raw root inode is checked separately. */
        char *options = strchr(separator + 9, ' '), *save = NULL;
        int filesystem = 0, root = 0;
        if (options == NULL)
            break;
        options++;
        options[strcspn(options, "\n")] = '\0';
        for (char *part = strtok_r(options, ",", &save); part; part = strtok_r(NULL, ",", &save)) {
            if (strcmp(part, "fscontext=system_u:object_r:tmpfs_t:s0") == 0 ||
                strcmp(part, "fscontext=\"system_u:object_r:tmpfs_t:s0\"") == 0)
                filesystem = 1;
            if (strcmp(part, "rootcontext=system_u:object_r:onpc_kiosk_runtime_t:s0") == 0 ||
                strcmp(part, "rootcontext=\"system_u:object_r:onpc_kiosk_runtime_t:s0\"") == 0)
                root = 1;
            if (strncmp(part, "context=", 8) == 0) {
                filesystem = root = 0;
                break;
            }
        }
        result = filesystem && root ? 0 : -1;
        break;
    }
    if (ferror(stream))
        result = -1;
    fclose(stream);
    return result;
}

static int
setup_kiosk_view(struct kiosk_view *view)
{
    struct stat info, before, after, named;
    struct statfs fs;
    unsigned long long parent_id, existing;
    DIR *directory = NULL;
    struct dirent *entry;
    void *library = NULL;
    int ns = -1, fresh = -1, scan = -1, empty = 1, result = -1, created;
    const char *stage = "staging", *reason = "metadata";
    int (*enabled)(void);
    memset(view, 0, sizeof(*view));
    view->root = -1;
    if (kiosk_private_fsuid()) goto done;
    if (kiosk_os_failure(&view->failure, stage, reason,
                        (view->mounts = calloc(KIOSK_VIEW_ROWS, sizeof(*view->mounts))) == NULL))
        goto done;
    library = dlopen("libselinux.so.1", RTLD_NOW | RTLD_LOCAL);
    if (library != NULL) {
        enabled = (int (*)(void)) dlsym(library, "is_selinux_enabled");
        if (enabled == NULL || (view->selinux = enabled()) < 0)
            goto done;
    } else if (access("/sys/fs/selinux/enforce", F_OK) == 0 || errno != ENOENT)
        goto done;
    stage = "namespace"; reason = "namespace";
    /* These descriptors witness namespace identity only. O_PATH permits the
     * fstat checks without requesting nsfs read access from the PAM caller. */
    ns = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
    if (kiosk_os_failure(&view->failure, stage, reason, ns < 0) ||
        kiosk_os_failure(&view->failure, stage, reason, fstat(ns, &before) != 0) ||
        kiosk_os_failure(&view->failure, stage, reason, unshare(CLONE_NEWNS) != 0) ||
        kiosk_os_failure(&view->failure, stage, "mount",
                         mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) != 0))
        goto done;
    fresh = open("/proc/self/ns/mnt", O_PATH | O_CLOEXEC);
    if (kiosk_os_failure(&view->failure, stage, reason, fresh < 0) ||
        kiosk_os_failure(&view->failure, stage, reason, fstat(fresh, &after) != 0) ||
        (before.st_dev == after.st_dev && before.st_ino == after.st_ino))
        goto done;
    view->namespace_device = after.st_dev;
    view->namespace_inode = after.st_ino;
    stage = "staging"; reason = "metadata";
    created = mkdir(KIOSK_CONFINEMENT_VIEW, 0700) == 0;
    if ((!created && errno != EEXIST) ||
        (view->root = open(KIOSK_CONFINEMENT_VIEW,
                           O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)) < 0 ||
        fstat(view->root, &info) != 0 || lstat(KIOSK_CONFINEMENT_VIEW, &named) != 0 ||
        !S_ISDIR(info.st_mode) || !S_ISDIR(named.st_mode) ||
        info.st_dev != named.st_dev || info.st_ino != named.st_ino ||
        kiosk_mount_id(KIOSK_CONFINEMENT_RUNTIME, &parent_id) != 0 ||
        kiosk_mount_id(KIOSK_CONFINEMENT_VIEW, &existing) != 0 || existing != parent_id ||
        kiosk_pin_fd_mount(view->root, &existing) != 0 || existing != parent_id ||
        (created && kiosk_private_initialize(view->root, 0700, 1)) ||
        fstat(view->root, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR) ||
        (info.st_mode & 07777) != 0700 ||
        (scan = fcntl(view->root, F_DUPFD_CLOEXEC, STDERR_FILENO + 1)) < 0 || (directory = fdopendir(scan)) == NULL)
        goto done;
    scan = -1; /* fdopendir owns the descriptor after success. */
    errno = 0;
    while ((entry = readdir(directory)) != NULL)
        if (strcmp(entry->d_name, ".") != 0 && strcmp(entry->d_name, "..") != 0)
            empty = 0;
    if (errno != 0 || !empty)
        goto done;
    closedir(directory);
    directory = NULL;
    if (kiosk_os_failure(&view->failure, stage, "mount",
        mount("tmpfs", KIOSK_CONFINEMENT_VIEW, "tmpfs", 0,
              view->selinux ? "mode=0700,uid=0,gid=0,size=536870912,nr_inodes=32776,fscontext=system_u:object_r:tmpfs_t:s0,rootcontext=system_u:object_r:onpc_kiosk_runtime_t:s0"
                            : "mode=0700,uid=0,gid=0,size=536870912,nr_inodes=32776") != 0))
        goto done;
    view->mounted = 1;
    if (kiosk_mount_id(KIOSK_CONFINEMENT_VIEW, &view->root_id) != 0 ||
        view->root_id == existing)
        goto done;
    close(view->root);
    view->root = open(KIOSK_CONFINEMENT_VIEW,
                      O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (view->root < 0 || kiosk_pin_fd_mount(view->root, &existing) != 0 || existing != view->root_id ||
        kiosk_private_initialize(view->root, 0700, 1) != 0 || fstat(view->root, &info) != 0 ||
        !kiosk_trusted_stat(&info, S_IFDIR) || (info.st_mode & 07777) != 0700 ||
        fstatfs(view->root, &fs) != 0 || (unsigned long) fs.f_type != 0x01021994UL ||
        fs.f_bsize <= 0 || !fs.f_blocks || !fs.f_files ||
        fs.f_blocks > 536870912ULL / (unsigned long long) fs.f_bsize ||
        fs.f_files > 32776 || kiosk_label(view->root, KIOSK_CONFINEMENT_VIEW, 0, view->selinux) != 0 ||
        (view->selinux && kiosk_tmpfs_context(view->root_id) != 0))
        goto done;
    result = 0;
done:
    if (result != 0)
        kiosk_failure(&view->failure, stage, reason, -1);
    if (directory != NULL)
        closedir(directory);
    if (ns >= 0)
        close(ns);
    if (fresh >= 0)
        close(fresh);
    if (scan >= 0)
        close(scan);
    if (library != NULL)
        dlclose(library);
    if (result != 0)
        (void) cleanup_kiosk_view(view, 0);
    return result;
}

static int
kiosk_record_compare(const void *a, const void *b)
{
    const struct kiosk_record *left = a, *right = b;
    return strcmp(left->key, right->key);
}

static struct kiosk_record *
kiosk_find(struct kiosk_record *rows, unsigned count, const char *path)
{
    struct kiosk_record key = {.key = (char *) path};
    return bsearch(&key, rows, count, sizeof(*rows), kiosk_record_compare);
}

static int
kiosk_sort_unique(struct kiosk_record *rows, unsigned count)
{
    qsort(rows, count, sizeof(*rows), kiosk_record_compare);
    for (unsigned i = 1; i < count; i++)
        if (strcmp(rows[i - 1].key, rows[i].key) == 0)
            return -1;
    return 0;
}

static int
kiosk_protected_descendant(struct kiosk_protocol *protocol, const char *path)
{
    char prefix[PATH_MAX];
    unsigned low = 0, high = protocol->nr;
    int n = snprintf(prefix, sizeof(prefix), "%s/", path);
    if (n < 0 || n >= PATH_MAX)
        return 1;
    while (low < high) {
        unsigned middle = low + (high - low) / 2;
        if (strcmp(protocol->roots[middle].key, prefix) < 0)
            low = middle + 1;
        else
            high = middle;
    }
    return low < protocol->nr && strncmp(protocol->roots[low].key, prefix, (size_t) n) == 0;
}

static int
kiosk_fields(char *line, char **fields, unsigned wanted)
{
    unsigned count = 1;
    fields[0] = line;
    for (char *p = line; *p; p++)
        if (*p == '\t') {
            if (count >= wanted)
                return -1;
            *p = '\0';
            fields[count++] = p + 1;
        }
    if (count != wanted)
        return -1;
    for (unsigned i = 0; i < wanted; i++)
        if (!fields[i][0])
            return -1;
    return 0;
}

static void
kiosk_free_protocol(struct kiosk_protocol *protocol)
{
    struct kiosk_record *groups[] = {protocol->roots, protocol->nodes, protocol->proofs, protocol->binds};
    unsigned counts[] = {protocol->nr, protocol->nn, protocol->np, protocol->nb};
    for (unsigned group = 0; group < 4; group++) {
        for (unsigned i = 0; i < counts[group]; i++)
            free(groups[group][i].storage);
        free(groups[group]);
    }
}

static int
kiosk_kind(const char *kind)
{
    return strcmp(kind, "file") == 0 ? S_IFREG : strcmp(kind, "link") == 0 ? S_IFLNK :
        (strcmp(kind, "directory") == 0 || strcmp(kind, "tree") == 0 ||
         strcmp(kind, "empty-directory") == 0) ? S_IFDIR : 0;
}

/* All intermediate aliases need their own exact proof. O_PATH never opens a
 * replacement special node for I/O, even when the final expectation is file.
 * Consume link targets component by component: unsafe/../safe must check the
 * unsafe directory before walking back. Terminal aliases also follow their
 * entire target chain and cannot hide a missing target proof. */
static int
kiosk_proof(struct kiosk_protocol *protocol, const char *original)
{
    char pending[PATH_MAX], traversed[PATH_MAX] = "/", link[PATH_MAX], part[PATH_MAX];
    struct stat info;
    int current = -1, child = -1, result = -1;
    unsigned links = 0;
    int original_checked = strcmp(original, "/") == 0;
    struct kiosk_record *original_record = kiosk_find(protocol->proofs, protocol->np, original);
    if (original_record == NULL)
        return -1;
    current = open("/", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    struct kiosk_record *root = kiosk_find(protocol->proofs, protocol->np, "/");
    if (current < 0 || root == NULL || strcmp(root->v[1], "directory") != 0 ||
        fstat(current, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR))
        goto done;
    strcpy(pending, original + 1);
    while (pending[0]) {
        char *slash = strchr(pending, '/');
        size_t length = slash == NULL ? strlen(pending) : (size_t) (slash - pending);
        memcpy(part, pending, length);
        part[length] = '\0';
        memmove(pending, slash == NULL ? pending + length : slash + 1,
                strlen(slash == NULL ? pending + length : slash + 1) + 1);
        if (!part[0] || strcmp(part, ".") == 0)
            continue;
        char next_path[PATH_MAX];
        strcpy(next_path, traversed);
        if (strcmp(part, "..") == 0) {
            char *last = strrchr(next_path, '/');
            if (last == next_path)
                next_path[1] = '\0';
            else
                *last = '\0';
        } else {
            if (strlen(next_path) + strlen(part) + 1 >= PATH_MAX)
                goto done;
            if (strcmp(next_path, "/") != 0)
                strcat(next_path, "/");
            strcat(next_path, part);
        }
        struct kiosk_record *proof = kiosk_find(protocol->proofs, protocol->np, next_path);
        if (proof == NULL || (child = openat(current, part, O_PATH | O_NOFOLLOW | O_CLOEXEC)) < 0 ||
            fstat(child, &info) != 0 || !kiosk_trusted_stat(&info, kiosk_kind(proof->v[1])))
            goto done;
        /* A lexical destination below an aliased parent has its own record,
         * although traversal reaches the canonical spelling of that inode. */
        if (!pending[0] && !original_checked) {
            if (strcmp(original_record->v[1], proof->v[1]) != 0 ||
                strcmp(original_record->v[3], proof->v[3]) != 0)
                goto done;
            original_checked = 1;
        }
        if (S_ISLNK(info.st_mode)) {
            ssize_t n = readlinkat(current, part, link, sizeof(link));
            if (n <= 0 || n >= PATH_MAX || strlen(proof->v[3]) != (size_t) n ||
                memcmp(link, proof->v[3], (size_t) n) != 0)
                goto done;
            link[n] = '\0';
            char combined[PATH_MAX];
            int used = snprintf(combined, sizeof(combined), "%s%s%s", link,
                                pending[0] ? "/" : "", pending);
            if (++links > 40 || used < 0 || used >= PATH_MAX)
                goto done;
            close(child);
            child = -1;
            if (link[0] == '/') {
                close(current);
                current = open("/", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
                if (current < 0 || fstat(current, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR))
                    goto done;
                strcpy(traversed, "/");
            }
            strcpy(pending, combined + (combined[0] == '/'));
            continue;
        }
        if (pending[0] && !S_ISDIR(info.st_mode))
            goto done;
        close(current);
        current = child;
        child = -1;
        strcpy(traversed, next_path);
    }
    if (!original_checked)
        goto done;
    strcpy(protocol->resolved, traversed);
    result = 0;
done:
    if (current >= 0)
        close(current);
    if (child >= 0)
        close(child);
    return result;
}

static int
kiosk_read_protocol(struct kiosk_protocol *protocol, struct kiosk_view *view, const char *role)
{
    struct stat info, manifest_info;
    char line[PATH_MAX * 3 + 256], *header[5];
    FILE *stream = NULL;
    int fd = -1, pin = -1, result = -1, phase = 0, terminal = 0;
    const char *reason = "manifest";
    size_t bytes = 0;
    memset(protocol, 0, sizeof(*protocol));
    protocol->roots = calloc(KIOSK_VIEW_ROWS, sizeof(*protocol->roots));
    protocol->nodes = calloc(KIOSK_VIEW_ROWS, sizeof(*protocol->nodes));
    protocol->proofs = calloc(KIOSK_VIEW_ROWS, sizeof(*protocol->proofs));
    protocol->binds = calloc(KIOSK_VIEW_ROWS, sizeof(*protocol->binds));
    if (!protocol->roots || !protocol->nodes || !protocol->proofs || !protocol->binds ||
        (strcmp(role, "manager") != 0 && strcmp(role, "gate") != 0))
        goto done;
    pin = openat(view->root, "bindings", O_PATH | O_NOFOLLOW | O_CLOEXEC);
    reason = "metadata";
    if (kiosk_os_failure(&view->failure, "manifest", reason, pin < 0) ||
        kiosk_os_failure(&view->failure, "manifest", reason, fstat(pin, &info) != 0) ||
        !kiosk_trusted_stat(&info, S_IFREG) ||
        (info.st_mode & 07777) != 0600 || info.st_nlink != 1 ||
        info.st_size <= 0 || info.st_size > KIOSK_VIEW_BYTES ||
        kiosk_label(pin, KIOSK_CONFINEMENT_BINDINGS, 0, view->selinux) != 0)
        goto done;
    manifest_info = info;
    char descriptor[64];
    snprintf(descriptor, sizeof(descriptor), "/proc/self/fd/%d", pin);
    fd = open(descriptor, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (kiosk_os_failure(&view->failure, "manifest", reason, fd < 0) ||
        kiosk_os_failure(&view->failure, "manifest", reason, (stream = fdopen(fd, "r")) == NULL))
        goto done;
    fd = -1;
    reason = "manifest";
    if (fgets(line, sizeof(line), stream) == NULL)
        goto done;
    bytes = strlen(line);
    if (!bytes || line[bytes - 1] != '\n')
        goto done;
    line[bytes - 1] = '\0';
    if (kiosk_fields(line, header, 5) != 0 || strcmp(header[0], "ONPC-KIOSK") != 0 ||
        strcmp(header[1], "1") != 0 || strcmp(header[3], role) != 0 ||
        (strcmp(header[2], "apparmor") != 0 && strcmp(header[2], "selinux") != 0) ||
        (view->selinux && strcmp(header[2], "selinux") != 0) ||
        (!view->selinux && strcmp(header[2], "apparmor") != 0) ||
        strlen(header[4]) != 64 || strspn(header[4], "0123456789abcdef") != 64)
        goto done;
    strcpy(protocol->backend, header[2]);
    strcpy(protocol->role, header[3]);
    if (snprintf(protocol->generation, sizeof(protocol->generation), "%s/%s",
                 KIOSK_CONFINEMENT_RUNTIME, header[4]) >= (int) sizeof(protocol->generation))
        goto done;
    while (fgets(line, sizeof(line), stream) != NULL) {
        size_t length = strlen(line);
        struct kiosk_record *record;
        unsigned *count, wanted;
        int next;
        bytes += length;
        if (terminal || !length || line[length - 1] != '\n' || bytes > KIOSK_VIEW_BYTES)
            goto done;
        line[length - 1] = '\0';
        if (strcmp(line, "attach\t/usr") == 0) {
            terminal = 1;
            continue;
        }
        if (strncmp(line, "root\t", 5) == 0) {
            count = &protocol->nr; record = protocol->roots; wanted = 4; next = 0;
        } else if (strncmp(line, "node\t", 5) == 0) {
            count = &protocol->nn; record = protocol->nodes; wanted = 4; next = 1;
        } else if (strncmp(line, "proof\t", 6) == 0) {
            count = &protocol->np; record = protocol->proofs; wanted = 4; next = 2;
        } else if (strncmp(line, "bind\t", 5) == 0) {
            count = &protocol->nb; record = protocol->binds; wanted = 6; next = 3;
        } else
            goto done;
        if (next < phase || *count >= KIOSK_VIEW_ROWS)
            goto done;
        phase = next;
        record += (*count)++;
        if ((record->storage = strdup(line)) == NULL ||
            kiosk_fields(record->storage, record->v, wanted) != 0)
            goto done;
        record->key = record->v[next == 3 ? 4 : 2];
        if (next == 0) {
            const char *kind = record->v[1];
            if ((strcmp(kind, "native") != 0 && strcmp(kind, "preserved") != 0 &&
                 strcmp(kind, "reserved") != 0 && strcmp(kind, "alias") != 0 &&
                 strcmp(kind, "covered") != 0 && strcmp(kind, "marker") != 0) ||
                !kiosk_path(record->v[2], 1) ||
                (strcmp(record->v[2], "/usr") != 0 && !kiosk_below(record->v[2], "/usr")) ||
                (strcmp(record->v[3], "-") != 0 && !kiosk_path(record->v[3], 1)))
                goto done;
        } else if (next == 1 || next == 2) {
            if (!kiosk_kind(record->v[1]) ||
                (next == 2 && strcmp(record->v[1], "tree") == 0) ||
                (next == 2 && strcmp(record->v[1], "empty-directory") == 0) ||
                !kiosk_path(record->v[2], next == 2) || strlen(record->v[3]) >= PATH_MAX ||
                (strcmp(record->v[1], "link") != 0 && strcmp(record->v[3], "-") != 0))
                goto done;
            for (const unsigned char *p = (const unsigned char *) record->v[3]; *p; p++)
                if (*p < 32 || *p == 127)
                    goto done;
        } else if ((strcmp(record->v[1], "required") != 0 && strcmp(record->v[1], "ambient") != 0) ||
                   (strcmp(record->v[2], "file") != 0 && strcmp(record->v[2], "directory") != 0) ||
                   !kiosk_path(record->v[3], 1) || !kiosk_path(record->v[4], 0) ||
                   (!kiosk_below(record->v[3], "/usr") &&
                    !kiosk_below(record->v[3], protocol->generation)))
            goto done;
    }
    if (ferror(stream) || bytes != (size_t) manifest_info.st_size ||
        fstat(pin, &info) != 0 || info.st_dev != manifest_info.st_dev ||
        info.st_ino != manifest_info.st_ino || info.st_size != manifest_info.st_size ||
        info.st_mode != manifest_info.st_mode || info.st_uid != 0 || info.st_nlink != 1 ||
        info.st_mtim.tv_sec != manifest_info.st_mtim.tv_sec ||
        info.st_mtim.tv_nsec != manifest_info.st_mtim.tv_nsec ||
        info.st_ctim.tv_sec != manifest_info.st_ctim.tv_sec ||
        info.st_ctim.tv_nsec != manifest_info.st_ctim.tv_nsec || !terminal || !protocol->nr ||
        !protocol->nn || !protocol->np ||
        kiosk_sort_unique(protocol->roots, protocol->nr) != 0 ||
        kiosk_sort_unique(protocol->nodes, protocol->nn) != 0 ||
        kiosk_sort_unique(protocol->proofs, protocol->np) != 0 ||
        kiosk_sort_unique(protocol->binds, protocol->nb) != 0)
        goto done;
    /* Pin and validate the selected shared generation and its unchanged marker.
     * It is preparation's digest, not a digest guessed by the native caller. */
    reason = "identity";
    char name[PATH_MAX], marker[66];
    int parent = kiosk_absolute_parent(protocol->generation, name);
    int generation = parent < 0 ? -1 : openat(parent, name, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent >= 0)
        close(parent);
    if (generation < 0 || fstat(generation, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR)) {
        if (generation >= 0)
            close(generation);
        goto done;
    }
    int marker_pin = openat(generation, "generation", O_PATH | O_NOFOLLOW | O_CLOEXEC);
    close(generation);
    if (marker_pin < 0)
        goto done;
    char pinned[64];
    snprintf(pinned, sizeof(pinned), "/proc/self/fd/%d", marker_pin);
    int marker_fd = -1;
    int valid = fstat(marker_pin, &info) == 0 && kiosk_trusted_stat(&info, S_IFREG) &&
        info.st_nlink == 1 && info.st_size == 65;
    if (valid)
        marker_fd = open(pinned, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    ssize_t received = marker_fd < 0 ? -1 : read(marker_fd, marker, sizeof(marker));
    valid = valid && received == 65 && marker[64] == '\n' &&
        memcmp(marker, strrchr(protocol->generation, '/') + 1, 64) == 0;
    if (marker_fd >= 0)
        close(marker_fd);
    close(marker_pin);
    if (!valid)
        goto done;
    result = 0;
done:
    if (result != 0)
        kiosk_failure(&view->failure, "manifest", reason, -1);
    if (stream != NULL)
        fclose(stream);
    if (fd >= 0)
        close(fd);
    if (pin >= 0)
        close(pin);
    return result;
}

static int
kiosk_tree_entries(struct kiosk_protocol *protocol, int tree, const char *relative, int branching)
{
    char path[PATH_MAX], name[PATH_MAX];
    int parent = relative[0] ? kiosk_parent(tree, relative, name) : -1;
    int fd = relative[0] ? (parent < 0 ? -1 : openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)) : fcntl(tree, F_DUPFD_CLOEXEC, STDERR_FILENO + 1);
    if (parent >= 0)
        close(parent);
    DIR *directory = fd < 0 ? NULL : fdopendir(fd);
    struct dirent *entry;
    int valid = 1;
    if (directory == NULL) {
        if (fd >= 0)
            close(fd);
        return -1;
    }
    errno = 0;
    while ((entry = readdir(directory)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0)
            continue;
        int n = snprintf(path, sizeof(path), "%s%s%s", relative, relative[0] ? "/" : "", entry->d_name);
        if (!branching || n < 0 || n >= PATH_MAX ||
            kiosk_find(protocol->nodes, protocol->nn, path) == NULL) {
            valid = 0;
            break;
        }
    }
    if (errno != 0)
        valid = 0;
    closedir(directory);
    return valid ? 0 : -1;
}

static int
kiosk_structure(struct kiosk_protocol *protocol, struct kiosk_view *view, int tree)
{
    struct stat info;
    char name[PATH_MAX], path[PATH_MAX], link[PATH_MAX];
    struct kiosk_record *usr = kiosk_find(protocol->roots, protocol->nr, "/usr");
    struct kiosk_record *marker = kiosk_find(protocol->roots, protocol->nr,
        "/usr/share/oh-no-parent-control/confinement/generation");
    if (usr == NULL || strcmp(usr->v[1], "covered") != 0 || strcmp(usr->v[3], "-") != 0)
        return -1;
    if (marker == NULL || strcmp(marker->v[1], "marker") != 0)
        return -1;
    if (kiosk_tree_entries(protocol, tree, "", 1) != 0)
        return -1;
    for (unsigned i = 0; i < protocol->nn; i++) {
        struct kiosk_record *node = &protocol->nodes[i];
        strcpy(path, node->v[2]);
        for (char *last = strrchr(path, '/'); last != NULL; last = strrchr(path, '/')) {
            *last = '\0';
            struct kiosk_record *parent_node = kiosk_find(protocol->nodes, protocol->nn, path);
            if (parent_node == NULL || strcmp(parent_node->v[1], "tree") != 0)
                return -1;
        }
        int parent = kiosk_parent(tree, node->v[2], name);
        int fd = parent < 0 ? -1 : openat(parent, name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        int valid = fd >= 0 && fstat(fd, &info) == 0 &&
            kiosk_trusted_stat(&info, kiosk_kind(node->v[1]));
        if (valid && strcmp(node->v[1], "file") == 0)
            valid = info.st_nlink == 1 && info.st_size == 0 && (info.st_mode & 07777) == 0644;
        if (valid && S_ISDIR(info.st_mode))
            valid = (info.st_mode & 07777) == 0755;
        if (valid && strcmp(node->v[1], "link") == 0) {
            ssize_t n = readlinkat(parent, name, link, sizeof(link));
            valid = n > 0 && n < PATH_MAX && strlen(node->v[3]) == (size_t) n &&
                memcmp(link, node->v[3], (size_t) n) == 0;
        }
        if (snprintf(path, sizeof(path), "%s/tree/%s", KIOSK_CONFINEMENT_VIEW, node->v[2]) >= PATH_MAX)
            valid = 0;
        unsigned long long mount_id;
        if (valid && (kiosk_mount_id(path, &mount_id) != 0 || mount_id != view->root_id))
            valid = 0;
        if (valid && kiosk_label(fd, path, S_ISLNK(info.st_mode), view->selinux) != 0)
            valid = 0;
        if (fd >= 0)
            close(fd);
        if (parent >= 0)
            close(parent);
        if (!valid)
            return -1;
        if (kiosk_kind(node->v[1]) == S_IFDIR &&
            kiosk_tree_entries(protocol, tree, node->v[2], strcmp(node->v[1], "tree") == 0) != 0)
            return -1;
        struct kiosk_record *binding = kiosk_find(protocol->binds, protocol->nb, node->v[2]);
        if ((strcmp(node->v[1], "file") == 0 || strcmp(node->v[1], "directory") == 0) ?
            binding == NULL : binding != NULL)
            return -1;
    }
    for (unsigned i = 0; i < protocol->nr; i++) {
        struct kiosk_record *root = &protocol->roots[i];
        const char *kind = root->v[1], *destination = root->v[2], *mapping = root->v[3];
        int copied = strcmp(kind, "native") == 0 || strcmp(kind, "marker") == 0;
        int preserved = strcmp(kind, "preserved") == 0;
        if (copied ? !kiosk_below(mapping, protocol->generation) :
            preserved ? strcmp(mapping, destination) != 0 : strcmp(mapping, "-") != 0)
            return -1;
        if (copied) {
            const char *base = mapping + strlen(protocol->generation) + 1;
            if (strcmp(kind, "marker") == 0) {
                if (strcmp(base, "generation") != 0 ||
                    strcmp(destination, "/usr/share/oh-no-parent-control/confinement/generation") != 0)
                    return -1;
            } else if (!base[0] || strspn(base, "0123456789") != strlen(base))
                return -1;
        }
        if (strcmp(kind, "marker") != 0 &&
            (kiosk_find(protocol->proofs, protocol->np, destination) == NULL ||
             kiosk_proof(protocol, destination) != 0))
            return -1;
        if (strcmp(kind, "marker") != 0) {
            struct kiosk_record *endpoint = kiosk_find(protocol->proofs, protocol->np, protocol->resolved);
            if (endpoint == NULL ||
                ((strcmp(kind, "native") == 0 || preserved || strcmp(kind, "alias") == 0) ?
                 strcmp(endpoint->v[1], "file") != 0 : strcmp(endpoint->v[1], "directory") != 0))
                return -1;
            if (strcmp(kind, "alias") == 0) {
                struct kiosk_record *canonical = kiosk_find(protocol->roots, protocol->nr, protocol->resolved);
                if (canonical == NULL ||
                    (strcmp(canonical->v[1], "native") != 0 && strcmp(canonical->v[1], "preserved") != 0))
                    return -1;
            }
        }
        if (copied) {
            if (kiosk_find(protocol->proofs, protocol->np, mapping) == NULL ||
                kiosk_proof(protocol, mapping) != 0)
                return -1;
            struct kiosk_record *endpoint = kiosk_find(protocol->proofs, protocol->np, protocol->resolved);
            if (endpoint == NULL || strcmp(endpoint->v[1], "file") != 0)
                return -1;
        }
        if (strcmp(destination, "/usr") == 0)
            continue;
        struct kiosk_record *node = kiosk_find(protocol->nodes, protocol->nn, destination + 5);
        if (node == NULL || ((copied || preserved) && strcmp(node->v[1], "file") != 0) ||
            ((strcmp(kind, "covered") == 0 || strcmp(kind, "reserved") == 0) &&
             strcmp(node->v[1], "tree") != 0 && strcmp(node->v[1], "directory") != 0 &&
             strcmp(node->v[1], "link") != 0))
            return -1;
        if (copied || preserved) {
            struct kiosk_record *binding = kiosk_find(protocol->binds, protocol->nb, destination + 5);
            if (binding == NULL || strcmp(binding->v[1], "required") != 0 ||
                strcmp(binding->v[3], mapping) != 0 ||
                (preserved ? strcmp(binding->v[5], "-") == 0 : strcmp(binding->v[5], "-") != 0))
                return -1;
        }
    }
    for (unsigned i = 0; i < protocol->np; i++)
        if (kiosk_proof(protocol, protocol->proofs[i].v[2]) != 0)
            return -1;
    for (unsigned i = 0; i < protocol->nb; i++) {
        struct kiosk_record *binding = &protocol->binds[i];
        struct kiosk_record *node = kiosk_find(protocol->nodes, protocol->nn, binding->v[4]);
        if (node == NULL || strcmp(node->v[1], binding->v[2]) != 0)
            return -1;
        if (snprintf(path, sizeof(path), "/usr/%s", binding->v[4]) >= PATH_MAX)
            return -1;
        struct kiosk_record *root = kiosk_find(protocol->roots, protocol->nr, path);
        if (strcmp(binding->v[1], "ambient") == 0) {
            if (root != NULL || strcmp(binding->v[5], "-") != 0 || strcmp(binding->v[3], path) != 0 ||
                kiosk_find(protocol->proofs, protocol->np, binding->v[3]) != NULL)
                return -1;
            /* An ambient directory may not cover any protected descendant. */
            if (kiosk_protected_descendant(protocol, path))
                return -1;
        } else if (root == NULL ||
                   strcmp(binding->v[3], strcmp(root->v[3], "-") == 0 ? path : root->v[3]) != 0)
            return -1;
    }
    return 0;
}

static int
kiosk_final_error(void)
{
    return errno == ENOENT || errno == EACCES || errno == EPERM || errno == EIO || errno == ESTALE;
}

static int
kiosk_source_state(int source, int parent, const char *name, int kind, struct stat *info,
                   struct kiosk_failure *failure)
{
    struct stat named;
    memset(failure, 0, sizeof(*failure));
    if (fstat(source, info) != 0) {
        kiosk_failure(failure, "source", "metadata", errno);
        return kiosk_final_error() ? 1 : -1;
    }
    if (!kiosk_trusted_stat(info, kind) || info->st_nlink == 0) {
        kiosk_failure(failure, "source", "metadata", -1);
        return 1;
    }
    if (fstatat(parent, name, &named, AT_SYMLINK_NOFOLLOW) != 0) {
        kiosk_failure(failure, "source", "metadata", errno);
        return kiosk_final_error() ? 1 : -1;
    }
    if (!kiosk_trusted_stat(&named, kind) || named.st_nlink == 0) {
        kiosk_failure(failure, "source", "metadata", -1);
        return 1;
    }
    if (named.st_dev != info->st_dev || named.st_ino != info->st_ino) {
        kiosk_failure(failure, "source", "identity", -1);
        return 1;
    }
    return 0;
}

static int
kiosk_source_ancestry(const char *path, int pinned)
{
    char name[PATH_MAX];
    struct stat before, now;
    int current = kiosk_absolute_parent(path, name);
    int valid = current >= 0 && fstat(pinned, &before) == 0 && fstat(current, &now) == 0 &&
        before.st_dev == now.st_dev && before.st_ino == now.st_ino;
    if (current >= 0)
        close(current);
    return valid ? 0 : -1;
}

static int
kiosk_omit(int parent, const char *name, const char *path,
           const struct stat *placeholder, unsigned long long root_id, int kind)
{
    struct stat info;
    unsigned long long id;
    if (fstatat(parent, name, &info, AT_SYMLINK_NOFOLLOW) != 0 ||
        info.st_dev != placeholder->st_dev || info.st_ino != placeholder->st_ino ||
        !kiosk_trusted_stat(&info, kind) ||
        kiosk_mount_id(path, &id) != 0 || id != root_id)
        return -1;
    if (kind == S_IFREG)
        return info.st_size == 0 && info.st_nlink == 1 && (info.st_mode & 07777) == 0644 &&
            unlinkat(parent, name, 0) == 0 ? 0 : -1;
    if ((info.st_mode & 07777) != 0755)
        return -1;
    int fd = openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    DIR *directory = fd < 0 ? NULL : fdopendir(fd);
    if (directory == NULL) {
        if (fd >= 0)
            close(fd);
        return -1;
    }
    struct dirent *entry;
    int empty = 1;
    errno = 0;
    while ((entry = readdir(directory)) != NULL)
        if (strcmp(entry->d_name, ".") != 0 && strcmp(entry->d_name, "..") != 0)
            empty = 0;
    int valid = errno == 0 && empty;
    closedir(directory);
    return valid ? 0 : -1;
}

static int
preserved_kiosk_identity(const struct stat *info, const char *assertion)
{
    unsigned long long values[8] = {0};
    const unsigned long long maximum = ~0ULL;
    const char *p = assertion;
    for (unsigned i = 0; i < 8; i++) {
        if (*p < '0' || *p > '9')
            return -1;
        do {
            unsigned digit = (unsigned) (*p++ - '0');
            if (values[i] > (maximum - digit) / 10)
                return -1;
            values[i] = values[i] * 10 + digit;
        } while (*p >= '0' && *p <= '9');
        if (i == 7 ? *p != '\0' : *p++ != ' ')
            return -1;
    }
    if (info == NULL)
        return 0;
    return (values[0] == (unsigned long long) info->st_dev &&
            values[1] == (unsigned long long) info->st_ino &&
            values[2] == (unsigned long long) info->st_size &&
            values[3] == (unsigned long long) info->st_mtim.tv_sec * 1000000000ULL + info->st_mtim.tv_nsec &&
            values[4] == (unsigned long long) info->st_ctim.tv_sec * 1000000000ULL + info->st_ctim.tv_nsec &&
            values[5] == (unsigned long long) info->st_mode && values[6] == info->st_uid && values[7] == info->st_gid)
        ? 0 : -1;
}

static inline int
bind_kiosk_executables(char *backend, size_t size, const char *role, struct kiosk_view *view)
{
    struct kiosk_protocol protocol = {0};
    struct mount_attr readonly = {.attr_set = MOUNT_ATTR_RDONLY};
    struct stat info, placeholder;
    char source_name[PATH_MAX], target_name[PATH_MAX], path[PATH_MAX];
    char fd_path[64], target_fd_path[64];
    int tree = -1, source = -1, target = -1, source_parent = -1, target_parent = -1;
    int result = -1;
    const char *stage = "manifest", *reason = "manifest";
    if (view->root < 0 || !view->mounted ||
        kiosk_read_protocol(&protocol, view, role) != 0 || strlen(protocol.backend) >= size)
        goto done;
    stage = "structure"; reason = "metadata";
    tree = openat(view->root, "tree", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (kiosk_os_failure(&view->failure, stage, reason, tree < 0))
        goto done;
    unsigned long long tree_id;
    if (snprintf(path, sizeof(path), "%s/tree", KIOSK_CONFINEMENT_VIEW) >= PATH_MAX ||
        kiosk_mount_id(path, &tree_id) != 0 || tree_id != view->root_id)
        goto done;
    if (tree < 0 || fstat(tree, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR) ||
        (info.st_mode & 07777) != 0755 ||
        kiosk_label(tree, NULL, 0, view->selinux) != 0 ||
        kiosk_structure(&protocol, view, tree) != 0)
        goto done;
    /* Validate every assertion before any source fallback or mount. */
    stage = "manifest"; reason = "identity";
    for (unsigned i = 0; i < protocol.nb; i++) {
        struct kiosk_record *record = &protocol.binds[i];
        if (strcmp(record->v[5], "-") != 0 &&
            (strcmp(record->v[1], "required") != 0 || strcmp(record->v[2], "file") != 0 ||
             preserved_kiosk_identity(NULL, record->v[5]) != 0))
            goto done;
    }
    for (unsigned i = 0; i < protocol.nb; i++) {
        struct kiosk_record *record = &protocol.binds[i];
        int ambient = strcmp(record->v[1], "ambient") == 0;
        int kind = kiosk_kind(record->v[2]);
        int assertion = strcmp(record->v[5], "-") != 0;
        int state;
        struct kiosk_failure source_failure;
        struct kiosk_owned_mount *owned = NULL;
        stage = "structure"; reason = "metadata";
        if (snprintf(path, sizeof(path), "%s/tree/%s", KIOSK_CONFINEMENT_VIEW, record->v[4]) >= PATH_MAX)
            goto done;
        target_parent = kiosk_parent(tree, record->v[4], target_name);
        target = target_parent < 0 ? -1 : openat(target_parent, target_name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        if (target_parent < 0 || kiosk_os_failure(&view->failure, stage, reason, target < 0) ||
            kiosk_os_failure(&view->failure, stage, reason, fstat(target, &placeholder) != 0) ||
            !kiosk_trusted_stat(&placeholder, kind) ||
            (kind == S_IFREG && (placeholder.st_nlink != 1 || placeholder.st_size != 0)))
            goto done;
        unsigned long long target_id;
        if (kiosk_mount_id(path, &target_id) != 0 || target_id != view->root_id)
            goto done;
        stage = "source"; reason = "identity";
        source_parent = kiosk_absolute_parent(record->v[3], source_name);
        if (source_parent < 0)
            goto done;
        source = openat(source_parent, source_name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        if (source < 0) {
            if (!ambient || !kiosk_final_error()) {
                kiosk_failure(&view->failure, stage, "metadata", errno);
                goto done;
            }
            goto omit;
        }
        state = kiosk_source_state(source, source_parent, source_name, kind, &info, &source_failure);
        if (state < 0 || (state != 0 && !ambient)) {
            view->failure = source_failure;
            goto done;
        }
        if (state != 0)
            goto omit;
        if (assertion && (info.st_nlink != 1 || preserved_kiosk_identity(&info, record->v[5]) != 0))
            goto done;
        if (kiosk_source_ancestry(record->v[3], source_parent) != 0)
            goto done;
        struct stat target_named;
        if (kiosk_source_ancestry(path, target_parent) != 0 ||
            fstatat(target_parent, target_name, &target_named, AT_SYMLINK_NOFOLLOW) != 0 ||
            target_named.st_dev != placeholder.st_dev || target_named.st_ino != placeholder.st_ino ||
            !kiosk_trusted_stat(&target_named, kind))
            goto done;
        /* Last descriptor/pathname measurement immediately before the bind. */
        state = kiosk_source_state(source, source_parent, source_name, kind, &info, &source_failure);
        if (state < 0 || (state != 0 && !ambient)) {
            view->failure = source_failure;
            goto done;
        }
        if (state != 0)
            goto omit;
        if (assertion && (info.st_nlink != 1 || preserved_kiosk_identity(&info, record->v[5]) != 0))
            goto done;
        if (view->count >= KIOSK_VIEW_ROWS)
            goto done;
        owned = &view->mounts[view->count++];
        if ((owned->path = strdup(path)) == NULL)
            goto done;
        snprintf(fd_path, sizeof(fd_path), "/proc/self/fd/%d", source);
        snprintf(target_fd_path, sizeof(target_fd_path), "/proc/self/fd/%d", target);
        stage = "bind"; reason = "mount";
        if (kiosk_os_failure(&view->failure, stage, reason,
                             mount(fd_path, target_fd_path, NULL, MS_BIND | MS_REC, NULL) != 0))
            goto done; /* A mount error is never an ambient omission. */
        owned->live = 1;
        reason = "identity";
        unsigned long long bound_id;
        if (kiosk_mount_id(path, &bound_id) != 0 || bound_id == view->root_id)
            goto done;
        int mounted_target = openat(target_parent, target_name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        int mounted_valid = mounted_target >= 0 && fstat(mounted_target, &target_named) == 0 &&
            target_named.st_dev == info.st_dev && target_named.st_ino == info.st_ino &&
            (target_named.st_mode & S_IFMT) == (mode_t) kind &&
            kiosk_source_ancestry(path, target_parent) == 0;
        if (mounted_target >= 0)
            close(mounted_target);
        if (!mounted_valid)
            goto done;
        owned->id = bound_id;
        stage = "source"; reason = "identity";
        if (kiosk_source_ancestry(record->v[3], source_parent) != 0)
            goto done;
        state = kiosk_source_state(source, source_parent, source_name, kind, &info, &source_failure);
        if (state < 0 || (state != 0 && !ambient)) {
            view->failure = source_failure;
            goto done;
        }
        if (state != 0) {
            if (kiosk_detach_owned(owned->path, owned->id, &view->failure) != 0)
                goto done;
            owned->live = 0;
            goto omit;
        }
        if (assertion && (info.st_nlink != 1 || preserved_kiosk_identity(&info, record->v[5]) != 0))
            goto done;
        goto next;
omit:
        stage = "source"; reason = "identity";
        if (kiosk_source_ancestry(record->v[3], source_parent) != 0 ||
            kiosk_source_ancestry(path, target_parent) != 0)
            goto done;
        stage = "structure"; reason = "metadata";
        if (kiosk_omit(target_parent, target_name, path, &placeholder, view->root_id, kind) != 0)
            goto done;
next:
        if (source >= 0)
            close(source);
        close(target);
        close(source_parent);
        close(target_parent);
        source = target = source_parent = target_parent = -1;
    }
    /* Required ancestry and full alias closure stay strict through attachment. */
    stage = "source"; reason = "identity";
    for (unsigned i = 0; i < protocol.np; i++)
        if (kiosk_proof(&protocol, protocol.proofs[i].v[2]) != 0)
            goto done;
    stage = "attach"; reason = "identity";
    target = open("/usr", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    struct stat tree_info, named_tree;
    unsigned long long previous_usr, attached_id;
    if (target < 0 || fstat(target, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR) ||
        kiosk_mount_id("/usr", &previous_usr) != 0 ||
        fstat(tree, &tree_info) != 0 || !kiosk_trusted_stat(&tree_info, S_IFDIR) ||
        tree_info.st_nlink == 0 ||
        fstatat(view->root, "tree", &named_tree, AT_SYMLINK_NOFOLLOW) != 0 ||
        tree_info.st_dev != named_tree.st_dev || tree_info.st_ino != named_tree.st_ino)
        goto done;
    snprintf(fd_path, sizeof(fd_path), "/proc/self/fd/%d", tree);
    snprintf(target_fd_path, sizeof(target_fd_path), "/proc/self/fd/%d", target);
    reason = "mount";
    if (kiosk_os_failure(&view->failure, stage, reason,
                         mount(fd_path, target_fd_path, NULL, MS_BIND | MS_REC, NULL) != 0))
        goto done;
    view->cloned = 1;
    reason = "identity";
    if (kiosk_mount_id("/usr", &attached_id) != 0 || attached_id == previous_usr ||
        attached_id == view->root_id)
        goto done;
    int clone = open("/usr", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    int clone_valid = clone >= 0 && fstat(clone, &named_tree) == 0 &&
        named_tree.st_dev == tree_info.st_dev && named_tree.st_ino == tree_info.st_ino &&
        kiosk_trusted_stat(&named_tree, S_IFDIR);
    if (clone >= 0)
        close(clone);
    if (!clone_valid)
        goto done;
    view->clone_id = attached_id;
    stage = "readonly"; reason = "readonly";
    if (kiosk_os_failure(&view->failure, stage, reason,
                         mount_setattr(AT_FDCWD, "/usr", AT_RECURSIVE, &readonly, sizeof(readonly)) != 0))
        goto done;
    close(tree);
    tree = -1;
    close(target);
    target = -1;
    /* The /usr clone owns the dentries now. Detach aliases, never unlink the
     * skeleton: deleting it would also delete names visible in the clone. */
    stage = "detach"; reason = "detach";
    if (cleanup_kiosk_view(view, 1) != 0) {
        /* This detach is required to finish binding; it is also independently
         * retained as cleanup evidence if later recovery cannot detach it. */
        if (view->failure.stage == NULL)
            view->failure = view->cleanup_failure;
        goto done;
    }
    strcpy(backend, protocol.backend);
    result = 0;
done:
    if (result != 0)
        kiosk_failure(&view->failure, stage, reason, -1);
    if (source >= 0)
        close(source);
    if (target >= 0)
        close(target);
    if (source_parent >= 0)
        close(source_parent);
    if (target_parent >= 0)
        close(target_parent);
    if (tree >= 0)
        close(tree);
    kiosk_free_protocol(&protocol);
    if (result != 0)
        (void) cleanup_kiosk_view(view, 0);
    return result;
}

static inline int
apply_kiosk_mac(const char *backend, const char *role)
{
    char context[128];
    void *library;
    int result = -1;
    if (strcmp(backend, "apparmor") == 0) {
        int (*change_profile)(const char *);
        int (*getcon)(char **, char **);
        char *label = NULL, *mode = NULL;
        library = dlopen("libapparmor.so.1", RTLD_NOW | RTLD_LOCAL);
        if (library == NULL)
            return -1;
        change_profile = (int (*)(const char *)) dlsym(library, "aa_change_profile");
        getcon = (int (*)(char **, char **)) dlsym(library, "aa_getcon");
        snprintf(context, sizeof(context), "onpc-kiosk-%s", role);
        /* Unconfined change_onexec does not check the first executable against
         * the target policy. Immediate change_profile closes that gap. */
        if (change_profile != NULL && getcon != NULL && change_profile(context) == 0 &&
            getcon(&label, &mode) >= 0 && label != NULL && mode != NULL &&
            strcmp(label, context) == 0 && strcmp(mode, "enforce") == 0)
            result = 0;
        free(label); /* mode points into the allocation returned in label. */
    } else {
        int (*enabled)(void), (*enforcing)(void), (*setexec)(const char *);
        char *pending = NULL;
        int (*getexec)(char **);
        int (*setcurrent)(const char *), (*getcurrent)(char **);
        void (*freecon)(char *);
        library = dlopen("libselinux.so.1", RTLD_NOW | RTLD_LOCAL);
        if (library == NULL)
            return -1;
        enabled = (int (*)(void)) dlsym(library, "is_selinux_enabled");
        enforcing = (int (*)(void)) dlsym(library, "security_getenforce");
        setexec = (int (*)(const char *)) dlsym(library, "setexeccon_raw");
        getexec = (int (*)(char **)) dlsym(library, "getexeccon_raw");
        setcurrent = (int (*)(const char *)) dlsym(library, "setcon_raw");
        getcurrent = (int (*)(char **)) dlsym(library, "getcon_raw");
        freecon = (void (*)(char *)) dlsym(library, "freecon");
        snprintf(context, sizeof(context), "system_u:system_r:onpc_kiosk_%s_t:s0", role);
        if (enabled != NULL && enforcing != NULL && setexec != NULL && getexec != NULL &&
            freecon != NULL && enabled() == 1 && enforcing() == 1) {
            if (strcmp(role, "manager") == 0) {
                /* systemd forks its PAM lifecycle child before the real exec.
                 * Enter a restricted current domain in the trusted executor;
                 * both descendants stay confined even when pam_selinux close
                 * clears its pending exec context. The kernel refuses unsafe
                 * multithreaded dynamic transitions. No reverse grant exists. */
                snprintf(context, sizeof(context), "system_u:system_r:onpc_kiosk_manager_pam_t:s0");
                if (setcurrent != NULL && getcurrent != NULL && setexec(NULL) == 0 &&
                    setcurrent(context) == 0 && getcurrent(&pending) == 0 && pending != NULL &&
                    strcmp(pending, context) == 0)
                    result = 0;
            } else {
                /* GDM's trusted root worker retains its vendor context. The
                 * session child must exec the private gate entrypoint; the
                 * kernel checks the actual selected command, not metadata. */
                if (setexec(context) == 0 && getexec(&pending) == 0 && pending != NULL &&
                    strcmp(pending, context) == 0)
                    result = 0;
            }
        }
        if (pending != NULL && freecon != NULL)
            freecon(pending);
    }
    dlclose(library);
    return result;
}

/* Both production roles use the same native authority and original deadline. */
#include "kiosk_fresh_startup.h"
#include "kiosk_retained_startup.h"

#define KIOSK_TRANSACTION_DATA "oh-no-parent-control.kiosk-transaction"
struct kiosk_admission_transaction {
    struct kiosk_retained_startup retained;
    int lock, gate, closed;
};

static int
kiosk_transaction_close(struct kiosk_admission_transaction *t)
{
    struct kiosk_fresh_startup *s = &t->retained.common;
    uint64_t now;
    if (t->closed) return 0;
    if (!s->armed) {
        if (kiosk_pin_now(&now) || now > UINT64_MAX - 5000000U ||
            (t->gate ? kiosk_retained_recover_until(&t->retained, now + 5000000U) :
                kiosk_fresh_recover_until(s, now + 5000000U))) return -1;
    }
    if (t->gate ? kiosk_retained_close(&t->retained) : kiosk_fresh_close(s)) return -1;
    if (t->lock >= 0) close(t->lock);
    t->lock = -1; t->closed = 1;
    return 0;
}

static void
release_kiosk_transaction(pam_handle_t *pamh, void *data, int status)
{
    struct kiosk_admission_transaction *t = data;
    (void)status;
    if (!t) return;
    if (kiosk_transaction_close(t)) {
        /* Preserve the exact unresolved owner and lock until executor exit.
         * Dropping its pidfd or sweeping ambiguous scratch is not recovery. */
        pam_syslog(pamh, LOG_ERR, "onpc.pam kiosk execution-boundary cleanup=failed");
        return;
    }
    free(t);
}

static int
kiosk_confinement(pam_handle_t *pamh)
{
    const char *username = NULL, *service = NULL, *role = NULL, *stage = "identity";
    struct stat info;
    const void *existing = NULL;
    struct kiosk_admission_transaction *transaction = NULL;
    uint64_t now, deadline;
    int fd = -1, result = PAM_SESSION_ERR;
    if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || username == NULL)
        return PAM_USER_UNKNOWN;
    if (strcmp(username, KIOSK_ACCOUNT_NAME) != 0)
        return PAM_SUCCESS;
    stage = "admission";
    if (kiosk_admission(pamh, username) != PAM_SUCCESS)
        goto done;
    if (pam_get_item(pamh, PAM_SERVICE, (const void **) &service) != PAM_SUCCESS ||
        service == NULL || geteuid() != 0)
        goto done;
    if (strcmp(service, "systemd-user") == 0)
        role = "manager";
    else if (strcmp(service, "gdm-password") == 0)
        role = "gate";
    else
        goto done;
    /* Repeated callbacks cannot allocate another generation or adopt a new
     * manager in this PAM handle, including after a failed attempt. */
    int previous = pam_get_data(pamh, KIOSK_TRANSACTION_DATA, &existing);
    if ((previous != PAM_NO_MODULE_DATA && previous != PAM_SUCCESS) || existing)
        goto done;
    if (kiosk_pin_now(&now) || now > UINT64_MAX - 60000000U)
        goto done;
    deadline = now + 60000000U;
    stage = "lock";
    fd = kiosk_private_lock_open(KIOSK_CONFINEMENT_LOCK, 0, 0);
    if (fd < 0 || fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_uid != 0 ||
        (info.st_mode & 07777) != 0600 || info.st_nlink != 1 ||
        flock(fd, LOCK_EX | LOCK_NB) != 0 ||
        kiosk_lock_identity(fd, KIOSK_CONFINEMENT_LOCK, 0) != 0)
        goto done;
    transaction = calloc(1, sizeof(*transaction));
    if (!transaction) goto done;
    kiosk_retained_startup_init(&transaction->retained);
    transaction->lock = fd; transaction->gate = !strcmp(role, "gate");
    if (pam_set_data(pamh, KIOSK_TRANSACTION_DATA, transaction, release_kiosk_transaction) != PAM_SUCCESS) {
        transaction->lock = -1; free(transaction); transaction = NULL; goto done;
    }
    fd = -1; /* The PAM-owned transaction retains unresolved cleanup and lock. */
    int admitted = transaction->gate ? kiosk_retained_startup_until(&transaction->retained, pamh,
            transaction->lock, kiosk_admission_fd(pamh), deadline) :
        kiosk_fresh_startup_until(&transaction->retained.common, pamh,
            transaction->lock, kiosk_admission_fd(pamh), deadline);
    struct kiosk_fresh_startup *s = &transaction->retained.common;
    stage = s->stage;
    if (!admitted) result = PAM_SUCCESS;
    if (kiosk_transaction_close(transaction)) {
        result = PAM_SESSION_ERR; stage = "cleanup";
        kiosk_failure(&s->cleanup_failure, "recovery", "unresolved", -1);
        pam_syslog(pamh, LOG_ERR, "onpc.pam kiosk execution-boundary cleanup=failed");
    }
    s->view.failure = s->failure;
    s->view.cleanup_failure = s->cleanup_failure;
    kiosk_native_diagnostic(pamh, &s->view, role);
done:
    if (fd >= 0)
        close(fd);
    pam_syslog(pamh, result == PAM_SUCCESS ? LOG_INFO : LOG_ERR,
               "onpc.pam kiosk execution-boundary outcome=%s stage=%s",
               result == PAM_SUCCESS ? "armed" : "denied", stage);
    return result;
}
