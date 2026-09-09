"""Sound envelope, animation-driven voices, and real PCM playback lifecycle."""

from array import array
import math
import random
import sys
import threading
from unittest.mock import Mock
import wave

import pytest

from oh_no_parent_control_kiosk import thunder
from oh_no_parent_control_kiosk.thunder import (
    BLOCK_FRAMES, GLib, Gst, LightningAudio, MAX_VOICES, SAMPLE_RATE,
    THUNDER_VOLUME, ThunderMixer, synthesize_thunder,
)


def decode(pcm):
    samples = array("f")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def rms(samples):
    return math.sqrt(sum(value * value for value in samples) / len(samples))


@pytest.fixture(scope="module")
def bank():
    return tuple(synthesize_thunder(seed) for seed in range(4))


def test_generated_crack_has_a_dark_decaying_rumble_and_no_loop(bank):
    assert len({samples.tobytes() for samples in bank}) == 4
    for samples in bank:
        assert 1.8 * SAMPLE_RATE <= len(samples) <= 2.4 * SAMPLE_RATE
        assert samples[0] == samples[-1] == 0
        assert max(abs(value) for value in samples) == pytest.approx(0.8)
        assert abs(sum(samples) / len(samples)) < 0.005
        crack = samples[:int(0.12 * SAMPLE_RATE)]
        roll = samples[int(0.2 * SAMPLE_RATE):int(0.6 * SAMPLE_RATE)]
        tail = samples[-int(0.2 * SAMPLE_RATE):]
        assert rms(crack) > rms(roll) > 5 * rms(tail) > 0
        # The rumble loses high-frequency energy after the sharp initial crack.
        roughness = lambda values: rms([b - a for a, b in zip(values, values[1:])]) / rms(values)
        assert roughness(roll) < roughness(crack) * 0.5


def test_mixer_is_silent_between_flashes_and_tails_end(bank):
    mixer = ThunderMixer(bank)
    assert not any(decode(mixer.render(BLOCK_FRAMES)))
    mixer.strike(1.0, 0.0)
    assert any(decode(mixer.render(BLOCK_FRAMES)))
    mixer.render(3 * SAMPLE_RATE)
    assert mixer.voices == []
    assert not any(decode(mixer.render(BLOCK_FRAMES)))


def test_overlapping_flashes_preserve_tails_and_bound_output(bank):
    mixer = ThunderMixer(bank)
    mixer.strike(1.0, 0)
    oldest = mixer.voices[0]
    mixer.render(BLOCK_FRAMES)
    mixer.strike(0.7, 0)
    assert mixer.voices[0] is oldest
    assert oldest.position == BLOCK_FRAMES
    assert mixer.voices[-1].position == 0
    assert mixer.voices[-1].samples is not oldest.samples
    for _ in range(30):
        mixer.strike(1.0, 0)
    assert len(mixer.voices) == MAX_VOICES
    assert max(abs(value) for value in decode(mixer.render(SAMPLE_RATE))) < 1


def test_flash_brightness_and_position_control_stereo_gain(bank):
    def strike(brightness, pan):
        mixer = ThunderMixer(bank)
        mixer._random = random.Random(4)
        mixer.strike(brightness, pan)
        return decode(mixer.render(BLOCK_FRAMES))

    bright = strike(1.0, -0.8)
    dim = strike(0.3, -0.8)
    right = strike(1.0, 0.8)
    assert rms(bright) > rms(dim) * 2
    assert rms(bright[::2]) > rms(bright[1::2]) * 3
    assert rms(right[1::2]) > rms(right[::2]) * 3


@pytest.fixture
def player(monkeypatch, bank):
    # Exercise actual appsrc/caps/conversion/volume and a clocked sink, without
    # opening the host's speakers or touching a desktop/audio session.
    launch = Gst.parse_launch
    monkeypatch.setattr(thunder, "_thunder_bank", lambda: bank)
    monkeypatch.setattr(Gst, "parse_launch", lambda description: launch(description.replace(
        "autoaudiosink name=thunder_sink",
        "bin.( name=thunder_sink fakesink name=capture sync=true signal-handoffs=true )",
    )))
    sound = LightningAudio()
    assert sound._pipeline is not None
    yield sound
    sound.close()


