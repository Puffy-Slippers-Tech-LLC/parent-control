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
    mode = sys.argv[1:]
    require(mode in ([], ['--experiment'], ['--stopped']) and os.geteuid() == 0, 'probe-context')
    uid = int(os.environ['PKEXEC_UID'])
    require(uid > 0, 'probe-user')
    os.setgroups([])
    os.setgid(pwd.getpwuid(uid).pw_gid)
    os.setuid(uid)
    from e2e_watch_viewer import Feed
    feed = Feed()
    if mode == ['--stopped']:
        deadline = time.monotonic() + 10
        while (BASE / str(uid) / 'current.json').exists() and time.monotonic() < deadline:
            time.sleep(.05)
        require(not (BASE / str(uid) / 'current.json').exists(), 'probe-keeper-not-stopped')
        print(json.dumps({'keeper_stopped_with_vm': True}))
        return
    activity = feed.activity()
    require(activity is not None and 'SSH $ printf' in activity['text']
            and 'ONPC-WATCH-SSH-STDOUT\n' in activity['text']
            and 'ls:' in activity['text']
            and '/onpc-watch-missing-entry' in activity['text'], 'probe-no-ssh-transcript')
    deadline = time.monotonic() + 25
    first = None
    states = set()
    last = None
    while time.monotonic() < deadline:
        frame = feed.poll()
        if isinstance(frame, tuple):
            last = frame[1]
            states.add(last['state'])
            if last['state'] == 'live':
                first = frame
                break
        elif frame == 'waiting':
            states.add('disconnected')
        time.sleep(.03)
    if first is None:
        print(json.dumps({'frame_states': sorted(states),
            'registry_present': (BASE / str(uid) / 'current.json').exists(),
            'last_frame_age_ms': ((time.monotonic_ns() - last['updated_ns']) / 1e6
                                  if last else None)}), file=sys.stderr, flush=True)
    require(first is not None, 'probe-no-live-frame')
    progress = first[1].get('progress', {})
    if mode == ['--experiment']:
        require(not progress and activity.get('operation') == 'Qualifying VM maintenance observation'
                and activity.get('operation_started_ns', 0) > 0, 'probe-no-experiment-intent')
    else:
        require(progress.get('title') == 'Spectator harness'
                and progress.get('step') == 'Observe VM frames and command output'
                and {'started_ns', 'case_started_ns', 'operation_started_ns'} <= progress.keys(),
                'probe-no-timed-progress')
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
                      'max_frame_age_ms': round(max(ages), 2), 'read_only': True,
                      'ssh_command_stdout_stderr': True, 'timed_progress_with_frames': not mode,
                      'without_e2e_recorder': mode == ['--experiment']}))


if __name__ == '__main__':
    main()
