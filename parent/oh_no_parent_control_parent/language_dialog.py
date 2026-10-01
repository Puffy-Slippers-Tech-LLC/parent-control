"""Personal language selection; translations are applied in future work."""

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
        super().__init__(title="Language", transient_for=parent, modal=True,
                         destroy_with_parent=True, deletable=False)
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
        logo.update_property([Gtk.AccessibleProperty.LABEL],
                             [f"{app_name()} logo"])
        heading.append(logo)
        title = Gtk.Label(label="Choose your language",
                          css_classes=["parent-language-title"])
        set_automation_id(title, "language-title")
        heading.append(title)
        subtitle = Gtk.Label(label="You can change it later in preferences", wrap=True,
                             justify=Gtk.Justification.CENTER,
                             css_classes=["parent-language-description"])
        set_automation_id(subtitle, "language-description")
        heading.append(subtitle)
        content.append(heading)
        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                css_classes=["parent-language-list"])
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            button = Gtk.CheckButton(css_classes=["parent-language-choice"])
            # Keep the native radio control on the trailing edge and the
            # catalogue's native-language labels aligned on the leading edge.
            button.set_direction(Gtk.TextDirection.RTL)
            label = Gtk.Label(label=name, xalign=0, hexpand=True)
            label.set_direction(Gtk.TextDirection.LTR)
            button.set_child(label)
            if first is None:
                first = button
            else:
                button.set_group(first)
            describe_control(button, name, f"Select {name}.",
                             automation_id=f"language-choice-{identity.lower()}")
            button.set_active(identity == selected)
            button.connect("toggled", self._choose, identity)
            self._choices.append(button)
        set_automation_id(self._choices, "language-list")
        content.append(self._choices)
        self._error = Gtk.Label(wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "language-error")
        content.append(self._error)
        self._continue = Gtk.Button(label="Continue",
                                   halign=Gtk.Align.END, width_request=160,
                                   css_classes=["suggested-action", "parent-language-continue"])
        describe_control(self._continue, "Continue", "Save your language preference.",
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
        self._error.set_label("Your language could not be saved. Please try again.")
        self._error.set_visible(True)
