"""Marketplace shopping assistants (Amazon Rufus, Walmart Sparky, ...).

These assistants have no public API and sit behind logged-in sessions, so Surfaced does NOT scrape
them. Instead you capture answers yourself (manually, or with your own tooling that respects the
marketplace's terms) and import them as JSON. `surfaced capture-template` writes the skeleton.

File format (either shape works):
    {"best insulated bottle": {"text": "...answer...", "citations": ["https://..."]}}
    [{"prompt": "...", "text": "...", "citations": []}]
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import EngineAnswer
from .base import Engine


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", s.lower()).strip()


class ImportedEngine(Engine):
    kind = "marketplace"
    mode = "imported"

    def __init__(self, path: str | Path, engine_id: str, name: str):
        self.id, self.name = engine_id, name
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(raw, list):
            raw = {r["prompt"]: r for r in raw}
        self.captures = {_norm(k): v for k, v in raw.items()}

    def ask(self, prompt: str) -> EngineAnswer:
        rec = self.captures.get(_norm(prompt))
        if not rec or not rec.get("text"):
            return EngineAnswer(self.id, prompt, error="no capture for this prompt")
        return EngineAnswer(self.id, prompt, rec["text"], rec.get("citations", []) or [])


MARKETPLACES = {
    "rufus": "Amazon Rufus",
    "sparky": "Walmart Sparky",
}
