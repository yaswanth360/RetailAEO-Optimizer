from __future__ import annotations

import os
from pathlib import Path

from .base import Engine
from .llm import LIVE_ENGINES
from .marketplace import MARKETPLACES, ImportedEngine


def build_engines(names: list[str] | None = None, captures_dir: str | Path = "captures",
                  demo: bool = False, product=None) -> list[Engine]:
    """Build every engine that is configured. Missing keys / captures are skipped, not fatal."""
    if demo:
        from .demo import DemoEngine, DEMO_PROFILES
        return [DemoEngine(eid, product) for eid in DEMO_PROFILES if not names or eid in names]

    engines: list[Engine] = []
    wanted = set(names) if names else None
    for eid, (cls, env) in LIVE_ENGINES.items():
        if (wanted is None or eid in wanted) and os.getenv(env):
            engines.append(cls())
    for eid, label in MARKETPLACES.items():
        path = Path(captures_dir) / f"{eid}.json"
        if (wanted is None or eid in wanted) and path.exists():
            engines.append(ImportedEngine(path, eid, label))
    return engines


__all__ = ["Engine", "build_engines", "LIVE_ENGINES", "MARKETPLACES", "ImportedEngine"]
