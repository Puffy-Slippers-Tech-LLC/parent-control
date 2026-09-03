"""Small UI state machine used to enforce single-flight requests."""

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
            "Request unavailable",
            "The request could not be completed. Please try again later.",
        )
    return (
        "Request unavailable",
        "The request could not be completed. Please return to login and try again later.",
    )
