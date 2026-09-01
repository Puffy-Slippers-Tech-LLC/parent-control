#!/usr/bin/env python3
"""Render Polkit policy metadata from the project's shared branding file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


def render(template: Path, branding: Path) -> str:
    """Return the policy template with XML-safe shared branding substituted."""
    values = json.loads(branding.read_text(encoding="utf-8"))
    vendor_name = values["vendor_name"]
    if not isinstance(vendor_name, str) or not vendor_name:
        raise ValueError("vendor_name must be a non-empty string")

    result = template.read_text(encoding="utf-8")
    result = result.replace("@VENDOR_NAME@", escape(vendor_name))
    if "@VENDOR_" in result:
        raise ValueError("policy template contains an unknown vendor placeholder")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--branding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.write_text(render(args.template, args.branding), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
