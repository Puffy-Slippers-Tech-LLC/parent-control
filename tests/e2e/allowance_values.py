"""Finite customer allowance inputs; broker-only 1440 acceptance is excluded."""

from accessible_ui import INVALID, INVALID_DESCRIPTION

PRESETS = (0, 15, 30, 45, *range(60, 1411, 30))
ACCEPTED = (0, 1, 15, 1439)
