import os
from types import SimpleNamespace

import pytest

from oh_no_parent_control.display_config import MAX_MONITORS_CONFIG_BYTES, read_monitors_config
from oh_no_parent_control_kiosk.display_config import plan

SPEC = ('DP-1', 'GSM', 'LG', '0x01')
SAVED = """<monitors version="2">
  <configuration>
    <logicalmonitor><x>0</x><y>0</y><scale>1</scale><primary>yes</primary>
      <monitor><monitorspec><connector>HDMI-1</connector><vendor>X</vendor>
        <product>Y</product><serial>Z</serial></monitorspec>
        <mode><width>800</width><height>600</height><rate>60.000</rate></mode></monitor>
    </logicalmonitor>
  </configuration>
  <configuration>
    <layoutmode>logical</layoutmode>
    <logicalmonitor><x>0</x><y>0</y><scale>1.5</scale><primary>yes</primary>
      <monitor><monitorspec><connector>DP-1</connector><vendor>GSM</vendor>
        <product>LG</product><serial>0x01</serial></monitorspec>
        <mode><width>2560</width><height>1440</height><rate>59.951</rate></mode></monitor>
    </logicalmonitor>
  </configuration>
</monitors>"""


def state(mode_id, scale, layout_mode=1):
    modes = [('1920x1080@60', 1920, 1080, 60.0, 1.0, [1.0, 1.25], {'is-current': mode_id == '1920x1080@60'}),
             ('2560x1440@59.951', 2560, 1440, 59.95100021, 1.0, [1.0, 1.5],
              {'is-current': mode_id == '2560x1440@59.951'})]
    return (7, [(SPEC, modes, {})], [(0, 0, scale, 0, True, [SPEC], {})],
            {'layout-mode': layout_mode, 'supports-changing-layout-mode': True})


def test_matching_screen_is_left_alone_and_different_screen_gets_saved_mode_and_scale():
    assert plan(SAVED, state('2560x1440@59.951', 1.5)) == ('unchanged', None)
    outcome, arguments = plan(SAVED, state('1920x1080@60', 1.0))
    assert outcome == 'applied'
    assert arguments.unpack() == (7, 2, [(0, 0, 1.5, 0, True, [('DP-1', '2560x1440@59.951', {})])], {'layout-mode': 1})
    outcome, arguments = plan(SAVED, state('2560x1440@59.951', 1.5, layout_mode=2))
    assert outcome == 'applied' and arguments.unpack()[3] == {'layout-mode': 1}


def test_saved_copy_in_the_current_layout_mode_is_preferred():
    logical = SAVED.split('<configuration>')[2].split('</configuration>')[0]
    physical = logical.replace('logical</layoutmode>', 'physical</layoutmode>')
    for first, second in ((logical, physical), (physical, logical)):
        text = (f'<monitors version="2"><configuration>{first}</configuration>'
                f'<configuration>{second}</configuration></monitors>')
        for layout_mode in (1, 2):
            assert plan(text, state('2560x1440@59.951', 1.5, layout_mode)) == ('unchanged', None)


def test_layout_for_other_monitors_or_unavailable_mode_is_not_applied():
    other = (7, [(('eDP-1', 'A', 'B', 'C'), [], {})], [], {})
    assert plan(SAVED, other) == ('unmatched', None)
    assert plan(SAVED.replace('59.951', '144.000'), state('1920x1080@60', 1.0)) == ('unmatched', None)
    assert plan('<monitors version="1"/>', state('1920x1080@60', 1.0)) == ('unmatched', None)


def make_home(tmp_path):
    (tmp_path / '.config').mkdir()
    return SimpleNamespace(pw_dir=str(tmp_path))


def test_reader_returns_owned_child_file_and_empty_when_absent(tmp_path):
    account = make_home(tmp_path)
    lookup = lambda _uid: account
    uid = os.getuid()
    assert read_monitors_config(uid, lookup) == ''
    (tmp_path / '.config/monitors.xml').write_text(SAVED, encoding='utf-8')
    assert read_monitors_config(uid, lookup) == SAVED
    with pytest.raises(PermissionError):
        read_monitors_config(uid + 1, lookup)


def test_reader_refuses_links_and_oversized_files(tmp_path):
    account = make_home(tmp_path)
    lookup = lambda _uid: account
    secret = tmp_path / 'secret'
    secret.write_text('private', encoding='utf-8')
    (tmp_path / '.config/monitors.xml').symlink_to(secret)
    with pytest.raises(OSError):
        read_monitors_config(os.getuid(), lookup)
    (tmp_path / '.config/monitors.xml').unlink()
    (tmp_path / '.config/monitors.xml').write_bytes(b' ' * (MAX_MONITORS_CONFIG_BYTES + 1))
    with pytest.raises(ValueError):
        read_monitors_config(os.getuid(), lookup)
    (tmp_path / '.config/monitors.xml').unlink()
    (tmp_path / '.config').rmdir()
    (tmp_path / '.config').symlink_to(tmp_path)
    with pytest.raises(OSError):
        read_monitors_config(os.getuid(), lookup)
