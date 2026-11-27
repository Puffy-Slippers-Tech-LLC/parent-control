"""Session preparation and protocol boundary; acceptance belongs to launchers.

Live sessions pin their executing checkout's selection. The checked-in `agent`
field selects one of two fixed adapters; there is no cross-agent fallback.
Agent-free policy defaults need no selection.
"""

from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Iterator, Literal, NamedTuple, Protocol


Role = Literal['backend_reviewer', 'monitor', 'worker', 'translator']
ProfileRole = Literal['implementation', 'backend_reviewer', 'monitor',
                      'worker', 'translator', 'commit_helper', 'conflict_resolver']

# Shared policy text. Adapters render it through their native mechanisms.
SESSION_GOAL = ('Simple, lean, robust; do not overengineer. Prefer solutions that simplify '
                'the resulting codebase as a whole, not merely minimize the patch. '
                'Keep refactoring within the task’s scope.')

BACKEND_REVIEW_INSTRUCTIONS = """For product backend code involving core functionalities,
AGENTS.md requires an independent code review by the backend_reviewer agent
(using its configured metadata profile) before completing the changes. This mandate applies across
all launchers, including repair, recovery and optimization sessions. It overrides
coordinator-model and no-delegation rules only for this required review; keep the launcher's
existing coordinator, implementation, consultation and escalation model policy.
Do not request this review for changes outside core backend code. Give the reviewer
the exact owned changes, relevant source/contracts and validation evidence in a
fresh context. Pause implementation while it reviews; wait for its findings and
close it before resuming. Resolve actionable findings and revalidate material
revisions; obtain a fresh review of material backend revisions before completion.
Record the review findings and resolution in the existing summary or handoff.
A missing or failed review is incomplete work, never a completed change; use the
launcher's existing continuation or blocker route. Review gives no test or installed
acceptance credit. The reviewer cannot implement, test, control resources or delegate.
"""

# Delegated roles: native name, instruction asset and description. The TOML
# assets' developer_instructions are the shared role instructions.
ROLES = {
    'backend_reviewer': ('backend_reviewer', 'backend_reviewer.toml',
        'Mandatory independent review of core backend changes only; no implementation'),
    'monitor': ('plan_monitor', 'plan_monitor.toml',
        'Routine read-only monitoring; no resource ownership or mutations'),
    'worker': ('plan_worker', 'plan_worker.toml',
        'Bounded routine work or coverage refresh on explicitly assigned files'),
    'translator': ('whatsnew_translator', 'sync_whatsnew_translator.toml',
        'Read-only latest-release translator/reviewer'),
}

# Roles name the metadata profiles in config/environment.json agents.tools.
WORKFLOWS = {
    'implementation': 'execute-plan', 'translator': 'sync-whatsnew',
    'commit_helper': 'commit-skill-driver', 'conflict_resolver': 'conflict-resolver',
    'worker': 'execution-plan-worker', 'monitor': 'execution-plan-monitor',
    'backend_reviewer': 'backend-reviewer',
}


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

    def adapter(self) -> 'AgentAdapter':
        """Fixed mapping; no config-supplied import or executable."""
        if self.name == 'claude':
            from agent_claude import ClaudeAdapter
            return ClaudeAdapter(self.root)
        from agent_codex import CodexAdapter
        return CodexAdapter(self.root)


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
    continuation_key: str | None = None
    thread_id: str | None = None


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
    Protocols that offer model selection supply list_models() and
    change_model(text), and emit model_options and model_changed events.
    Protocols with skill completion emit skill_options with the session's
    available names and resolve $name in user input using their native API.
    """
    kind: Literal['ready', 'turn_completed', 'retry_input',
                  'discard_result', 'text', 'text_delta', 'item', 'diagnostic',
                  'command_output', 'usage', 'notice', 'failure', 'model_options',
                  'model_changed', 'skill_options']
    data: dict


def model_choice(text: str, options: dict, model: str) -> tuple[str, str]:
    """Resolve `/model [model] [--reasoning=<level>]` against published options."""
    match = re.fullmatch(r'/model(?:[ \t]+([^\s-][^\s]*))?(?:[ \t]+--reasoning(?:=|[ \t]+)(\S+))?',
                         text.strip())
    if not match or not any(match.groups()):
        raise ValueError('Use /model, /model <model>, or /model [model] --reasoning=<level>.')
    requested, effort = match.groups()
    choice = options.get(requested or model)
    if choice is None:
        raise ValueError('Choose a model from the /model picker.')
    effort = effort or choice['default']
    if effort not in choice['efforts']:
        raise ValueError(f"Choose a reasoning level for {choice['model']}: {', '.join(choice['efforts'])}.")
    return choice['model'], effort


class BatchPresentation(Protocol):
    """Decode batch stdout; the native result file retains its owner.

    A CLI without a result-file option has its adapter persist only the
    successful coordinator's structured result to the run's agent-result.json.
    """

    def feed(self, data: bytes) -> Iterator[SessionEvent]: ...
    def finish(self) -> Iterator[SessionEvent]: ...


class SessionProtocol(Protocol):
    """One structured interactive conversation; no process or filesystem writes.

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
    def poll(self) -> SessionEvent | None: ...
    def finalize_result(self, text: str) -> dict | None: ...


class GoalSessionProtocol(Protocol):
    """A fresh plain assignment whose native runtime owns goal continuation.

    done/status describe native lifecycle only. Plain sessions have neither a
    workflow response schema nor a final-result decoder. chat_ready reports
    when steer() can accept developer input.
    """
    outgoing: bytearray
    done: bool
    status: int

    @property
    def chat_ready(self) -> bool: ...

    def start(self) -> None: ...
    def start_turn(self, text: str) -> None: ...
    def feed(self, data: bytes) -> Iterator[SessionEvent]: ...
    def poll(self) -> SessionEvent | None: ...


