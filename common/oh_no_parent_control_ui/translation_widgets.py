"""Explicit GTK text bindings; relabel without rebuilding controls or drafts."""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk

from .localization import load_translations
from .languages import language_direction, selected_language
from .message import Message, JoinedMessage, render


class TranslationContext:
    def __init__(self, language=''):
        self.translations = load_translations(language, GLib.get_language_names())
        self.language = selected_language(language, GLib.get_language_names())
        self.direction = language_direction(self.language)
        self.members = set()

    def apply(self, language):
        # Load first: a package error keeps the last usable context intact.
        translations = load_translations(language, GLib.get_language_names())
        self.translations = translations
        self.language = selected_language(language, GLib.get_language_names())
        self.direction = language_direction(self.language)
        roots = set()
        for bindings in list(self.members):
            widget = bindings.widget()
            if isinstance(widget, Gtk.Widget):
                roots.add(widget.get_root() or widget)
        for root in roots:
            _direction_tree(root, self)
        for bindings in list(self.members):
            widget = bindings.widget()
            if widget is not None:
                _refresh(widget, bindings=bindings)


class _Bindings:
    """Keep source bindings for the native object's lifetime, not its wrapper."""

    def __init__(self, widget):
        self.values = {}
        self.callback = None
        self.context = None
        self.fixed_direction = None
        self.label_alignment = None
        self.direction_pending = False
        self.widget = widget.weak_ref(self.release)
        if isinstance(widget, Gtk.Widget):
            # Signal user data survives recreation of a PyGObject wrapper.
            widget.connect('notify::root', _refresh, self)

    def release(self):
        if self.context is not None:
            self.context.members.discard(self)
            self.context = None

    def join(self, context):
        if self.context is not context:
            self.release()
            self.context = context
            context.members.add(self)


def _bindings_for(widget):
    if not hasattr(widget, '_message_bindings'):
        widget._message_bindings = _Bindings(widget)
    return widget._message_bindings


def fixed_direction(widget, direction):
    """Keep visual-order controls and native language names independent of UI locale."""
    _bindings_for(widget).fixed_direction = direction
    widget.set_direction(direction)


def _direction_widget(widget, context):
    bindings = _bindings_for(widget)
    direction = (bindings.fixed_direction if bindings.fixed_direction is not None else
                 Gtk.TextDirection.RTL if context.direction == 'rtl' else Gtk.TextDirection.LTR)
    widget.set_direction(direction)
    if isinstance(widget, Gtk.Label) and bindings.fixed_direction is None:
        if bindings.label_alignment is None:
            bindings.label_alignment = widget.get_xalign()
        # Gtk.Label.xalign is physical, unlike container start/end alignment.
        widget.set_xalign(1 - bindings.label_alignment if context.direction == 'rtl'
                          else bindings.label_alignment)


def _direction_tree(widget, context):
    _direction_widget(widget, context)
    child = widget.get_first_child()
    while child is not None:
        _direction_tree(child, context)
        child = child.get_next_sibling()


def _refresh_direction(widget, context):
    if not isinstance(widget, Gtk.Widget):
        return
    root = widget.get_root() or widget
    current = widget
    while current is not None:
        _direction_widget(current, context)
        current = current.get_parent()
    bindings = _bindings_for(root)
    if not bindings.direction_pending:
        bindings.direction_pending = True
        def synchronize():
            bindings.direction_pending = False
            live = bindings.widget()
            if live is not None:
                _direction_tree(live, context_for(live))
            return GLib.SOURCE_REMOVE
        GLib.idle_add(synchronize)


def context_for(widget):
    owner = getattr(widget, '_translation_owner', None)
    if owner is not None:
        return context_for(owner)
    root = widget.get_root() if isinstance(widget, Gtk.Widget) else None
    if root is not None and root is not widget:
        return context_for(root)
    # A language chooser previews its candidate in a private window context.
    # Ordinary shared dialogs still inherit their transient parent's context.
    if hasattr(widget, '_translation_context'):
        return widget._translation_context
    if isinstance(widget, Gtk.Window) and widget.get_transient_for() is not None:
        return context_for(widget.get_transient_for())
    if not hasattr(widget, '_translation_context'):
        widget._translation_context = TranslationContext()
    return widget._translation_context


def _refresh(widget, _property=None, bindings=None):
    bindings = bindings or _bindings_for(widget)
    widget._message_bindings = bindings
    context = context_for(widget)
    bindings.join(context)
    _refresh_direction(widget, context)
    for (kind, key), value in bindings.values.items():
        text = render(value, context.translations)
        if kind == 'property':
            widget.set_property(key, text)
        else:
            widget.update_property([key], [text])
    callback = bindings.callback
    if callback is not None:
        callback(context.translations)


def _bind(widget, kind, key, value):
    bindings = _bindings_for(widget)
    identity = (kind, key)
    if isinstance(value, (Message, JoinedMessage)):
        bindings.values[identity] = value
    else:
        bindings.values.pop(identity, None)
    context = context_for(widget)
    bindings.join(context)
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
    bindings = _bindings_for(widget)
    if getattr(callback, '__self__', None) is widget:
        # A bound method would keep the native widget alive through its context.
        # Resolve its receiver through the same native weak reference instead.
        function = callback.__func__
        bindings.callback = lambda translations: function(bindings.widget(), translations)
    else:
        bindings.callback = callback
    _refresh(widget)
