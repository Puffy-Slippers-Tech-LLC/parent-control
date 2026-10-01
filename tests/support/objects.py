"""Explicit method binding for unit tests that do not construct GTK widgets."""

from types import MethodType


def bind_methods(target, cls, names):
    """Bind actual class methods to a test-owned state object, without rewriting code."""
    for name in names:
        setattr(target, name, MethodType(getattr(cls, name), target))
    return target


def set_plain_text(widget, property_name, value):
    """English presentation boundary for displayless controller/widget doubles.

    Real native binding lifetime and language switching are covered by UI tests.
    Keep the existing setter observations in controller tests independent of GTK.
    """
    from gettext import NullTranslations
    from common.oh_no_parent_control_ui.message import render
    getattr(widget, 'set_' + property_name.replace('-', '_'))(render(value, NullTranslations()))


def plain_accessible_text(widget, properties, values):
    from gettext import NullTranslations
    from common.oh_no_parent_control_ui.message import render
    widget.update_property(properties, [render(value, NullTranslations()) for value in values])
