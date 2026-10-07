"""Parent-only release notes, translated before native Markdown rendering."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, Gtk

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.about import app_name, branding_asset_path
from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for, register_retranslation,
)
from common.oh_no_parent_control_ui.whats_new import load_whats_new_translations, translate_content
from .release_markdown import markdown_blocks, safe_link


class WhatsNewDialog(Gtk.Window):
    def __init__(self, parent, record, closed):
        super().__init__(application=parent.get_application(), transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self._record = record
        self._closed = closed
        self._displayed = False
        self._dismissed = False
        title = m.WHATS_NEW_VERSION % {'version': record['ProductVersion']}
        set_text(self, 'title', title)
        set_automation_id(self, 'whats-new-dialog')
        self.add_css_class('parent-whats-new-dialog')
        self.set_default_size(660, 740)
        self.set_titlebar(Gtk.Box())
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                          margin_start=28, margin_end=28, margin_top=24, margin_bottom=22)
        heading = Gtk.Box(spacing=24)
        logo = Gtk.Image.new_from_file(str(branding_asset_path('app_logo.png')))
        logo.set_pixel_size(88)
        accessible_text(logo, [Gtk.AccessibleProperty.LABEL],
                        [m.APP_NAME_S_LOGO % {'app_name': app_name()}])
        heading.append(logo)
        title_widget = localized(Gtk.Label, label=title, xalign=0, wrap=True,
                                 hexpand=True, css_classes=['parent-whats-new-title'])
        set_automation_id(title_widget, 'whats-new-title')
        heading.append(title_widget)
        dismiss = Gtk.Button(icon_name='window-close-symbolic', valign=Gtk.Align.START,
                             css_classes=['circular', 'flat'])
        describe_control(dismiss, m.CLOSE, m.CLOSE, automation_id='whats-new-dismiss')
        dismiss.connect('clicked', self._dismiss)
        heading.append(dismiss)
        content.append(heading)
        self._blocks = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                               margin_start=24, margin_end=24, margin_top=20, margin_bottom=20)
        scroller = Gtk.ScrolledWindow(child=self._blocks, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      overlay_scrolling=False,
                                      min_content_height=1,
                                      css_classes=['parent-whats-new-content'])
        set_automation_id(scroller, 'whats-new-content')
        content.append(scroller)
        actions = Gtk.Box(spacing=12)
        hint = localized(Gtk.Label, label=m.WHATS_NEW_MENU_HINT, wrap=True, xalign=0,
                         hexpand=True, css_classes=['parent-whats-new-hint'])
        set_automation_id(hint, 'whats-new-menu-hint')
        actions.append(Gtk.Image(icon_name='dialog-information-symbolic', pixel_size=24))
        actions.append(hint)
        if record.get('SeeMore') and safe_link(record['SeeMore']):
            more = localized(Gtk.LinkButton, uri=record['SeeMore'], label=m.SEE_MORE)
            describe_control(more, m.SEE_MORE, m.SEE_MORE, automation_id='whats-new-see-more')
            actions.append(more)
        close = localized(Gtk.Button, label=m.CLOSE, valign=Gtk.Align.CENTER,
                          css_classes=['suggested-action', 'parent-whats-new-close'])
        describe_control(close, m.CLOSE, m.CLOSE, automation_id='whats-new-close')
        close.connect('clicked', self._dismiss)
        actions.append(close)
        content.append(actions)
        self.set_child(content)
        self.set_default_widget(close)
        self.connect('close-request', self._close_requested)
        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', self._key_pressed)
        self.add_controller(keys)
        self.connect('map', self._mapped)
        register_retranslation(self, self._render)

    def _render(self, _translations):
        translations = load_whats_new_translations(
            self._record['ProductVersion'], context_for(self).language)
        self._content = translate_content(self._record, translations)
        child = self._blocks.get_first_child()
        while child is not None:
            self._blocks.remove(child)
            child = self._blocks.get_first_child()
        for index, (kind, markup) in enumerate(markdown_blocks(self._content)):
            if kind == 'rule':
                widget = Gtk.Separator(margin_top=12, margin_bottom=12)
            else:
                widget = localized(Gtk.Label, label=markup, use_markup=True, xalign=0,
                                   wrap=True, selectable=True, hexpand=True, max_width_chars=52,
                                   css_classes=['parent-whats-new-' + kind])
                widget.connect('activate-link', self._activate_link)
            set_automation_id(widget, f'whats-new-block-{index}')
            self._blocks.append(widget)

    @staticmethod
    def _activate_link(_label, uri):
        if safe_link(uri):
            Gio.AppInfo.launch_default_for_uri(uri, None)
        return True

    def _mapped(self, _window):
        self._displayed = True
        surface = self.get_transient_for().get_surface()
        if surface is not None:
            monitor = self.get_display().get_monitor_at_surface(surface)
            if monitor is not None:
                geometry = monitor.get_geometry()
                self.set_default_size(min(660, max(1, geometry.width - 64)),
                                      min(740, max(1, geometry.height - 96)))

    def _dismiss(self, *_args):
        self.close()

    def _key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _close_requested(self, *_args):
        if not self._dismissed:
            self._dismissed = True
            self.destroy()
            self._closed(self._displayed)
        return True
