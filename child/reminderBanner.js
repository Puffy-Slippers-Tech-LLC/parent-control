import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Pango from 'gi://Pango';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import {describeControl} from './accessibility.js';

// Shell's tray times out noncritical banners after four seconds. Own only
// this product's chrome and lifetime so fullscreen urgency stays independent.
let activeSource = null;
let fontLoaded = false;

// Both the delivery timeout and the remaining-time countdown use whole-second
// cells. Keep the original cell count as the denominator while fills go dark.
function createCountdown(totalSeconds, translations) {
    const actor = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL,
        style_class: 'screen-time-reminder-countdown', visible: totalSeconds > 0});
    const row = new St.BoxLayout({style_class: 'screen-time-reminder-progress-row'});
    const track = new St.BoxLayout({style_class: 'screen-time-reminder-track',
        x_expand: true, y_align: Clutter.ActorAlign.CENTER});
    if (totalSeconds > 5) track.set_style('spacing: 1px;');
    const segments = Array.from({length: totalSeconds}, () => {
        const cell = new St.Widget({layout_manager: new Clutter.BinLayout(), x_expand: true,
            style_class: 'screen-time-reminder-segment'});
        const fill = new St.Widget({style_class: 'screen-time-reminder-fill',
            x_expand: true, y_expand: true});
        cell.add_child(fill);
        track.add_child(cell);
        return fill;
    });
    const time = new St.Label({style_class: 'screen-time-reminder-time'});
    row.add_child(track);
    row.add_child(time);
    actor.add_child(row);
    return {actor, update(left) {
        const remaining = Math.max(0, Math.min(totalSeconds, Math.ceil(left)));
        segments.forEach((fill, index) => { fill.visible = index < remaining; });
        time.text = translations.text('COMPACT_SECONDS', {count: remaining});
    }};
}

export function showReminderBanner(title, icon, body, urgency, seconds, translations, openPreferences) {
    activeSource?.destroy();
    const source = new MessageTray.Source({title, icon});
    activeSource = source;
    try {
        return createBanner(source, icon, body, urgency, seconds, translations, openPreferences);
    } catch (error) {
        source.destroy();
        throw error;
    }
}

