/* Private, bounded native probe protocol. This is not a policy receipt. */
#ifndef ONPC_EXECUTION_PROBE_PROTOCOL_H
#define ONPC_EXECUTION_PROBE_PROTOCOL_H

#include <errno.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define PROBE_FRAME_SIZE 40
#define PROBE_TIMEOUT_MS 2000
#define PROBE_FD 3
#define PROBE_EXIT 23

static inline int64_t probe_now(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0)
        return -1;
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static inline bool probe_id(const char *value) {
    if (!value || strlen(value) != 32)
        return false;
    bool nonzero = false;
    for (int i = 0; i < 32; i++) {
        if (!((value[i] >= '0' && value[i] <= '9') ||
              (value[i] >= 'a' && value[i] <= 'f')))
            return false;
        nonzero |= value[i] != '0';
    }
    return nonzero;
}

static inline void probe_frame(unsigned char *frame, char stage, const char *id) {
    memcpy(frame, "ONP1", 4);
    frame[4] = (unsigned char)stage;
    memset(frame + 5, 0, 3);
    memcpy(frame + 8, id, 32);
}

static inline bool probe_wait(int fd, short events, int64_t deadline) {
    for (;;) {
        int64_t now = probe_now();
        if (now < 0 || now >= deadline)
            return false;
        struct pollfd item = {.fd = fd, .events = events};
        int result = poll(&item, 1, (int)(deadline - now));
        if (result < 0 && errno == EINTR)
            continue;
        return result > 0 && !(item.revents & POLLNVAL);
    }
}

static inline bool probe_send(int fd, const unsigned char *frame, int64_t deadline) {
    size_t offset = 0;
    while (offset < PROBE_FRAME_SIZE) {
        if (!probe_wait(fd, POLLOUT, deadline))
            return false;
        ssize_t count = send(fd, frame + offset, PROBE_FRAME_SIZE - offset,
                             MSG_NOSIGNAL | MSG_DONTWAIT);
        if (count < 0 && (errno == EINTR || errno == EAGAIN))
            continue;
        if (count <= 0)
            return false;
        offset += (size_t)count;
    }
    return true;
}

/* Reject ancillary data and close every received descriptor even on truncation. */
static inline ssize_t probe_recv(int fd, unsigned char *data, size_t size) {
    union {
        struct cmsghdr alignment;
        unsigned char bytes[CMSG_SPACE(16 * sizeof(int))];
    } control;
    struct iovec vector = {.iov_base = data, .iov_len = size};
    struct msghdr message = {
        .msg_iov = &vector, .msg_iovlen = 1,
        .msg_control = control.bytes, .msg_controllen = sizeof(control.bytes),
    };
    ssize_t count = recvmsg(fd, &message, MSG_DONTWAIT | MSG_CMSG_CLOEXEC);
    if (count < 0)
        return count;
    bool ancillary = (message.msg_flags & (MSG_CTRUNC | MSG_TRUNC)) != 0;
    for (struct cmsghdr *item = CMSG_FIRSTHDR(&message); item;
         item = CMSG_NXTHDR(&message, item)) {
        ancillary = true;
        if (item->cmsg_level == SOL_SOCKET && item->cmsg_type == SCM_RIGHTS &&
            item->cmsg_len >= CMSG_LEN(0)) {
            size_t bytes = item->cmsg_len - CMSG_LEN(0);
            for (size_t offset = 0; offset + sizeof(int) <= bytes; offset += sizeof(int)) {
                int received;
                memcpy(&received, (unsigned char *)CMSG_DATA(item) + offset, sizeof(int));
                close(received);
            }
        }
    }
    if (ancillary) {
        errno = EPROTO;
        return -1;
    }
    return count;
}

/* Admission includes the sender's write EOF: extra/delayed frames cannot exec. */
static inline bool probe_admission(int fd, const char *id, int64_t deadline) {
    unsigned char expected[PROBE_FRAME_SIZE], received[PROBE_FRAME_SIZE + 1];
    probe_frame(expected, 'A', id);
    size_t offset = 0;
    for (;;) {
        if (!probe_wait(fd, POLLIN, deadline))
            return false;
        ssize_t count = probe_recv(fd, received + offset, sizeof(received) - offset);
        if (count < 0 && (errno == EINTR || errno == EAGAIN))
            continue;
        if (count < 0)
            return false;
        if (count == 0)
            return offset == PROBE_FRAME_SIZE &&
                   memcmp(received, expected, PROBE_FRAME_SIZE) == 0;
        offset += (size_t)count;
        if (offset > PROBE_FRAME_SIZE)
            return false;
    }
}

static inline bool probe_peer(int fd) {
    struct ucred peer;
    socklen_t size = sizeof(peer);
    return getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &peer, &size) == 0 &&
           size == sizeof(peer) && peer.uid == geteuid();
}
#endif
