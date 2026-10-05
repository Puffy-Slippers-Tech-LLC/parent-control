"""Personal language selection with an isolated live translation preview."""

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for, TranslationContext, fixed_direction,
)

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.application_ui import bind_ui
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
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._search_keys)
        self.add_controller(keys)
        content.append(self._search)
        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._language_rows = []
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            button = localized(Gtk.CheckButton, css_classes=["parent-language-choice"])
            # Keep the native radio control on the trailing edge and the
            # catalogue's native-language labels aligned on the leading edge.
            fixed_direction(button, Gtk.TextDirection.RTL)
            label = localized(Gtk.Label, label=name, xalign=0, hexpand=True)
            fixed_direction(label, Gtk.TextDirection.RTL if language_direction(identity) == 'rtl'
                            else Gtk.TextDirection.LTR, language=identity)
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
                                      css_classes=["parent-language-list"],
                                      accessible_role=Gtk.AccessibleRole.GROUP,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      overlay_scrolling=False,
                                      min_content_height=1)
        self._scroller = scroller
        describe_control(scroller, m.LANGUAGE, m.CHOOSE_YOUR_LANGUAGE,
                         automation_id="language-list")
        bind_ui(scroller, get_value=lambda: self._selected,
                set_value=self._ui_select_language,
                choices=lambda: [identity for _row, identity, _name in self._language_rows])
        content.append(scroller)
        self._error = localized(Gtk.Label, wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "language-error")
        content.append(self._error)
        actions = Gtk.Box(spacing=12, homogeneous=True, hexpand=True)
        # Previewing an RTL candidate must not swap Save and Cancel under the
        # pointer. Button text still follows the candidate's own direction.
        fixed_direction(actions, Gtk.TextDirection.LTR)
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
            # Include the scroller's one-pixel CSS border around the first ten rows.
            self._list_height = (self._choices.measure(Gtk.Orientation.VERTICAL, list_width)[1]
                                 - sum(heights[10:]) + 2)
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
        has_matches = False
        for row, identity, name in self._language_rows:
            matches = language_matches(search.get_text(), identity, name)
            row.set_visible(matches)
            has_matches = has_matches or matches
        self._scroller.set_focusable(has_matches)
        self._scroller.get_vadjustment().set_value(0)

    def _ui_select_language(self, value):
        for row, identity, _name in self._language_rows:
            if value == identity:
                if not row.get_visible() or not row.is_sensitive():
                    raise ValueError("language choice is unavailable")
                row.set_active(True)
                return
        raise ValueError("unknown language code")

    def _search_keys(self, _controller, keyval, _keycode, state):
        if keyval == Gdk.KEY_Escape and self._search.is_sensitive() and self._search.get_text():
            self._search.set_text("")
            return True
        if keyval == Gdk.KEY_Tab and not state & Gtk.accelerator_get_default_mod_mask():
            # GTK's radio-group Tab entry can skip every match when its active
            # member is hidden. Enter a visible row without changing selection.
            matches = [(row, identity) for row, identity, _name in self._language_rows
                       if row.get_visible() and row.is_sensitive()]
            focus = self.get_focus()
            in_search = focus is not None and (focus == self._search
                                               or focus.is_ancestor(self._search))
            if not matches and (in_search or self._scroller.has_focus()):
                return self._cancel.grab_focus()
            if matches and self._scroller.has_focus():
                row = next((row for row, identity in matches if identity == self._selected),
                           matches[0][0])
                return row.grab_focus()
        return False

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
