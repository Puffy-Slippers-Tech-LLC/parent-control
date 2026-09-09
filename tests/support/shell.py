"""Filesystem rewriting for tests that separately replace system commands."""


SYSTEM_PREFIXES = ("/etc/", "/var/", "/run/", "/home/", "/usr/")


def relocate_system_paths(source, root, prefixes=SYSTEM_PREFIXES):
    """Relocate known absolute prefixes in a test copy of a maintained script.

    This is fixture construction, not a sandbox. Callers must also provide
    command doubles or an explicit safe PATH before executing the copy.
    """
    for prefix in prefixes:
        source = source.replace(prefix, str(root) + prefix)
    return source
