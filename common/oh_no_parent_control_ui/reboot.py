"""Product reboot detection shared by runtime entry points and scenarios.

Requests live in /run and expire at reboot. The global Ubuntu marker alone is
not a product request: its package list must contain our exact package name.
This module has no GTK, D-Bus or privileged-service dependencies.
"""

from pathlib import Path


def product_reboot_required(run=Path("/run")):
    """Recognize installation/upgrade requests, preserving unrelated reboots."""
    if (run / "oh-no-parent-control-child-trust-reboot").exists():
        return True
    if (run / "oh-no-parent-control-reboot-required").is_file():
        return True
    if not (run / "reboot-required").is_file():
        return False
    try:
        packages = (run / "reboot-required.pkgs").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return "oh-no-parent-control" in packages.splitlines()
