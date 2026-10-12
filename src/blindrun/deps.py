"""One place builds the adapters from settings (plug-and-play)."""

from blindrun.adapters import (
    make_ear,
    make_events,
    make_llm,
    make_sandbox,
    make_search,
    make_store,
    make_vcs,
)
from blindrun.config import Settings, get_settings
from blindrun.pipeline.orchestrator import Deps
from blindrun.ports import LLM, VCS, Ear, Events, Sandbox, Search, Store

PORTS = {
    "llm": LLM,
    "ear": Ear,
    "sandbox": Sandbox,
    "search": Search,
    "vcs": VCS,
    "store": Store,
    "events": Events,
}


def build_deps(settings: Settings | None = None, **overrides) -> Deps:
    s = settings or get_settings()
    world: dict = {
        "fixed": False,
        "aria_yaml": "- button 'Add to cart'\n- group:\n  - button\n  - button\n  - button\n",
    }
    parts = {
        "llm": make_llm(
            s.llm_backend, api_key=s.nebius_api_key.get_secret_value(), world=world, models=s.model_map()
        ),
        "ear": make_ear(s.ear_driver, world=world),
        "sandbox": make_sandbox(s.sandbox_backend, world=world, base_dir=s.demo_shop_dir),
        "search": make_search(s.search_backend, api_key=s.tavily_api_key),
        "vcs": make_vcs(s.vcs_backend, base_dir=s.demo_shop_dir),
        "store": make_store(s.store_backend),
        "events": make_events(s.events_backend),
    }
    parts.update(overrides)  # tests pass fakes here
    for name, port in PORTS.items():  # fail at startup, not mid-run
        assert isinstance(parts[name], port), f"{name} adapter doesn't match its port"
    return Deps(world=world, **parts)
