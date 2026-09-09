"""Run actual graphical Perl helpers with scenario-supplied public API doubles."""

import subprocess

from tests.support.paths import ROOT

LIB = ROOT / "tests/integration/graphical_smoke/lib"


def run_perl(program, *arguments, timeout=10):
    """Return both output streams and preserve interpreter failures and deadlines."""
    return subprocess.run(
        ["/usr/bin/perl", "-I", str(LIB), "-", *arguments],
        input=program, text=True, capture_output=True, timeout=timeout, check=True,
    )
