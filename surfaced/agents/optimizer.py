"""Agent 2, the Optimizer: turns audit gaps + listing weaknesses into a ranked fix list.

Two layers:
  1. Listing audit: deterministic checks on your title, bullets, attributes, Q&A, reviews.
     This works offline and is what gets marketplace assistants (Rufus, Sparky) to understand you.
  2. Gap analysis: uses the scorer's report (which prompts you lose, which sources the winners are
     cited from) to recommend off-listing moves that help ChatGPT, Gemini, Claude, Perplexity.
"""
from __future__ import annotations

import json
import re

from ..llm import LLM
from ..models import Product

ATTR_CHECKLIST = ["material", "capacity", "dimensions", "weight", "color", "care instructions",
                  "warranty", "certifications", "country of origin"]
ALL = ["claude", "chatgpt", "gemini", "perplexity", "rufus", "sparky"]
MARKET = ["rufus", "sparky"]


def _rec(id_, area, title, detail, impact, effort, engines, evidence, kind="listing") -> dict:
    return {"id": id_, "area": area, "kind": kind, "title": title, "detail": detail,
            "impact": impact, "effort": effort, "engines": engines, "evidence": evidence}


def suggest_title(p: Product) -> str:
    bits = [p.brand, p.name.replace(p.brand, "").strip()]
    spec = ", ".join(p.features[:2])
    use = f" for {p.use_cases[0]}" if p.use_cases else ""
    return f"{' '.join(b for b in bits if b)} | {spec}{use}"[:200]


