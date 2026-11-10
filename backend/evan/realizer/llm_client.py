from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass, field
from typing import Any

import httpx

from evan.config import ConfigurationError, EvanSettings


@dataclass
class LLMResponse:
    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    cost_usd: float | None = None


class LLMGenerationError(RuntimeError):
    def __init__(self, message: str, response: LLMResponse | None = None):
        super().__init__(message)
        self.response = response


class LLMClient:
    def __init__(self, settings: EvanSettings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def generate(self, system: str, prompt: str) -> LLMResponse:
        key = self.settings.require_llm_api_key()
        provider = self.settings.llm_provider
        base_url = self.settings.llm_base_url or {
            "openrouter": "https://openrouter.ai/api/v1",
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
        }.get(provider)
        if not base_url:
            raise ConfigurationError("A provider base URL is required.")
        if provider == "anthropic":
            path = "/messages"
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
            body = {
                "model": self.settings.llm_model,
                "max_tokens": 4096,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            }
        else:
            path = "/chat/completions"
            headers = {"Authorization": f"Bearer {key}"}
            body = {
                "model": self.settings.llm_model,
                "max_tokens": 4096,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }
        try:
            async with asyncio.timeout(65):
                if self.client is not None:
                    return await self._request(self.client, base_url.rstrip("/") + path, headers, body)
                async with httpx.AsyncClient(timeout=60.0) as client:
                    return await self._request(client, base_url.rstrip("/") + path, headers, body)
        except TimeoutError:
            raise LLMGenerationError("Provider exceeded the total generation timeout") from None

    async def _request(
        self, client: httpx.AsyncClient, url: str, headers: dict[str, str], body: dict[str, Any]
    ) -> LLMResponse:
        try:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                raise ConfigurationError("The configured LLM provider rejected authentication or access. Check the selected provider, model and live API key.") from None
            raise LLMGenerationError(f"Provider HTTP status {exc.response.status_code}") from None
        except (httpx.HTTPError, ValueError):
            raise LLMGenerationError("Provider transport or JSON response failure") from None
        if not isinstance(payload, dict):
            raise LLMGenerationError("Provider returned a non-object response")
        raw_usage = payload.get("usage", {})
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        cost = usage.get("cost")
        reported_cost = (
            float(cost)
            if isinstance(cost, (int, float)) and not isinstance(cost, bool)
            and math.isfinite(cost) and cost >= 0
            else None
        )
        result = LLMResponse("", usage, reported_cost)
        try:
            if self.settings.llm_provider == "anthropic":
                content_blocks = payload.get("content")
                if not isinstance(content_blocks, list):
                    raise ValueError("Invalid Anthropic content")
                text_parts: list[str] = []
                for item in content_blocks:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid Anthropic content block")
                    if item.get("type") == "text":
                        part = item.get("text")
                        if not isinstance(part, str):
                            raise ValueError("Invalid Anthropic text block")
                        text_parts.append(part)
                result.text = "".join(text_parts)
                if payload.get("stop_reason") == "max_tokens":
                    raise ValueError("Truncated output")
            else:
                choices = payload.get("choices")
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    raise ValueError("Invalid choices")
                choice = choices[0]
                message = choice.get("message")
                if not isinstance(message, dict):
                    raise ValueError("Invalid message")
                result.text = message.get("content", "")
                if choice.get("finish_reason") not in (None, "stop"):
                    raise ValueError("Incomplete output")
            if not isinstance(result.text, str) or not result.text.strip():
                raise ValueError("Missing prose")
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise LLMGenerationError("Provider response has no complete textual generation", result) from None
        return result


def record_usage(commentary: Any, response: LLMResponse | None) -> None:
    if response is None:
        return
    requests = commentary.usage.setdefault("requests", [])
    requests.append({"usage": response.usage, "cost_usd": response.cost_usd})
    for target, aliases in {
        "input_tokens": ("prompt_tokens", "input_tokens"),
        "output_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
    }.items():
        value = next((response.usage[a] for a in aliases if a in response.usage), None)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            commentary.usage[target] = commentary.usage.get(target, 0) + value
    costs = [request["cost_usd"] for request in requests]
    commentary.cost_usd = sum(costs) if all(cost is not None for cost in costs) else None


def parse_generation(response: LLMResponse) -> dict[str, Any]:
    try:
        result = json.loads(response.text)
        if not isinstance(result, dict):
            raise ValueError("Expected an object")
        return result
    except (ValueError, TypeError):
        raise LLMGenerationError("Provider generation is not a JSON object", response) from None
