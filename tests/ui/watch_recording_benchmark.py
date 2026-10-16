"""Synthetic moving-feed benchmark; supplies no VM acceptance evidence."""

import os
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import watch_recording_worker as worker


class Feed:
    def __init__(self, name, color):
        self.vm_name, self.color, self.sequence = name, color, 0
        self.text = ''

    def poll(self, *, pixels=True):
        self.sequence += 2
        self.text += f'Synthetic SSH command {self.sequence}\n'
        frame = bytearray(bytes((*self.color, 255)) * (640 * 480)) if pixels else b''
        if pixels:
            left = self.sequence % 576
            top = self.sequence % 416
            line = bytes((230, 230, 230, 255)) * 64
            for row in range(top, top + 64):
                begin = (row * 640 + left) * 4
                frame[begin:begin + 256] = line
        return self.sequence, dict(width=640, height=480, stride=2560, format=0x20020888,
            state='live', updated_ns=time.monotonic_ns(), lease_locked=True,
            cursor_width=0, cursor_height=0, cursor_on=False), bytes(frame), b''

    def progress(self):
        return dict(current=1, total=1, case_id='1', title='Synthetic recording benchmark',
                    step=f'Synthetic frame {self.sequence}', operation='Synthetic workload')

    def activity(self):
        return dict(run='a' * 32, sequence=self.sequence, text=self.text, offset=0,
                    operation='Synthetic SSH', operation_started_ns=0, operation_active=True)

    def close(self):
        pass


class NoUI:
    def poll(self, **kwargs):
        return {}

    def close(self):
        pass


class Output:
    def __init__(self):
        self.first = True

    def poll(self):
        first, self.first = self.first, False
        return 'Synthetic runner', True, first, b'Synthetic runner progress\n'


class NoEncoder:
    """Download identical GTK frames without running the video encoder."""
    def __init__(self, _output):
        self.started_ns = time.monotonic_ns()
        self.count = 0
        self.error = None

    def submit(self, _pixels, *, names=()):
        self.count += 1

    def seconds(self):
        return (time.monotonic_ns() - self.started_ns) / 1e9

    def close(self):
        return dict(frames=self.count, fps=5, duration_seconds=self.seconds())


original_render = worker.render


def synthetic(control, root, output, **kwargs):
    names = json.loads(os.environ.get('ONPC_RECORDING_SYNTHETIC_NAMES',
                                     '["Synthetic-One","Synthetic-Two"]'))
    return original_render(control, root, output, sources={root: dict(
        feeds=NoUI(), output=Output(), vm_feeds={name: Feed(name, color)
            for name, color in zip(names, ((30, 60, 100), (100, 60, 30)))})}, **kwargs)


worker.render = synthetic
if os.environ.get('ONPC_RECORDING_BENCHMARK') == 'encoded-transient':
    original_pixels = worker.widget_pixels
    samples = 0

    def transient_pixels(*args, **kwargs):
        global samples
        samples += 1
        # Exercise both pre-readiness mapping and a later GTK relayout gap.
        return None if samples in (1, 2, 3, 8) else original_pixels(*args, **kwargs)

    worker.widget_pixels = transient_pixels
if os.environ.get('ONPC_RECORDING_BENCHMARK') == 'no-encoder':
    worker.Encoder = NoEncoder
raise SystemExit(worker.main())
