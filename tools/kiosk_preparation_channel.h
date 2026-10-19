#ifndef ONPC_KIOSK_PREPARATION_CHANNEL_H
#define ONPC_KIOSK_PREPARATION_CHANNEL_H
/* Parent-side transport; never call in a post-fork PAM child.
 * Native must independently acquire/verify every object, receipt, source clone,
 * trust/label/content and required closure before capture. This transport proves
 * descriptor identity, not recursive clone coverage or receipt semantics.
 *
 * Launch is deliberately separate: one identity-owned bounded exec helper, a
 * sanitized fixed executable/environment, and no inherited setup FDs except its
 * explicit channel duplicate and separately verified lock/lease duplicates.
 * Only that child channel duplicate may lose CLOEXEC. Parent retains originals,
 * closes both endpoints on launch failure, closes its child endpoint on success,
 * and reaps/cleans the exact child within the same absolute transaction deadline.
 * No setup descriptor may reach the session payload. Helper output must be
 * independently checked against these acquisitions before binding/publication.
 * Caller starts the existing maximum 60-second transaction deadline once, uses
 * its CLOCK_MONOTONIC nanoseconds throughout, and exclusively owns the borrowed
 * descriptor table entries until send completes. Capture creates no new budget.
 * Other native guards use absolute microseconds: convert that original deadline
 * to nanoseconds by checked multiplication by 1000, never by sampling a new
 * start time. Reject conversion overflow. Initial V is zero (not finalized).
 */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define KIOSK_PREPARATION_MAX_FDS 5
#define KIOSK_PREPARATION_HEADER 96
#define KIOSK_PREPARATION_ID_WORDS 12
#define KIOSK_PREPARATION_BYTES (KIOSK_PREPARATION_HEADER + KIOSK_PREPARATION_MAX_FDS * 96)
/* Initial: material receipt, copy directory, fresh target root.
 * Retained: material receipt, selected view receipt, recursive /usr clone,
 *           copy directory, fresh target root. No variable paths/indices here;
 * finite vendor/source indices belong to the independently checked receipts. */
struct kiosk_preparation_input {
    unsigned char packet[KIOSK_PREPARATION_BYTES];
    size_t bytes;
    unsigned count;
};

static void kiosk_preparation_u64(unsigned char *out, uint64_t value)
{
    for (unsigned i = 0; i < 8; i++) out[i] = (unsigned char) (value >> (56 - i * 8));
}

static int kiosk_preparation_before(uint64_t deadline_ns)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return -1;
    uint64_t ns = (uint64_t) now.tv_sec * 1000000000ULL + (uint64_t) now.tv_nsec;
    if (!deadline_ns || ns >= deadline_ns) { errno = ETIMEDOUT; return -1; }
    return 0;
}

static int kiosk_preparation_identity(int fd, unsigned char out[96], int regular)
{
    struct stat before, after;
    char path[64], line[256];
    unsigned long long mount = 0;
    int found = 0, flags = fcntl(fd, F_GETFL), fdflags = fcntl(fd, F_GETFD);
    if (flags < 0 || fdflags < 0 || !(fdflags & FD_CLOEXEC) ||
        (flags & O_ACCMODE) != O_RDONLY || (regular && (flags & O_PATH)) || fstat(fd, &before) != 0 ||
        (regular ? !S_ISREG(before.st_mode) : !S_ISDIR(before.st_mode))) return -1;
    snprintf(path, sizeof(path), "/proc/self/fdinfo/%d", fd);
    int info = open(path, O_RDONLY | O_CLOEXEC);
    if (info < 0) return -1;
    FILE *stream = fdopen(info, "r");
    if (!stream) { close(info); return -1; }
    while (fgets(line, sizeof(line), stream)) {
        if (sscanf(line, "mnt_id: %llu", &mount) == 1) found++;
    }
    int failed = ferror(stream); fclose(stream);
    if (failed || found != 1 || fstat(fd, &after) != 0) return -1;
    /* Linux may report mnt_id 0 for the internal shmem mount backing a
     * memfd. This is record identity only, never source/mount authority. The
     * sole zero-ID exception is an anonymous, completely sealed regular
     * record; named files and all source/target directories still need a
     * positive mount identity. Stable inode metadata remains checked below. */
    if (!mount) {
        int seals = regular && before.st_nlink == 0 ? fcntl(fd, F_GET_SEALS) : -1;
        int required = F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL;
        if (seals < 0 || (seals & required) != required) return -1;
    }
    uint64_t a[] = {before.st_dev, before.st_ino, before.st_mode, before.st_uid,
        before.st_gid, before.st_size, before.st_nlink, before.st_mtim.tv_sec,
        before.st_mtim.tv_nsec, before.st_ctim.tv_sec, before.st_ctim.tv_nsec, mount};
    uint64_t b[] = {after.st_dev, after.st_ino, after.st_mode, after.st_uid,
        after.st_gid, after.st_size, after.st_nlink, after.st_mtim.tv_sec,
        after.st_mtim.tv_nsec, after.st_ctim.tv_sec, after.st_ctim.tv_nsec, mount};
    if (memcmp(a, b, sizeof(a))) { errno = ESTALE; return -1; }
    for (unsigned i = 0; i < KIOSK_PREPARATION_ID_WORDS; i++) kiosk_preparation_u64(out + 8 * i, a[i]);
    return 0;
}

