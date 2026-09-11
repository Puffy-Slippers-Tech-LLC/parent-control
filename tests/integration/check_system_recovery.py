#!/usr/bin/python3
"""Finish only identity-verified cleanup of an interrupted installed-system run."""

from check_graphical_recovery import main as recover


def main():
    return recover(graphics_type='spice')


if __name__ == '__main__':
    raise SystemExit(main())
