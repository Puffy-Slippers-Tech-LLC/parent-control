"""Shared VM customer-download destination, relative to the bound user's home."""
from pathlib import Path

DIRECTORY = 'Downloads'


def download_directory(home):
    """Return ~/Downloads for an explicitly bound account, never the host home."""
    return Path(home) / DIRECTORY