def audit_listing(p: Product) -> list[dict]:
    recs: list[dict] = []
    tlen = len(p.title)
    if tlen < 80:
        recs.append(_rec("title", "Title", "Make the title say what it is, who it's for and one hard spec",
                         "Shopping assistants read titles first. Include category, top use case and your strongest "
                         f"measurable feature. Draft: \"{suggest_title(p)}\"",
                         5, 1, ALL, f"Current title is {tlen} characters; 80 to 200 is the usual sweet spot."))
    if len(p.bullets) < 5 or (p.bullets and sum(map(len, p.bullets)) / len(p.bullets) < 60):
        recs.append(_rec("bullets", "Bullets", "Rewrite bullets as full, specific answers",
                         "Each bullet should answer a shopper question (how long, how big, who is it for) with a "
                         "number or a named material. Aim for five bullets of 80 to 200 characters.",
                         5, 2, ALL, f"{len(p.bullets)} bullets, average "
                         f"{int(sum(map(len, p.bullets)) / max(1, len(p.bullets)))} characters."))
    numeric = sum(1 for b in p.bullets if re.search(r"\d", b))
    if p.bullets and numeric < max(2, len(p.bullets) // 2):
        recs.append(_rec("numbers", "Bullets", "Add measurable claims you can prove",
                         "Assistants quote numbers (hours, ounces, cycles, warranty years). Pull them from your "
                         f"spec sheet, e.g.: {'; '.join(p.features[:2]) or 'add features to your profile'}.",
                         4, 1, ALL, f"Only {numeric} of {len(p.bullets)} bullets contain a number."))
    if len(p.listing_description) < 300:
        recs.append(_rec("description", "Description", "Expand the description to cover who, when and why",
                         "Write 300+ characters that name use cases, audiences and how you differ from "
                         "alternatives, in plain sentences an assistant can lift verbatim.",
                         4, 2, ALL, f"Description is {len(p.listing_description)} characters."))
    have = {k.lower() for k in p.attributes}
    missing = [a for a in ATTR_CHECKLIST if a not in have]
    if len(p.attributes) < 8:
        recs.append(_rec("attributes", "Attributes", "Fill every product attribute field",
                         "Structured attributes feed filters and comparison answers. Missing: "
                         + ", ".join(missing[:6]) + ".", 4, 1, ALL,
                         f"{len(p.attributes)} attributes filled; 8+ recommended."))
    if len(p.qa) < 6:
        recs.append(_rec("qa", "Q&A", "Publish answers to the questions shoppers actually ask",
                         "Answer 6+ real questions on the listing and your site (fit, care, compatibility, "
                         "warranty). The content agent drafts them from your lost prompts.",
                         4, 2, ALL, f"{len(p.qa)} Q&A entries."))
    text = p.listing_text()
    missing_uc = [u for u in p.use_cases if u.lower() not in text]
    if missing_uc:
        recs.append(_rec("usecases", "Coverage", "Name the use cases shoppers ask about",
                         f"Shoppers ask \"best {p.category} for {missing_uc[0]}\" and similar. Your listing never "
                         "mentions: " + ", ".join(missing_uc) + ". Assistants need that evidence to match you.",
                         4, 1, ALL, f"{len(missing_uc)} of {len(p.use_cases)} use cases missing from title, bullets and description."))
    missing_aud = [a for a in p.audience if a.lower() not in text]
    if missing_aud:
        recs.append(_rec("audience", "Coverage", "Say who it's for",
                         "Name these audiences and why it fits each: " + ", ".join(missing_aud) + ".",
                         3, 1, ALL, f"{len(missing_aud)} of {len(p.audience)} audiences missing from listing text."))
    if (p.rating and p.rating < 4.3) or (p.review_count is not None and p.review_count < 100):
        recs.append(_rec("reviews", "Reviews", "Grow review volume and fix recurring complaints",
                         "Use the marketplace's approved review-request feature, fix the top complaint theme, "
                         "and never offer incentives or post fake reviews.",
                         5, 4, ALL, f"Rating {p.rating}, {p.review_count} reviews."))
    if not re.search(r"\bvs\b|compared|compare|alternative", text):
        recs.append(_rec("comparison", "Comparison", "Add an honest comparison block",
                         "Assistants answer \"X vs Y\". A factual table (specs, warranty, price band) gives them "
                         "quotable material. Use verifiable specs only.",
                         3, 3, ["claude", "chatgpt", "gemini", "perplexity"], "No comparison language found."))
    if p.url:
        recs.append(_rec("schema", "Structured data", "Add Product + FAQ schema to your product page",
                         "Generated for you by the content agent (see out/<product>/schema.html). Paste it in the "
                         "<head> of your product page.", 4, 1, ["gemini", "chatgpt", "perplexity", "claude"],
                         "Structured data helps web-grounded assistants read price, specs and Q&A.", kind="external"))
    return recs


def gap_recommendations(report: dict, p: Product) -> list[dict]:
    recs: list[dict] = []
    engines = report["engines"]
    weak = sorted(engines.items(), key=lambda kv: kv[1]["score"])[:2]
    for eid, st in weak:
        if st["score"] < 40:
            recs.append(_rec(f"weak_{eid}", "Visibility", f"Priority engine: {st['name']}",
                             f"You appear in {st['mention_rate']:.0f}% of {st['name']} answers "
                             f"(score {st['score']:.0f}). Fix the listing gaps above first"
                             + ("; this is a marketplace assistant, so listing quality is the main lever."
                                if st["kind"] == "marketplace" else
                                "; this engine reads the open web, so pair them with content on the sources below."),
                             4, 3, [eid], f"Mention rate {st['mention_rate']:.0f}%, top-pick rate {st['top_pick_rate']:.0f}%.",
                             kind="external"))
    rates = report["gaps"]["intent_mention_rate"]
    for intent, rate in sorted(rates.items(), key=lambda kv: kv[1])[:2]:
        if rate < 40:
            nice = {"discovery": "generic \"best X\" searches", "use_case": "use-case questions",
                    "comparison": "head-to-head comparisons", "price": "price-based questions",
                    "trust": "brand and review questions"}.get(intent, intent)
            recs.append(_rec(f"intent_{intent}", "Content", f"Publish content for {nice}",
                             f"You show up in only {rate:.0f}% of {nice}. Create one page or video per lost prompt "
                             "that answers it in the first two sentences.", 4, 2,
                             ["claude", "chatgpt", "gemini", "perplexity"],
                             f"Mention rate for {intent} prompts: {rate:.0f}%.", kind="content"))
    for d in report["gaps"]["competitor_domains"][:4]:
        dom = d["domain"]
        if "reddit" in dom:
            how = ("Answer real questions in relevant subreddits as yourself, disclose you work for the brand, "
                   "and follow each community's rules. Do not astroturf.")
        elif "youtube" in dom:
            how = "Publish a video that answers the lost prompts directly (the content agent scripts it)."
        else:
            how = f"Pitch {dom} with a review sample or updated spec sheet; ask to be considered for their roundup."
        recs.append(_rec(f"src_{re.sub(r'[^a-z]+', '_', dom)}", "Sources", f"Earn a presence on {dom}", how,
                         4 if d["count"] >= 5 else 3, 3, ["claude", "chatgpt", "gemini", "perplexity"],
                         f"Cited {d['count']} times in answers where you were missing.", kind="external"))
    return recs


def prioritise(recs: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for r in recs:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    for r in unique:
        r["priority"] = round(r["impact"] * 2 - r["effort"] * 0.5, 1)
    return sorted(unique, key=lambda r: (-r["priority"], r["effort"]))


def optimize(p: Product, report: dict | None = None) -> list[dict]:
    recs = audit_listing(p)
    if report:
        recs += gap_recommendations(report, p)
    return prioritise(recs)


def propose_listing(p: Product, report: dict | None, llm: LLM | None) -> dict | None:
    """Optional: ask an LLM for a full rewrite draft. Returns None without an API key."""
    if llm is None:
        return None
    lost = []
    if report:
        by_id = {r["id"]: r["text"] for r in report["prompts"]}
        lost = [by_id[i] for i in report["gaps"]["lost_prompts"] if i in by_id][:8]
    user = (
        "Rewrite this marketplace listing so shopping assistants can answer these lost shopper questions. "
        "Return ONLY JSON with keys title, bullets (5 strings), description, qa (list of {q,a}). "
        f"Lost questions: {lost}\n\nProduct profile:\n{json.dumps(p.__dict__, default=lambda o: o.__dict__, indent=1)}"
    )
    try:
        raw = llm.complete("You are an ecommerce listing optimizer.", user)
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
