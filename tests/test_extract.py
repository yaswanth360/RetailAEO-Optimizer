from surfaced.extract import analyze_answer, score_result
from surfaced.models import EngineAnswer


def _ans(text, cites=()):
    return EngineAnswer("t", "q", text, list(cites))


def test_rank_follows_first_mention(product):
    r = analyze_answer(_ans("Ridgeline is great. Kestrel is fine. Alpenglow too."), product)
    assert r["Ridgeline"].rank == 1
    assert r[product.brand].rank == 2
    assert r["Alpenglow"].rank == 3
    assert not r["TerraFlask"].mentioned


def test_alias_and_word_boundary(product):
    r = analyze_answer(_ans("We like Summit and Co. Kestrelian bottles are unrelated."), product)
    assert r["Summit & Co"].mentioned          # alias matched
    assert not r[product.brand].mentioned      # 'Kestrelian' must not match 'Kestrel'


def test_top_pick_and_sentiment(product):
    r = analyze_answer(_ans("Best overall: Kestrel Outdoors, a durable and reliable choice."), product)
    me = r[product.brand]
    assert me.top_pick and me.sentiment > 0


def test_negative_sentiment_lowers_score(product):
    good = analyze_answer(_ans("Kestrel Outdoors is excellent and durable."), product)[product.brand]
    bad = analyze_answer(_ans("Kestrel Outdoors has complaints and leaks, avoid."), product)[product.brand]
    assert bad.score < good.score


def test_citation_of_own_domain(product):
    r = analyze_answer(_ans("Kestrel Outdoors is good.", ["https://kestrel-outdoors.example/x"]), product)
    assert r[product.brand].cited


def test_score_bounds():
    assert score_result(False, None, False, False, 1) == 0
    assert score_result(True, 1, True, True, 1) == 100
    assert 0 < score_result(True, 5, False, False, -1) < 100
