"""Session preparation and protocol boundary; acceptance belongs to launchers.

This extraction deliberately pins Codex. Configuration-driven selection is a
separate step, not an implicit provider fallback.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator, Literal, Protocol


Role = Literal['backend_reviewer', 'monitor', 'worker', 'adviser', 'translator']


@dataclass(frozen=True)
class Delegation:
    roles: tuple[Role, ...] = ('backend_reviewer',)
    enabled: bool = True
    max_concurrent: int = 1
    max_depth: int = 1
    model: str | None = None
    effort: str | None = None


@dataclass(frozen=True)
class SessionRequest:
    root: Path
    model: str
    effort: str
    run: Path | None = None
    schema: Path | None = None
    permissions: Literal['workspace', 'read_only'] = 'workspace'
    delegation: Delegation = Delegation()
    standard_speed: bool = False
    shell_environment: tuple[tuple[str, str], ...] = ()
    extra_directories: tuple[Path, ...] = ()
    instructions: str = ''
    interactive: bool = False


class AgentAdapter(Protocol):
    name: str

    def prepare_session(self, request: SessionRequest, environment: dict[str, str]) -> 'PreparedSession': ...


@dataclass(frozen=True)
class SessionEvent:
    """Normalized transport/presentation output, never acceptance evidence.

    Text events carry id/text/complete; item events carry a renderer item and
    complete flag. Usage carries the provider's counters under usage, preserving
    absent counters. Diagnostics carry plain text or an inert value. Failures
    carry message/context/details/capacity; batch failures also mark terminal,
    with an optional inert diagnostic payload for display, and interactive
    failures supply task_error for shared status handling.
    Native wire names and request IDs stay inside the concrete handler.
    """
    kind: Literal['ready', 'turn_completed', 'retry_input',
                  'discard_result', 'text', 'text_delta', 'item', 'diagnostic',
                  'command_output', 'usage', 'notice', 'failure']
    data: dict


class BatchPresentation(Protocol):
    """Decode batch stdout only; the native result file retains its owner."""

    def feed(self, data: bytes) -> Iterator[SessionEvent]: ...
    def finish(self) -> Iterator[SessionEvent]: ...


class SessionProtocol(Protocol):
    """One fresh interactive session; no process, mailbox or filesystem writes.

    The supervisor drains outgoing bytes and feeds stdout chunks. Events are
    consumed in order before polling input/acceptance. Completion requires a
    terminal coordinator turn and settled input requests; it is only a candidate
    until the shared mailbox and workflow guards accept it. Interrupted turns
    must drain before cleanup and continuation. finalize_result decodes only;
    task identity, schema validation and result persistence remain shared.
    """
    outgoing: bytearray

    @property
    def ready(self) -> bool: ...

    @property
    def active_turn(self) -> bool: ...

    @property
    def turn_requests_pending(self) -> bool: ...

    def start(self) -> None: ...
    def start_turn(self, text: str) -> None: ...
    def steer(self, text: str) -> None: ...
    def interrupt(self) -> None: ...
    def feed(self, data: bytes) -> Iterator[SessionEvent]: ...
    def finalize_result(self, text: str) -> dict | None: ...


@dataclass(frozen=True)
class PreparedSession:
    adapter: AgentAdapter
    request: SessionRequest
    argv: tuple[str, ...]
    environment: dict[str, str]
    cwd: Path
    protocol: SessionProtocol | None = None
    presentation: BatchPresentation | None = None

    def revised(self, **changes) -> 'PreparedSession':
        """Reprepare under the same adapter, including capacity attempts."""
        return self.adapter.prepare_session(replace(self.request, **changes), self.environment)


def prepare_session(request: SessionRequest, environment: dict[str, str]) -> PreparedSession:
    # Selection stays inactive until every transport and caller is qualified.
    from agent_codex import CodexAdapter
    return CodexAdapter().prepare_session(request, environment)
