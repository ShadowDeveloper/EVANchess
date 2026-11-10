from pathlib import Path
import shutil
import pytest
from pydantic import ValidationError
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


@pytest.mark.parametrize(
    ("provider", "key_name", "error_name"),
    [
        ("openrouter", "openrouter_api_key", "OPENROUTER_API_KEY"),
        ("openai", "openai_api_key", "OPENAI_API_KEY"),
        ("anthropic", "anthropic_api_key", "ANTHROPIC_API_KEY"),
    ],
)
@pytest.mark.parametrize("missing", [None, "", "   "])
def test_selected_provider_never_uses_missing_or_whitespace_credentials(provider, key_name, error_name, missing):
    settings = EvanSettings.model_validate({"llm_provider": provider, key_name: missing})
    with pytest.raises(ConfigurationError, match=error_name):
        settings.require_llm_api_key()


@pytest.mark.parametrize(
    ("url", "key", "error_name"),
    [
        (None, "test-local", "EVAN_LLM_BASE_URL"),
        ("   ", "test-local", "EVAN_LLM_BASE_URL"),
        ("http://localhost:1234/v1", None, "OPENAI_API_KEY"),
        ("http://localhost:1234/v1", "   ", "OPENAI_API_KEY"),
    ],
)
def test_local_provider_requires_explicit_url_and_credentials(url, key, error_name):
    settings = EvanSettings(llm_provider="local", llm_base_url=url, openai_api_key=key)
    with pytest.raises(ConfigurationError, match=error_name):
        settings.require_llm_api_key()


def test_local_provider_returns_explicit_key_not_a_sentinel():
    settings = EvanSettings(
        llm_provider="local", llm_base_url="http://localhost:1234/v1", openai_api_key="test-local"
    )
    assert settings.require_llm_api_key() == "test-local"


@pytest.mark.parametrize(
    "field",
    [
        "engine_threads",
        "engine_hash_mb",
        "coarse_nodes",
        "deep_nodes_tier1",
        "deep_nodes_primary",
        "challenge_nodes",
    ],
)
@pytest.mark.parametrize("value", [0, -1])
def test_engine_budgets_must_be_positive(field, value):
    with pytest.raises(ValidationError):
        EvanSettings.model_validate({field: value})


@pytest.mark.parametrize("value", [0, 2, 7, -1])
def test_critical_moment_count_stays_inside_supported_bounds(value):
    with pytest.raises(ValidationError):
        EvanSettings(critical_moments_count=value)


def test_invalid_environment_default_is_validated(monkeypatch):
    monkeypatch.setenv("EVAN_ENGINE_THREADS", "0")
    with pytest.raises(ValidationError):
        EvanSettings()


def test_api_keys_are_not_exposed_in_settings_repr():
    settings = EvanSettings(
        openrouter_api_key="private-openrouter-value",
        openai_api_key="private-openai-value",
        anthropic_api_key="private-anthropic-value",
    )
    rendered = repr(settings)
    assert "private-openrouter-value" not in rendered
    assert "private-openai-value" not in rendered
    assert "private-anthropic-value" not in rendered
