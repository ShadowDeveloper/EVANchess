from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

DEFAULT_WINDOWS_STOCKFISH = Path(r"D:\Chess\Engines\Stockfish\stockfish-windows-x86-64-universal.exe")


class ConfigurationError(RuntimeError):
    """Raised when required external binaries or credentials are missing."""


def resolve_stockfish_path(
    configured_path: str | None = None,
    allow_system_default: bool = True,
) -> str:
    candidate = configured_path or os.environ.get("STOCKFISH_PATH")
    if candidate:
        path_obj = Path(candidate)
        if path_obj.is_file():
            return str(path_obj.resolve())
        found = shutil.which(candidate)
        if found:
            return found
        raise ConfigurationError(
            f"STOCKFISH_PATH='{candidate}' does not exist or is not executable."
        )
    from_path = shutil.which("stockfish")
    if from_path:
        return from_path
    if allow_system_default and DEFAULT_WINDOWS_STOCKFISH.is_file():
        return str(DEFAULT_WINDOWS_STOCKFISH.resolve())
    raise ConfigurationError(
        "Stockfish binary not found. Set STOCKFISH_PATH in .env or add 'stockfish' to system PATH."
    )


class EvanSettings(BaseModel):
    stockfish_path: str | None = Field(
        default_factory=lambda: os.environ.get("STOCKFISH_PATH")
    )
    secondary_engine_path: str | None = Field(
        default_factory=lambda: os.environ.get("SECONDARY_ENGINE_PATH")
    )
    sqlite_path: str = Field(
        default_factory=lambda: os.environ.get("EVAN_DB_PATH", "evan.db")
    )

    llm_provider: Literal["openrouter", "openai", "anthropic", "local"] = Field(
        default_factory=lambda: os.environ.get("EVAN_LLM_PROVIDER", "openrouter")  # type: ignore[arg-type]
    )
    llm_model: str = Field(
        default_factory=lambda: os.environ.get("EVAN_LLM_MODEL", "openai/gpt-4o-mini")
    )
    llm_base_url: str | None = Field(
        default_factory=lambda: os.environ.get("EVAN_LLM_BASE_URL") or None
    )
    openrouter_api_key: str | None = Field(
        default_factory=lambda: os.environ.get("OPENROUTER_API_KEY") or None
    )
    openai_api_key: str | None = Field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY") or None
    )
    anthropic_api_key: str | None = Field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY") or None
    )

    engine_threads: int = Field(
        default_factory=lambda: int(os.environ.get("EVAN_ENGINE_THREADS", "1"))
    )
    engine_hash_mb: int = Field(
        default_factory=lambda: int(os.environ.get("EVAN_ENGINE_HASH_MB", "64"))
    )
    coarse_nodes: int = Field(
        default_factory=lambda: int(os.environ.get("EVAN_COARSE_NODES", "25000"))
    )
    deep_nodes_tier1: int = Field(
        default_factory=lambda: int(os.environ.get("EVAN_DEEP_NODES_TIER1", "75000"))
    )
    deep_nodes_primary: int = Field(
        default_factory=lambda: int(os.environ.get("EVAN_DEEP_NODES_PRIMARY", "150000"))
    )
    challenge_nodes: int = Field(
        default_factory=lambda: int(os.environ.get("EVAN_CHALLENGE_NODES", "60000"))
    )
    critical_moments_count: int = Field(
        default_factory=lambda: int(os.environ.get("EVAN_CRITICAL_MOMENTS_COUNT", "5"))
    )

    def require_llm_api_key(self) -> str:
        if self.llm_provider == "openrouter":
            if not self.openrouter_api_key:
                raise ConfigurationError(
                    "OPENROUTER_API_KEY is required when EVAN_LLM_PROVIDER='openrouter'."
                )
            return self.openrouter_api_key
        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ConfigurationError(
                    "OPENAI_API_KEY is required when EVAN_LLM_PROVIDER='openai'."
                )
            return self.openai_api_key
        if self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ConfigurationError(
                    "ANTHROPIC_API_KEY is required when EVAN_LLM_PROVIDER='anthropic'."
                )
            return self.anthropic_api_key
        if self.llm_provider == "local":
            if not self.llm_base_url:
                raise ConfigurationError(
                    "EVAN_LLM_BASE_URL is required when EVAN_LLM_PROVIDER='local'."
                )
            return self.openai_api_key or "local-key"
        raise ConfigurationError(f"Unsupported LLM provider: {self.llm_provider}")
