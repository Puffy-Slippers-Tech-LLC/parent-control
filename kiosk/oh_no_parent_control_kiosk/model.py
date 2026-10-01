"""Small UI state machine used to enforce single-flight requests."""

from common.oh_no_parent_control_ui import messages as m

from dataclasses import dataclass


@dataclass
class RequestState:
    in_flight: bool = False

    def begin(self) -> bool:
        if self.in_flight:
            return False
        self.in_flight = True
        return True

    def finish(self) -> None:
        self.in_flight = False


def public_error(_error: Exception, *, child_overlay=False) -> tuple[str, str]:
    """Never expose D-Bus names, paths, or backend messages to the request UI."""
    if child_overlay:
        return (
            m.REQUEST_UNAVAILABLE,
            m.THE_REQUEST_COULD_NOT_BE_COMPLETED_PLEASE_TRY_AGAIN_LATER,
        )
    return (
        m.REQUEST_UNAVAILABLE,
        m.THE_REQUEST_COULD_NOT_BE_COMPLETED_PLEASE_RETURN_TO_LOGIN_AND_TR,
    )
