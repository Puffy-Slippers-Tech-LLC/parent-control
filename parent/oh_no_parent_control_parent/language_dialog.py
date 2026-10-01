"""Personal language selection; translations are applied in future work."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.languages import SUPPORTED_LANGUAGES


class LanguageDialog(Gtk.Window):
    def __init__(self, parent, selected, save, saved):
        super().__init__(title="Language", transient_for=parent, modal=True,
                         destroy_with_parent=True, deletable=False)
        set_automation_id(self, "parent-language-dialog")
        self.set_default_size(440, 620)
        self._save = save
        self._saved = saved
        self._selected = selected
        self._saving = False
        header = Gtk.HeaderBar(show_title_buttons=False)
        self.set_titlebar(header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                          margin_start=28, margin_end=28, margin_top=20, margin_bottom=24)
        content.append(Gtk.Image(icon_name="preferences-desktop-locale-symbolic", pixel_size=40))
        title = Gtk.Label(label="Choose your language", css_classes=["title-1"])
        set_automation_id(title, "parent-language-title")
        content.append(title)
        subtitle = Gtk.Label(label="You can change it later in preferences", wrap=True,
                             justify=Gtk.Justification.CENTER, css_classes=["dim-label"])
        set_automation_id(subtitle, "parent-language-description")
        content.append(subtitle)
        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                                css_classes=["card"])
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            button = Gtk.CheckButton(label=name, margin_start=16, margin_end=16,
                                     margin_top=7, margin_bottom=7)
            if first is None:
                first = button
            else:
                button.set_group(first)
            describe_control(button, name, f"Select {name}.",
                             automation_id=f"parent-language-choice-{identity.lower()}")
            button.set_active(identity == selected)
            button.connect("toggled", self._choose, identity)
            self._choices.append(button)
        scroller = Gtk.ScrolledWindow(child=self._choices, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      min_content_height=180)
        set_automation_id(scroller, "parent-language-list")
        content.append(scroller)
        self._error = Gtk.Label(wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "parent-language-error")
        content.append(self._error)
        self._continue = Gtk.Button(label="Continue", css_classes=["suggested-action", "pill"])
        describe_control(self._continue, "Continue", "Save your language preference.",
                         automation_id="parent-language-continue")
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
