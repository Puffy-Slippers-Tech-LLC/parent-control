"""Filesystem rewriting for tests that separately replace system commands."""

import re


SYSTEM_PREFIXES = ("/etc/", "/var/", "/run/", "/home/", "/usr/")


def relocate_system_paths(source, root, prefixes=SYSTEM_PREFIXES):
    """Relocate known absolute prefixes in a test copy of a maintained script.

    This is fixture construction, not a sandbox. Callers must also provide
    command doubles or an explicit safe PATH before executing the copy.
    """
    if not prefixes:
        return source
    # Rewrite only the original input. A later str.replace pass would rewrite
    # an inserted /var/tmp or /home fixture root and corrupt earlier paths.
    pattern = '|'.join(re.escape(prefix) for prefix in sorted(prefixes, key=len, reverse=True))
    return re.sub(pattern, lambda match: str(root) + match.group(), source)
