"""Session preparation boundary; execution and acceptance belong to launchers.

This first extraction deliberately pins Codex. Configuration-driven selection
and protocol normalization are separate steps, not implicit provider fallbacks.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol


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
class PreparedSession:
    adapter: AgentAdapter
    request: SessionRequest
    argv: tuple[str, ...]
    environment: dict[str, str]
    cwd: Path

    def revised(self, **changes) -> 'PreparedSession':
        """Reprepare under the same adapter, including capacity attempts."""
        return self.adapter.prepare_session(replace(self.request, **changes), self.environment)


def prepare_session(request: SessionRequest, environment: dict[str, str]) -> PreparedSession:
    # Selection stays inactive until every transport and caller is qualified.
    from agent_codex import CodexAdapter
    return CodexAdapter().prepare_session(request, environment)
