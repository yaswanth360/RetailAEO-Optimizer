"""Regenerate the sample data embedded in ui/index.html from the real demo pipeline.

Run after changing scoring, the optimizer, or the content templates:
    python scripts/refresh_demo_ui.py
"""
import json
import re
import tempfile
from pathlib import Path

from surfaced.models import Product
from surfaced.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent
ui = ROOT / "ui" / "index.html"

with tempfile.TemporaryDirectory() as tmp:
    state = run_pipeline(Product.from_yaml(ROOT / "examples" / "product.yaml"), demo=True,
                         data_dir=tmp, out_dir=tmp, log=lambda *_: None)
state.pop("content_dir", None)
blob = json.dumps(state, separators=(",", ":")).replace("</", "<\\/")
html = ui.read_text(encoding="utf-8")
html, n = re.subn(r'(<script id="demo-data" type="application/json">).*?(</script>)',
                  lambda m: m.group(1) + blob + m.group(2), html, count=1, flags=re.S)
assert n == 1, "demo-data script tag not found"
ui.write_text(html, encoding="utf-8")
print(f"embedded {len(blob) // 1024} KB of demo data into {ui}")
