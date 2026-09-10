"""Fixed terminal contexts for read-only guest recipient proofs.

These are trusted program fragments, not a caller-selectable device interface.
VT6 uses the kernel-rendered VNC surface; serial remains a separate transport.
Foreground observation supplements pixel/recipient checks, never authorizes
input by itself and cannot make the observation-to-input interval atomic.
"""

SERIAL = '''import os,pathlib
terminal_unit = 'serial-getty@ttyS0.service'
terminal_path = '/dev/ttyS0'
terminal_device = os.makedev(4,64)
def check_active_terminal():
    pass
'''

VT6 = '''import os,pathlib
terminal_unit = 'getty@tty6.service'
terminal_path = '/dev/tty6'
terminal_device = os.makedev(4,6)
def check_active_terminal():
    assert pathlib.Path('/sys/class/tty/tty0/active').read_text() == 'tty6\\n'
'''
