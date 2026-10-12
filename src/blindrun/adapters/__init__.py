"""Adapter factories. .env picks the implementation; tests pass overrides."""

from .ear_fake import FakeEar
from .events_inproc import InProcEvents
from .llm_fake import FakeLLM
from .sandbox_contree import ContreeSandbox
from .sandbox_fake import FakeSandbox
from .search_fake import CachedSearch
from .store_memory import MemoryStore
from .vcs_fake import FakeVCS

__all__ = [
    "CachedSearch",
    "ContreeSandbox",
    "FakeEar",
    "FakeLLM",
    "FakeSandbox",
    "FakeVCS",
    "InProcEvents",
    "MemoryStore",
    "make_ear",
    "make_events",
    "make_llm",
    "make_sandbox",
    "make_search",
    "make_store",
    "make_vcs",
]


def make_llm(backend: str, *, api_key: str = "", world: dict | None = None, models: dict | None = None):
    if backend == "fake":
        return FakeLLM(world=world)
    if backend == "tokenfactory":
        from .llm_tokenfactory import TokenFactoryLLM  # lazy: needs openai extras only when used

        return TokenFactoryLLM(api_key=api_key, models=models)
    raise ValueError(f"unknown llm backend: {backend}")


def make_ear(driver: str, *, world: dict | None = None):
    if driver == "fake":
        return FakeEar(world=world)
    if driver in ("virtual", "voiceover", "nvda"):
        from .ear_real import RealEar  # arrives with DR-3 (playwright extras)

        return RealEar()
    raise ValueError(f"unknown ear driver: {driver}")


def make_sandbox(backend: str, *, world: dict | None = None, base_dir: str = "demo-shop"):
    if backend == "fake":
        return FakeSandbox(world=world)
    if backend == "contree":
        # world matters: the orchestrator publishes page_file there; without it
        # the sandbox defaults to index.html and patches the WRONG page
        return ContreeSandbox(base_dir=base_dir, world=world)
    if backend == "local":
        from .sandbox_local import LocalSandbox

        return LocalSandbox(base_dir=base_dir, world=world)
    raise ValueError(f"unknown sandbox backend: {backend}")


def make_search(backend: str, *, api_key: str = ""):
    if backend in ("cache", "fake"):
        return CachedSearch()
    if backend == "tavily":
        from .search_tavily import TavilySearch

        return TavilySearch(api_key=api_key)
    raise ValueError(f"unknown search backend: {backend}")


def make_vcs(backend: str, *, base_dir: str = "demo-shop"):
    if backend == "fake":
        return FakeVCS()
    if backend == "local":
        from .vcs_local import LocalVCS

        return LocalVCS(base_dir=base_dir)
    if backend == "github":
        from .vcs_github import GitHubVCS  # lands with DR-8

        return GitHubVCS()
    raise ValueError(f"unknown vcs backend: {backend}")


def make_store(backend: str):
    if backend in ("memory", "fake"):
        return MemoryStore()
    if backend == "sqlite":
        raise NotImplementedError("sqlite store lands with the data extras (sqlalchemy)")
    raise ValueError(f"unknown store backend: {backend}")


def make_events(backend: str):
    if backend in ("inproc", "fake"):
        return InProcEvents()
    if backend == "redis":
        raise NotImplementedError("redis events land with the queue extras (arq/redis)")
    raise ValueError(f"unknown events backend: {backend}")
