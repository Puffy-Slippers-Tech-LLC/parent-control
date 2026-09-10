"""Real Mutter virtual monitors: allocations/scales are observed, not forced."""

import json
import os
from pathlib import Path
import sys
import time

import pytest

from kiosk.oh_no_parent_control_kiosk.preview import OwnedProcess, PreviewSession
from kiosk.oh_no_parent_control_kiosk.preview_screen import Screen
from tests.support.paths import ROOT

pytestmark = pytest.mark.ui


@pytest.mark.parametrize("width,height,percent,logical", [
    (800, 600, 100, (800, 600)),
    (1920, 1200, 100, (1920, 1200)),
    (1920, 1200, 125, (1536, 960)),
    (3840, 2160, 200, (1920, 1080)),
])
@pytest.mark.parametrize("child", [False, True])
def test_real_fullscreen_resolution_scale_and_dialog(tmp_path, width, height, percent, logical, child):
    output = tmp_path / "screen.json"
    environment = {**os.environ, "PYTHONPATH": f"{ROOT}:{ROOT}/kiosk",
                   "ONPC_SCREEN_EVIDENCE": str(output), "ONPC_SCREEN_CHILD": str(int(child))}
    session = PreviewSession(
        Screen(width, height, percent), environment, viewer=False,
        app_command=[sys.executable, str(ROOT / "tests/ui/screen_preview_probe.py")],
    )
    try:
        deadline = time.monotonic() + 15
        while not output.exists() and time.monotonic() < deadline and session.running():
            time.sleep(0.1)
        assert output.exists(), "preview did not produce surface/dialog evidence"
        result = json.loads(output.read_text())
        assert (result["width"], result["height"]) == logical
        assert result["viewport"] == list(logical)
        assert result["scale"] == percent / 100
        assert result["fullscreen"]
        assert result["invalid_error"]
        assert result["save_still_enabled"]
    finally:
        session.close()


def test_save_rejects_unsupported_scale_then_reopens_custom_screen(hermetic_ui_session, tmp_path):
    output = tmp_path / "screen.json"
    environment = {**hermetic_ui_session.environment, "PYTHONPATH": f"{ROOT}:{ROOT}/kiosk",
                   "ONPC_SCREEN_EVIDENCE": str(output), "ONPC_SCREEN_CHANGE": "1"}
    launcher = OwnedProcess([sys.executable, str(ROOT / "tests/ui/screen_preview_launcher.py")],
                            env=environment)
    try:
        deadline = time.monotonic() + 40
        while not output.exists() and time.monotonic() < deadline and launcher.child.poll() is None:
            time.sleep(0.1)
        assert output.exists(), "Save did not recover from rejection and render the custom screen"
        result = json.loads(output.read_text())
        assert (result["width"], result["height"]) == (2048, 1280)
        assert result["scale"] == 1.25
        assert result["fullscreen"]
    finally:
        launcher.close()


@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize("width,height,percent", [(1280, 800, 100), (1920, 1200, 125),
                                                (3840, 2160, 200)])
def test_viewer_pixels_match_production_and_input_reaches_same_monitor(
        hermetic_ui_session, tmp_path, child, width, height, percent):
    from PIL import Image, ImageChops

    images = []
    layouts = []
    for production in (False, True):
        output = tmp_path / f"viewer-{int(production)}.json"
        environment = {**hermetic_ui_session.environment,
                       "PYTHONPATH": f"{ROOT}:{ROOT}/kiosk",
                       "ONPC_SCREEN_CHILD": str(int(child)),
                       "ONPC_FIDELITY_PRODUCTION": str(int(production)),
                       "ONPC_FIDELITY_APP": str(tmp_path / f"app-{int(production)}.json"),
                       "ONPC_FIDELITY_VIEWER": str(output)}
        session = PreviewSession(
            Screen(width, height, percent), environment,
            app_command=[sys.executable, str(ROOT / "tests/ui/screen_fidelity_app.py")],
            viewer_command=[sys.executable, str(ROOT / "tests/ui/screen_fidelity_viewer.py")],
        )
        try:
            deadline = time.monotonic() + 15
            while not output.exists() and time.monotonic() < deadline and session.running():
                time.sleep(0.1)
            assert output.exists(), "viewer did not produce video/input evidence"
            evidence = json.loads(output.read_text())
            assert evidence["mapped"]
            assert evidence["source"] == [width, height]
            assert evidence["monitors"] == evidence["logical_monitors"] == 1
            assert evidence["pixel_view"] == [round(width / evidence["host_scale"]),
                                               round(height / evidence["host_scale"])]
            assert evidence["before"]["selected"][1] == 1800
            assert evidence["after"]["selected"][1] == 300
            assert 65364 in evidence["after_keyboard"]["keyvals"]  # GDK_KEY_Down
            assert 32 in evidence["after_keyboard"]["keyvals"]  # GDK_KEY_space
            assert evidence["before"]["width"] == evidence["after"]["width"]
            assert evidence["before"]["height"] == round(height / (percent / 100))
            assert evidence["before"]["scale"] == percent / 100
            images.append(Image.open(output.with_suffix(".png")).convert("RGB"))
            layouts.append(evidence["before"])
        finally:
            session.close()
    assert images[0].size == images[1].size == (width, height)
    for key in ("width", "height", "scale", "duration_target"):
        assert layouts[0][key] == layouts[1][key], f"production/preview geometry differs: {key}"
    difference = ImageChops.difference(*images)
    difference.save(tmp_path / "production-preview-difference.png")
    if difference.getbbox():
        for index, image in enumerate(images):
            image.crop(difference.getbbox()).save(tmp_path / f"difference-detail-{index}.png")
        print("Pixel difference:", difference.getextrema(), difference.getbbox())
    # Keep native GPU rendering. Independently rendered antialiased text has
    # small channel-rounding differences; neither geometry errors nor broad
    # color shifts are accepted. Retain quantitative evidence for each case.
    maximum = max(high for _low, high in difference.getextrema())
    red, green, blue = difference.split()
    maximum_channel = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    changed = width * height - maximum_channel.histogram()[0]
    (tmp_path / "pixel-comparison.json").write_text(json.dumps({
        "width": width, "height": height, "scale_percent": percent,
        "maximum_channel_difference": maximum, "changed_pixels": changed,
        "total_pixels": width * height,
    }))
    assert maximum <= 2, (
        "preview pixels differ from production beyond RGB rounding tolerance")
    assert changed / (width * height) < 0.005, "more than 0.5% of captured pixels differ"


def test_missing_video_link_policy_fails_startup(hermetic_ui_session):
    class WithoutLinkPolicy(PreviewSession):
        def start(self, command, **kwargs):
            if command[0] == "wireplumber":
                return None
            return super().start(command, **kwargs)

    with pytest.raises(RuntimeError, match="full-resolution preview video"):
        WithoutLinkPolicy(Screen(1280, 800, 100), {
            **hermetic_ui_session.environment, "PYTHONPATH": f"{ROOT}:{ROOT}/kiosk",
        })
