"""Generated lightning cracks and rolling thunder for both request surfaces.

No recordings, music, or continuous noise: each visible return flash excites
one finite sound. Short PCM blocks keep the attack close to the rendered flash.
"""

from array import array
from dataclasses import dataclass
from functools import lru_cache
import logging
import math
import random
import sys
import threading

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst


LOG = logging.getLogger("oh-no-parent-control")
SAMPLE_RATE = 24_000
BLOCK_FRAMES = SAMPLE_RATE // 100
MAX_VOICES = 8
THUNDER_VOLUME = 0.65


def synthesize_thunder(seed):
    """Make a broadband crack, scattered reflections, and a darkening rumble.

    Filtered random pressure waves avoid a pitched oscillator or an electrical
    hiss. Reflections arrive at unequal intervals; slower low-frequency waves
    swell behind the crack and outlive it. Each variant has its own contour.
    """
    rng = random.Random(seed)
    duration = rng.uniform(1.8, 2.4)
    count = int(duration * SAMPLE_RATE)
    # An impulse plus short, progressively softer channel reflections.
    reflections = [(0.0, 1.0, 0.018)]
    reflections.extend(
        (delay * rng.uniform(0.8, 1.2), gain, width)
        for delay, gain, width in (
            (0.017, 0.55, 0.014), (0.041, 0.38, 0.023),
            (0.083, 0.25, 0.036), (0.149, 0.16, 0.052),
        )
    )
    crack_envelope = array("f", [0.0]) * count
    for delay, gain, decay in reflections:
        start = int(delay * SAMPLE_RATE)
        for offset in range(min(count - start, int(decay * 8 * SAMPLE_RATE))):
            age = offset / SAMPLE_RATE
            crack_envelope[start + offset] += (
                gain * (1 - math.exp(-age / 0.0007)) * math.exp(-age / decay)
            )

    # One-pole low passes, followed by a DC blocker; no resonant musical tones.
    air = body = deep = drift = movement = 0.0
    air_alpha = 1 - math.exp(-2 * math.pi * 3_200 / SAMPLE_RATE)
    body_alpha = 1 - math.exp(-2 * math.pi * rng.uniform(180, 260) / SAMPLE_RATE)
    deep_alpha = 1 - math.exp(-2 * math.pi * rng.uniform(55, 85) / SAMPLE_RATE)
    drift_alpha = 1 - math.exp(-2 * math.pi * 18 / SAMPLE_RATE)
    movement_alpha = 1 - math.exp(-2 * math.pi * 9 / SAMPLE_RATE)
    samples = array("f")
    for index in range(count):
        age = index / SAMPLE_RATE
        noise = rng.uniform(-1, 1)
        air += air_alpha * (noise - air)
        body += body_alpha * (noise - body)
        deep += deep_alpha * (body - deep)
        drift += drift_alpha * (deep - drift)
        movement += movement_alpha * (rng.uniform(-1, 1) - movement)
        roll = (1 - math.exp(-age / 0.045)) * math.exp(-age / 0.48)
        swell = 0.65 + min(0.65, abs(movement) * 12)
        sample = (
            (air - body) * crack_envelope[index]
            + 2.8 * (body - deep) * roll * math.exp(-age / 0.26)
            + 7.5 * (deep - drift) * roll * swell
        )
        # The last 150 ms reach exact silence without a cut or looping seam.
        samples.append(sample * min(1.0, (count - 1 - index) / (0.15 * SAMPLE_RATE)))
    scale = 0.8 / max(max(abs(value) for value in samples), 0.001)
    return array("f", (value * scale for value in samples))


@lru_cache(maxsize=1)
def _thunder_bank():
    # Built once before playback, never inside the GTK drawing callback.
    rng = random.SystemRandom()
    return tuple(synthesize_thunder(rng.getrandbits(64)) for _ in range(4))


@dataclass
class _Voice:
    samples: array
    position: int
    left: float
    right: float


class ThunderMixer:
    """Bounded stereo voices; the player serializes access with its audio lock."""

    def __init__(self, bank=None):
        self._bank = _thunder_bank() if bank is None else bank
        self._random = random.Random()
        self._last_variant = None
        self.voices = []

    def clear(self):
        self.voices.clear()

    def strike(self, brightness, pan):
        brightness = max(0.0, min(1.0, brightness))
        if brightness == 0:
            return
        choices = [index for index in range(len(self._bank)) if index != self._last_variant]
        variant = self._random.choice(choices or [0])
        self._last_variant = variant
        angle = (max(-0.8, min(0.8, pan)) + 1) * math.pi / 4
        gain = brightness * self._random.uniform(0.88, 1.0)
        # Drop the oldest fading tail only when a dense burst fills the budget.
        self.voices = self.voices[-(MAX_VOICES - 1):]
        self.voices.append(_Voice(
            self._bank[variant], 0, gain * math.cos(angle), gain * math.sin(angle),
        ))

    def render(self, frames):
        if not self.voices:
            return bytes(frames * 2 * 4)
        output = array("f", [0.0]) * (frames * 2)
        for voice in self.voices:
            count = min(frames, len(voice.samples) - voice.position)
            for index in range(count):
                value = voice.samples[voice.position + index]
                output[index * 2] += value * voice.left
                output[index * 2 + 1] += value * voice.right
            voice.position += count
        self.voices = [voice for voice in self.voices if voice.position < len(voice.samples)]
        # A soft limiter leaves headroom even when several return strokes overlap.
        for index, value in enumerate(output):
            output[index] = value / (1 + abs(value))
        if sys.byteorder != "little":
            output.byteswap()
        return output.tobytes()


