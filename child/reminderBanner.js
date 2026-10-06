import Clutter from 'gi://Clutter';
import Pango from 'gi://Pango';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';

// Countdown and editor previews share one product banner. A real threshold
// replaces a preview immediately instead of queuing behind a Critical banner.
let activeSource = null;

export function showReminderBanner(title, icon, body, urgency) {
    activeSource?.destroy();
    const source = new MessageTray.Source({title, icon});
    activeSource = source;
    source.connect('destroy', () => {
        if (activeSource === source) activeSource = null;
    });
    Main.messageTray.add(source);
    const notification = new MessageTray.Notification({source,
        title: '', body, gicon: icon, useBodyMarkup: false, urgency,
        privacyScope: MessageTray.PrivacyScope.USER, isTransient: true});
    notification.connect('notify::acknowledged', () => {
        if (notification.acknowledged && activeSource === source)
            compactBanner(notification);
    });
    source.addNotification(notification);
    return {source, notification};
}

function compactBanner(notification) {
    const visit = actor => {
        if (actor.notification === notification) {
            actor.add_style_class_name('screen-time-reminder');
            actor.x_expand = false;
            actor.x_align = Clutter.ActorAlign.CENTER;
            const compact = child => {
                if (child.has_style_class_name?.('message-header') ||
                    child.has_style_class_name?.('message-title')) child.hide();
                if (child.has_style_class_name?.('message-icon'))
                    child.y_align = Clutter.ActorAlign.CENTER;
                if (child.has_style_class_name?.('message-body')) {
                    const bin = child.get_parent();
                    const content = bin.get_parent();
                    if (!content.has_style_class_name('message-content')) return;
                    // Keep Shell's expansion bin for its animation lifecycle,
                    // but let the literal body determine its natural height.
                    bin.remove_child(child);
                    bin.hide();
                    content.add_child(child);
                    child.clutter_text.line_wrap = true;
                    child.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
                    child.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
                    const update = () => child.clutter_text.set_text(notification.body);
                    notification.connectObject('notify::body', update, child);
                    update();
                }
                for (const descendant of [...child.get_children()]) compact(descendant);
            };
            compact(actor);
            return;
        }
        for (const child of actor.get_children()) visit(child);
    };
    visit(Main.messageTray);
}
