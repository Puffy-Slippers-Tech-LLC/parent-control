"""Load standalone scripts through Python's supported file-import API."""

import importlib.util
import sys


def load_module(name, path):
    """Load a fresh script, registering it for dataclasses and recursive imports.

    Successful loads remain addressable by their explicit test-only name. A
    failed import restores the previous registration instead of poisoning
    subsequent tests. Normal package imports should use normal Python imports.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Python module: {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return module