/* acquisition 1=initial, 2=retained; role 1=manager, 2=gate;
 * backend 1=apparmor, 2=selinux. M/V are raw SHA-256, never path strings.
 * Capture borrows native-owned descriptors, never adopts or closes them. */
static int kiosk_preparation_capture(struct kiosk_preparation_input *input,
    unsigned acquisition, unsigned role, unsigned backend, const unsigned char material[32],
    const unsigned char view[32], const int *fds, unsigned count, uint64_t deadline_ns)
{
    if (!input) return -1;
    memset(input, 0, sizeof(*input));
    if (!fds || !material || !view || acquisition < 1 || acquisition > 2 ||
        role != acquisition || backend < 1 || backend > 2 ||
        count != (acquisition == 1 ? 3U : 5U) || kiosk_preparation_before(deadline_ns)) return -1;
    if (acquisition == 1) {
        unsigned char empty[32] = {0};
        if (memcmp(view, empty, sizeof(empty))) return -1;
    }
    memcpy(input->packet, "ONPCPRE1", 8);
    input->packet[8] = (unsigned char) acquisition;
    input->packet[9] = (unsigned char) role;
    input->packet[10] = (unsigned char) backend;
    input->packet[11] = (unsigned char) count;
    kiosk_preparation_u64(input->packet + 16, deadline_ns);
    memcpy(input->packet + 24, material, 32); memcpy(input->packet + 56, view, 32);
    for (unsigned i = 0; i < count; i++) {
        int regular = i == 0 || (acquisition == 2 && i == 1);
        if (kiosk_preparation_identity(fds[i], input->packet + 96 + 96 * i, regular)) return -1;
        for (unsigned j = 0; j < i; j++)
            if (!memcmp(input->packet + 96 + 96 * i, input->packet + 96 + 96 * j, 16)) return -1;
    }
    if (kiosk_preparation_before(deadline_ns)) return -1;
    input->count = count; input->bytes = 96 + 96 * count;
    return 0;
}

static int kiosk_preparation_socketpair(int channels[2])
{
    return socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, channels);
}

/* A successful send transfers kernel duplicates, not ownership of originals.
 * MSG_DONTWAIT plus poll share the caller's deadline; EINTR never renews it. */
