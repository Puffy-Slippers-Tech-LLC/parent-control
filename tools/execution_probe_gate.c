#define _GNU_SOURCE
#include "execution_probe_protocol.h"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/un.h>

/* Tests relocate only the private runtime root; there is no runtime override. */
#ifndef PROBE_RUNTIME_ROOT
#define PROBE_RUNTIME_ROOT "/run/oh-no-parent-control/probes"
#endif

static bool private_directory(const char *path) {
    struct stat info;
    return lstat(path, &info) == 0 && S_ISDIR(info.st_mode) &&
           info.st_uid == geteuid() && (info.st_mode & 0777) == 0700;
}

static bool gate(const char *token, const char *invocation) {
    char directory[sizeof(((struct sockaddr_un *)0)->sun_path)];
    char target[sizeof(directory) + 16];
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    if (!probe_id(token) || !probe_id(invocation) || getuid() != geteuid())
        return false;
    int length = snprintf(directory, sizeof(directory), "%s/%s", PROBE_RUNTIME_ROOT, token);
    if (length < 0 || (size_t)length >= sizeof(directory) ||
        !private_directory(PROBE_RUNTIME_ROOT) || !private_directory(directory))
        return false;
    length = snprintf(address.sun_path, sizeof(address.sun_path), "%s/channel", directory);
    if (length < 0 || (size_t)length >= sizeof(address.sun_path))
        return false;
    length = snprintf(target, sizeof(target), "%s/witness", directory);
    if (length < 0 || (size_t)length >= sizeof(target))
        return false;
    struct stat info;
    if (lstat(target, &info) < 0 || !S_ISREG(info.st_mode) ||
        info.st_uid != geteuid() || (info.st_mode & 0222) || !(info.st_mode & S_IXUSR))
        return false;

    int64_t now = probe_now();
    if (now < 0)
        return false;
    int64_t deadline = now + PROBE_TIMEOUT_MS;
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (fd < 0)
        return false;
    if (connect(fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        if (errno != EINPROGRESS || !probe_wait(fd, POLLOUT, deadline))
            goto done;
        int error = 0;
        socklen_t size = sizeof(error);
        if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &size) < 0 || error)
            goto done;
    }
    unsigned char frame[PROBE_FRAME_SIZE];
    probe_frame(frame, 'H', invocation);
    if (!probe_peer(fd) || !probe_send(fd, frame, deadline) ||
        !probe_admission(fd, invocation, deadline))
        goto done;

    /* The connected capability stays in this process, never in a unit FD store. */
    if (fd != PROBE_FD) {
        if (dup3(fd, PROBE_FD, 0) < 0)
            goto done;
        close(fd);
        fd = PROBE_FD;
    } else if (fcntl(fd, F_SETFD, 0) < 0) {
        goto done;
    }
    if (close_range(PROBE_FD + 1, ~0U, 0) < 0)
        goto done;
    char *const arguments[] = {target, (char *)invocation, NULL};
    char *const environment[] = {NULL};
    execve(target, arguments, environment);
    /* Only the separate witness image can emit X. No errno/path is disclosed. */
    probe_frame(frame, 'F', invocation);
    (void)probe_send(fd, frame, deadline);
done:
    close(fd);
    return false;
}

int main(int argc, char **argv) {
    if (argc == 2 && gate(argv[1], getenv("INVOCATION_ID")))
        return 0;
    fputs("execution-probe: gate-refused\n", stderr);
    return 70;
}
