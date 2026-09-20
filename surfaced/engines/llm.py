"""Live adapters for AI assistants that expose an API with web grounding.

These are written against each vendor's public REST docs. Model names change often,
so every model is overridable with an environment variable.
"""
from __future__ import annotations

import os
from typing import Any

from ..http import post_json
from ..models import EngineAnswer
from .base import Engine


class AnthropicEngine(Engine):
    id, name = "claude", "Claude"

    def __init__(self, api_key: str | None = None, model: str | None = None, web_search: bool = True):
        self.key = api_key or os.environ["ANTHROPIC_API_KEY"]
        self.model = model or os.getenv("SURFACED_ANTHROPIC_MODEL", "claude-sonnet-5")
        self.web = web_search

    def ask(self, prompt: str) -> EngineAnswer:
        body: dict[str, Any] = {"model": self.model, "max_tokens": 1500,
                                "messages": [{"role": "user", "content": prompt}]}
        if self.web:
            body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
        try:
            data = post_json("https://api.anthropic.com/v1/messages",
                             {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                              "content-type": "application/json"}, body)
            texts, cites = [], []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                    cites += [c["url"] for c in block.get("citations", []) or [] if c.get("url")]
                elif block.get("type") == "web_search_tool_result" and isinstance(block.get("content"), list):
                    cites += [c["url"] for c in block["content"] if isinstance(c, dict) and c.get("url")]
            return EngineAnswer(self.id, prompt, "".join(texts), list(dict.fromkeys(cites)))
        except Exception as exc:  # noqa: BLE001
            return EngineAnswer(self.id, prompt, error=str(exc))


class OpenAIEngine(Engine):
    id, name = "chatgpt", "ChatGPT"

    def __init__(self, api_key: str | None = None, model: str | None = None, web_search: bool = True):
        self.key = api_key or os.environ["OPENAI_API_KEY"]
        self.model = model or os.getenv("SURFACED_OPENAI_MODEL", "gpt-4o")
        self.web = web_search

    def ask(self, prompt: str) -> EngineAnswer:
        body: dict[str, Any] = {"model": self.model, "input": prompt}
        if self.web:
            body["tools"] = [{"type": "web_search"}]
        try:
            data = post_json("https://api.openai.com/v1/responses",
                             {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}, body)
            text, cites = data.get("output_text") or "", []
            for item in data.get("output", []):
                if item.get("type") != "message":
                    continue
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        if not data.get("output_text"):
                            text += part.get("text", "")
                        cites += [a["url"] for a in part.get("annotations", []) if a.get("url")]
            return EngineAnswer(self.id, prompt, text, list(dict.fromkeys(cites)))
        except Exception as exc:  # noqa: BLE001
            return EngineAnswer(self.id, prompt, error=str(exc))


class GeminiEngine(Engine):
    id, name = "gemini", "Gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, web_search: bool = True):
        self.key = api_key or os.environ["GEMINI_API_KEY"]
        self.model = model or os.getenv("SURFACED_GEMINI_MODEL", "gemini-2.5-flash")
        self.web = web_search

    def ask(self, prompt: str) -> EngineAnswer:
        body: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
        if self.web:
            body["tools"] = [{"google_search": {}}]
        try:
            data = post_json(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                {"x-goog-api-key": self.key, "Content-Type": "application/json"}, body)
            cand = (data.get("candidates") or [{}])[0]
            text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
            cites = []
            for ch in cand.get("groundingMetadata", {}).get("groundingChunks", []) or []:
                web = ch.get("web", {})
                title = web.get("title", "")
                # Gemini returns redirect URLs; the title is usually the real domain.
                cites.append(title if "." in title and " " not in title else web.get("uri", ""))
            return EngineAnswer(self.id, prompt, text, [c for c in dict.fromkeys(cites) if c])
        except Exception as exc:  # noqa: BLE001
            return EngineAnswer(self.id, prompt, error=str(exc))


class PerplexityEngine(Engine):
    id, name = "perplexity", "Perplexity"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.key = api_key or os.environ["PERPLEXITY_API_KEY"]
        self.model = model or os.getenv("SURFACED_PERPLEXITY_MODEL", "sonar")

    def ask(self, prompt: str) -> EngineAnswer:
        try:
            data = post_json("https://api.perplexity.ai/chat/completions",
                             {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                             {"model": self.model, "messages": [{"role": "user", "content": prompt}]})
            text = data["choices"][0]["message"]["content"]
            cites = data.get("citations") or [r.get("url") for r in data.get("search_results", []) if r.get("url")]
            return EngineAnswer(self.id, prompt, text, list(dict.fromkeys(cites or [])))
        except Exception as exc:  # noqa: BLE001
            return EngineAnswer(self.id, prompt, error=str(exc))


LIVE_ENGINES = {
    "claude": (AnthropicEngine, "ANTHROPIC_API_KEY"),
    "chatgpt": (OpenAIEngine, "OPENAI_API_KEY"),
    "gemini": (GeminiEngine, "GEMINI_API_KEY"),
    "perplexity": (PerplexityEngine, "PERPLEXITY_API_KEY"),
}
