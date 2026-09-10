import pytest

from oh_no_parent_control_kiosk.preview_screen import Screen


@pytest.mark.parametrize("screen", [Screen(), Screen(1920, 1200, 125), Screen(3840, 2160, 200)])
def test_screen_round_trip(screen):
    assert Screen.decode(screen.encode()) == screen


@pytest.mark.parametrize("values", [(0, 1080, 100), (-1, 720, 100), (1920.5, 1080, 100),
                                    (True, 1080, 100), (7680, 7680, 100),
                                    (1920, 1080, 99), (1920, 1080, 125.0)])
def test_invalid_or_unbounded_screens_are_rejected(values):
    with pytest.raises(ValueError):
        Screen(*values)
