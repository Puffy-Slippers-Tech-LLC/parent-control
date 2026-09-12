"""Development-only fixtures for kiosk and child-overlay previews."""

from common.oh_no_parent_control_ui.test_identities import preview_users

PREVIEW_USERS = preview_users("child")
PREVIEW_APPROVERS = preview_users("parent")
PREVIEW_PREFERENCES = {
    1001: {
        "parent_control_enabled": True,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
    1002: {
        "parent_control_enabled": False,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
    1003: {
        "parent_control_enabled": True,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
    1004: {
        "parent_control_enabled": True,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
    1005: {
        "parent_control_enabled": True,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
}

