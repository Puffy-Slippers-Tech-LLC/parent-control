"""Finite customer allowance inputs; broker-only 1440 acceptance is excluded."""

from accessible_ui import INVALID, INVALID_DESCRIPTION, PRESETS

ACCEPTED = (0, 1, 15, 1439)

# Equivalent preset classes: minimum, whole hour, half hour, maximum.
REPRESENTATIVE_PRESETS = (0, 60, 90, 1410)
