import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';

function readJson(path) {
    const [ok, contents] = GLib.file_get_contents(path);
    if (!ok)
        throw new Error(`could not read ${path}`);
    return JSON.parse(new TextDecoder().decode(contents));
}

function dataDir(extensionPath) {
    const installed = '/usr/share/oh-no-parent-control';
    return GLib.file_test(installed, GLib.FileTest.IS_DIR)
        ? installed : GLib.build_filenamev([extensionPath, '..', 'data']);
}

function launch(uri) {
    Gio.AppInfo.launch_default_for_uri(uri, null);
}

function fileIcon(directory, name) {
    return new Gio.FileIcon({file: Gio.File.new_for_path(
        GLib.build_filenamev([directory, name]))});
}

export class AboutDialog extends ModalDialog.ModalDialog {
    constructor(extension) {
        super({styleClass: 'oh-no-parent-control-about-dialog'});
        const directory = dataDir(extension.path);
        const brand = readJson(GLib.build_filenamev([directory, 'brand.json']));
        const app = readJson(GLib.build_filenamev([directory, 'app.json']));
        const content = new St.BoxLayout({vertical: true,
            style_class: 'oh-no-parent-control-content'});
        content.add_child(new St.Icon({
            gicon: fileIcon(directory, 'app_logo.png'),
            icon_size: 128,
            style_class: 'oh-no-parent-control-about-logo',
        }));
        content.add_child(new St.Label({text: brand.app_name,
            style_class: 'oh-no-parent-control-title'}));
        content.add_child(new St.Label({
            text: `Version ${app.version}\nHelping families build healthy digital habits.`,
            style_class: 'oh-no-parent-control-subtitle',
        }));
        for (const [title, value, uri] of [
            ['Website', brand.app_url, brand.app_url],
            ['Support', brand.contact,
                `mailto:${brand.contact}?subject=${encodeURIComponent(`${brand.app_name}: Feedbacks`)}`],
            ['License', 'GNU General Public License v3.0',
                Gio.File.new_for_path(GLib.build_filenamev([directory, 'LICENSE'])).get_uri()],
        ]) {
            const link = new St.Button({
                style_class: 'oh-no-parent-control-about-link', can_focus: true,
                reactive: true});
            const linkContent = new St.BoxLayout({
                style_class: 'oh-no-parent-control-about-link-content',
            });
            if (title === 'Website') {
                linkContent.add_child(new St.Icon({
                    gicon: fileIcon(directory, 'company_logo.png'),
                    icon_size: 32,
                    style_class: 'oh-no-parent-control-website-icon',
                }));
            }
            linkContent.add_child(new St.Label({text: `${title}\n${value}`}));
            link.set_child(linkContent);
            link.connect('clicked', () => launch(uri));
            content.add_child(link);
        }
        content.add_child(new St.Label({
            text: `© 2026 ${brand.vendor_name}\nAll rights reserved.`,
            style_class: 'oh-no-parent-control-subtitle',
        }));
        this.contentLayout.add_child(content);
        this.setButtons([{label: 'Close', action: () => this.close()}]);
    }
}
