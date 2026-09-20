"""Agent 1, the Scorer: asks every engine every shopper question and scores you against competitors."""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from statistics import mean

from ..engines.base import Engine
from ..extract import EntityResult, analyze_answer, cited_domains
from ..models import EngineAnswer, Product, Prompt

# Marketplace assistants sit closest to the buy button, so they can be weighted up.
DEFAULT_WEIGHTS = {"llm-web": 1.0, "marketplace": 1.0}


def _r(x: float, n: int = 1) -> float:
    return round(x, n)


def run_audit(product: Product, engines: list[Engine], prompts: list[Prompt],
              weights: dict[str, float] | None = None, workers: int = 8, progress=None) -> dict:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    jobs = [(e, p) for e in engines for p in prompts]

    def work(job: tuple[Engine, Prompt]) -> tuple[Engine, Prompt, EngineAnswer]:
        e, p = job
        ans = e.ask(p.text)
        if progress:
            progress(e.id, p.id)
        return e, p, ans

    with ThreadPoolExecutor(max_workers=workers) as pool:
        raw = list(pool.map(work, jobs))

    entities = [product.brand] + [c.name for c in product.competitors]
    scored_ids = {p.id for p in prompts if p.intent != "trust"}
    # results[engine][prompt][entity] -> EntityResult ; only valid answers
    results: dict[str, dict[str, dict[str, EntityResult]]] = defaultdict(dict)
    answers: dict[tuple[str, str], EngineAnswer] = {}
    for e, p, ans in raw:
        answers[(e.id, p.id)] = ans
        if not ans.error and ans.text:
            results[e.id][p.id] = analyze_answer(ans, product)

    engine_meta = {e.id: e for e in engines}
    live = [e.id for e in engines if results.get(e.id)]

    # ---- per engine, per brand ---------------------------------------------------------------
    def brand_engine_stats(brand: str, eid: str) -> dict | None:
        # Branded "trust" prompts name you, so you always appear; they'd inflate every metric. Skip them.
        scored = {pid: r for pid, r in results[eid].items() if pid in scored_ids}
        rs = [r[brand] for r in scored.values()]
        if not rs:
            return None
        ment = [r for r in rs if r.mentioned]
        total_mentions = sum(1 for r in scored.values() for b in entities if r[b].mentioned)
        return {
            "score": _r(mean(r.score for r in rs)),
            "mention_rate": _r(100 * len(ment) / len(rs)),
            "avg_rank": _r(mean(r.rank for r in ment), 2) if ment else None,
            "top_pick_rate": _r(100 * sum(r.top_pick for r in rs) / len(rs)),
            "citation_rate": _r(100 * sum(r.cited for r in rs) / len(rs)),
            "sentiment": _r(mean(r.sentiment for r in ment), 2) if ment else 0.0,
            "sov": _r(100 * len(ment) / total_mentions) if total_mentions else 0.0,
        }

    per: dict[str, dict[str, dict]] = {b: {} for b in entities}
    for b in entities:
        for eid in live:
            st = brand_engine_stats(b, eid)
            if st:
                per[b][eid] = st

    def weighted(brand: str, key: str = "score") -> float:
        num = den = 0.0
        for eid, st in per[brand].items():
            w = weights.get(engine_meta[eid].kind, 1.0)
            num += w * st[key]
            den += w
        return num / den if den else 0.0

    brands = []
    for b in entities:
        brands.append({
            "name": b, "is_you": b == product.brand,
            "overall": _r(weighted(b)), "sov": _r(weighted(b, "sov")),
            "mention_rate": _r(weighted(b, "mention_rate")),
            "by_engine": {eid: st["score"] for eid, st in per[b].items()},
        })
    brands.sort(key=lambda x: -x["overall"])
    for i, b in enumerate(brands, 1):
        b["rank"] = i
    you = next(b for b in brands if b["is_you"])
    rivals = [b for b in brands if not b["is_you"]]
    best = rivals[0] if rivals else None

    # ---- prompt map ---------------------------------------------------------------------------
    prompt_rows, lost = [], []
    for p in prompts:
        row = {"id": p.id, "text": p.text, "intent": p.intent, "results": {}}
        seen_by_any = False
        for eid in live:
            rs = results[eid].get(p.id)
            if rs is None:
                continue
            mine = rs[product.brand]
            order = sorted([b for b in entities if rs[b].mentioned], key=lambda b: rs[b].rank or 99)
            row["results"][eid] = {
                "mentioned": mine.mentioned, "rank": mine.rank, "top_pick": mine.top_pick,
                "cited": mine.cited, "score": mine.score, "order": order,
                "sources": cited_domains(answers[(eid, p.id)])[:6],
            }
            seen_by_any = seen_by_any or mine.mentioned
        if row["results"] and p.intent != "trust" and mean(v["score"] for v in row["results"].values()) < 25:
            lost.append(p.id)
        prompt_rows.append(row)

    # ---- gaps ----------------------------------------------------------------------------------
    intent_rates: dict[str, list[float]] = defaultdict(list)
    domain_counter: Counter = Counter()
    own = [m.lower() for m in product.own_markers()]
    for row in prompt_rows:
        for v in row["results"].values():
            if row["intent"] == "trust":
                continue
            intent_rates[row["intent"]].append(100.0 if v["mentioned"] else 0.0)
            if not v["mentioned"]:
                for d in v["sources"]:
                    if not any(m in d.lower() for m in own):
                        domain_counter[d] += 1

    engines_out = {}
    for eid in live:
        st = per[product.brand].get(eid)
        if not st:
            continue
        valid = len([1 for pid in results[eid] if pid in scored_ids])
        engines_out[eid] = {"name": engine_meta[eid].name, "kind": engine_meta[eid].kind,
                            "mode": engine_meta[eid].mode, **st,
                            "coverage": _r(100 * valid / max(1, len(scored_ids)))}
    warnings = []
    for eid, e in engines_out.items():
        if e["coverage"] < 60:
            warnings.append(f"{e['name']} answered only {e['coverage']:.0f}% of the scored questions, "
                            "so its score is unreliable. Capture more answers or re-run.")
    skipped = [{"id": e.id, "name": e.name, "reason": "no valid answers"} for e in engines if e.id not in live]

    return {
        "meta": {
            "product": product.name, "brand": product.brand, "category": product.category,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": "demo" if any(e.mode == "demo" for e in engines) else "live",
            "n_prompts": len(prompts), "n_scored_prompts": len(scored_ids), "skipped_engines": skipped, "warnings": warnings,
        },
        "overall": {
            "score": you["overall"], "rank": you["rank"], "of": len(brands), "sov": you["sov"],
            "best_competitor": {"name": best["name"], "score": best["overall"]} if best else None,
            "gap": _r(best["overall"] - you["overall"]) if best else 0.0,
        },
        "engines": engines_out,
        "brands": brands,
        "prompts": prompt_rows,
        "gaps": {
            "intent_mention_rate": {k: _r(mean(v)) for k, v in intent_rates.items()},
            "lost_prompts": lost,
            "competitor_domains": [{"domain": d, "count": c} for d, c in domain_counter.most_common(8)],
        },
    }
