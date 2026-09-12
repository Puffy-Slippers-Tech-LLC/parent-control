#define _GNU_SOURCE
#include "execution_probe_protocol.h"

#include <stdio.h>

int main(int argc, char **argv) {
    int type = 0;
    socklen_t size = sizeof(type);
    int64_t now = probe_now();
    if (argc != 2 || !probe_id(argv[1]) || now < 0 ||
        getsockopt(PROBE_FD, SOL_SOCKET, SO_TYPE, &type, &size) < 0 ||
        type != SOCK_STREAM || !probe_peer(PROBE_FD)) {
        fputs("execution-probe: witness-refused\n", stderr);
        return 70;
    }
    unsigned char frame[PROBE_FRAME_SIZE];
    probe_frame(frame, 'X', argv[1]);
    bool sent = probe_send(PROBE_FD, frame, now + PROBE_TIMEOUT_MS);
    bool ended = shutdown(PROBE_FD, SHUT_WR) == 0;
    close(PROBE_FD);
    if (!sent || !ended) {
        fputs("execution-probe: witness-send-failed\n", stderr);
        return 70;
    }
    return PROBE_EXIT;
}
