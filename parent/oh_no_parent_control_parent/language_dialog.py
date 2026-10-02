"""Personal language selection with an isolated live translation preview."""

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for, TranslationContext,
)

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.about import app_name, branding_asset_path
from common.oh_no_parent_control_ui.languages import (
    SUPPORTED_LANGUAGES, language_direction, language_matches, selected_language,
)


class LanguageDialog(Gtk.Window):
    def __init__(self, parent, language, save, saved, cancelled):
        super().__init__(application=parent.get_application(),
                         title=m.LANGUAGE, transient_for=parent, modal=True,
                         destroy_with_parent=True, deletable=False)
        selected = selected_language(language, GLib.get_language_names())
        self._translation_context = TranslationContext(selected)
        set_text(self, 'title', m.LANGUAGE)
        set_automation_id(self, "language-dialog")
        self.add_css_class("parent-language-dialog")
        self.set_default_size(540, -1)
        self._save = save
        self._saved = saved
        self._cancelled = cancelled
        self._selected = selected
        self._saving = False
        self.set_titlebar(Gtk.Box())
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                          margin_start=28, margin_end=28, margin_top=16, margin_bottom=24)
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        logo = Gtk.Image.new_from_file(str(branding_asset_path("app_logo.png")))
        logo.set_pixel_size(64)
        accessible_text(logo, [Gtk.AccessibleProperty.LABEL],
                        [m.APP_NAME_S_LOGO % {'app_name': app_name()}])
        heading.append(logo)
        title = localized(Gtk.Label, label=m.CHOOSE_YOUR_LANGUAGE, wrap=True,
                          css_classes=["parent-language-title"])
        set_automation_id(title, "language-title")
        heading.append(title)
        content.append(heading)
        self._search = localized(Gtk.SearchEntry, placeholder_text=m.SEARCH_LANGUAGES)
        describe_control(self._search, m.SEARCH_LANGUAGES, m.SEARCH_LANGUAGES,
                         automation_id="language-search")
        self._search.connect("changed", self._filter_languages)
        content.append(self._search)
        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                css_classes=["parent-language-list"])
        self._language_rows = []
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            button = localized(Gtk.CheckButton, css_classes=["parent-language-choice"])
            # Keep the native radio control on the trailing edge and the
            # catalogue's native-language labels aligned on the leading edge.
            button.set_direction(Gtk.TextDirection.RTL)
            label = localized(Gtk.Label, label=name, xalign=0, hexpand=True)
            label.set_direction(Gtk.TextDirection.RTL if language_direction(identity) == 'rtl'
                                else Gtk.TextDirection.LTR)
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
            self._language_rows.append((button, identity, name))
        scroller = Gtk.ScrolledWindow(child=self._choices, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      overlay_scrolling=False,
                                      min_content_height=1)
        self._scroller = scroller
        set_automation_id(scroller, "language-list")
        content.append(scroller)
        self._error = localized(Gtk.Label, wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "language-error")
        content.append(self._error)
        actions = Gtk.Box(spacing=12, homogeneous=True, hexpand=True)
        self._cancel = localized(Gtk.Button, label=m.CANCEL,
                                 css_classes=["parent-language-cancel"])
        describe_control(self._cancel, m.CANCEL, m.CANCEL,
                         automation_id="language-cancel")
        self._cancel.connect("clicked", self._dismiss)
        actions.append(self._cancel)
        self._continue = localized(Gtk.Button, label=m.SAVE,
                                   css_classes=["suggested-action", "parent-language-continue"])
        describe_control(self._continue, m.SAVE, m.SAVE_YOUR_LANGUAGE_PREFERENCE,
                         automation_id="language-continue")
        self._continue.connect("clicked", self._submit)
        actions.append(self._continue)
        content.append(actions)
        self.set_child(content)
        self.set_default_widget(self._continue)
        self.connect("close-request", lambda *_args: True)
        parent.connect_object("notify::is-active", LanguageDialog._parent_activated, self)
        self.connect("map", self._size_to_host)
        self._size_to_host(self)

    def _size_to_host(self, _window):
        width = max(540, self.get_child().measure(Gtk.Orientation.HORIZONTAL, -1)[0])
        list_width = width - 56
        if not self._search.get_text():
            heights = [row.measure(Gtk.Orientation.VERTICAL, list_width)[1]
                       for row, _identity, _name in self._language_rows]
            # Include the list's own CSS border/padding around the first ten rows.
            self._list_height = (self._choices.measure(Gtk.Orientation.VERTICAL, list_width)[1]
                                 - sum(heights[10:]))
        # Window measurement also includes GTK's title-bar area/decorations.
        natural_height = (self.measure(Gtk.Orientation.VERTICAL, width)[1]
                          - self._scroller.measure(Gtk.Orientation.VERTICAL, list_width)[1]
                          + self._list_height)
        surface = self.get_transient_for().get_surface()
        if surface is not None:
            monitor = self.get_display().get_monitor_at_surface(surface)
            if monitor is not None:
                # Leave space for desktop panels, decorations and outer clearance.
                natural_height = min(natural_height, monitor.get_geometry().height - 96)
        self.set_default_size(width, max(1, natural_height))

    def _filter_languages(self, search):
        for row, identity, name in self._language_rows:
            row.set_visible(language_matches(search.get_text(), identity, name))
        self._scroller.get_vadjustment().set_value(0)

    def _parent_activated(self, *_args):
        # A compositor may activate the parent on an outside click, especially
        # when it is fullscreen. Keep the modal chooser above that window.
        if self.get_visible() and self.get_transient_for().is_active():
            self.present()

    def _choose(self, button, identity):
        if button.get_active():
            # Relabel the existing controls together, without remapping the window.
            context_for(self).apply(identity)
            self._selected = identity
            self._size_to_host(self)

    def _submit(self, _button):
        if self._saving:
            return
        self._saving = True
        self._error.set_visible(False)
        self._choices.set_sensitive(False)
        self._search.set_sensitive(False)
        self._continue.set_sensitive(False)
        self._cancel.set_sensitive(False)
        self._save(self._selected, self._success, self._failure)

    def _dismiss(self, _button):
        if self._saving:
            return
        self._cancelled()
        self.destroy()

    def _success(self, language):
        # Close the preview before applying the saved language to the frontend.
        self.destroy()
        self._saved(language)

    def _failure(self, _error):
        self._saving = False
        self._choices.set_sensitive(True)
        self._search.set_sensitive(True)
        self._continue.set_sensitive(True)
        self._cancel.set_sensitive(True)
        set_text(self._error, 'label', m.YOUR_LANGUAGE_COULD_NOT_BE_SAVED_PLEASE_TRY_AGAIN)
        self._error.set_visible(True)
        self._size_to_host(self)
