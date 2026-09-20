"""Live adapters are tested against canned responses shaped like each vendor's documented format.
(They are NOT tested against the real APIs in CI: that needs your keys.)"""
from surfaced.engines import llm


def _patch(monkeypatch, payload):
    monkeypatch.setattr(llm, "post_json", lambda *a, **k: payload)


def test_anthropic_parses_text_and_citations(monkeypatch):
    _patch(monkeypatch, {"content": [
        {"type": "web_search_tool_result", "content": [{"type": "web_search_result", "url": "https://a.example/x"}]},
        {"type": "text", "text": "Try Ridgeline.", "citations": [{"url": "https://b.example/y"}]}]})
    a = llm.AnthropicEngine("k").ask("q")
    assert a.text == "Try Ridgeline." and a.citations == ["https://a.example/x", "https://b.example/y"]


def test_openai_responses_shape(monkeypatch):
    _patch(monkeypatch, {"output": [{"type": "web_search_call"}, {"type": "message", "content": [
        {"type": "output_text", "text": "Try Alpenglow.", "annotations": [{"type": "url_citation", "url": "https://c.example"}]}]}]})
    a = llm.OpenAIEngine("k").ask("q")
    assert a.text == "Try Alpenglow." and a.citations == ["https://c.example"]


def test_gemini_grounding_uses_title_as_domain(monkeypatch):
    _patch(monkeypatch, {"candidates": [{"content": {"parts": [{"text": "Try Summit."}]},
          "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://redirect/abc", "title": "reddit.com"}}]}}]})
    a = llm.GeminiEngine("k").ask("q")
    assert a.text == "Try Summit." and a.citations == ["reddit.com"]


def test_perplexity_shape(monkeypatch):
    _patch(monkeypatch, {"choices": [{"message": {"content": "Try TerraFlask."}}], "citations": ["https://d.example"]})
    a = llm.PerplexityEngine("k").ask("q")
    assert a.text == "Try TerraFlask." and a.citations == ["https://d.example"]


def test_failure_becomes_error_not_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("429")
    monkeypatch.setattr(llm, "post_json", boom)
    assert llm.PerplexityEngine("k").ask("q").error
