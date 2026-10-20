/* One bounded preparation process for the PAM coordinator's duplex channel.
 * Include after kiosk_preparation_channel.h. This is not an admission decision:
 * the caller still owns material/receipt validation, locks and all source FDs.
 * The child receives only channel/lock/lease duplicates; the parent keeps its
 * originals. No allocator, parser, logger or stdio runs in the post-clone child.
 */
#ifndef ONPC_KIOSK_PREPARATION_CHILD_H
#define ONPC_KIOSK_PREPARATION_CHILD_H
#include <linux/sched.h>
#include <signal.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/wait.h>

#ifndef KIOSK_CONFINEMENT_PREPARE
#define KIOSK_CONFINEMENT_PREPARE "/usr/libexec/oh-no-parent-control-kiosk-confinement"
#endif
#ifndef KIOSK_PREPARATION_LOCK_OWNER
#define KIOSK_PREPARATION_LOCK_OWNER 0
#endif

struct kiosk_preparation_child {
    int channel, pidfd, started, reaped;
    unsigned role, phase, backend, refusal;
    unsigned char material[32], view[32];
    uint64_t deadline_ns;
    struct kiosk_preparation_account account;
};

static void kiosk_preparation_child_init(struct kiosk_preparation_child *child)
{
    memset(child, 0, sizeof(*child));
    child->channel = child->pidfd = -1;
}

/* The transaction starts elsewhere, once. Conversion never renews it. */
static int kiosk_preparation_deadline_ns(uint64_t deadline_us, uint64_t *deadline_ns)
{
    if (!deadline_ns || !deadline_us || deadline_us > UINT64_MAX / 1000U) return -1;
    *deadline_ns = deadline_us * 1000U;
    return kiosk_preparation_before(*deadline_ns);
}

static int kiosk_preparation_lease(int fd)
{
    struct stat info;
    int flags = fcntl(fd, F_GETFD);
    return flags >= 0 && (flags & FD_CLOEXEC) && fstat(fd, &info) == 0 &&
        S_ISREG(info.st_mode) && info.st_uid == KIOSK_PREPARATION_LOCK_OWNER && (info.st_mode & 07777) == 0600 &&
        info.st_nlink == 1 ? 0 : -1;
}

/* Caller must check named lock identities and ownership before and after this
 * operation. Atomically acquire a pidfd, with no numeric-PID signal fallback.
 * The private clone avoids ordinary pre-exec SIGCHLD reapers. __WALL below also
 * handles Linux resetting the child's exit signal during exec.
 */
