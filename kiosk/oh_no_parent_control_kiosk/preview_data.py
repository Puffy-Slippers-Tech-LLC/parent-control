"""Development-only fixtures for kiosk and child-overlay previews."""

from common.oh_no_parent_control_ui.test_identities import TEST_IDENTITIES, preview_users

PREVIEW_USERS = preview_users("child")
PREVIEW_APPROVERS = preview_users("parent")
JORDAN_UID = next(identity.preview_uid for identity in TEST_IDENTITIES
                  if identity.username == "onpc-child-jordan")
INTERACTIVE_PREVIEW_USERS = tuple(sorted(PREVIEW_USERS, key=lambda user: user[0] != JORDAN_UID))


def preview_preferences(target_uid, *, interactive):
    enabled_uid = JORDAN_UID if interactive else PREVIEW_USERS[0][0]
    return {
        "parent_control_enabled": target_uid == enabled_uid,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    }

