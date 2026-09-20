from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .engines.marketplace import MARKETPLACES
from .models import Product
from .pipeline import NoEnginesError, run_pipeline
from .prompts import generate_prompts


def _load_env() -> None:
    env = Path(".env")
    if not env.exists():
        return
    import os
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    _load_env()
    ap = argparse.ArgumentParser(prog="surfaced", description="Answer engine optimization agents for sellers")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("product", help="path to product.yaml")
        p.add_argument("--demo", action="store_true", help="use simulated engines (no API keys needed)")
        p.add_argument("--engines", help="comma list: claude,chatgpt,gemini,perplexity,rufus,sparky")
        p.add_argument("--prompts", type=int, default=30)
        p.add_argument("--data", default="data")
        p.add_argument("--out", default="out")

    sub.add_parser("init", help="write an example product.yaml here")
    for name, hlp in [("audit", "score visibility"), ("optimize", "recommend fixes"),
                      ("content", "draft blogs/videos/social"), ("run", "audit + optimize + content")]:
        p = sub.add_parser(name, help=hlp)
        common(p)
        if name in ("content", "run"):
            p.add_argument("--render", action="store_true", help="render silent TikTok text-card videos (ffmpeg)")
    ct = sub.add_parser("capture-template", help="write a JSON skeleton for Rufus/Sparky answers")
    ct.add_argument("product")
    ct.add_argument("engine", choices=list(MARKETPLACES))
    ct.add_argument("--captures", default="captures")
    sv = sub.add_parser("serve", help="start the dashboard")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)

    a = ap.parse_args(argv)

    if a.cmd == "init":
        src = Path(__file__).resolve().parent.parent / "examples" / "product.yaml"
        dst = Path("product.yaml")
        if dst.exists():
            print("product.yaml already exists")
            return 1
        shutil.copy(src, dst)
        print("wrote product.yaml. Edit it, then run: surfaced run product.yaml --demo")
        return 0

    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("surfaced.server:app", host=a.host, port=a.port)
        return 0

    product = Product.from_yaml(a.product)

    if a.cmd == "capture-template":
        Path(a.captures).mkdir(exist_ok=True)
        f = Path(a.captures) / f"{a.engine}.json"
        skeleton = {p.text: {"text": "", "citations": []} for p in generate_prompts(product, 30)}
        f.write_text(json.dumps(skeleton, indent=2), encoding="utf-8")
        print(f"wrote {f}. Ask {MARKETPLACES[a.engine]} each question, paste the answer into \"text\".")
        return 0

    steps = {"audit": ("score",), "optimize": ("optimize",), "content": ("content",),
             "run": ("score", "optimize", "content")}[a.cmd]
    try:
        state = run_pipeline(product, demo=a.demo, engine_names=a.engines.split(",") if a.engines else None,
                             data_dir=a.data, out_dir=a.out, steps=steps, n_prompts=a.prompts,
                             render=getattr(a, "render", False))
    except NoEnginesError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if "report" in state and a.cmd in ("audit", "run"):
        o = state["report"]["overall"]
        lead = (f"gap to leader {o['gap']}" if o["gap"] > 0 else f"ahead of the next brand by {abs(o['gap'])}")
        print(f"\nAEO visibility score: {o['score']} (rank {o['rank']} of {o['of']}; {lead})")
        for w in state["report"]["meta"].get("warnings", []):
            print(f"warning: {w}")
    if "recommendations" in state and a.cmd in ("optimize", "run"):
        print("\nTop fixes:")
        for r in state["recommendations"][:5]:
            print(f"  [{r['impact']}/5 impact, {r['effort']}/5 effort] {r['title']}")
    print(f"\nState saved to {a.data}/state.json. View it: surfaced serve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
