"""Runs the three agents end to end and persists state for the CLI and the UI."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .agents.content import ContentAgent
from .agents.optimizer import optimize, propose_listing
from .agents.scorer import run_audit
from .engines import build_engines
from .llm import LLM
from .models import Product
from .prompts import generate_prompts


class NoEnginesError(RuntimeError):
    pass


def load_state(data_dir: str | Path = "data") -> dict | None:
    f = Path(data_dir) / "state.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def save_state(state: dict, data_dir: str | Path = "data") -> Path:
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "state.json"
    f.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return f


def run_pipeline(product: Product, *, demo: bool = False, engine_names: list[str] | None = None,
                 captures_dir: str = "captures", data_dir: str = "data", out_dir: str = "out",
                 steps: tuple[str, ...] = ("score", "optimize", "content"), n_prompts: int = 30,
                 weights: dict | None = None, render: bool = False, log=print) -> dict:
    state = load_state(data_dir) or {}
    state["product"] = asdict(product)
    agents = []

    def mark(name: str, note: str) -> None:
        agents.append({"agent": name, "status": "done", "note": note,
                       "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})

    prompts = generate_prompts(product, n_prompts)
    if "score" in steps:
        engines = build_engines(engine_names, captures_dir, demo=demo, product=product)
        if not engines:
            raise NoEnginesError(
                "No engines configured. Set at least one API key (see .env.example), add marketplace captures to "
                "captures/, or run with --demo.")
        log(f"[scorer] asking {len(engines)} engines x {len(prompts)} prompts")
        state["report"] = run_audit(product, engines, prompts, weights)
        r = state["report"]["overall"]
        mark("Scorer", f"score {r['score']}, rank {r['rank']} of {r['of']}")
    report = state.get("report")

    llm = LLM.from_env()
    if "optimize" in steps:
        log("[optimizer] auditing listing and gaps")
        state["recommendations"] = optimize(product, report)
        draft = propose_listing(product, report, llm)
        if draft:
            state["listing_draft"] = draft
        mark("Optimizer", f"{len(state['recommendations'])} recommendations"
             + (", LLM listing draft" if draft else ""))

    if "content" in steps:
        log("[content] drafting blogs, YouTube, TikTok, Instagram")
        agent = ContentAgent(product, llm)
        content = agent.generate(report)
        root = agent.write(content, out_dir)
        state["content"] = content
        state["content_dir"] = str(root)
        if render:
            from .render.slideshow import render_beats
            for i, t in enumerate(content["tiktok"]):
                v = t["variants"][0]
                render_beats(v["beats"], Path(root) / "tiktok" / f"video_{i + 1}.mp4")
            log("[content] rendered silent text-card videos")
        mark("Content", f"{len(content['blogs'])} blogs, {len(content['youtube'])} YouTube, "
             f"{len(content['tiktok'])} TikTok, {len(content['instagram'])} Instagram")

    state["agents"] = agents
    save_state(state, data_dir)
    return state
