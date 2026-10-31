"""Run the installed broker with an explicit, unshipped investigation gate.

Use only on an installed development target, never on the development host.
The ordinary installed launcher still owns trust and migration readiness.
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


def suppress_extension_activation(manager):
    """Suppress every activation write while retaining normal disable/cleanup."""
    original = manager.set_enabled

    def set_enabled(self, uid, enabled, *, recover_global_switch=False):
        if enabled:
            print("DEVELOPMENT ONLY: child extension activation suppressed; "
                  "extension readiness is not established", file=sys.stderr, flush=True)
            return None
        return original(self, uid, enabled, recover_global_switch=recover_global_switch)

    manager.set_enabled = set_enabled


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disable-child-extension-recovery', action='store_true',
                        help='suppress child extension activation and global-switch recovery')
    arguments = parser.parse_args(argv)
    # Always use installed modules, even when invoked from a checkout. Do not
    # replace the package's readiness checks or mix checkout and installed code.
    root = Path('/usr/lib/oh-no-parent-control')
    sys.path[:0] = [str(root), str(root / 'broker')]
    if arguments.disable_child_extension_recovery:
        from oh_no_parent_control.extension_manager import ExtensionManager
        suppress_extension_activation(ExtensionManager)
        print('DEVELOPMENT ONLY: child extension recovery disabled for this broker process',
              file=sys.stderr, flush=True)
    runpy.run_path('/usr/libexec/oh-no-parent-control-broker', run_name='__main__')


if __name__ == '__main__':
    main()
