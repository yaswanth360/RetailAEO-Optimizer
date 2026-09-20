"""Deterministic simulated engines so you can try Surfaced with zero API keys.

Everything here is FICTIONAL sample output. It exists to exercise the scoring, optimizer and UI,
never to draw conclusions about a real brand.
"""
from __future__ import annotations

import random

from ..models import EngineAnswer, Product
from .base import Engine

# (display name, kind, chance your brand is included, answer style)
DEMO_PROFILES: dict[str, tuple[str, str, float, str]] = {
    "chatgpt":    ("ChatGPT",        "llm-web",     0.38, "list"),
    "claude":     ("Claude",         "llm-web",     0.30, "prose"),
    "gemini":     ("Gemini",         "llm-web",     0.44, "list"),
    "perplexity": ("Perplexity",     "llm-web",     0.60, "cited"),
    "rufus":      ("Amazon Rufus",   "marketplace", 0.52, "shop"),
    "sparky":     ("Walmart Sparky", "marketplace", 0.22, "shop"),
}

SOURCES = [
    "https://www.reddit.com/r/gear/comments/abc123/best_bottle",
    "https://www.youtube.com/watch?v=demo0001",
    "https://trailtested.example/best-insulated-bottles",
    "https://www.youtube.com/watch?v=demo0002",
    "https://gearpilot.example/reviews/bottles",
    "https://www.reddit.com/r/hiking/comments/xyz789/what_bottle",
    "https://outdoorlab.example/roundup",
]
GENERIC_REASONS = [
    "keeps drinks cold for many hours", "praised for durability", "great value for the price",
    "a popular, well-reviewed option", "leak-proof lid that reviewers like", "easy to clean",
    "wide range of sizes and colors", "trusted brand with a long track record",
]
MILD_NEGATIVE = ["some reviewers mention the lid feels stiff", "a few complaints about the paint chipping",
                 "priced a little higher than average"]


class DemoEngine(Engine):
    def __init__(self, engine_id: str, product: Product | None):
        name, kind, _, style = DEMO_PROFILES[engine_id]
        self.id, self.name, self.kind, self.mode = engine_id, name, kind, "demo"
        self.style = style
        self.product = product

    def ask(self, prompt: str) -> EngineAnswer:
        p = self.product
        assert p is not None, "DemoEngine needs a Product"
        rng = random.Random(f"{self.id}|{prompt}|surfaced-demo")
        chance = DEMO_PROFILES[self.id][2]
        low = prompt.lower()
        branded = p.brand.lower() in low
        if branded:
            chance = 1.0
        elif " vs " in low:
            chance = min(1.0, chance + 0.25)

        pool: list[tuple[str, float]] = []
        strengths = [0.85, 0.75, 0.6, 0.5, 0.4, 0.3]
        for i, c in enumerate(p.competitors):
            if rng.random() < strengths[min(i, len(strengths) - 1)] + 0.1:
                pool.append((c.name, strengths[min(i, len(strengths) - 1)] + rng.random() * 0.4))
        include_you = rng.random() < chance
        if include_you:
            pool.append((p.brand, 0.35 + rng.random() * 0.75))
        if not pool:
            pool.append((p.competitors[0].name, 1.0))
        pool.sort(key=lambda t: -t[1])
        order = [n for n, _ in pool][:5]

        lines: list[str] = []
        for i, name in enumerate(order, 1):
            if name == p.brand:
                reason = rng.choice(p.features) if p.features else rng.choice(GENERIC_REASONS)
                extra = f"; {rng.choice(MILD_NEGATIVE)}" if rng.random() < 0.25 else ""
            else:
                reason, extra = rng.choice(GENERIC_REASONS), ""
            tag = "Best overall: " if i == 1 else ""
            lines.append(f"{i}. {tag}**{name}**, {reason}{extra}.")

        cat = p.category
        if self.style == "shop":
            text = f"Based on customer reviews, these {cat} are worth a look: " + " ".join(lines)
        elif self.style == "prose":
            text = f"There are several strong {cat}. " + " ".join(lines) + " Check current pricing before buying."
        else:
            text = f"Here are the top options for {cat}:\n\n" + "\n".join(lines)

        cites: list[str] = []
        if self.style in ("cited", "list", "prose"):
            cites = rng.sample(SOURCES, k=rng.randint(2, 4))
            if include_you and rng.random() < 0.35 and p.url:
                cites.append(p.url)
        return EngineAnswer(self.id, prompt, text, cites)