static int kiosk_preparation_launch(struct kiosk_preparation_child *child,
    const char *role, int lock, int lease, uint64_t deadline_us)
{
    int sockets[2] = {-1, -1}, explicit_fds[4] = {-1, -1, -1, -1}, null = -1;
    char deadline[32];
    char *args[] = {(char *) KIOSK_CONFINEMENT_PREPARE, (char *) "--native-channel",
        (char *) role, (char *) "3", deadline, NULL};
    char *env[] = {(char *) "PATH=/usr/sbin:/usr/bin:/sbin:/bin", (char *) "LC_ALL=C", NULL};
    pid_t parent = getpid(), spawned;
    int result = -1;
    if (!child || child->started || child->pidfd >= 0 || child->channel >= 0 ||
        !role || (strcmp(role, "manager") && strcmp(role, "gate")) ||
        kiosk_preparation_deadline_ns(deadline_us, &child->deadline_ns) ||
        lock == lease || kiosk_preparation_lease(lock) || kiosk_preparation_lease(lease)) return -1;
    struct stat locked, admitted;
    if (fstat(lock, &locked) || fstat(lease, &admitted) ||
        (locked.st_dev == admitted.st_dev && locked.st_ino == admitted.st_ino)) return -1;
    struct timespec observed;
    if (clock_gettime(CLOCK_MONOTONIC, &observed)) return -1;
    uint64_t now = (uint64_t) observed.tv_sec * 1000000000ULL + observed.tv_nsec;
    if (child->deadline_ns - now > 60000000000ULL) return -1;
    /* Closed stdio can otherwise be reused by a setup open. Never inherit an
     * unclassified proc/root/bus FD in slots 0..2. The parent reports bounded
     * helper failures through the checked channel and native diagnostics. */
    null = open("/dev/null", O_RDWR | O_NOFOLLOW | O_CLOEXEC);
    struct stat null_info;
    if (null < 0 || fstat(null, &null_info) || !S_ISCHR(null_info.st_mode) ||
        null_info.st_uid != 0 || null_info.st_rdev != makedev(1, 3)) goto done;
    int length = snprintf(deadline, sizeof(deadline), "%llu", (unsigned long long) child->deadline_ns);
    if (length <= 0 || length >= (int) sizeof(deadline) || kiosk_preparation_socketpair(sockets)) goto done;
    int inputs[] = {sockets[1], lock, lease, null};
    for (unsigned i = 0; i < 4; i++)
        if ((explicit_fds[i] = fcntl(inputs[i], F_DUPFD_CLOEXEC, 6)) < 0) goto done;
    if (kiosk_preparation_before(child->deadline_ns)) goto done;
    struct clone_args clone = {.flags = CLONE_PIDFD | CLONE_CLEAR_SIGHAND,
        .pidfd = (uintptr_t) &child->pidfd};
    spawned = (pid_t) syscall(SYS_clone3, &clone, sizeof(clone));
    if (spawned == 0) {
        if (prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != parent) _exit(127);
        for (int i = 0; i < 3; i++)
            if (dup2(explicit_fds[3], i) < 0) _exit(127);
        for (unsigned i = 0; i < 3; i++)
            if (dup2(explicit_fds[i], (int) i + 3) < 0) _exit(127);
        if (syscall(SYS_close_range, 6U, ~0U, 0U)) _exit(127);
        execve(KIOSK_CONFINEMENT_PREPARE, args, env);
        _exit(127);
    }
    if (spawned < 0) goto done;
    child->started = 1;
    child->role = !strcmp(role, "manager") ? 1 : 2;
    child->phase = 1;
    child->channel = sockets[0]; sockets[0] = -1;
    result = 0;
done:
    for (unsigned i = 0; i < 4; i++) if (explicit_fds[i] >= 0) close(explicit_fds[i]);
    for (unsigned i = 0; i < 2; i++) if (sockets[i] >= 0) close(sockets[i]);
    if (null >= 0) close(null);
    return result;
}

/* Each exchange operation poisons the state before I/O. Failure requires exact
 * child cancellation/reaping, never a replacement helper or renewed deadline.
 * Measurement is discovery only; native independently verifies its assertions
 * before select. The checked selection must retain that exact M/backend.
 */
static int kiosk_preparation_child_measurement(struct kiosk_preparation_child *child,
    unsigned role, struct kiosk_preparation_response *response)
{
    if (!child || !child->started || child->reaped || child->channel < 0 ||
        child->phase != 1 || role != child->role) return -1;
    child->phase = 0;
    int received = kiosk_preparation_receive_phase(child->channel, 1, role, 0, NULL, NULL,
        child->deadline_ns, response);
    if (received) {
        if (received == -2) child->refusal = response->refusal;
        return -1;
    }
    if (kiosk_preparation_account_read(response->fds[2], child->deadline_ns, &child->account)) {
        kiosk_preparation_response_close(response);
        return -1;
    }
    child->backend = response->input.packet[10];
    memcpy(child->material, response->input.packet + 24, 32);
    child->phase = 2;
    return 0;
}

