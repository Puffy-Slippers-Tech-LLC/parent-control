#!/usr/bin/python3
"""Compatibility entry point for the shared packaging helper."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))
from package_activation import *  # noqa: F403

if __name__ == "__main__":
    main()
