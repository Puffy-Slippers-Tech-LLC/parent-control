"""Personal language selection in the owning frontend's current language."""

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for,
)

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.about import app_name, branding_asset_path
from common.oh_no_parent_control_ui.languages import (
    SUPPORTED_LANGUAGES, selected_language,
)


class LanguageDialog(Gtk.Window):
    def __init__(self, parent, language, save, saved):
        super().__init__(title=m.LANGUAGE, transient_for=parent, modal=True,
                         destroy_with_parent=True, deletable=False)
        set_text(self, 'title', m.LANGUAGE)
        set_automation_id(self, "language-dialog")
        self.add_css_class("parent-language-dialog")
        self.set_default_size(540, 660)
        self._save = save
        self._saved = saved
        selected = selected_language(language, GLib.get_language_names())
        self._selected = selected
        self._saving = False
        header = Gtk.HeaderBar(show_title_buttons=False,
                               css_classes=["parent-language-header"])
        self.set_titlebar(header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                          margin_start=28, margin_end=28, margin_top=16, margin_bottom=24)
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        logo = Gtk.Image.new_from_file(str(branding_asset_path("app_logo.png")))
        logo.set_pixel_size(64)
        accessible_text(logo, [Gtk.AccessibleProperty.LABEL],
                        [m.APP_NAME_S_LOGO % {'app_name': app_name()}])
        heading.append(logo)
        title = localized(Gtk.Label, label=m.CHOOSE_YOUR_LANGUAGE,
                          css_classes=["parent-language-title"])
        set_automation_id(title, "language-title")
        heading.append(title)
        subtitle = localized(Gtk.Label, label=m.YOU_CAN_CHANGE_IT_IN_PREFERENCES, wrap=True,
                             justify=Gtk.Justification.CENTER,
                             css_classes=["parent-language-description"])
        set_automation_id(subtitle, "language-description")
        heading.append(subtitle)
        content.append(heading)
        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                css_classes=["parent-language-list"])
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            button = localized(Gtk.CheckButton, css_classes=["parent-language-choice"])
            # Keep the native radio control on the trailing edge and the
            # catalogue's native-language labels aligned on the leading edge.
            button.set_direction(Gtk.TextDirection.RTL)
            label = localized(Gtk.Label, label=name, xalign=0, hexpand=True)
            label.set_direction(Gtk.TextDirection.LTR)
            button.set_child(label)
            if first is None:
                first = button
            else:
                button.set_group(first)
            describe_control(button, name, m.SELECT_NAME_S % {'name': name},
                             automation_id=f"language-choice-{identity.lower()}")
            button.set_active(identity == selected)
            button.connect("toggled", self._choose, identity)
            self._choices.append(button)
        set_automation_id(self._choices, "language-list")
        content.append(self._choices)
        self._error = localized(Gtk.Label, wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "language-error")
        content.append(self._error)
        self._continue = localized(Gtk.Button, label=m.CONTINUE,
                                   halign=Gtk.Align.END, width_request=160,
                                   css_classes=["suggested-action", "parent-language-continue"])
        describe_control(self._continue, m.CONTINUE, m.SAVE_YOUR_LANGUAGE_PREFERENCE,
                         automation_id="language-continue")
        self._continue.connect("clicked", self._submit)
        content.append(self._continue)
        self.set_child(content)
        self.set_default_widget(self._continue)
        self.connect("close-request", lambda *_args: True)

    def _choose(self, button, identity):
        if button.get_active():
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
