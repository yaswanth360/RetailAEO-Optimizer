"""Turn a raw AI answer into per-brand visibility facts and a 0-100 score."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import EngineAnswer, Product, domain_of

TOP_PATTERNS = re.compile(
    r"top pick|best overall|our pick|#1|number one|editor'?s choice|best choice|"
    r"most recommended|top choice|overall winner|best for most",
    re.I,
)
POSITIVE = {
    "best", "great", "excellent", "durable", "reliable", "popular", "recommended", "top", "love",
    "well-reviewed", "well reviewed", "value", "sturdy", "praised", "standout", "impressive", "leak-proof",
    "highly rated", "favorite", "high-quality", "trusted",
}
NEGATIVE = {
    "avoid", "poor", "flimsy", "complaints", "worse", "disappointing", "cheap", "unreliable",
    "leaks", "problem", "problems", "overpriced", "stiff", "mixed reviews", "fragile", "issue", "issues",
}


@dataclass
class EntityResult:
    entity: str
    mentioned: bool
    rank: int | None
    top_pick: bool
    sentiment: float
    cited: bool
    score: float


def _first_index(text: str, names: list[str]) -> int | None:
    best: int | None = None
    for n in names:
        n = n.strip()
        if not n:
            continue
        m = re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", text, re.I)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


def _windows(text: str, names: list[str], radius: int = 120) -> list[str]:
    spans = []
    for n in names:
        if not n.strip():
            continue
        for m in re.finditer(r"(?<!\w)" + re.escape(n.strip()) + r"(?!\w)", text, re.I):
            spans.append(text[max(0, m.start() - radius): m.end() + radius].lower())
    return spans


def _sentiment(windows: list[str]) -> float:
    pos = neg = 0
    for w in windows:
        pos += sum(1 for p in POSITIVE if p in w)
        neg += sum(1 for n in NEGATIVE if n in w)
    if pos + neg == 0:
        return 0.0
    return max(-1.0, min(1.0, (pos - neg) / (pos + neg)))


def _top_pick(text: str, names: list[str]) -> bool:
    for n in names:
        if not n.strip():
            continue
        for m in re.finditer(r"(?<!\w)" + re.escape(n.strip()) + r"(?!\w)", text, re.I):
            window = text[max(0, m.start() - 80): m.end() + 120]
            if TOP_PATTERNS.search(window):
                return True
    return False


def score_result(mentioned: bool, rank: int | None, top_pick: bool, cited: bool, sentiment: float) -> float:
    """0-100. Mentioned earns a base; earlier rank, top-pick, citation and sentiment add on."""
    if not mentioned:
        return 0.0
    rank_pts = {1: 30, 2: 22, 3: 15, 4: 9}.get(rank or 99, 4)
    s = 35 + rank_pts + (15 if top_pick else 0) + (12 if cited else 0) + round(8 * sentiment)
    return float(max(0, min(100, s)))


def analyze_answer(answer: EngineAnswer, product: Product) -> dict[str, EntityResult]:
    """Returns {entity name: EntityResult} for your brand and every tracked competitor."""
    text = answer.text or ""
    entities: dict[str, tuple[list[str], list[str]]] = {
        product.brand: (product.brand_names(), product.own_markers())
    }
    for c in product.competitors:
        entities[c.name] = (c.names(), [d for d in c.domains if d])

    firsts = {e: _first_index(text, names) for e, (names, _) in entities.items()}
    ordered = sorted([e for e, i in firsts.items() if i is not None], key=lambda e: firsts[e])  # type: ignore[arg-type]
    cite_blob = [c.lower() for c in answer.citations]

    results: dict[str, EntityResult] = {}
    for e, (names, markers) in entities.items():
        mentioned = firsts[e] is not None
        rank = ordered.index(e) + 1 if mentioned else None
        top = _top_pick(text, names) if mentioned else False
        cited = any(m.lower() in c for m in markers for c in cite_blob) if markers else False
        sent = _sentiment(_windows(text, names)) if mentioned else 0.0
        results[e] = EntityResult(e, mentioned, rank, top, round(sent, 2), cited,
                                  score_result(mentioned, rank, top, cited, sent))
    return results


def cited_domains(answer: EngineAnswer) -> list[str]:
    seen, out = set(), []
    for c in answer.citations:
        d = domain_of(c) or c
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out
