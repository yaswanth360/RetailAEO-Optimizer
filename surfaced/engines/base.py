from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import EngineAnswer


class Engine(ABC):
    """One place a shopper can ask a question. Implement `ask` to add a new one."""

    id: str = "engine"
    name: str = "Engine"
    kind: str = "llm-web"      # "llm-web" (AI assistants / answer engines) or "marketplace"
    mode: str = "live"         # "live" | "imported" | "demo"

    @abstractmethod
    def ask(self, prompt: str) -> EngineAnswer: ...

    def describe(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "mode": self.mode}
