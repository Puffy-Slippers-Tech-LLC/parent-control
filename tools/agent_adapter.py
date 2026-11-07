"""Session preparation and protocol boundary; acceptance belongs to launchers.

Existing callers remain pinned to Codex until their selection handoff is wired.
The selection API prepares that boundary without enabling unqualified execution.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator, Literal, NamedTuple, Protocol


Role = Literal['backend_reviewer', 'monitor', 'worker', 'adviser', 'translator']
ProfileRole = Literal['implementation', 'repair', 'backend_reviewer', 'monitor',
                      'worker', 'adviser', 'translator', 'commit_helper', 'conflict_resolver']


@dataclass(frozen=True)
class AgentSelection:
    """One logical session's choice from its executing checkout, never provenance."""

    name: Literal['codex', 'claude']
    root: Path

    @property
    def execution_qualified(self) -> bool:
        # Transport foundations do not grant workflow execution capabilities.
        return self.name == 'codex'

    def adapter(self) -> 'AgentAdapter':
        """Fixed qualified mapping; no config-supplied import or executable."""
        if not self.execution_qualified:
            raise ValueError(f'Agent {self.name!r} selected by {self.root} is not qualified '
                             'for workflow execution; no agent was started or fallback selected')
        from agent_codex import CodexAdapter
        return CodexAdapter()


def resolve_selection(root: Path) -> AgentSelection:
    """Read only the executing checkout, after branch/host dispatch has settled.

    Legacy agent-free documents may omit agent; a live selection must not.
    Resolving records configuration, not CLI readiness or model access. Callers
    retain this frozen value through turns/helpers/retries without rereading it.
    """
    from vm_selection import read_document
    root = root.resolve()
    try:
        document = read_document(root / 'config/environment.json')
        if 'agent' not in document:
            raise ValueError('agent is required for a live session')
    except ValueError as error:
        raise ValueError(f'Cannot select an agent for executing checkout {root}: {error}') from error
    return AgentSelection(document['agent'], root)


class ModelProfile(NamedTuple):
    model: str
    effort: str


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

    def resolve_profile(self, role: ProfileRole, *, model: str | None = None,
                        effort: str | None = None) -> ModelProfile: ...

    def capacity_fallback(self, model: str) -> str | None: ...

    def preflight(self, request: SessionRequest, environment: dict[str, str],
                  profiles: tuple[ModelProfile, ...] = ()) -> None: ...

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

    def preflight(self, *profiles: ModelProfile) -> None:
        """Check readiness without starting task work or changing its budgets."""
        self.adapter.preflight(self.request, self.environment, profiles)

    def revised(self, **changes) -> 'PreparedSession':
        """Reprepare under the same adapter, including capacity attempts."""
        return self.adapter.prepare_session(replace(self.request, **changes), self.environment)


def prepare_session(request: SessionRequest, environment: dict[str, str]) -> PreparedSession:
    # Selection stays inactive until every transport and caller is qualified.
    from agent_codex import CodexAdapter
    return CodexAdapter().prepare_session(request, environment)


def resolve_profile(role: ProfileRole, *, model: str | None = None,
                    effort: str | None = None) -> ModelProfile:
    from agent_codex import CodexAdapter
    return CodexAdapter().resolve_profile(role, model=model, effort=effort)


def capacity_fallback(model: str) -> str | None:
    from agent_codex import CodexAdapter
    return CodexAdapter().capacity_fallback(model)
