"""All configuration. Only this module reads env vars; secrets are SecretStr."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"  # dev | demo | prod

    # --- Nebius Token Factory (all model calls) ---
    nebius_api_key: SecretStr = SecretStr("")  # empty => only fake LLM works
    token_factory_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    nebius_project_id: str = ""  # needed by contree-sdk once Sandboxes land

    # --- model router (.env switches models, never code) ---
    planner_model: str = "nvidia/nemotron-3-super-120b-a12b"
    # Fixer defaults to Ultra: quality-first (the recorded demo fix came from Ultra).
    # Super is the cheaper first choice if cost matters; escalation_model is the last resort.
    fixer_model: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    escalation_model: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    # DR-0 (Oct 6): no NVIDIA vision model on the account. Auditor is A/B:
    # text-only Nemotron vs a vision model; decide on the benchmark, not vibes.
    auditor_model: str = "nvidia/nemotron-3-super-120b-a12b"
    auditor_vision_model: str = "openbmb/MiniCPM-V-4_5"  # candidate, unused by default
    lightning_model: str = "nvidia/Nemotron-3_5-Lightning"
    guard_model: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    embed_model: str = "Qwen/Qwen3-Embedding-8B"

    # --- backends: fake until the real one lands (plug-and-play) ---
    llm_backend: str = "fake"  # fake | tokenfactory
    ear_driver: str = "fake"  # fake | virtual | voiceover | nvda
    sandbox_backend: str = "fake"  # fake | contree | local
    search_backend: str = "cache"  # cache | tavily
    vcs_backend: str = "fake"  # fake | github
    store_backend: str = "memory"  # memory | sqlite
    events_backend: str = "inproc"  # inproc | redis

    # --- policy knobs ---
    run_token_budget: int = 400_000
    max_fix_rounds: int = 2
    fix_candidates: int = 3
    ear_timeout_s: int = 180

    # --- services (day 1 runs without any of these) ---
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite+aiosqlite:///./blindrun.db"
    tavily_api_key: str = ""
    github_repo: str = ""
    demo_shop_dir: str = "demo-shop"

    def model_map(self) -> dict[str, str]:
        """Role -> model id, for the Token Factory adapter's .env-driven router."""
        return {
            "planner": self.planner_model,
            "fixer": self.fixer_model,
            "auditor": self.auditor_model,
            "guard": self.guard_model,
            "lightning": self.lightning_model,
            "escalation": self.escalation_model,
        }


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Some SDKs (contree-sdk) read NEBIUS_* from the process env, not from .env;
    # export what .env provided so backend adapters see the same credentials.
    import os

    if s.nebius_api_key.get_secret_value() and not os.environ.get("NEBIUS_API_KEY"):
        os.environ["NEBIUS_API_KEY"] = s.nebius_api_key.get_secret_value()
    if s.nebius_project_id and not os.environ.get("NEBIUS_PROJECT_ID"):
        os.environ["NEBIUS_PROJECT_ID"] = s.nebius_project_id
    return s
