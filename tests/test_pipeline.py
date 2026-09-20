import json

import pytest

from surfaced.agents.optimizer import audit_listing, optimize
from surfaced.engines import build_engines
from surfaced.engines.marketplace import ImportedEngine
from surfaced.agents.scorer import run_audit
from surfaced.pipeline import NoEnginesError, run_pipeline
from surfaced.prompts import generate_prompts


def test_prompts_unique_and_cover_intents(product):
    ps = generate_prompts(product, 40)
    assert len({p.text.lower() for p in ps}) == len(ps)
    assert {"discovery", "use_case", "comparison", "trust"} <= {p.intent for p in ps}


def test_demo_audit_shape_and_determinism(product):
    ps = generate_prompts(product)
    a = run_audit(product, build_engines(demo=True, product=product), ps)
    b = run_audit(product, build_engines(demo=True, product=product), ps)
    a["meta"].pop("generated_at"); b["meta"].pop("generated_at")
    assert a == b
    assert 0 <= a["overall"]["score"] <= 100
    assert len(a["brands"]) == 1 + len(product.competitors)
    assert a["meta"]["mode"] == "demo"
    assert set(a["engines"]) == {"chatgpt", "claude", "gemini", "perplexity", "rufus", "sparky"}
    assert abs(sum(b_["sov"] for b_ in a["brands"]) - 100) < 5   # share of voice roughly sums to 100


def test_weak_listing_gets_recommendations_and_strong_gets_fewer(product):
    weak = {r["id"] for r in audit_listing(product)}
    assert {"title", "bullets", "attributes", "qa"} <= weak
    product.title = "Kestrel Outdoors Ridge 32oz Insulated Steel Water Bottle | 24-hour cold, leak-proof lid, fits cup holders for hiking, gym workouts and commuting " + "x" * 5
    product.bullets = [f"Feature {i}: keeps drinks cold 24 hours, tested 10,000 cycles, for hikers students office commuters hiking gym workouts keeping water cold all day commuting" for i in range(5)]
    product.listing_description = "Compare with alternatives: " + "a" * 320
    product.attributes = {k: "x" for k in "abcdefghij"}
    product.qa = [{"q": "q", "a": "a"}] * 6
    product.rating, product.review_count = 4.7, 500
    strong = {r["id"] for r in audit_listing(product)}
    assert len(strong) < len(weak) and "title" not in strong


def test_optimize_orders_by_priority(product):
    recs = optimize(product, None)
    pr = [r["priority"] for r in recs]
    assert pr == sorted(pr, reverse=True)


def test_imported_marketplace_engine(tmp_path, product):
    f = tmp_path / "rufus.json"
    f.write_text(json.dumps({"Best insulated water bottles for hiking": {"text": "Try Kestrel Outdoors."}}))
    e = ImportedEngine(f, "rufus", "Amazon Rufus")
    assert e.ask("best insulated water bottles for hiking!").text == "Try Kestrel Outdoors."
    assert e.ask("something else").error


def test_no_engines_error(tmp_path, product, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "PERPLEXITY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(NoEnginesError):
        run_pipeline(product, captures_dir=str(tmp_path), data_dir=str(tmp_path), out_dir=str(tmp_path))


def test_full_pipeline_writes_content_with_disclosure(tmp_path, product, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    st = run_pipeline(product, demo=True, data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "o"), log=lambda *_: None)
    assert {"report", "recommendations", "content", "agents"} <= set(st)
    blogs = list((tmp_path / "o").rglob("blog/*.md"))
    assert blogs and all("Disclosure" in b.read_text() for b in blogs)
    assert "application/ld+json" in blogs[0].read_text()
    assert (tmp_path / "d" / "state.json").exists()
    assert list((tmp_path / "o").rglob("schema.html"))


def test_schema_never_includes_unverified_answers(product):
    from surfaced.jsonld import faq_jsonld
    out = faq_jsonld([{"q": "a?", "a": "checked answer"}, {"q": "b?", "a": "draft [VERIFY: fact]"}])
    assert [q["name"] for q in out["mainEntity"]] == ["a?"]


def test_low_coverage_warns(tmp_path, product):
    import json
    from surfaced.engines.marketplace import ImportedEngine
    f = tmp_path / "rufus.json"
    ps = generate_prompts(product)
    f.write_text(json.dumps({ps[0].text: {"text": "Try Kestrel Outdoors."}}))
    rep = run_audit(product, [ImportedEngine(f, "rufus", "Amazon Rufus")], ps)
    assert rep["meta"]["warnings"] and "unreliable" in rep["meta"]["warnings"][0]
