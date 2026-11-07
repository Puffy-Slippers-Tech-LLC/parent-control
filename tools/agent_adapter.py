"""Session preparation and protocol boundary; acceptance belongs to launchers.

Live sessions pin their executing checkout's selection. Unqualified transports
are refused before task launch; agent-free policy defaults need no selection.
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

    def record(self) -> dict:
        """Private subprocess handoff, not a restart configuration source."""
        return {'name': self.name, 'root': str(self.root)}

    @classmethod
    def from_record(cls, value: dict, *, root: Path) -> 'AgentSelection':
        if (not isinstance(value, dict) or set(value) != {'name', 'root'}
                or value['name'] not in ('codex', 'claude')
                or not isinstance(value['root'], str)
                or value['root'] != str(root.resolve())):
            raise ValueError('invalid executing checkout agent selection handoff')
        return cls(value['name'], root.resolve())

    @property
    def execution_qualified(self) -> bool:
        # Transport foundations do not grant workflow execution capabilities.
        return self.name == 'codex'

    def adapter(self) -> 'AgentAdapter':
        """Fixed qualified mapping; no config-supplied import or executable."""
        if not self.execution_qualified:
            raise ValueError(f'Agent {self.name!r} selected by {self.root} is not qualified '
                             'for workflow execution; no agent was started or fallback selected. '
                             'Configure a qualified agent before starting a workflow')
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
    selection: AgentSelection | None = None
    logical_tier: str | None = None


class AgentAdapter(Protocol):
    name: str

    def setup(self, root: Path, *, headless: bool) -> None: ...

    def readiness(self, root: Path, environment: dict[str, str]) -> str: ...

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
    selection = request.selection or resolve_selection(request.root)
    # Dependent Git recovery may execute in another owned checkout while
    # retaining the originating session's selection authority.
    return selection.adapter().prepare_session(replace(request, selection=selection,
        logical_tier=request.logical_tier or f'{request.model} {request.effort}'), environment)


def resolve_profile(role: ProfileRole, *, model: str | None = None,
                    effort: str | None = None,
                    selection: AgentSelection | None = None) -> ModelProfile:
    if selection is not None:
        return selection.adapter().resolve_profile(role, model=model, effort=effort)
    from agent_codex import CodexAdapter
    return CodexAdapter().resolve_profile(role, model=model, effort=effort)


def capacity_fallback(model: str, *, selection: AgentSelection | None = None) -> str | None:
    if selection is not None:
        return selection.adapter().capacity_fallback(model)
    from agent_codex import CodexAdapter
    return CodexAdapter().capacity_fallback(model)


def setup_agent(root: Path, *, headless: bool = False) -> None:
    """User-owned native policy preparation, called only by setup.sh.

    Unqualified selections are informational during setup, never permission to
    prepare another provider or install/authenticate a CLI. Installer failures
    for a qualified provider still fail setup normally.
    """
    try:
        selection = resolve_selection(root)
        adapter = selection.adapter()
    except ValueError as error:
        print(f'setup: action needed: {error}')
        return
    adapter.setup(selection.root, headless=headless)


def report_readiness(root: Path, environment: dict[str, str]) -> None:
    """Bounded account-local readiness, without starting a model session."""
    selection = None
    try:
        selection = resolve_selection(root)
        message = selection.adapter().readiness(selection.root, environment)
        print(f'setup: agent {selection.name} selected by {selection.root}: {message}')
    except (OSError, ValueError) as error:
        context = f'agent {selection.name} selected by {selection.root}: ' if selection else ''
        print(f'setup: action needed: {context}{error}')


if __name__ == '__main__':
    import os
    import sys

    # Isolated Python setup invocations do not add the script directory.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    root = Path(__file__).resolve().parents[1]
    try:
        if sys.argv[1:] in (['--setup'], ['--setup', '--headless']):
            setup_agent(root, headless='--headless' in sys.argv)
        elif sys.argv[1:] == ['--readiness']:
            report_readiness(root, dict(os.environ))
        else:
            sys.exit('agent setup: invoke through ./setup.sh')
    except ValueError as error:
        sys.exit(f'agent setup: {error}')
    except OSError as error:
        sys.exit(f'agent setup: filesystem operation failed (errno={error.errno})')
