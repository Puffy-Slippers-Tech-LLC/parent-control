#!/usr/bin/python3
"""Qualify TIME05 clock observations in the owned VM without desktop input."""
from check_graphical_smoke import main as smoke


def main():
    return smoke(local_calendar=True)


if __name__ == '__main__':
    raise SystemExit(main())
