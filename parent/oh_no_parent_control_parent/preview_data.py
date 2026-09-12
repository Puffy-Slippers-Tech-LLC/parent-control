"""Development-only fixtures for the parent UI preview."""

import copy
from pathlib import Path

from common.oh_no_parent_control_ui.test_identities import preview_users

PREVIEW_USERS = preview_users("child")
PREVIEW_THUNDERBIRD_ICON = str(Path(__file__).with_name("thunderbird-default128.png"))
PREVIEW_PREFERENCES = {
    1001: {
        "parent_control_enabled": True,
        "daily_time_limit_minutes": 90,
        "apps": {
            "thunderbird_thunderbird.desktop": {
                "state": "allowed",
                "targets": ["/snap/bin/thunderbird"],
                "patterns": ["ABC"],
                "user_saved_match_rule": True,
            },
            "lunarclient.desktop": {
                "state": "permanent",
                "targets": ["/home/riley/Applications/Lunar Client-3.8.0.AppImage"],
                "patterns": ["/home/riley/Applications/Lunar Client-*.AppImage"],
                "user_saved_match_rule": True,
            },
            "com.mojang.Minecraft.desktop": {
                "state": "conditional",
                "targets": ["app/com.mojang.Minecraft/x86_64/stable"],
                "patterns": [],
                "user_saved_match_rule": False,
            },
            "steam.desktop": {
                "state": "conditional",
                "targets": ["/usr/bin/steam"],
                "patterns": [],
                "user_saved_match_rule": False,
            },
        },
        "request": {},
    },
    1002: {
        "parent_control_enabled": False,
        "daily_time_limit_minutes": 60,
        "apps": {},
        "request": {},
    },
}
PREVIEW_APPS = (
    {
        "id": "thunderbird_thunderbird.desktop",
        "name": "Thunderbird",
        "description": "Email and calendar",
        "icon": PREVIEW_THUNDERBIRD_ICON,
        "targets": ["/snap/bin/thunderbird"],
        "suggested_patterns": ["ABC"],
    },
    {
        "id": "lunarclient.desktop",
        "name": "Lunar Client",
        "description": "Play Minecraft",
        "icon": "lunar-client",
        "targets": ["/home/riley/Applications/Lunar Client-3.8.0.AppImage"],
        "suggested_patterns": ["/home/riley/Applications/Lunar Client-*.AppImage"],
    },
    {
        "id": "com.mojang.Minecraft.desktop",
        "name": "Minecraft",
        "description": "Play Minecraft",
        "icon": "com.mojang.Minecraft",
        "targets": ["app/com.mojang.Minecraft/x86_64/stable"],
        "suggested_patterns": [],
    },
    {
        "id": "steam.desktop",
        "name": "Steam",
        "description": "Play games",
        "icon": "steam",
        "targets": ["/usr/bin/steam"],
        "suggested_patterns": [],
    },
)


class PreviewBrokerClient:
    """In-memory representative data for GUI work without system services."""

    def __init__(self):
        self._preferences = copy.deepcopy(PREVIEW_PREFERENCES)

    def list_users(self):
        return PREVIEW_USERS

    def get_preferences(self, uid):
        return copy.deepcopy(self._preferences[uid])

    def list_apps(self, _uid):
        return copy.deepcopy(PREVIEW_APPS)

    def get_time_status(self, _uid):
        return {
            "daily_allowance_remaining_seconds": 47 * 60,
            "one_time_grant_remaining_seconds": 15 * 60,
            "additional_one_time_grant_seconds": 0,
            "calculated_active_extension_seconds": 47 * 60,
        }

    def set_preferences(self, uid, value):
        self._preferences[uid] = copy.deepcopy(value)
        return self.get_preferences(uid)

    def set_parent_control(self, uid, enabled, daily_limit_minutes):
        preferences = self._preferences[uid]
        preferences["parent_control_enabled"] = enabled
        preferences["daily_time_limit_minutes"] = daily_limit_minutes
        return self.get_preferences(uid)

    def revoke_one_time_grant(self, _uid):
        return None