def test_real_stream_silence_flash_mute_unmute_and_close(player):
    sink = player._pipeline.get_by_name("capture")
    silent = threading.Event()
    audible = threading.Event()

    def received(_sink, buffer, _pad):
        pcm = decode(buffer.extract_dup(0, buffer.get_size()))
        (audible if any(pcm) else silent).set()

    sink.connect("handoff", received)
    assert player._muted
    player.play()
    assert player._mixer.voices == []
    player.set_muted(False)
    assert silent.wait(2), "PCM pipeline did not deliver silence while idle"
    assert not audible.is_set()
    player.play(1.0, -0.5)
    assert audible.wait(2), "Rendered flash did not reach the audio sink"
    player.set_muted(True)
    assert player._mixer.voices == []
    assert player._pipeline.get_state(Gst.SECOND)[1] == Gst.State.READY
    player.play()
    assert player._mixer.voices == []
    silent.clear()
    audible.clear()
    player.set_muted(False)
    assert silent.wait(2)
    assert not audible.is_set(), "Unmuting replayed a previous flash"
    player.play()
    assert audible.wait(2)
    assert player._bus.pop_filtered(Gst.MessageType.ERROR) is None
    pipeline = player._pipeline
    player.close()
    player.close()
    player.play()
    player.set_muted(False)
    assert player._pipeline is None
    assert player._mixer.voices == []
    assert pipeline.get_state(Gst.SECOND)[1] == Gst.State.NULL


def test_success_fade_can_be_cancelled_and_close_removes_timer(player, monkeypatch):
    ticks = []
    removed = []
    now = [1_000_000]
    monkeypatch.setattr(GLib, "get_monotonic_time", lambda: now[0])
    monkeypatch.setattr(GLib, "timeout_add", lambda _interval, callback: ticks.append(callback) or 123)
    monkeypatch.setattr(GLib, "source_remove", removed.append)
    player.fade_out(3_000)
    now[0] += 1_500_000
    assert ticks[-1]() == GLib.SOURCE_CONTINUE
    assert player._gain.get_property("volume") == pytest.approx(THUNDER_VOLUME / 2)
    now[0] += 1_500_000
    assert ticks[-1]() == GLib.SOURCE_REMOVE
    assert player._gain.get_property("volume") == 0
    player.cancel_fade()
    assert player._gain.get_property("volume") == pytest.approx(THUNDER_VOLUME)
    player.fade_out(3_000)
    player.close()
    assert removed == [123]
    assert player._fade_source_id is None


def test_live_pcm_blocks_have_contiguous_timestamps(player):
    blocks = []
    ready = threading.Event()

    def received(_sink, buffer, _pad):
        blocks.append((buffer.pts, buffer.duration))
        if len(blocks) >= 12:
            ready.set()

    player._pipeline.get_by_name("capture").connect("handoff", received)
    player.set_muted(False)
    player.play()
    assert ready.wait(2)
    player.set_muted(True)
    for (pts, duration), (next_pts, _) in zip(blocks, blocks[1:]):
        assert duration == BLOCK_FRAMES * Gst.SECOND // SAMPLE_RATE
        assert next_pts == pts + duration


def test_missing_gstreamer_element_leaves_requests_usable(monkeypatch, bank, caplog):
    monkeypatch.setattr(thunder, "_thunder_bank", lambda: bank)
    monkeypatch.setattr(Gst, "parse_launch", Mock(side_effect=GLib.Error("private device path")))
    player = LightningAudio()
    player.set_muted(False)
    player.play()
    player.close()
    assert player._pipeline is None
    assert "lightning audio unavailable" in caplog.text
    assert "private device path" not in caplog.text


def test_audio_backend_failure_stops_playback_without_logging_private_details(player, caplog):
    message = Mock()
    message.parse_error.return_value = (GLib.Error("private device", code=7), "private debug path")
    player._error(None, message)
    assert player._closed
    assert player._pipeline is None
    assert "error_code=7" in caplog.text
    assert "private" not in caplog.text


def test_export_thunder_preview(bank, tmp_path):
    mixer = ThunderMixer(bank)
    mixer._random = random.Random(8)
    mixer.strike(1, -0.6)
    pcm = bytearray(mixer.render(int(0.2 * SAMPLE_RATE)))
    mixer.strike(0.65, -0.6)
    pcm.extend(mixer.render(3 * SAMPLE_RATE))
    mixer.strike(0.9, 0.6)
    pcm.extend(mixer.render(3 * SAMPLE_RATE))
    samples = array("h", (round(value * THUNDER_VOLUME * 32767) for value in decode(pcm)))
    if sys.byteorder != "little":
        samples.byteswap()
    artifact = tmp_path / "thunder-preview.wav"
    with wave.open(str(artifact), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(samples.tobytes())
    assert artifact.stat().st_size > SAMPLE_RATE * 4
    print(f"Thunder preview: {artifact}")
