"""Agent 3, the Content agent: drafts blogs, YouTube, TikTok and Instagram assets aimed at lost prompts.

Offline it fills templates using ONLY facts in your product profile (unknowns become [VERIFY] markers).
With an LLM key it polishes those drafts. Nothing is auto-posted: everything is written to out/ for a
human to review, because platform terms, disclosure rules and brand risk all need a person in the loop.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..jsonld import faq_jsonld, product_jsonld, script_tag
from ..llm import LLM
from ..models import Product
from ..prompts import generate_prompts


# ------------------------------------------------------------------ topic selection
def pick_topics(p: Product, report: dict | None, n: int = 4) -> list[str]:
    if report and report.get("prompts"):
        scored = []
        for row in report["prompts"]:
            res = row["results"].values()
            avg = sum(r["score"] for r in res) / len(res) if res else 0
            scored.append((avg, row["text"]))
        scored.sort()
        texts = [t for _, t in scored]
    else:
        texts = [x.text for x in generate_prompts(p)]
    # branded trust questions make weak standalone content; prefer generic ones first
    generic = [t for t in texts if p.brand.lower() not in t.lower()]
    return (generic + [t for t in texts if t not in generic])[:n]


def _facts(p: Product, k: int = 3) -> list[str]:
    return p.features[:k] or ["[VERIFY: add product features to your profile]"]


def _disclosure(p: Product) -> str:
    return f"Disclosure: this was created by {p.brand}, the maker of the {p.name}."


def _short(text: str, n: int = 48) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(",;:-") + "…"


def _title_case_topic(topic: str) -> str:
    t = topic.rstrip("?").strip()
    return t[0].upper() + t[1:]


def _generated_faq(p: Product, topic: str) -> list[dict[str, str]]:
    qa = list(p.qa)
    qa.append({"q": topic if topic.endswith("?") else topic + "?",
               "a": f"Check these first: {'; '.join(_facts(p, 3))}. The {p.name} is built around them. "
                    "[VERIFY: add one sentence on who it is and is not best for]"})
    for uc in p.use_cases[:2]:
        qa.append({"q": f"Is the {p.name} good for {uc}?",
                   "a": f"Relevant to {uc}: {_facts(p, 1)[0]}. "
                        f"[VERIFY: add a concrete detail for {uc}]"})
    return qa


# ------------------------------------------------------------------ channel templates
def blog_draft(p: Product, topic: str) -> str:
    title = f"{_title_case_topic(topic)}: what to look for, and how the {p.name} fits"
    facts = _facts(p, 3)
    qa = _generated_faq(p, topic)
    specs = "\n".join(f"| {k.title()} | {v} |" for k, v in p.attributes.items()) or "| [VERIFY] | add attributes |"
    audience = "\n".join(f"- **{a.title()}**: [VERIFY: one sentence on why it suits them]" for a in p.audience) or "- [VERIFY]"
    criteria = "\n".join(f"- {f[0].upper() + f[1:]}" for f in p.features) or "- [VERIFY]"
    faq = "\n\n".join(f"### {x['q']}\n{x['a']}" for x in qa)
    return f"""---
title: "{title}"
description: "A direct answer to '{topic}' with specs, use cases and FAQs."
---
# {title}

> {_disclosure(p)}

**Short answer:** when choosing {p.category}, check these first: {'; '.join(facts)}. The {p.brand} {p.name} is built around those points{(' at $' + format(p.price, '.2f')) if p.price else ''}.

## What to look for in {p.category}
{criteria}

## {p.name} at a glance
| Spec | Detail |
|---|---|
{specs}

## Who it's for
{audience}

## Frequently asked questions
{faq}

## Notes for the editor
- Replace every [VERIFY] with a checked fact or delete the sentence.
- Add 1 to 2 original photos and link to your product page.
- The JSON-LD below leaves out any FAQ answer that still has a [VERIFY] marker. Re-generate it after you edit.

