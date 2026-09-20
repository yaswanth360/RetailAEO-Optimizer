"""Turn a TikTok/Reel beat list into a silent vertical MP4 of text cards using ffmpeg.

Deliberately simple: no voice, no stock footage. Drop your own voiceover/music on top, or replace this
module with a call to any video generation service (see docs/EXTENDING.md).
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font() -> str | None:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    return None


def render_beats(beats: list[dict], out_path: str | Path, bg: str = "0x14213D", fg: str = "white",
                 size: tuple[int, int] = (1080, 1920)) -> Path:
    """beats: [{"on_screen": "text", "sec": 4}, ...]"""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install it (brew install ffmpeg / apt install ffmpeg).")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    font = _font()
    w, h = size
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        segs = []
        for i, b in enumerate(beats):
            text = "\n".join(textwrap.wrap(b.get("on_screen") or b.get("text") or "", 22)) or " "
            tf = tmpd / f"t{i}.txt"
            tf.write_text(text, encoding="utf-8")
            seg = tmpd / f"s{i}.mp4"
            draw = (f"drawtext=textfile='{tf}':fontcolor={fg}:fontsize=76:line_spacing=18:"
                    f"x=(w-text_w)/2:y=(h-text_h)/2" + (f":fontfile='{font}'" if font else ""))
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                   "-i", f"color=c={bg}:s={w}x{h}:d={b.get('sec', 4)}:r=30", "-vf", draw,
                   "-pix_fmt", "yuv420p", "-c:v", "libx264", str(seg)]
            subprocess.run(cmd, check=True)
            segs.append(seg)
        lst = tmpd / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs), encoding="utf-8")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", str(out_path)], check=True)
    return out_path
