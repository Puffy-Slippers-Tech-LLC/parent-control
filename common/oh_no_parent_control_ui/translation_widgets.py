"""Explicit GTK text bindings; relabel without rebuilding controls or drafts."""

import weakref

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk

from .localization import load_translations
from .message import Message, JoinedMessage, render


class TranslationContext:
    def __init__(self, language=''):
        self.translations = load_translations(language, GLib.get_language_names())
        self.members = weakref.WeakSet()

    def apply(self, language):
        # Load first: a package error keeps the last usable context intact.
        translations = load_translations(language, GLib.get_language_names())
        self.translations = translations
        for widget in list(self.members):
            _refresh(widget)


def context_for(widget):
    owner = getattr(widget, '_translation_owner', None)
    if owner is not None:
        return context_for(owner)
    root = widget.get_root() if isinstance(widget, Gtk.Widget) else None
    if root is not None and root is not widget:
        return context_for(root)
    if isinstance(widget, Gtk.Window) and widget.get_transient_for() is not None:
        return context_for(widget.get_transient_for())
    if not hasattr(widget, '_translation_context'):
        widget._translation_context = TranslationContext()
    return widget._translation_context


def _refresh(widget, *_args):
    context = context_for(widget)
    context.members.add(widget)
    for (kind, key), value in getattr(widget, '_message_bindings', {}).items():
        text = render(value, context.translations)
        if kind == 'property':
            widget.set_property(key, text)
        else:
            widget.update_property([key], [text])
    callback = getattr(widget, '_retranslate', None)
    if callback is not None:
        callback(context.translations)


def _bind(widget, kind, key, value):
    if not hasattr(widget, '_message_bindings'):
        widget._message_bindings = {}
        if isinstance(widget, Gtk.Widget):
            widget.connect('notify::root', _refresh)
    identity = (kind, key)
    if isinstance(value, (Message, JoinedMessage)):
        widget._message_bindings[identity] = value
    else:
        widget._message_bindings.pop(identity, None)
    context = context_for(widget)
    context.members.add(widget)
    return render(value, context.translations)


def localized(factory, *args, translation_owner=None, **kwargs):
    bindings = {key.replace('_', '-'): value for key, value in kwargs.items()
                if isinstance(value, (Message, JoinedMessage))}
    widget = factory(*args, **{key: str(value) if isinstance(value, (Message, JoinedMessage))
                              else value for key, value in kwargs.items()})
    if translation_owner is not None:
        widget._translation_owner = translation_owner
    for key, value in bindings.items():
        set_text(widget, key, value)
    return widget


def set_text(widget, property_name, value):
    widget.set_property(property_name, _bind(widget, 'property', property_name, value))


def accessible_text(widget, properties, values):
    widget.update_property(properties, [_bind(widget, 'accessible', key, value)
                                       for key, value in zip(properties, values)])


def register_retranslation(widget, callback):
    widget._retranslate = callback
    if not hasattr(widget, '_message_bindings'):
        widget._message_bindings = {}
        widget.connect('notify::root', _refresh)
    _refresh(widget)
