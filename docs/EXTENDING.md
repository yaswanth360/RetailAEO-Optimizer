# Extending Surfaced

## Add an engine

An engine is anything that can answer a shopper question. Subclass `Engine`, return an `EngineAnswer`, and register it.

```python
# surfaced/engines/copilot.py
import os
from ..http import post_json
from ..models import EngineAnswer
from .base import Engine

class CopilotEngine(Engine):
    id, name, kind = "copilot", "Microsoft Copilot", "llm-web"

    def __init__(self):
        self.key = os.environ["COPILOT_API_KEY"]

    def ask(self, prompt: str) -> EngineAnswer:
        try:
            data = post_json("https://example.invalid/v1/answer", {"Authorization": f"Bearer {self.key}"},
                             {"q": prompt})
            return EngineAnswer(self.id, prompt, data["text"], data.get("sources", []))
        except Exception as exc:
            return EngineAnswer(self.id, prompt, error=str(exc))
```

Then add it to `LIVE_ENGINES` in `surfaced/engines/llm.py` as `"copilot": (CopilotEngine, "COPILOT_API_KEY")` and add its id to `ENGINE_ORDER` in `ui/index.html`. Return `error=` instead of raising, so one failing engine never stops an audit.

For a marketplace assistant with no API, do not automate it. Add it to `MARKETPLACES` in `surfaced/engines/marketplace.py` and have users import captures.

## Add a content channel

Write a `<channel>_draft(product, topic)` function in `surfaced/agents/content.py` that returns a dict using only product facts (use `[VERIFY: ...]` for unknowns and keep `_disclosure(product)`), then wire it into `ContentAgent.generate` and `ContentAgent.write`. Add a tab in `renderContent` in the UI.

## Swap the video renderer

`surfaced/render/slideshow.py` exposes `render_beats(beats, out_path)`. To use a generation service instead, write a function with the same signature that calls the service and saves an MP4, then call it from `pipeline.py` in place of `render_beats`. Beats look like `{"on_screen": "text", "voiceover": "...", "sec": 4, "visual": "shot idea"}`.

## Publishing content automatically

Surfaced writes drafts to `out/` and stops. That is deliberate: platform APIs need your OAuth credentials, most platforms require paid-partnership or AI-content disclosures, and a wrong claim on a public channel is a brand risk. If you add a publisher, keep it behind an explicit `--publish` flag and only publish drafts that contain no `[VERIFY]` markers.

## Change the scoring

Per-answer scoring lives in `score_result` in `surfaced/extract.py`; engine weights live in `surfaced/agents/scorer.py`. Pass `weights={"marketplace": 1.5}` to `run_audit` to count marketplace assistants more heavily than open-web assistants.
