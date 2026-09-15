"""Unprivileged live spectator transport qualification; no VM access."""

import json
import os
from pathlib import Path
import pwd
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from e2e_watch_protocol import BASE, read_frame, receive_frames, require


def snapshot(memory):
    # The production viewer likewise skips a frame being written. Receiving a
    # descriptor does not stop the collector or promise an idle seqlock.
    deadline = time.monotonic() + .5
    while time.monotonic() < deadline:
        current = read_frame(memory)
        if current is not None:
            return current
        time.sleep(.003)
    raise ValueError('watch:probe-frame-timeout')


def main():
    require(len(sys.argv) == 1 and os.geteuid() == 0, 'probe-context')
    uid = int(os.environ['PKEXEC_UID'])
    require(uid > 0, 'probe-user')
    os.setgroups([])
    os.setgid(pwd.getpwuid(uid).pw_gid)
    os.setuid(uid)
    from e2e_watch_viewer import Feed
    feed = Feed()
    deadline = time.monotonic() + 25
    first = None
    while time.monotonic() < deadline:
        frame = feed.poll()
        if isinstance(frame, tuple) and frame[1]['state'] == 'live':
            first = frame
            break
        time.sleep(.03)
    require(first is not None, 'probe-no-live-frame')
    path = BASE / str(uid) / (first[1]['run'] + '.sock')
    ages = []
    for index in range(60):
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as client:
            client.settimeout(1)
            client.connect(str(path))
            if index % 3 == 0:
                # Early closes and unsolicited input cannot reach the VM.
                client.send(b'keyboard-mouse-clipboard-resize')
                continue
            with receive_frames(client) as memory:
                current = snapshot(memory)
                ages.append((time.monotonic_ns() - current[1]['updated_ns']) / 1e6)
        time.sleep(.02)
    time.sleep(.7)
    current = snapshot(feed.memory)
    require(current[0] > first[0] and current[1]['state'] != 'stopped'
            and time.monotonic_ns() - current[1]['updated_ns'] < 1_000_000_000, 'probe-writer-stopped')
    feed.close()
    print(json.dumps({'connections': 60, 'frame_size': [first[1]['width'], first[1]['height']],
                      'max_frame_age_ms': round(max(ages), 2), 'read_only': True}))


if __name__ == '__main__':
    main()