function createBanner(source, icon, body, urgency, seconds, translations, openPreferences) {
    let card = null;
    let tooltip = null;
    let tooltipChromeAdded = false;
    let chromeAdded = false;
    let timer = 0;
    source.connect('destroy', () => {
        if (activeSource === source) activeSource = null;
        if (timer) GLib.source_remove(timer);
        timer = 0;
        if (tooltip) {
            if (tooltipChromeAdded) Main.layoutManager.removeChrome(tooltip);
            tooltipChromeAdded = false;
            tooltip.destroy();
            tooltip = null;
        }
        if (card) {
            if (chromeAdded) Main.layoutManager.removeChrome(card);
            chromeAdded = false;
            card.destroy();
            card = null;
        }
    });
    const notification = new MessageTray.Notification({source,
        title: '', body, gicon: icon, useBodyMarkup: false, urgency,
        privacyScope: MessageTray.PrivacyScope.USER, isTransient: true});
    const assets = icon.get_file().get_parent();
    card = new St.BoxLayout({style_class: 'screen-time-reminder', reactive: true,
        x_align: Clutter.ActorAlign.CENTER, y_align: Clutter.ActorAlign.START});
    // Horizontal BoxLayout defaults to width-for-height. This card has a
    // monitor-bounded width and wrapped text, so measure its height at that
    // width to keep the countdown inside the frame when the message wraps.
    card.set_request_mode(Clutter.RequestMode.HEIGHT_FOR_WIDTH);
    if (!fontLoaded) {
        const bundled = assets.get_child('Monocraft.ttf');
        const sourceFont = assets.get_parent().get_child('kiosk').get_child('oh_no_parent_control_kiosk')
            .get_child('fonts').get_child('Monocraft.ttf');
        const font = bundled.query_exists(null) ? bundled : sourceFont;
        // Shell renders with Clutter's font map, not Cairo's default map.
        fontLoaded = card.get_pango_context().get_font_map().add_font_file(font.get_path());
    }
    card.set_style(`border-image: url("${assets.get_child('reminder-frame.svg').get_path()}") 32;`);
    card.set_text_direction(translations.direction === 'rtl' ? Clutter.TextDirection.RTL : Clutter.TextDirection.LTR);
    card.add_child(new St.Icon({gicon: icon, icon_size: 56,
        style_class: 'screen-time-reminder-logo', y_align: Clutter.ActorAlign.CENTER}));
    const content = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL,
        style_class: 'screen-time-reminder-content', x_expand: true,
        y_align: Clutter.ActorAlign.CENTER});
    const message = new St.Label({text: body, style_class: 'screen-time-reminder-message'});
    message.clutter_text.line_wrap = true;
    message.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
    message.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
    content.add_child(message);
    const autoClose = seconds >= 60;
    const totalSeconds = autoClose ? 5 : Math.max(0, Math.ceil(seconds));
    const countdown = createCountdown(totalSeconds, translations);
    content.add_child(countdown.actor);
    card.add_child(content);
    const actions = [];
    let monitor = null;
    tooltip = new St.Label({style_class: 'dash-label screen-time-tooltip',
        visible: false, reactive: false});
    const syncTooltip = () => {
        if (!tooltip || !card) return;
        const action = actions.find(({control}) => control.hover && control.mapped);
        tooltip.visible = Boolean(action && card.visible && monitor);
        if (!tooltip.visible) return;
        tooltip.text = translations.text(action.key);
        tooltip.set_text_direction(card.get_text_direction());
        const [x, y] = action.control.get_transformed_position();
        const [width, height] = action.control.get_transformed_size();
        const [, tooltipWidth] = tooltip.get_preferred_width(-1);
        const [, tooltipHeight] = tooltip.get_preferred_height(tooltipWidth);
        const gap = 8 * St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const top = y + height + gap;
        tooltip.set_position(
            Math.max(monitor.x, Math.min(x + (width - tooltipWidth) / 2,
                monitor.x + monitor.width - tooltipWidth)),
            Math.max(monitor.y, top + tooltipHeight <= monitor.y + monitor.height
                ? top : y - tooltipHeight - gap));
    };
    const actionRow = new St.BoxLayout({style_class: 'screen-time-reminder-actions',
        x_align: Clutter.ActorAlign.CENTER, y_align: Clutter.ActorAlign.CENTER});
    const button = (key, filename, callback) => {
        const icon = new St.Icon({gicon: new Gio.FileIcon({file: assets.get_child(filename)}),
            icon_size: 40, style_class: 'screen-time-reminder-action-icon',
            x_align: Clutter.ActorAlign.CENTER});
        const control = new St.Button({child: icon, can_focus: true,
            reactive: true, track_hover: true,
            style_class: 'screen-time-reminder-action', y_align: Clutter.ActorAlign.CENTER});
        describeControl(control, `child-reminder-${key.toLowerCase()}`,
            translations.text(key), translations.text(key));
        control.connect('clicked', callback);
        control.connect('notify::hover', syncTooltip);
        control.connect('notify::mapped', syncTooltip);
        control.connect('notify::allocation', syncTooltip);
        actions.push({key, control});
        actionRow.add_child(control);
        return control;
    };
    const dismiss = () => { if (activeSource === source) source.destroy(); };
    const preferences = () => {
        if (activeSource !== source) return;
        dismiss();
        openPreferences();
    };
    card.add_child(new St.Widget({style_class: 'screen-time-reminder-divider', y_expand: true}));
    button('PREFERENCES', 'reminder-preferences.svg', preferences);
    button('DISMISS', 'reminder-dismiss.svg', dismiss);
    card.add_child(actionRow);
    card.connect('notify::allocation', syncTooltip);
    // Usable time keeps running even while fullscreen suppresses presentation.
    let deadline = !autoClose && totalSeconds > 0
        ? GLib.get_monotonic_time() + seconds * 1000000 : null;
    const tick = () => {
        const left = Math.max(0, (deadline - GLib.get_monotonic_time()) / 1000000);
        countdown.update(left);
        if (left === 0) {
            timer = 0;
            if (autoClose) dismiss();
            return GLib.SOURCE_REMOVE;
        }
        return GLib.SOURCE_CONTINUE;
    };
    const sync = () => {
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter) {
            dismiss();
            return;
        }
        // Follow the app the child is using, including fullscreen games on a
        // secondary display. Only use monitors in Shell's current active list:
        // focus/primary references can lag behind a hotplug or display switch.
        const {monitors, primaryMonitor} = Main.layoutManager;
        monitor = monitors[global.display.focus_window?.get_monitor()] ??
            (monitors.includes(primaryMonitor) ? primaryMonitor : monitors[0]) ?? null;
        card.visible = Boolean(monitor) && (notification.urgency === MessageTray.Urgency.CRITICAL ||
            (!monitor.inFullscreen && source.policy.showBanners));
        if (!monitor) {
            syncTooltip();
            return;
        }
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        // Reserve the frame corners, logo, message and gaps independently of
        // translated action widths. Let native layout move both buttons inward.
        const actionWidth = actions.reduce((width, {control}) =>
            width + control.get_preferred_width(-1)[1], 0);
        card.width = Math.min(Math.max(517 * scale, 360 * scale + actionWidth),
            monitor.width - 16 * scale);
        card.set_position(monitor.x + (monitor.width - card.width) / 2, monitor.y + 8 * scale);
        syncTooltip();
        // Start on delivery, never while fullscreen suppresses the banner.
        if (card.visible && autoClose && deadline === null) {
            deadline = GLib.get_monotonic_time() + 5000000;
            tick();
            timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, tick);
        }
    };
    const relabel = () => {
        message.text = notification.body;
        card.set_text_direction(translations.direction === 'rtl' ? Clutter.TextDirection.RTL : Clutter.TextDirection.LTR);
        const joining = ['ar', 'fa', 'he', 'ug', 'ur', 'bn', 'hi', 'mr', 'ne', 'ta', 'te', 'ml', 'pa', 'th', 'ka'];
        card.set_style(`border-image: url("${assets.get_child('reminder-frame.svg').get_path()}") 32;` +
            (joining.includes(translations.language?.split('-')[0]) ? ' font-family: sans-serif;' : ''));
        for (const {key, control} of actions) {
            const text = translations.text(key);
            describeControl(control, `child-reminder-${key.toLowerCase()}`, text, text);
        }
        countdown.update(deadline === null ? totalSeconds :
            (deadline - GLib.get_monotonic_time()) / 1000000);
        sync();
    };
    notification.connectObject('notify::body', relabel, card);
    notification.connectObject('notify::urgency', sync, card);
    Main.layoutManager.connectObject('monitors-changed', sync, card);
    Main.sessionMode.connectObject('updated', sync, card);
    global.display.connectObject('in-fullscreen-changed', sync, card);
    global.display.connectObject('notify::focus-window', sync, card);
    global.display.connectObject('window-entered-monitor', sync, card);
    source.addNotification(notification);
    // Ordinary chrome is below Mutter's override-redirect window group,
    // which X11/Xwayland games can use in fullscreen. Keep our owned actors
    // above that group too; urgency still controls fullscreen suppression.
    // Attach before measuring themed controls in relabel()/sync().
    Main.layoutManager.addTopChrome(card, {trackFullscreen: false});
    chromeAdded = true;
    Main.layoutManager.addTopChrome(tooltip, {trackFullscreen: false});
    tooltipChromeAdded = true;
    relabel();
    if (!autoClose && deadline !== null && tick())
        timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, tick);
    return {source, notification, card, dismiss, preferences,
        updateRemaining: remaining => {
            if (autoClose || totalSeconds === 0 || !card) return;
            deadline = GLib.get_monotonic_time() + Math.max(0, remaining) * 1000000;
            countdown.update(remaining);
            if (!timer && remaining > 0)
                timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, tick);
        },
        countdown: () => deadline === null ? null : Math.max(0,
            Math.ceil((deadline - GLib.get_monotonic_time()) / 1000000))};
}
