"""The fixed, non-production identities used by previews and VM preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestIdentity:
    """One role-labelled test account shared by local preview and VM tooling."""

    label: str
    username: str
    given_name: str
    display_role: str
    role: str
    preview_uid: int

    @property
    def icon_file(self) -> str:
        return str(Path(__file__).resolve().parent / "test_user_icons" / f"{self.given_name.lower()}.png")

    @property
    def display_name(self) -> str:
        return f"{self.given_name} ({self.display_role})"


TEST_IDENTITIES = (
    TestIdentity("[Test parent 1]", "onpc-parent-jamie", "Jamie", "Parent", "administrator", 1000),
    TestIdentity("[Test parent 2]", "onpc-parent-casey", "Casey", "Parent", "administrator", 1010),
    TestIdentity("[Test child 1]", "onpc-child-riley", "Riley", "Child", "standard", 1001),
    TestIdentity("[Test child 2]", "onpc-child-jordan", "Jordan", "Child", "standard", 1002),
)


def preview_users(display_role: str) -> tuple[tuple[int, str, str], ...]:
    """Return the UI-facing identifiers for the requested test-account role."""
    return tuple(
        (identity.preview_uid, identity.display_name, identity.icon_file)
        for identity in TEST_IDENTITIES
        if identity.display_role.casefold() == display_role.casefold()
    )
