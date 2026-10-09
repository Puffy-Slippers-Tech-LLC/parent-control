"""Child release notes on the request session's riveted metal board."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, Gtk, Pango

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.about import app_name, branding_asset_path
from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.release_markdown import markdown_blocks, safe_link
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for, register_retranslation,
)
from common.oh_no_parent_control_ui.whats_new import load_whats_new_translations, translate_content
from .chrome import ArmoredButton, MetalBoard


class WhatsNewDialog(Gtk.Window):
    def __init__(self, parent, record, closed, *, links_enabled):
        super().__init__(application=parent.get_application(), transient_for=parent,
                         modal=True, destroy_with_parent=True, decorated=False)
        self._record = record
        self._closed = closed
        self._links_enabled = links_enabled
        self._displayed = False
        self._dismissed = False
        self.add_css_class('kiosk-whats-new-dialog')
        set_automation_id(self, 'whats-new-dialog')
        title = m.WHATS_NEW_VERSION % {'version': record['ProductVersion']}
        set_text(self, 'title', title)
        self.set_default_size(580, 700)
        board = MetalBoard(orientation=Gtk.Orientation.VERTICAL,
                           css_classes=['kiosk-whats-new-board'])
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                          margin_start=32, margin_end=32, margin_top=28, margin_bottom=28)
        header = Gtk.Box(spacing=20)
        logo = Gtk.Image.new_from_file(str(branding_asset_path('app_logo.png')))
        logo.set_pixel_size(64)
        accessible_text(logo, [Gtk.AccessibleProperty.LABEL],
                        [m.APP_NAME_S_LOGO % {'app_name': app_name()}])
        header.append(logo)
        heading = localized(Gtk.Label, label=title, xalign=0, wrap=True, hexpand=True,
                            wrap_mode=Pango.WrapMode.WORD_CHAR,
                            css_classes=['kiosk-whats-new-title'])
        set_automation_id(heading, 'whats-new-title')
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        titles.append(heading)
        subtitle = localized(Gtk.Label, label=m.WHATS_NEW_CHILD_SUBTITLE, xalign=0,
                             wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                             css_classes=['kiosk-whats-new-subtitle'])
        set_automation_id(subtitle, 'whats-new-subtitle')
        titles.append(subtitle)
        header.append(titles)
        dismiss = ArmoredButton(label='×', armor_kind='cancel', valign=Gtk.Align.START,
                                css_classes=['kiosk-whats-new-dismiss'])
        describe_control(dismiss, m.CLOSE, m.CLOSE, automation_id='whats-new-dismiss')
        dismiss.connect('clicked', self._dismiss)
        header.append(dismiss)
        content.append(header)
        self._blocks = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                               margin_start=20, margin_end=20, margin_top=18, margin_bottom=18)
        scroller = Gtk.ScrolledWindow(child=self._blocks, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      overlay_scrolling=False, min_content_height=1,
                                      css_classes=['kiosk-whats-new-content'])
        set_automation_id(scroller, 'whats-new-content')
        content.append(scroller)
        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        if links_enabled and record.get('SeeMore') and safe_link(record['SeeMore']):
            more = localized(Gtk.LinkButton, uri=record['SeeMore'], label=m.SEE_MORE,
                             halign=Gtk.Align.END)
            describe_control(more, m.SEE_MORE, m.SEE_MORE, automation_id='whats-new-see-more')
            footer.append(more)
        actions = Gtk.Box(spacing=16)
        info = Gtk.Image(icon_name='dialog-information-symbolic', pixel_size=24,
                         css_classes=['kiosk-whats-new-info'])
        actions.append(info)
        hint = localized(Gtk.Label, label=m.WHATS_NEW_MENU_HINT, wrap=True, xalign=0,
                         wrap_mode=Pango.WrapMode.WORD_CHAR, hexpand=True, max_width_chars=22,
                         css_classes=['kiosk-whats-new-hint'])
        set_automation_id(hint, 'whats-new-menu-hint')
        actions.append(hint)
        close = localized(ArmoredButton, label=m.CONTINUE, valign=Gtk.Align.CENTER,
                          armor_kind='request', css_classes=['oh-no-parent-control-request-button',
                                                            'kiosk-whats-new-continue'])
        describe_control(close, m.CONTINUE, m.CLOSE, automation_id='whats-new-close')
        close.connect('clicked', self._dismiss)
        actions.append(close)
        footer.append(actions)
        content.append(footer)
        board.append(content)
        self.set_child(board)
        self.set_default_widget(close)
        self.connect('close-request', self._close_requested)
        self.connect('map', self._mapped)
        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', self._key_pressed)
        self.add_controller(keys)
        register_retranslation(self, self._render)

    def _render(self, _translations):
        translations = load_whats_new_translations(
            self._record['ProductVersion'], context_for(self).language)
        source = translate_content(self._record, translations)
        child = self._blocks.get_first_child()
        while child is not None:
            self._blocks.remove(child)
            child = self._blocks.get_first_child()
        for index, (kind, markup) in enumerate(markdown_blocks(
                source, links_enabled=self._links_enabled)):
            if kind == 'rule':
                widget = Gtk.Separator(margin_top=12, margin_bottom=12)
            else:
                widget = localized(Gtk.Label, label=markup, use_markup=True, xalign=0,
                                   wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                   selectable=True, hexpand=True, max_width_chars=48,
                                   css_classes=['kiosk-whats-new-' + kind])
                widget.connect('activate-link', self._activate_link)
            if kind == 'heading':
                if index:
                    self._blocks.append(Gtk.Separator(margin_top=12, margin_bottom=8))
                row = Gtk.Box(spacing=14)
                row.append(Gtk.Label(label='★', valign=Gtk.Align.START,
                                     css_classes=['kiosk-whats-new-star']))
                row.append(widget)
                self._blocks.append(row)
            else:
                self._blocks.append(widget)
            set_automation_id(widget, f'whats-new-block-{index}')

    def _activate_link(self, _label, uri):
        if self._links_enabled and safe_link(uri):
            Gio.AppInfo.launch_default_for_uri(uri, None)
        return True

    def _mapped(self, _window):
        self._displayed = True
        surface = self.get_transient_for().get_surface()
        if surface is not None:
            monitor = self.get_display().get_monitor_at_surface(surface)
            if monitor is not None:
                geometry = monitor.get_geometry()
                self.set_default_size(min(580, max(1, geometry.width - 48)),
                                      min(700, max(1, geometry.height - 64)))

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
