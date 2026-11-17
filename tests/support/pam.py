"""Real libpam dispatch for host tests, with the host audit transport doubled."""

import ctypes
import subprocess

from tests.support.paths import ROOT
from tools.test_storage import scratch_descriptors


_audit = None


def load_private_pam(directory):
    """Load the audit double before libpam resolves its audit_open symbol.

    Private account names and stacks must neither write host audit events nor
    depend on permission to open its netlink socket. Only that transport is
    replaced; libpam still dispatches modules and returns their real results.
    All host-side libpam users share this loader so load order is consistent.
    Exec'd children and installed-system probes retain the real audit library.
    """
    global _audit
    if _audit is None:
        output = directory / 'pam-audit.so'
        subprocess.run(
            ['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
             '-o', str(output), str(ROOT / 'tests/support/pam_audit_fixture.c')],
            check=True, capture_output=True, text=True, timeout=30,
            pass_fds=scratch_descriptors(),
        )
        # Keep the symbol provider loaded for libpam's process lifetime.
        _audit = ctypes.CDLL(str(output), mode=ctypes.RTLD_GLOBAL)
    return ctypes.CDLL('libpam.so.0')
