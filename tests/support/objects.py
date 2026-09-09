"""Explicit method binding for unit tests that do not construct GTK widgets."""

from types import MethodType


def bind_methods(target, cls, names):
    """Bind actual class methods to a test-owned state object, without rewriting code."""
    for name in names:
        setattr(target, name, MethodType(getattr(cls, name), target))
    return target
