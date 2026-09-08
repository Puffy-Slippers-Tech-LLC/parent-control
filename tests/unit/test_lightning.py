"""Discharge geometry, frame-independent flashes, and shared renderer timing."""

import random
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import cairo
import pytest

from oh_no_parent_control_kiosk.lightning import LightningDischarge
from oh_no_parent_control_kiosk.main import (
    CRYSTAL_LIGHTNING_TIPS, GATEWAY_INNER_CORNERS,
    LIGHTNING_SIZZLE_VOLUME, GLib, Gst, GatewayBackground, LightningSizzle,
    _gateway_artwork_geometry,
)


def test_channels_have_fixed_ends_and_attached_forward_forks():
    channels = [LightningDischarge(random.Random(seed)) for seed in range(30)]
    assert len({channel.points for channel in channels}) == len(channels)
    for channel in channels:
        assert channel.points[0] == (0, 0)
        assert channel.points[-1] == (1, 0)
        assert all(left[0] < right[0]
                   for left, right in zip(channel.points, channel.points[1:]))
        for points, _width in channel.branches:
            assert points[0] in channel.points
            assert points[-1][0] > points[0][0]
        for previous, flash in zip(channel.flashes, channel.flashes[1:]):
            gap = (previous.starts_at + previous.duration + flash.starts_at) / 2
            assert channel.active_flash(gap) is None
        assert channel.active_flash(-1) is None
        assert channel.active_flash(channel.duration) is None


def test_cairo_flashes_reach_both_contacts_immediately_and_do_not_depend_on_frames(tmp_path):
    channel = LightningDischarge(random.Random(8))
    source, target = (40, 110), (550, 220)

    def frame(age):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 320)
        channel.draw(cairo.Context(surface), source, target, 1.0, age)
        surface.flush()
        return bytes(surface.get_data())

    for flash in channel.flashes:
        for fraction in (0, 0.5):
            pixels = frame(flash.starts_at + flash.duration * fraction)
            for x, y in (source, target):
                # Both ends light up at once, rather than the tip travelling
                # across the screen. Inspect all channels, independent of endian.
                offset = (y * 600 + x) * 4
                assert any(pixels[offset:offset + 4])
    assert not any(frame(-0.1))
    assert not any(frame(channel.duration))

    at_time = channel.flashes[-1].starts_at + 0.025
    sparse = frame(at_time)
    for index in range(int(at_time * 120)):
        frame(index / 120)
    assert frame(at_time) == sparse

    # Keep an actual Cairo scene frame for visual review alongside test output.
    scene = cairo.ImageSurface.create_from_png(str(
        Path(__file__).resolve().parents[2]
        / "kiosk/oh_no_parent_control_kiosk/kiosk-background-still.png",
    ))
    context = cairo.Context(scene)
    channel.draw(context, (272, 90), (599, 251), 1.0, 0.015)
    another = LightningDischarge(random.Random(16))
    another.draw(context, (1320, 358), (991, 413), 1.0, 0.015)
    artifact = tmp_path / "lightning-scene.png"
    scene.write_to_png(str(artifact))
    print(f"Lightning render: {artifact}")


@pytest.mark.parametrize("size", ((1920, 1080), (1280, 1024), (900, 1200)))
def test_shared_renderer_keeps_contacts_in_artwork_space_and_sounds_each_flash_once(size):
    width, height = size
    background = SimpleNamespace(
        _random=random.Random(8), _lightning_enabled=True,
        _next_lightning_burst_at=float("inf"),
        _floating_islands=SimpleNamespace(offset=lambda _index, elapsed: elapsed * 0.01),
        _lightning_sizzle=Mock(), queue_draw=Mock(),
    )
    bolt = GatewayBackground._new_lightning_bolt(background, 0.0)
    background._lightning_bolts = [bolt]
    channel = bolt["channel"]
    channel.draw = Mock(wraps=channel.draw)
    context = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height))
    snapshot = SimpleNamespace(append_cairo=lambda _bounds: context)
    image_x, image_y, image_width, image_height = _gateway_artwork_geometry(width, height)
    tip = CRYSTAL_LIGHTNING_TIPS[bolt["source_index"]]
    rail = GATEWAY_INNER_CORNERS[0 if tip[0] < 0.35 else 1]
    assert bolt["target_x"] == rail[0]

    for flash_index, flash in enumerate(channel.flashes):
        age = flash.starts_at + 0.025
        GatewayBackground._append_gateway_energy(background, snapshot, width, height, age)
        GatewayBackground._append_gateway_energy(background, snapshot, width, height, age)
        assert background._lightning_sizzle.call_count == flash_index + 1
        remaining, fade, light = background._lightning_sizzle.call_args.args
        assert remaining == pytest.approx(flash.duration - 0.025)
        assert fade == flash.fade_rate
        assert light == pytest.approx(flash.light(age))
        _context, source, target, _scale, _age = channel.draw.call_args.args
        assert source == pytest.approx((
            image_x + tip[0] * image_width,
            image_y + (tip[1] + age * 0.01) * image_height,
        ))
        assert target == pytest.approx((
            image_x + rail[0] * image_width,
            image_y + bolt["target_y"] * image_height,
        ))

    GatewayBackground.set_lightning_enabled(background, False)
    assert background._lightning_bolts == []
    # A muted renderer must not allocate a context, draw a frame, or play audio.
    calls = background._lightning_sizzle.call_count
    GatewayBackground._append_gateway_energy(background, None, width, height, 1)
    assert background._lightning_sizzle.call_count == calls


def test_sizzle_starts_at_the_flash_brightness_and_fades_to_silence(monkeypatch):
    monkeypatch.setattr(GLib, "get_monotonic_time", lambda: 1_000_000)
    monkeypatch.setattr(GLib, "timeout_add", lambda *_args: 123)
    sizzle = SimpleNamespace(
        _pipeline=Mock(), _gain=Mock(), _active_bolts=[], _sizzle_level=0.0,
        _dismissal_level=1.0, _muted=False, _stop_source_id=None,
    )
    sizzle._apply_volume = lambda: LightningSizzle._apply_volume(sizzle)
    sizzle._stop_if_idle = lambda: LightningSizzle._stop_if_idle(sizzle)
    LightningSizzle.play(sizzle, 0.12, 1.65, 0.7)
    sizzle._gain.set_property.assert_called_with("volume", LIGHTNING_SIZZLE_VOLUME * 0.7)
    sizzle._pipeline.set_state.assert_called_with(Gst.State.PLAYING)

    monkeypatch.setattr(GLib, "get_monotonic_time", lambda: 1_060_000)
    assert sizzle._stop_if_idle() == GLib.SOURCE_CONTINUE
    assert sizzle._sizzle_level == pytest.approx(0.7 * 0.5 ** 1.65)
    monkeypatch.setattr(GLib, "get_monotonic_time", lambda: 1_120_000)
    assert sizzle._stop_if_idle() == GLib.SOURCE_REMOVE
    sizzle._gain.set_property.assert_called_with("volume", 0.0)
    sizzle._pipeline.set_state.assert_called_with(Gst.State.READY)
