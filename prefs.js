import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

import {listLaunchableApps} from './appCatalog.js';
import {AppFilterClient} from './appFilterClient.js';
import {
    getBlockedTargets,
    loadAppPolicy,
    saveAppPolicy,
} from './appPolicyStore.js';

const STATES = Object.freeze([
    {
        id: 'allowed',
        label: 'Allowed',
        icon: 'emblem-ok-symbolic',
        css: 'policy-allowed',
    },
    {
        id: 'permanent',
        label: 'Permanently Blocked',
        icon: 'window-close-symbolic',
        css: 'policy-permanent',
    },
    {
        id: 'conditional',
        label: 'Conditionally Blocked',
        icon: 'dialog-warning-symbolic',
        css: 'policy-conditional',
    },
]);

function cloneApps(apps) {
    return JSON.parse(JSON.stringify(apps));
}

const AppPolicyPage = GObject.registerClass(class AppPolicyPage extends Adw.PreferencesPage {
    constructor(window) {
        super({
            title: 'App Access',
            icon_name: 'system-lock-screen-symbolic',
        });
        this._window = window;
        this._policy = loadAppPolicy();
        this._draft = cloneApps(this._policy.apps);
        this._rows = [];
        this._apps = [];
        this._working = false;

        this._appsGroup = new Adw.PreferencesGroup({
            css_classes: ['apps-panel'],
        });
        const searchRow = new Adw.ActionRow({
            title: 'Installed apps',
            subtitle: 'Desktop, AppImage, Flatpak, Snap, and system launchers',
            css_classes: ['apps-panel-header'],
        });
        this._search = new Gtk.SearchEntry({
            placeholder_text: 'Search installed apps',
            valign: Gtk.Align.CENTER,
            width_chars: 25,
            css_classes: ['apps-search'],
        });
        this._search.connect('search-changed', () => this._filterRows());
        searchRow.add_suffix(this._search);
        this._appsGroup.add(searchRow);

        for (const app of listLaunchableApps()) {
            this._apps.push(app);
            this._addApp(app);
        }
        this.add(this._appsGroup);

        const actions = new Adw.PreferencesGroup();
        const actionRow = new Adw.ActionRow({
            title: 'Administrator approval required',
            subtitle: 'Saving replaces the current system app-filter policy for this account.',
        });
        this._saveButton = new Gtk.Button({
            label: 'Loading System Policy…',
            css_classes: ['suggested-action', 'policy-save'],
            valign: Gtk.Align.CENTER,
            sensitive: false,
        });
        this._saveButton.connect('clicked', () => this._save());
        actionRow.add_suffix(this._saveButton);
        actions.add(actionRow);
        this.add(actions);

        this._loadSystemPolicy();
    }

    _addApp(app) {
        const state = this._draft[app.id]?.state ?? 'allowed';
        if (state !== 'allowed')
            this._draft[app.id].targets = app.targets;
        const row = new Adw.ActionRow({
            title: app.name,
            subtitle: app.description || app.id,
            css_classes: ['app-policy-row'],
        });
        row.searchText = `${app.name} ${app.description} ${app.id}`.toLowerCase();
        row.policyButtons = new Map();
        if (app.icon)
            row.add_prefix(new Gtk.Image({gicon: app.icon, pixel_size: 32}));

        const selector = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 3,
            valign: Gtk.Align.CENTER,
            css_classes: ['policy-selector'],
        });
        let firstButton = null;
        for (const definition of STATES) {
            const button = new Gtk.CheckButton({
                group: firstButton,
                active: definition.id === state,
                sensitive: false,
                tooltip_text: definition.label,
                css_classes: ['policy-choice', definition.css],
                child: new Gtk.Image({
                    icon_name: definition.icon,
                    pixel_size: 19,
                }),
                valign: Gtk.Align.CENTER,
            });
            if (!firstButton)
                firstButton = button;
            row.policyButtons.set(definition.id, button);
            button.connect('toggled', () => {
                if (!button.active)
                    return;
                this._draft[app.id] = {
                    state: definition.id,
                    targets: app.targets,
                };
                this._saveButton.sensitive = true;
            });
            selector.append(button);
        }
        row.add_suffix(selector);
        this._appsGroup.add(row);
        this._rows.push(row);
    }

    _setPolicyControlsSensitive(sensitive) {
        for (const row of this._rows) {
            for (const button of row.policyButtons.values())
                button.sensitive = sensitive;
        }
    }

    async _loadSystemPolicy() {
        try {
            const blocked = new Set(await new AppFilterClient().getBlockedTargets());
            for (let index = 0; index < this._apps.length; index++) {
                const app = this._apps[index];
                const cachedState = this._draft[app.id]?.state;
                const isBlocked = app.targets.length > 0 &&
                    app.targets.every(target => blocked.has(target));
                const state = isBlocked
                    ? (cachedState === 'conditional' ? 'conditional' : 'permanent')
                    : 'allowed';

                if (state === 'allowed')
                    delete this._draft[app.id];
                else
                    this._draft[app.id] = {state, targets: app.targets};
                this._rows[index].policyButtons.get(state).active = true;
            }
            this._saveButton.sensitive = false;
        } catch (error) {
            console.error(`[oh-no-parent-control] could not read app filter: ${error.message}`);
            this._window.add_toast(new Adw.Toast({
                title: `Could not read system app access: ${error.message}`,
                timeout: 5,
            }));
        } finally {
            this._setPolicyControlsSensitive(true);
            this._saveButton.label = 'Save Changes';
        }
    }

    _filterRows() {
        const query = this._search.text.trim().toLowerCase();
        for (const row of this._rows)
            row.visible = !query || row.searchText.includes(query);
    }

    async _save() {
        if (this._working)
            return;
        this._working = true;
        this._saveButton.sensitive = false;
        this._saveButton.label = 'Authenticating…';
        try {
            const blocked = getBlockedTargets({apps: this._draft}, false);
            const client = new AppFilterClient();
            await client.setBlockedTargets(blocked, true);
            const applied = await client.getBlockedTargets();
            if (blocked.length !== applied.length ||
                blocked.some(target => !applied.includes(target)))
                throw new Error('the system did not retain the requested app filter');
            saveAppPolicy(this._draft);
            this._policy.apps = cloneApps(this._draft);
            this._window.add_toast(new Adw.Toast({
                title: `App access saved — ${blocked.length} restricted target${blocked.length === 1 ? '' : 's'}`,
            }));
        } catch (error) {
            console.error(`[oh-no-parent-control] could not save app policy: ${error.message}`);
            this._window.add_toast(new Adw.Toast({
                title: `Could not save app access: ${error.message}`,
                timeout: 5,
            }));
            this._saveButton.sensitive = true;
        } finally {
            this._working = false;
            this._saveButton.label = 'Save Changes';
        }
    }
});

export default class OhNoParentControlPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const provider = new Gtk.CssProvider();
        provider.load_from_path(`${this.path}/prefs.css`);
        Gtk.StyleContext.add_provider_for_display(
            window.get_display(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
        window.set_default_size(880, 720);
        window.set_search_enabled(true);
        window.add(new AppPolicyPage(window));
    }
}
