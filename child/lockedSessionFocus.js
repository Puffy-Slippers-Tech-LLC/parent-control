import Clutter from 'gi://Clutter';

// GNOME 50 compatibility: keyboard_enable restores the remembered Wayland
// surface when devices return, even while Shell's existing grab is active.
// Mutter's normal device-added handler enables the keyboard synchronously.
// The after-handler asks its existing grab-notification handler to apply the
// same focus policy again; it does not create a grab or change actor focus.
// https://gitlab.gnome.org/GNOME/mutter/-/blob/50.1/src/wayland/meta-wayland-keyboard.c
// https://gitlab.gnome.org/GNOME/mutter/-/blob/50.1/src/wayland/meta-wayland-input.c
export class LockedSessionFocus {
    constructor(seat, stage, sessionMode, observe = () => {}) {
        this._seat = seat;
        this._stage = stage;
        this._sessionMode = sessionMode;
        this._observe = observe;
        this._closed = false;
        this._notifying = false;
        this._handler = seat.connect_after('device-added', (_seat, device) => {
            this._deviceAdded(device);
        });
    }

    _record(outcome) {
        try { this._observe(outcome); } catch (_error) { /* diagnostics only */ }
    }

    _deviceAdded(device) {
        if (this._closed || this._notifying)
            return;
        try {
            if (!(device.get_capabilities() & Clutter.InputCapabilities.KEYBOARD) ||
                !this._sessionMode.isLocked || this._sessionMode.isGreeter ||
                this._stage.get_grab_actor() === null)
                return;
            this._notifying = true;
            try {
                this._stage.notify('is-grabbed');
                this._record('complete');
            } finally {
                this._notifying = false;
            }
        } catch (_error) {
            // Never expose device identities or exception text, or interrupt
            // Shell's normal device handling when the compatibility hook fails.
            this._record('failed');
        }
    }

    close() {
        // A disconnect may synchronously run other callbacks. Close first;
        // there is no deferred work, and a repeated close owns no new handler.
        this._closed = true;
        if (this._handler) {
            this._seat.disconnect(this._handler);
            this._handler = 0;
        }
        this._seat = null;
    }
}