@dataclass(frozen=True)
class PreparedSession:
    adapter: AgentAdapter
    request: SessionRequest
    argv: tuple[str, ...]
    environment: dict[str, str]
    cwd: Path
    protocol: SessionProtocol | GoalSessionProtocol | None = None
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
    selection = selection or resolve_selection(Path(__file__).resolve().parents[1])
    return selection.adapter().resolve_profile(role, model=model, effort=effort)


def resolve_role_profile(role: ProfileRole, *, selection: AgentSelection,
                         model: str | None = None, effort: str | None = None) -> ModelProfile:
    if role not in WORKFLOWS:
        raise ValueError('unsupported agent model profile')
    return resolve_workflow_profile(WORKFLOWS[role], selection=selection, model=model, effort=effort)


def helper_profile(adapter: AgentAdapter, request: SessionRequest, role: Role) -> ModelProfile:
    """Translators follow their coordinator; other helpers use their pinned role profile."""
    delegation = request.delegation
    return (adapter.resolve_profile(role, model=delegation.model or request.model,
                                    effort=delegation.effort or request.effort)
            if role == 'translator' else adapter.resolve_profile(role))


def _token(value, field):
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError(f'{field} must be a nonempty token')
    return value


def _profile(profiles, key, field):
    try:
        profile = profiles[key]
    except (KeyError, TypeError) as error:
        raise ValueError(f'{field}.{key} is required') from error
    if (not isinstance(profile, dict) or 'model' not in profile
            or set(profile) - {'model', 'effort'}):
        raise ValueError(f'{field}.{key} requires model and optional effort')
    for name, value in profile.items():
        _token(value, f'{field}.{key}.{name}')
    return profile


def _profiles(selection):
    from vm_selection import read_document
    path = selection.root / 'config/environment.json'
    field = f'{path}: agents'
    document = read_document(path)
    try:
        profiles = document['agents']
    except (KeyError, TypeError) as error:
        raise ValueError(f'{field} is required') from error
    if not isinstance(profiles, dict):
        raise ValueError(f'{field} must be an object')
    if not isinstance(profiles.get(selection.name), dict):
        raise ValueError(f'{field}.{selection.name} must be an object')
    return profiles, field


def _defaults(profiles, field):
    defaults = profiles.get('defaults', {})
    if not isinstance(defaults, dict):
        raise ValueError(f'{field}.defaults must be an object')
    for name in defaults:
        _token(name, field + '.defaults')
        preset = _profile(defaults, name, field + '.defaults')
        if 'effort' not in preset or preset['model'] in defaults:
            raise ValueError(f'{field}.defaults.{name} requires a literal model and effort')
    return defaults


def resolve_workflow_profile(workflow: str, *, selection: AgentSelection,
                             model: str | None = None, effort: str | None = None) -> ModelProfile:
    """Resolve a named preset or literal model/effort in the executing checkout.

    A preset supplies both fields; an optional effort overrides its effort.
    Literal models require effort. CLI overrides win over the resolved profile.
    Metadata cannot qualify an inactive adapter or change workflow retry policy.
    """
    profiles, field = _profiles(selection)
    if not isinstance(profiles.get('tools'), dict):
        raise ValueError(f'{field}.tools must be an object')
    profile = _profile(profiles['tools'], workflow, field + '.tools')
    defaults = _defaults(profiles[selection.name], field + '.' + selection.name)
    preset = defaults.get(profile['model'], {})
    selected_model = preset.get('model', profile['model'])
    selected_effort = profile.get('effort', preset.get('effort'))
    if selected_effort is None:
        raise ValueError(f'{field}.tools.{workflow} requires effort for a literal model or a complete preset')
    return ModelProfile(_token(model if model is not None else selected_model, field + '.model'),
                        _token(effort if effort is not None else selected_effort, field + '.effort'))


def resolve_capacity_fallback(model: str, *, selection: AgentSelection) -> str | None:
    """Metadata selects models; the shared runtime still owns finite retry policy.

    Fallback edges name presets but use only their models, preserving the
    session's current effort. There is no recursive fallback or escalation.
    """
    profiles, field = _profiles(selection)
    profiles, field = profiles[selection.name], field + '.' + selection.name
    defaults = _defaults(profiles, field)
    fallbacks = profiles.get('capacity_fallbacks', {})
    if not isinstance(fallbacks, dict):
        raise ValueError(f'{field}.capacity_fallbacks must be an object')
    matches = set()
    for source, target in fallbacks.items():
        if not isinstance(target, str) or source not in defaults or target not in defaults:
            raise ValueError(f'{field}.capacity_fallbacks must reference named defaults')
        if defaults[source]['model'] == defaults[target]['model']:
            raise ValueError(f'{field}.capacity_fallbacks must select a different model')
        if defaults[source]['model'] == model:
            matches.add(defaults[target]['model'])
    if len(matches) > 1:
        raise ValueError(f'{field}.capacity_fallbacks has ambiguous targets for {model}')
    return next(iter(matches), None)


def capacity_fallback(model: str, *, selection: AgentSelection | None = None) -> str | None:
    selection = selection or resolve_selection(Path(__file__).resolve().parents[1])
    return selection.adapter().capacity_fallback(model)


def setup_agent(root: Path, *, headless: bool = False) -> None:
    """User-owned native policy preparation, called only by setup.sh.

    An invalid selection is informational during setup, never permission to
    prepare another provider or install/authenticate a CLI. Installer failures
    for the selected provider still fail setup normally.
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