class LightningAudio:
    """Window-owned GStreamer stream, silent until an unmuted visible flash.

    GStreamer's streaming thread mixes 10 ms blocks; GTK only queues a voice.
    Pipeline state changes happen outside the lock so stopping cannot deadlock
    while the streaming callback finishes. Muting flushes queued audio and tails.
    """

    def __init__(self):
        Gst.init(None)
        self._lock = threading.Lock()
        self._mixer = ThunderMixer()
        self._muted = True
        self._closed = False
        self._next_pts = 0
        self._dismissal_level = 1.0
        self._fade_source_id = None
        self._pipeline = self._gain = self._bus = None
        try:
            self._pipeline = Gst.parse_launch(
                "appsrc name=thunder_source is-live=true format=time "
                "max-bytes=1920 min-latency=0 max-latency=0 "
                f"caps=audio/x-raw,format=F32LE,rate={SAMPLE_RATE},channels=2,layout=interleaved ! "
                "audioconvert ! audioresample ! volume name=thunder_gain ! "
                "autoaudiosink name=thunder_sink"
            )
            self._gain = self._pipeline.get_by_name("thunder_gain")
            self._apply_volume()
            self._pipeline.get_by_name("thunder_source").connect("need-data", self._need_data)
            self._pipeline.get_by_name("thunder_sink").connect("child-added", self._sink_added)
            self._bus = self._pipeline.get_bus()
            self._bus.add_signal_watch()
            self._bus.connect("message::error", self._error)
            self._bus.connect("message::warning", self._warning)
        except GLib.Error as error:
            LOG.warning("lightning audio unavailable error_type=%s", type(error).__name__)
            self.close()

    @staticmethod
    def _sink_added(_proxy, sink, _name):
        # GstAudioBaseSink's supported latency controls are in microseconds.
        for name, value in (("buffer-time", 40_000), ("latency-time", 10_000)):
            if sink.find_property(name) is not None:
                sink.set_property(name, value)

    def _need_data(self, source, _length):
        with self._lock:
            if self._closed or self._muted:
                return
            pcm = self._mixer.render(BLOCK_FRAMES)
            duration = BLOCK_FRAMES * Gst.SECOND // SAMPLE_RATE
            clock = source.get_clock()
            if clock is not None:
                running_time = max(0, clock.get_time() - source.get_base_time())
                # Resynchronize after a real underrun, without stretching every
                # block to include callback/sink scheduling delays.
                if running_time > self._next_pts + 100 * Gst.MSECOND:
                    self._next_pts = running_time
            pts = self._next_pts
            self._next_pts += duration
        buffer = Gst.Buffer.new_wrapped(pcm)
        buffer.pts = pts
        buffer.duration = duration
        # Contiguous timestamps preserve the waveform through block boundaries.
        result = source.emit("push-buffer", buffer)
        if result not in (Gst.FlowReturn.OK, Gst.FlowReturn.FLUSHING):
            LOG.debug("lightning audio buffer rejected flow=%s", result.value_nick)

    def play(self, brightness=1.0, pan=0.0):
        with self._lock:
            if self._closed or self._muted or self._pipeline is None:
                return
            self._mixer.strike(brightness, pan)
        LOG.debug("lightning thunder triggered brightness=%.2f pan=%.2f", brightness, pan)

    def _apply_volume(self):
        if self._gain is not None:
            self._gain.set_property("mute", self._muted)
            self._gain.set_property("volume", THUNDER_VOLUME * self._dismissal_level)

    def set_muted(self, muted):
        with self._lock:
            if self._closed or self._muted == bool(muted):
                return
            self._muted = bool(muted)
            self._mixer.clear()
            self._next_pts = 0
        self._apply_volume()
        if self._pipeline is not None:
            state = Gst.State.READY if muted else Gst.State.PLAYING
            if self._pipeline.set_state(state) == Gst.StateChangeReturn.FAILURE:
                LOG.warning("lightning audio state change failed muted=%s", muted)
                self.close()
        LOG.info("lightning audio muted=%s", muted)

    def fade_out(self, duration_ms):
        self.cancel_fade(restore=False)
        started_us = GLib.get_monotonic_time()
        start_level = self._dismissal_level
        duration_us = max(1, duration_ms) * 1_000

        def tick():
            progress = (GLib.get_monotonic_time() - started_us) / duration_us
            self._dismissal_level = start_level * max(0.0, 1 - progress)
            self._apply_volume()
            if progress >= 1:
                self._fade_source_id = None
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        if not self._closed:
            self._fade_source_id = GLib.timeout_add(25, tick)

    def cancel_fade(self, restore=True):
        if self._fade_source_id is not None:
            GLib.source_remove(self._fade_source_id)
            self._fade_source_id = None
        if restore:
            self._dismissal_level = 1.0
            self._apply_volume()

    def _error(self, _bus, message):
        error, _debug = message.parse_error()
        # Device names and GStreamer debug strings may contain personal paths.
        LOG.warning("lightning audio playback failed error_code=%d", error.code)
        self.close()

    @staticmethod
    def _warning(_bus, message):
        warning, _debug = message.parse_warning()
        LOG.warning("lightning audio backend warning error_code=%d", warning.code)

    def close(self):
        self.cancel_fade(restore=False)
        with self._lock:
            self._closed = self._muted = True
            self._mixer.clear()
        self._apply_volume()
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None
        if self._bus is not None:
            self._bus.remove_signal_watch()
            self._bus = None
        LOG.debug("lightning audio closed")