static int kiosk_preparation_child_select(struct kiosk_preparation_child *child,
    unsigned role, unsigned backend, const unsigned char material[32], const unsigned char view[32],
    const int *fds, unsigned count)
{
    struct kiosk_preparation_input input;
    if (!child || !child->started || child->reaped || child->channel < 0 ||
        child->phase != 2 || role != child->role) return -1;
    child->phase = 0;
    if (!material || !view || backend != child->backend || memcmp(material, child->material, 32) ||
        kiosk_preparation_capture_phase(&input, 2, role, backend, material, view, fds, count,
            child->deadline_ns) || kiosk_preparation_send_phase(child->channel, &input, fds,
            child->deadline_ns)) return -1;
    memcpy(child->view, view, 32);
    child->phase = 3;
    return 0;
}

static int kiosk_preparation_child_result(struct kiosk_preparation_child *child,
    unsigned role, unsigned backend, const unsigned char material[32], const unsigned char view[32],
    struct kiosk_preparation_response *response)
{
    if (!child || !child->started || child->reaped || child->channel < 0 ||
        child->phase != 3 || role != child->role) return -1;
    child->phase = 0;
    if (!material || !view || backend != child->backend || memcmp(material, child->material, 32) ||
        memcmp(view, child->view, 32) || kiosk_preparation_receive_phase(child->channel, 3, role,
            backend, material, view, child->deadline_ns, response)) return -1;
    child->phase = 4;
    return 0;
}

static void kiosk_preparation_child_channel_close(struct kiosk_preparation_child *child)
{
    if (child->channel >= 0) { close(child->channel); child->channel = -1; }
}

/* A finished helper is a required observation, never proof of its output.
 * ECHILD means a competing reaper consumed status and refuses admission.
 * Deadline failure keeps the atomically recorded pidfd for explicit recovery;
 * a later recovery budget must never be used to revive failed admission.
 */
static int kiosk_preparation_finish(struct kiosk_preparation_child *child)
{
    if (!child || !child->started || child->pidfd < 0 || child->reaped) return -1;
    for (;;) {
        siginfo_t status = {0};
        int waited = waitid(P_PIDFD, (id_t) child->pidfd, &status, WEXITED | WNOHANG | __WALL);
        if (waited == 0 && status.si_pid) {
            child->reaped = 1;
            close(child->pidfd); child->pidfd = -1;
            kiosk_preparation_child_channel_close(child);
            return status.si_code == CLD_EXITED && status.si_status == 0 &&
                kiosk_preparation_before(child->deadline_ns) == 0 ? 0 : -1;
        }
        if (waited < 0 && errno != EINTR) {
            if (errno == ECHILD) {
                child->reaped = 1; close(child->pidfd); child->pidfd = -1;
            }
            kiosk_preparation_child_channel_close(child);
            return -1;
        }
        if (kiosk_preparation_before(child->deadline_ns)) {
            (void) syscall(SYS_pidfd_send_signal, child->pidfd, SIGKILL, NULL, 0);
            kiosk_preparation_child_channel_close(child);
            return -1;
        }
        struct timespec pause = {.tv_nsec = 1000000}; nanosleep(&pause, NULL);
    }
}

/* Cancellation/recovery only. Never signals the manager or any outside PID. */
static int kiosk_preparation_cancel_until(struct kiosk_preparation_child *child, uint64_t deadline_ns)
{
    if (!child) return -1;
    kiosk_preparation_child_channel_close(child);
    if (child->pidfd < 0) return !child->started || child->reaped ? 0 : -1;
    if (syscall(SYS_pidfd_send_signal, child->pidfd, SIGKILL, NULL, 0) && errno != ESRCH) return -1;
    for (;;) {
        siginfo_t status = {0};
        int waited = waitid(P_PIDFD, (id_t) child->pidfd, &status, WEXITED | WNOHANG | __WALL);
        if ((waited == 0 && status.si_pid) || (waited < 0 && errno == ECHILD)) {
            child->reaped = 1; close(child->pidfd); child->pidfd = -1; return 0;
        }
        if (waited < 0 && errno != EINTR) return -1;
        if (kiosk_preparation_before(deadline_ns)) return -1;
        struct timespec pause = {.tv_nsec = 1000000}; nanosleep(&pause, NULL);
    }
}
#endif