{script_tag(faq_jsonld(qa))}
"""


def youtube_draft(p: Product, topic: str) -> dict:
    facts = _facts(p, 3)
    title = f"{_title_case_topic(topic)} (what actually matters)"[:70]
    beats = [
        {"t": "0:00", "beat": "Answer first", "say": f"Short answer: when choosing {p.category}, check {facts[0]}.",
         "show": f"Product hero shot of the {p.name}"},
        {"t": "0:20", "beat": "What to look for", "say": "Here are the three things that matter: " + "; ".join(facts) + ".",
         "show": "On-screen checklist, one item at a time"},
        {"t": "1:10", "beat": "Demo", "say": f"Showing the {p.name} in real use: {p.use_cases[0] if p.use_cases else '[VERIFY: use case]'}.",
         "show": "B-roll of real use, close-up of the feature"},
        {"t": "2:30", "beat": "Who should skip it", "say": "[VERIFY: an honest limitation, e.g. size or price band]",
         "show": "Talking head"},
        {"t": "3:00", "beat": "Wrap up", "say": f"If that matches what you need, the {p.name} is linked below.",
         "show": "End card with link"},
    ]
    return {
        "title": title,
        "description": (f"{_title_case_topic(topic)}: a direct answer with specs and a real demo.\n\n"
                        + "\n".join(f"{b['t']} {b['beat']}" for b in beats)
                        + f"\n\n{_disclosure(p)}\nProduct page: {p.url or '[VERIFY: link]'}"),
        "chapters": [{"time": b["t"], "title": b["beat"]} for b in beats],
        "script": beats,
        "tags": [p.category, p.brand, *p.use_cases[:3]],
        "thumbnail": f"Big text: the one spec that matters. Product on a clean background. No clickbait faces.",
        "pinned_comment": f"Questions about {p.category}? Ask below and we'll answer. {_disclosure(p)}",
    }


def tiktok_draft(p: Product, topic: str) -> dict:
    facts = _facts(p, 3)
    hooks = [f"{_title_case_topic(topic)}? Do this first.",
             f"Stop scrolling if you're shopping for {p.category}.",
             f"3 things to check before you buy {p.category}."]
    variants = []
    for i, hook in enumerate(hooks):
        beats = [{"sec": 3, "voiceover": hook, "on_screen": hook, "visual": "Face or product, fast cut"}]
        for f in facts:
            beats.append({"sec": 6, "voiceover": f"Check this: {f}.", "on_screen": _short(f), "visual": "Close-up showing it"})
        beats.append({"sec": 4, "voiceover": f"The {p.name} covers all three. Link in bio. {p.brand} made this.",
                      "on_screen": f"{p.name} | link in bio", "visual": "Product end card"})
        variants.append({"variant": i + 1, "hook": hook, "beats": beats,
                         "caption": f"{hook} #{re.sub(r'[^a-z0-9]', '', p.category.lower())} (by {p.brand})",
                         "hashtags": [f"#{re.sub(r'[^a-z0-9]', '', t.lower())}" for t in [p.category, *p.use_cases[:2]]]})
    return {"topic": topic, "variants": variants, "disclosure": _disclosure(p)}


def instagram_draft(p: Product, topic: str) -> dict:
    facts = _facts(p, 4)
    slides = [{"n": 1, "text": _title_case_topic(topic) + "?", "note": "Cover: the question, big type"}]
    slides += [{"n": i + 2, "text": f, "note": "One fact per slide, add a photo"} for i, f in enumerate(facts)]
    slides.append({"n": len(slides) + 1, "text": f"Meet the {p.name}. Link in bio.", "note": "CTA slide"})
    return {
        "carousel": slides,
        "reel": {"hook": f"{_title_case_topic(topic)}? Three checks.",
                 "beats": [{"sec": 3, "on_screen": f, "visual": "Close-up"} for f in facts[:3]]},
        "caption": f"{_title_case_topic(topic)}? Swipe for what matters. {_disclosure(p)}",
        "alt_text": f"{p.brand} {p.name}, {p.category}, shown in use for {p.use_cases[0] if p.use_cases else '[VERIFY]'}.",
        "hashtags": [f"#{re.sub(r'[^a-z0-9]', '', t.lower())}" for t in [p.category, p.brand, *p.use_cases[:2]]],
    }


# ------------------------------------------------------------------ agent
class ContentAgent:
    def __init__(self, product: Product, llm: LLM | None = None):
        self.p, self.llm = product, llm

    def _polish_json(self, kind: str, draft: dict) -> dict:
        if not self.llm:
            return draft
        try:
            raw = self.llm.complete(
                f"Improve this {kind} draft so it sounds natural and specific. Keep the exact JSON shape, keep all "
                "[VERIFY] markers, keep the disclosure. Return ONLY JSON.",
                f"Product profile:\n{json.dumps(self.p.__dict__, default=lambda o: o.__dict__)}\n\nDraft:\n{json.dumps(draft)}")
            return json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
        except Exception:  # noqa: BLE001
            return draft

    def _polish_md(self, md: str) -> str:
        if not self.llm:
            return md
        try:
            out = self.llm.complete(
                "Rewrite this blog draft to read naturally while keeping structure, the answer-first opening, the "
                "disclosure, every [VERIFY] marker and the JSON-LD block unchanged. Return Markdown only.",
                f"Product profile:\n{json.dumps(self.p.__dict__, default=lambda o: o.__dict__)}\n\nDraft:\n{md}")
            return out if "[VERIFY" in out or "Disclosure" in out else md
        except Exception:  # noqa: BLE001
            return md

    def generate(self, report: dict | None = None, n_topics: int = 4) -> dict:
        topics = pick_topics(self.p, report, n_topics)
        out: dict = {"topics": topics, "blogs": [], "youtube": [], "tiktok": [], "instagram": [],
                     "schema": {"product": product_jsonld(self.p), "faq": faq_jsonld(_generated_faq(self.p, topics[0]))}}
        for i, t in enumerate(topics):
            out["blogs"].append({"topic": t, "markdown": self._polish_md(blog_draft(self.p, t))})
            if i < 2:
                out["youtube"].append({"topic": t, **self._polish_json("YouTube", youtube_draft(self.p, t))})
            out["tiktok"].append(self._polish_json("TikTok", tiktok_draft(self.p, t)))
            if i < 3:
                out["instagram"].append({"topic": t, **self._polish_json("Instagram", instagram_draft(self.p, t))})
        return out

    def write(self, content: dict, out_dir: str | Path) -> Path:
        root = Path(out_dir) / self.p.slug()
        for sub in ("blog", "youtube", "tiktok", "instagram"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]  # noqa: E731
        for b in content["blogs"]:
            (root / "blog" / f"{slug(b['topic'])}.md").write_text(b["markdown"], encoding="utf-8")
        for y in content["youtube"]:
            (root / "youtube" / f"{slug(y['topic'])}.json").write_text(json.dumps(y, indent=2), encoding="utf-8")
        for t in content["tiktok"]:
            (root / "tiktok" / f"{slug(t['topic'])}.json").write_text(json.dumps(t, indent=2), encoding="utf-8")
        for ig in content["instagram"]:
            (root / "instagram" / f"{slug(ig['topic'])}.json").write_text(json.dumps(ig, indent=2), encoding="utf-8")
        (root / "schema.html").write_text(
            script_tag(content["schema"]["product"]) + "\n" + script_tag(content["schema"]["faq"]) + "\n", encoding="utf-8")
        return root
