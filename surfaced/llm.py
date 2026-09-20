"""Plain text generation used by the Optimizer and Content agents (no web search needed).

Pick a provider with SURFACED_LLM_PROVIDER=anthropic|openai|gemini (default: first key found).
If no key is set, agents fall back to deterministic templates, so everything still runs offline.
"""
from __future__ import annotations

import os

from .http import post_json

GUARDRAILS = (
    "You write marketing content for a real retail brand. Hard rules: use ONLY facts given in the "
    "product profile; never invent statistics, awards, certifications, reviews, testimonials or "
    "competitor claims; if a needed fact is missing write [VERIFY: what is needed] instead of guessing; "
    "be fair to competitors; write for people first and answer engines second; keep any disclosure line."
)


class LLM:
    def __init__(self, provider: str, key: str):
        self.provider, self.key = provider, key

    @classmethod
    def from_env(cls) -> "LLM | None":
        want = os.getenv("SURFACED_LLM_PROVIDER", "").lower()
        order = [("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY"), ("gemini", "GEMINI_API_KEY")]
        for prov, env in order:
            if (not want or want == prov) and os.getenv(env):
                return cls(prov, os.environ[env])
        return None

    def complete(self, system: str, user: str, max_tokens: int = 3000) -> str:
        system = f"{GUARDRAILS}\n\n{system}"
        if self.provider == "anthropic":
            d = post_json("https://api.anthropic.com/v1/messages",
                          {"x-api-key": self.key, "anthropic-version": "2023-06-01"},
                          {"model": os.getenv("SURFACED_ANTHROPIC_MODEL", "claude-sonnet-5"),
                           "max_tokens": max_tokens, "system": system,
                           "messages": [{"role": "user", "content": user}]})
            return "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")
        if self.provider == "openai":
            d = post_json("https://api.openai.com/v1/chat/completions",
                          {"Authorization": f"Bearer {self.key}"},
                          {"model": os.getenv("SURFACED_OPENAI_MODEL", "gpt-4o"),
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            return d["choices"][0]["message"]["content"]
        model = os.getenv("SURFACED_GEMINI_MODEL", "gemini-2.5-flash")
        d = post_json(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      {"x-goog-api-key": self.key},
                      {"systemInstruction": {"parts": [{"text": system}]},
                       "contents": [{"parts": [{"text": user}]}]})
        return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