static int kiosk_preparation_send_packet(int channel, const struct kiosk_preparation_input *input,
    const int *fds, uint64_t deadline_ns)
{
    int type; socklen_t length = sizeof(type);
    struct sockaddr_un address;
    socklen_t address_length = sizeof(address);
    if (getsockopt(channel, SOL_SOCKET, SO_TYPE, &type, &length) || type != SOCK_SEQPACKET ||
        getsockname(channel, (struct sockaddr *) &address, &address_length) ||
        address.sun_family != AF_UNIX || address_length != sizeof(sa_family_t) ||
        getpeername(channel, (struct sockaddr *) &address, &address_length) ||
        address.sun_family != AF_UNIX || address_length != sizeof(sa_family_t)) return -1;
    union { struct cmsghdr alignment; char bytes[CMSG_SPACE(sizeof(int) * KIOSK_PREPARATION_MAX_FDS)]; } control = {0};
    struct iovec io = {.iov_base = (void *) input->packet, .iov_len = input->bytes};
    struct msghdr message = {.msg_iov = &io, .msg_iovlen = 1, .msg_control = control.bytes,
        .msg_controllen = CMSG_SPACE(sizeof(int) * input->count)};
    struct cmsghdr *rights = CMSG_FIRSTHDR(&message);
    rights->cmsg_level = SOL_SOCKET; rights->cmsg_type = SCM_RIGHTS;
    rights->cmsg_len = CMSG_LEN(sizeof(int) * input->count);
    memcpy(CMSG_DATA(rights), fds, sizeof(int) * input->count);
    for (;;) {
        if (kiosk_preparation_before(deadline_ns)) return -1;
        for (unsigned i = 0; i < input->count; i++) {
            unsigned char identity[96];
            int phase = input->packet[7] == '2', regular;
            if (!phase) regular = i == 0 || (input->packet[8] == 2 && i == 1);
            else regular = input->packet[8] == 1 ||
                (input->packet[8] == 2 && input->packet[9] == 2 && (i == 0 || i == 2)) ||
                (input->packet[8] == 3 && i == 0);
            if (kiosk_preparation_identity(fds[i], identity, regular) ||
                memcmp(identity, input->packet + 96 + 96 * i, sizeof(identity))) return -1;
        }
        ssize_t sent = sendmsg(channel, &message, MSG_NOSIGNAL | MSG_DONTWAIT);
        if (sent >= 0) return sent == (ssize_t) input->bytes &&
            kiosk_preparation_before(deadline_ns) == 0 ? 0 : -1;
        if (errno == EINTR) continue;
        if (errno != EAGAIN && errno != EWOULDBLOCK) return -1;
        struct timespec now;
        if (clock_gettime(CLOCK_MONOTONIC, &now)) return -1;
        uint64_t ns = (uint64_t) now.tv_sec * 1000000000ULL + now.tv_nsec;
        if (ns >= deadline_ns) { errno = ETIMEDOUT; return -1; }
        uint64_t ms = (deadline_ns - ns + 999999ULL) / 1000000ULL;
        struct pollfd waiting = {.fd = channel, .events = POLLOUT};
        int ready = poll(&waiting, 1, ms > 2147483647ULL ? 2147483647 : (int) ms);
        if (ready < 0 && errno != EINTR) return -1;
    }
}

static inline int kiosk_preparation_send(int channel, const struct kiosk_preparation_input *input,
    const int *fds, uint64_t deadline_ns)
{
    struct kiosk_preparation_input checked;
    unsigned char deadline[8]; kiosk_preparation_u64(deadline, deadline_ns);
    if (!input || !fds || memcmp(input->packet + 16, deadline, 8) ||
        kiosk_preparation_capture(&checked, input->packet[8], input->packet[9], input->packet[10],
            input->packet + 24, input->packet + 56, fds, input->count, deadline_ns) ||
        input->bytes != checked.bytes || memcmp(input->packet, checked.packet, checked.bytes)) return -1;
    return kiosk_preparation_send_packet(channel, input, fds, deadline_ns);
}

/* Closed v2 exchange: measure(1), select(2), intended result(3).
 * Role: manager(1), gate(2). Backend: apparmor(1), selinux(2).
 * Phase 1: material receipt, configuration, sealed account record (regular files).
 * Phase 2 manager: fresh target directory.
 * Phase 2 gate: original V receipt, verified /usr clone, source-slot file,
 *               fresh target directory.
 * Phase 3 manager: intended result receipt, child-created copy directory.
 * Phase 3 gate: intended result receipt. The native caller completes V/I.
 */
static unsigned kiosk_preparation_phase_count(unsigned phase, unsigned role)
{
    if (role < 1 || role > 2) return 0;
    if (phase == 1) return 3;
    if (phase == 2) return role == 1 ? 1 : 4;
    if (phase == 3) return role == 1 ? 2 : 1;
    return 0;
}

