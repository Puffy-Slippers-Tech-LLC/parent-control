"""The request screens' language chooser, with their own metal-board UI."""

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for,
)

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.languages import SUPPORTED_LANGUAGES, selected_language
from .chrome import ArmoredButton, MetalBoard


class LanguageDialog(Gtk.Window):
    def __init__(self, parent, language, save, saved):
        super().__init__(title=m.LANGUAGE, transient_for=parent, modal=True,
                         destroy_with_parent=True, deletable=False, decorated=False)
        set_text(self, 'title', m.LANGUAGE)
        set_automation_id(self, "language-dialog")
        self.add_css_class("oh-no-parent-control-language-dialog")
        self.set_default_size(400, 540)
        self._save, self._saved = save, saved
        self._selected = selected_language(language, GLib.get_language_names())
        self._saving = False

        board = MetalBoard(orientation=Gtk.Orientation.VERTICAL)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          margin_start=24, margin_end=24, margin_top=24, margin_bottom=24)
        content.append(localized(Gtk.Label, label="🌍", css_classes=["title-1"]))
        title = localized(Gtk.Label, label=m.SELECT_LANGUAGE, css_classes=["title-1"])
        set_automation_id(title, "language-title")
        content.append(title)
        description = localized(Gtk.Label, label=m.YOU_CAN_CHANGE_IT_IN_PREFERENCES_LATER,
                                wrap=True, justify=Gtk.Justification.CENTER)
        set_automation_id(description, "language-description")
        content.append(description)

        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            choice = localized(Gtk.CheckButton, label=name)
            if first is None:
                first = choice
            else:
                choice.set_group(first)
            describe_control(choice, name, m.SELECT_NAME_S % {'name': name},
                             automation_id=f"language-choice-{identity.lower()}")
            choice.set_active(identity == self._selected)
            choice.connect("toggled", self._choose, identity)
            self._choices.append(choice)
        scroller = Gtk.ScrolledWindow(child=self._choices, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      min_content_height=150)
        set_automation_id(scroller, "language-list")
        content.append(scroller)
        self._error = localized(Gtk.Label, wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "language-error")
        content.append(self._error)
        self._continue = localized(ArmoredButton, label=m.CONTINUE,
                                       css_classes=["oh-no-parent-control-request-button"])
        describe_control(self._continue, m.CONTINUE, m.SAVE_YOUR_LANGUAGE_PREFERENCE,
                         automation_id="language-continue")
        self._continue.connect("clicked", self._submit)
        content.append(self._continue)
        board.append(content)
        self.set_child(board)
        self.set_default_widget(self._continue)
        self.connect("close-request", lambda *_args: True)

    def _choose(self, choice, identity):
        if choice.get_active():
            self._selected = identity

    def _submit(self, _button):
        if self._saving:
            return
        self._saving = True
        self._error.set_visible(False)
        self._choices.set_sensitive(False)
        self._continue.set_sensitive(False)
        self._save(self._selected, self._success, self._failure)

    def _success(self, language):
        self._saved(language)
        self.destroy()

    def _failure(self, _error):
        self._saving = False
        self._choices.set_sensitive(True)
        self._continue.set_sensitive(True)
        set_text(self._error, 'label', m.YOUR_LANGUAGE_COULD_NOT_BE_SAVED_PLEASE_TRY_AGAIN)
        self._error.set_visible(True)
