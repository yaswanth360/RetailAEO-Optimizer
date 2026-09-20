"""Plain dataclasses shared by every agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


def domain_of(url: str) -> str:
    """Return a bare, lower-case host for a URL or domain-like string."""
    url = (url or "").strip()
    if not url:
        return ""
    if "//" not in url:
        url = "//" + url
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


@dataclass
class Competitor:
    name: str
    aliases: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)

    def names(self) -> list[str]:
        return [self.name, *self.aliases]


@dataclass
class Product:
    name: str
    brand: str
    category: str
    brand_aliases: list[str] = field(default_factory=list)
    description: str = ""
    url: str = ""                                  # your own product page / site
    marketplace_ids: dict[str, str] = field(default_factory=dict)  # {"amazon": "B0...", "walmart": "..."}
    price: float | None = None
    audience: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    # current listing
    title: str = ""
    bullets: list[str] = field(default_factory=list)
    listing_description: str = ""
    qa: list[dict[str, str]] = field(default_factory=list)
    rating: float | None = None
    review_count: int | None = None
    competitors: list[Competitor] = field(default_factory=list)

    # ---- helpers -------------------------------------------------------
    def brand_names(self) -> list[str]:
        return [self.brand, *self.brand_aliases]

    def own_markers(self) -> list[str]:
        """Substrings that mean 'this citation points at us'."""
        markers = [m for m in [domain_of(self.url)] if m]
        markers += [str(v) for v in self.marketplace_ids.values() if v]
        return markers

    def listing_text(self) -> str:
        return " ".join([self.title, *self.bullets, self.listing_description]).lower()

    # ---- constructors ---------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Product":
        d = dict(d)
        comps = []
        for c in d.pop("competitors", []) or []:
            if isinstance(c, str):
                comps.append(Competitor(name=c))
            else:
                comps.append(Competitor(**c))
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in d.items() if k in known}
        return cls(competitors=comps, **clean)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Product":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh))

    def slug(self) -> str:
        import re
        return re.sub(r"[^a-z0-9]+", "-", f"{self.brand}-{self.name}".lower()).strip("-")[:60]


@dataclass
class Prompt:
    id: str
    text: str
    intent: str  # discovery | use_case | comparison | price | trust


@dataclass
class EngineAnswer:
    engine: str
    prompt: str
    text: str = ""
    citations: list[str] = field(default_factory=list)
    error: str | None = None