static int kiosk_preparation_phase_regular(unsigned phase, unsigned role, unsigned index)
{
    return phase == 1 || (phase == 2 && role == 2 && (index == 0 || index == 2)) ||
        (phase == 3 && index == 0);
}

static int kiosk_preparation_capture_phase(struct kiosk_preparation_input *input,
    unsigned phase, unsigned role, unsigned backend, const unsigned char material[32],
    const unsigned char view[32], const int *fds, unsigned count, uint64_t deadline_ns)
{
    unsigned char empty[32] = {0};
    if (!input) return -1;
    memset(input, 0, sizeof(*input));
    if (!fds || !material || !view || backend < 1 || backend > 2 ||
        !count || count != kiosk_preparation_phase_count(phase, role) ||
        ((phase == 1 || role == 1) && memcmp(view, empty, 32)) ||
        kiosk_preparation_before(deadline_ns)) return -1;
    memcpy(input->packet, "ONPCPRE2", 8);
    input->packet[8] = (unsigned char) phase; input->packet[9] = (unsigned char) role;
    input->packet[10] = (unsigned char) backend; input->packet[11] = (unsigned char) count;
    kiosk_preparation_u64(input->packet + 16, deadline_ns);
    memcpy(input->packet + 24, material, 32); memcpy(input->packet + 56, view, 32);
    for (unsigned i = 0; i < count; i++) {
        if (kiosk_preparation_identity(fds[i], input->packet + 96 + 96 * i,
                kiosk_preparation_phase_regular(phase, role, i))) return -1;
        for (unsigned j = 0; j < i; j++)
            if (!memcmp(input->packet + 96 + 96 * i, input->packet + 96 + 96 * j, 16)) return -1;
    }
    for (unsigned i = 0; i < count; i++) {
        unsigned char check[96];
        if (kiosk_preparation_identity(fds[i], check, kiosk_preparation_phase_regular(phase, role, i)) ||
            memcmp(check, input->packet + 96 + 96 * i, sizeof(check))) return -1;
    }
    if (kiosk_preparation_before(deadline_ns)) return -1;
    input->count = count; input->bytes = 96 + 96 * count;
    return 0;
}

static int kiosk_preparation_send_phase(int channel, const struct kiosk_preparation_input *input,
    const int *fds, uint64_t deadline_ns)
{
    struct kiosk_preparation_input checked;
    unsigned char deadline[8]; kiosk_preparation_u64(deadline, deadline_ns);
    if (!input || !fds || memcmp(input->packet + 16, deadline, 8) ||
        kiosk_preparation_capture_phase(&checked, input->packet[8], input->packet[9], input->packet[10],
            input->packet + 24, input->packet + 56, fds, input->count, deadline_ns) ||
        input->bytes != checked.bytes || memcmp(input->packet, checked.packet, checked.bytes)) return -1;
    return kiosk_preparation_send_packet(channel, input, fds, deadline_ns);
}

struct kiosk_preparation_response {
    struct kiosk_preparation_input input;
    int fds[KIOSK_PREPARATION_MAX_FDS];
    unsigned count;
};

/* Closed canonical account snapshot from the one bounded NSS helper. Native
 * independently checks the package-owned UID marker before using this identity.
 * Primary GID is included in the sorted, unique supplementary set. No NSS or
 * account-path lookup occurs here; pread preserves the borrowed offset. The
 * ASCII record is ONPC-KIOSK-ACCOUNT TAB 1 TAB UID TAB GID TAB COUNT LF,
 * followed by COUNT canonical decimal GIDs, each terminated by LF. */
#define KIOSK_PREPARATION_ACCOUNT_GROUPS 128
struct kiosk_preparation_account {
    uid_t uid;
    gid_t gid, groups[KIOSK_PREPARATION_ACCOUNT_GROUPS];
    unsigned count;
};

static int kiosk_preparation_account_number(const char **cursor, const char *end,
    char delimiter, uint32_t *value)
{
    const char *p = *cursor, *start = p;
    uint64_t number = 0;
    while (p < end && *p >= '0' && *p <= '9') {
        number = number * 10U + (unsigned) (*p++ - '0');
        if (number >= UINT32_MAX) return -1;
    }
    if (p == start || (p - start > 1 && *start == '0') || p == end || *p != delimiter) return -1;
    *value = (uint32_t) number; *cursor = p + 1;
    return 0;
}

