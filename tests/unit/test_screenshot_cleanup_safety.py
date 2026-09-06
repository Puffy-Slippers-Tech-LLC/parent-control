"""Safety boundary for the persistently approved screenshot cleanup command."""

from pathlib import Path
import runpy
import tempfile

import pytest


CLEANUP = runpy.run_path(str(Path(__file__).resolve().parents[2] / "tools/cleanup-screenshots"))["cleanup"]


@pytest.fixture
def screenshot():
    with tempfile.NamedTemporaryFile(prefix="onpc-cleanup-test-", suffix=".png", dir="/tmp", delete=False) as file:
        path = Path(file.name)
    yield path
    path.unlink(missing_ok=True)


def test_removes_selected_file_and_accepts_missing_and_duplicates(screenshot):
    CLEANUP([str(screenshot), str(screenshot)])
    assert not screenshot.exists()
    CLEANUP([str(screenshot)])


@pytest.mark.parametrize("invalid", ["/tmp/unrelated.png", "/tmp/onpc-x.log", "/tmp/onpc-*.png", "/tmp/onpc-x/../victim.png", "/tmp/../tmp/onpc-x.png", "onpc-x.png", "-rf", "/home/onpc-x.png"])
def test_invalid_selection_preserves_valid_file(screenshot, invalid):
    with pytest.raises(ValueError):
        CLEANUP([str(screenshot), invalid])
    assert screenshot.exists()


def test_refuses_empty_selection():
    with pytest.raises(ValueError):
        CLEANUP([])


def test_refuses_symlink_and_preserves_target(screenshot):
    link = screenshot.with_name(screenshot.stem + "-link.png")
    link.symlink_to(screenshot)
    try:
        with pytest.raises(ValueError):
            CLEANUP([str(screenshot), str(link)])
        assert screenshot.exists()
    finally:
        link.unlink()


def test_refuses_directory(screenshot):
    screenshot.unlink()
    screenshot.mkdir()
    try:
        with pytest.raises(ValueError):
            CLEANUP([str(screenshot)])
    finally:
        screenshot.rmdir()


def test_refuses_other_owner(screenshot, monkeypatch):
    monkeypatch.setattr("os.getuid", lambda: screenshot.stat().st_uid + 1)
    with pytest.raises(ValueError):
        CLEANUP([str(screenshot)])
    assert screenshot.exists()
