"""Model access for the agents, built on Microsoft Agent Framework.

Providers (``BOOTH_LLM``):

* ``offline``  – no model calls; every agent uses its deterministic template path (default).
* ``foundry``  – a model deployed in Microsoft Foundry / Azure OpenAI (OpenAI v1-compatible endpoint).
* ``github``   – GitHub Models (free, rate limited) – handy for development.
* ``openai``   – any other OpenAI-compatible endpoint.

The runtime adds what a live broadcast needs around every call: a concurrency cap, a per-call timeout,
a call budget and a circuit breaker that switches the crew to templates when the provider keeps failing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass

log = logging.getLogger("booth.llm")

GITHUB_MODELS_URL = "https://models.github.ai/inference"


class LLMUnavailable(RuntimeError):
    """Raised when a model call cannot be made or fails; callers fall back to templates."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "offline"
    model: str = ""
    base_url: str | None = None
    api_key: str | None = None
    timeout_s: float = 12.0
    max_concurrency: int = 2
    min_importance: float = 0.5
    breaker_threshold: int = 3
    breaker_cooldown_s: float = 60.0

    @property
    def enabled(self) -> bool:
        return self.provider != "offline" and bool(self.model and self.api_key)

    def public(self) -> dict:
        return {
            "provider": self.provider if self.enabled else "offline",
            "model": self.model if self.enabled else None,
            "configured": self.enabled,
        }

    @classmethod
    def from_env(cls) -> LLMConfig:
        provider = os.getenv("BOOTH_LLM", "offline").strip().lower()
        common = {
            "timeout_s": float(os.getenv("BOOTH_LLM_TIMEOUT", "12")),
            "max_concurrency": int(os.getenv("BOOTH_LLM_CONCURRENCY", "2")),
            "min_importance": float(os.getenv("BOOTH_LLM_MIN_IMPORTANCE", "0.5")),
        }
        if provider == "foundry":
            return cls(
                "foundry",
                os.getenv("FOUNDRY_MODEL", ""),
                os.getenv("FOUNDRY_ENDPOINT"),
                os.getenv("FOUNDRY_API_KEY"),
                **common,
            )
        if provider == "github":
            return cls(
                "github",
                os.getenv("GITHUB_MODEL", "openai/gpt-4.1-mini"),
                GITHUB_MODELS_URL,
                os.getenv("GITHUB_TOKEN"),
                **common,
            )
        if provider == "openai":
            return cls(
                "openai",
                os.getenv("OPENAI_MODEL", ""),
                os.getenv("OPENAI_BASE_URL"),
                os.getenv("OPENAI_API_KEY"),
                **common,
            )
        return cls(**common)


class LLMRuntime:
    def __init__(self, config: LLMConfig | None = None, client=None):
        self.config = config or LLMConfig.from_env()
        self._client = client
        self._semaphore = asyncio.Semaphore(self.config.max_concurrency)
        self._failures = 0
        self._open_until = 0.0
        self.calls = 0
        self.errors = 0

    @property
    def client(self):
        if self._client is None and self.config.enabled:
            from agent_framework.openai import OpenAIChatCompletionClient

            self._client = OpenAIChatCompletionClient(
                model=self.config.model, base_url=self.config.base_url, api_key=self.config.api_key
            )
        return self._client

    def available(self) -> bool:
        return (self._client is not None or self.config.enabled) and time.monotonic() >= self._open_until

    def status(self) -> dict:
        return {
            **self.config.public(),
            "breaker_open": time.monotonic() < self._open_until,
            "calls": self.calls,
            "errors": self.errors,
        }

    async def run(self, name: str, instructions: str, prompt: str, tools: list | None = None) -> str:
        """Run one agent turn and return its text. Raises ``LLMUnavailable`` on any failure."""
        if not self.available():
            raise LLMUnavailable("model provider not configured or temporarily disabled")
        from agent_framework import Agent

        agent = Agent(self.client, instructions, name=name, tools=tools or None)
        async with self._semaphore:
            self.calls += 1
            try:
                response = await asyncio.wait_for(agent.run(prompt), timeout=self.config.timeout_s)
            except Exception as exc:  # network, quota, content filter, timeout ...
                self._record_failure(name, exc)
                raise LLMUnavailable(f"{name} failed: {type(exc).__name__}") from exc
        text = (response.text or "").strip()
        if not text:
            self._record_failure(name, ValueError("empty response"))
            raise LLMUnavailable(f"{name} returned an empty response")
        self._failures = 0
        return text

    def _record_failure(self, name: str, exc: Exception) -> None:
        self.errors += 1
        self._failures += 1
        log.warning("agent %s call failed: %s", name, exc)
        if self._failures >= self.config.breaker_threshold:
            self._open_until = time.monotonic() + self.config.breaker_cooldown_s
            self._failures = 0
            log.warning("circuit breaker open for %.0fs", self.config.breaker_cooldown_s)
