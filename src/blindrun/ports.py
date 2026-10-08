"""The seven interfaces. The pipeline imports only these Protocols; each has a
real adapter and a fake, chosen by .env (see adapters/__init__.py and deps.py)."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from blindrun.schemas import (
    BBox,
    BranchResult,
    Budget,
    EarResult,
    Event,
    Finding,
    Patch,
    Plan,
    PRDraft,
    RawFinding,
    RunId,
    Shot,
    Verification,
)
from blindrun.types import RunStatus

T = TypeVar("T", bound=BaseModel)
Role = Literal["planner", "auditor", "fixer", "guard", "lightning"]


class Pattern(BaseModel):
    widget: str
    url: str
    summary: str
    keyboard: list[str]
    source: Literal["cache", "tavily"]


@runtime_checkable
class LLM(Protocol):
    async def structured(
        self,
        role: Role,
        messages: list[dict],
        schema: type[T],
        *,
        images: tuple[bytes, ...] = (),
        budget: Budget,
        thinking: bool | None = None,
    ) -> T: ...

    async def text(self, role: Role, messages: list[dict], *, budget: Budget) -> str: ...


@runtime_checkable
class Ear(Protocol):
    driver: str

    async def run(
        self,
        url: str,
        plan: Plan,
        *,
        timeout_s: int = 180,
        on_phrase: "Callable[[str, int, int], Awaitable[None]] | None" = None,
    ) -> EarResult: ...


class SandboxHandle(Protocol):
    id: str

    async def sh(self, cmd: str, *, timeout_s: int = 300) -> tuple[int, str]: ...

    async def branch(self) -> "SandboxHandle": ...

    async def close(self) -> None: ...


@runtime_checkable
class Sandbox(Protocol):
    async def prepare(self, repo: str, ref: str, setup: list[str]) -> SandboxHandle: ...


@runtime_checkable
class Search(Protocol):
    async def pattern(self, widget: str) -> Pattern: ...


@runtime_checkable
class VCS(Protocol):
    async def fetch(self, repo: str, ref: str, paths: list[str]) -> dict[str, str]: ...

    async def open_pr(self, repo: str, base: str, draft: PRDraft, diff: str) -> str: ...


@runtime_checkable
class Store(Protocol):
    async def save_run(self, run: dict) -> None: ...

    async def set_status(self, run_id: RunId, status: RunStatus, reason: str = "") -> None: ...

    async def add_findings(self, items: list[Finding]) -> None: ...

    async def get_run(self, run_id: RunId) -> dict | None: ...


@runtime_checkable
class Events(Protocol):
    async def emit(self, run_id: RunId, type_: str, data: dict) -> int: ...

    def subscribe(self, run_id: RunId, after_seq: int = 0) -> AsyncIterator[Event]: ...


# Re-exports used across adapters and the orchestrator.
__all__ = [
    "LLM",
    "VCS",
    "BBox",
    "BranchResult",
    "Budget",
    "Ear",
    "EarResult",
    "Event",
    "Events",
    "PRDraft",
    "Patch",
    "Pattern",
    "Plan",
    "RawFinding",
    "Role",
    "RunId",
    "RunStatus",
    "Sandbox",
    "SandboxHandle",
    "Search",
    "Shot",
    "Verification",
]
