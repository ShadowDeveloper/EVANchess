from pathlib import Path
import shutil
import pytest
import evan.config as config_mod
from evan.config import EvanSettings, resolve_stockfish_path, ConfigurationError


def test_resolve_stockfish_raises_when_missing(monkeypatch):
    monkeypatch.delenv("STOCKFISH_PATH", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(config_mod, "DEFAULT_WINDOWS_STOCKFISH", Path("nonexistent_sf.exe"))
    with pytest.raises(ConfigurationError, match="STOCKFISH_PATH"):
        resolve_stockfish_path(None)


def test_resolve_stockfish_accepts_explicit_file(tmp_path):
    fake_bin = tmp_path / "stockfish.exe"
    fake_bin.write_text("binary")
    assert resolve_stockfish_path(str(fake_bin)) == str(fake_bin.resolve())


def test_settings_cloud_first_defaults():
    settings = EvanSettings(
        stockfish_path="stockfish",
        llm_provider="openrouter",
        llm_model="openai/gpt-4o-mini",
        openrouter_api_key="sk-or-test",
    )
    assert settings.llm_provider == "openrouter"
    assert settings.coarse_nodes == 25_000
    assert settings.deep_nodes_primary == 150_000
    assert settings.critical_moments_count == 5
    assert settings.require_llm_api_key() == "sk-or-test"


def test_require_llm_api_key_raises_when_missing():
    settings = EvanSettings(
        stockfish_path="stockfish",
        llm_provider="openrouter",
        openrouter_api_key=None,
    )
    with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
        settings.require_llm_api_key()