static int kiosk_preparation_account_read(int fd, uint64_t deadline_ns,
    struct kiosk_preparation_account *account)
{
    char bytes[64 + 11 * KIOSK_PREPARATION_ACCOUNT_GROUPS];
    const char prefix[] = "ONPC-KIOSK-ACCOUNT\t1\t";
    struct kiosk_preparation_account checked = {0};
    struct stat info;
    unsigned char before[96], after[96];
    int required = F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL;
    int seals = fcntl(fd, F_GET_SEALS);
    if (!account || kiosk_preparation_before(deadline_ns) ||
        kiosk_preparation_identity(fd, before, 1) || fstat(fd, &info) || info.st_nlink != 0 ||
        info.st_size <= 0 || info.st_size > (off_t) sizeof(bytes) ||
        seals < 0 || (seals & required) != required) return -1;
    size_t size = (size_t) info.st_size;
    /* One tiny sealed memfd record fits the fixed buffer. Require a complete
     * read, never a prefix; a fixed syscall bound also remains transparent to
     * the package compiler's fortified object-size analysis after inlining. */
    for (;;) {
        if (kiosk_preparation_before(deadline_ns)) return -1;
        ssize_t n = pread(fd, bytes, sizeof(bytes), 0);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0 || (size_t)n != size) return -1;
        break;
    }
    if (size < sizeof(prefix) - 1 || memcmp(bytes, prefix, sizeof(prefix) - 1)) return -1;
    const char *p = bytes + sizeof(prefix) - 1, *end = bytes + size;
    uint32_t uid, gid, count, group;
    if (kiosk_preparation_account_number(&p, end, '\t', &uid) || !uid ||
        kiosk_preparation_account_number(&p, end, '\t', &gid) || !gid ||
        kiosk_preparation_account_number(&p, end, '\n', &count) ||
        !count || count > KIOSK_PREPARATION_ACCOUNT_GROUPS ||
        (uint64_t) (uid_t) uid != uid || (uint64_t) (gid_t) gid != gid) return -1;
    checked.uid = (uid_t) uid; checked.gid = (gid_t) gid; checked.count = count;
    int primary = 0;
    for (unsigned i = 0; i < count; i++) {
        if (kiosk_preparation_account_number(&p, end, '\n', &group) || !group ||
            (uint64_t) (gid_t) group != group || (i && group <= checked.groups[i - 1])) return -1;
        checked.groups[i] = (gid_t) group;
        if (group == gid) primary = 1;
    }
    if (p != end || !primary || kiosk_preparation_identity(fd, after, 1) ||
        memcmp(before, after, sizeof(before)) || kiosk_preparation_before(deadline_ns)) return -1;
    *account = checked;
    return 0;
}

static void kiosk_preparation_response_init(struct kiosk_preparation_response *response)
{
    memset(response, 0, sizeof(*response));
    for (unsigned i = 0; i < KIOSK_PREPARATION_MAX_FDS; i++) response->fds[i] = -1;
}

static void kiosk_preparation_response_close(struct kiosk_preparation_response *response)
{
    if (!response) return;
    for (unsigned i = 0; i < response->count; i++) if (response->fds[i] >= 0) close(response->fds[i]);
    kiosk_preparation_response_init(response);
}

/* response must be initialized and empty. Success owns only SCM_RIGHTS
 * duplicates; close it on every outcome after its last independent check.
 * Only measurement permits backend=0 and material/view=NULL for discovery.
 * Discovery does not authenticate config or material: callers must independently
 * attest current inputs and compare the exact payload before selection.
 */
static int kiosk_preparation_receive_phase(int channel, unsigned phase, unsigned role,
    unsigned backend, const unsigned char *material, const unsigned char *view,
    uint64_t deadline_ns, struct kiosk_preparation_response *response)
{
    struct kiosk_preparation_response received; kiosk_preparation_response_init(&received);
    struct kiosk_preparation_input checked;
    int result = -1, type, invalid = 0;
    unsigned count = kiosk_preparation_phase_count(phase, role);
    socklen_t length = sizeof(type), address_length = sizeof(struct sockaddr_un);
    struct sockaddr_un address;
    if (!response || response->count || !count ||
        (phase != 1 && (!backend || !material || !view)) || backend > 2 ||
        getsockopt(channel, SOL_SOCKET, SO_TYPE, &type, &length) || type != SOCK_SEQPACKET ||
        getsockname(channel, (struct sockaddr *) &address, &address_length) ||
        address.sun_family != AF_UNIX || address_length != sizeof(sa_family_t) ||
        getpeername(channel, (struct sockaddr *) &address, &address_length) ||
        address.sun_family != AF_UNIX || address_length != sizeof(sa_family_t)) return -1;
    union { struct cmsghdr alignment; char bytes[CMSG_SPACE(sizeof(int) * KIOSK_PREPARATION_MAX_FDS)]; } control;
    struct iovec io = {.iov_base = received.input.packet, .iov_len = sizeof(received.input.packet)};
    struct msghdr message;
    ssize_t bytes;
    for (;;) {
        if (kiosk_preparation_before(deadline_ns)) goto done;
        memset(&message, 0, sizeof(message)); memset(&control, 0, sizeof(control));
        message.msg_iov = &io; message.msg_iovlen = 1;
        message.msg_control = control.bytes; message.msg_controllen = sizeof(control.bytes);
        bytes = recvmsg(channel, &message, MSG_CMSG_CLOEXEC | MSG_DONTWAIT);
        if (bytes >= 0) break;
        if (errno == EINTR) continue;
        if (errno != EAGAIN && errno != EWOULDBLOCK) goto done;
        struct timespec now;
        if (clock_gettime(CLOCK_MONOTONIC, &now)) goto done;
        uint64_t ns = (uint64_t) now.tv_sec * 1000000000ULL + now.tv_nsec;
        if (ns >= deadline_ns) { errno = ETIMEDOUT; goto done; }
        uint64_t ms = (deadline_ns - ns + 999999ULL) / 1000000ULL;
        struct pollfd waiting = {.fd = channel, .events = POLLIN};
        if (poll(&waiting, 1, ms > 2147483647ULL ? 2147483647 : (int) ms) < 0 && errno != EINTR) goto done;
    }
    unsigned records = 0;
    for (struct cmsghdr *rights = CMSG_FIRSTHDR(&message); rights; rights = CMSG_NXTHDR(&message, rights)) {
        records++;
        if (rights->cmsg_level != SOL_SOCKET || rights->cmsg_type != SCM_RIGHTS ||
            rights->cmsg_len < CMSG_LEN(0)) { invalid = 1; continue; }
        size_t size = rights->cmsg_len - CMSG_LEN(0);
        if (size % sizeof(int)) invalid = 1;
        for (size_t i = 0; i < size / sizeof(int); i++) {
            int fd; memcpy(&fd, (char *) CMSG_DATA(rights) + i * sizeof(int), sizeof(fd));
            if (received.count < KIOSK_PREPARATION_MAX_FDS) received.fds[received.count++] = fd;
            else { close(fd); invalid = 1; }
        }
    }
    if (invalid || records != 1 || message.msg_flags & (MSG_TRUNC | MSG_CTRUNC) ||
        received.count != count || bytes != (ssize_t) (96 + 96 * count) ||
        memcmp(received.input.packet, "ONPCPRE2", 8) || received.input.packet[8] != phase ||
        received.input.packet[9] != role ||
        (backend && received.input.packet[10] != backend) ||
        (material && memcmp(received.input.packet + 24, material, 32)) ||
        (view && memcmp(received.input.packet + 56, view, 32))) goto done;
    if (kiosk_preparation_capture_phase(&checked, phase, role, received.input.packet[10],
            received.input.packet + 24, received.input.packet + 56, received.fds, received.count, deadline_ns) ||
        memcmp(received.input.packet, checked.packet, checked.bytes)) goto done;
    received.input = checked;
    if (phase == 1) {
        struct kiosk_preparation_account account;
        if (kiosk_preparation_account_read(received.fds[2], deadline_ns, &account)) goto done;
    }
    *response = received; kiosk_preparation_response_init(&received);
    result = 0;
done:
    kiosk_preparation_response_close(&received);
    return result;
}
#endif
