"""Scout: turn a product profile into the questions real shoppers ask AI assistants."""
from __future__ import annotations

import hashlib
from datetime import date

from .models import Product, Prompt


def _id(text: str) -> str:
    return "p_" + hashlib.sha1(text.lower().encode()).hexdigest()[:8]


def generate_prompts(product: Product, limit: int = 24) -> list[Prompt]:
    cat = product.category
    year = date.today().year
    out: list[tuple[str, str]] = []

    out += [
        (f"What are the best {cat} in {year}?", "discovery"),
        (f"Which {cat} should I buy?", "discovery"),
        (f"Top rated {cat}", "discovery"),
        (f"Best {cat} brands", "discovery"),
    ]
    for uc in product.use_cases:
        out.append((f"Best {cat} for {uc}", "use_case"))
    for aud in product.audience:
        out.append((f"What {cat} do you recommend for {aud}?", "use_case"))
    if product.price:
        cap = int(round(product.price * 1.25 / 5.0) * 5)
        out.append((f"Best {cat} under ${cap}", "price"))
        out.append((f"What are good budget {cat}?", "price"))
    for comp in product.competitors[:4]:
        out.append((f"{product.brand} vs {comp.name}: which {cat} is better?", "comparison"))
        out.append((f"Alternatives to {comp.name}", "comparison"))
    out += [
        (f"Is {product.brand} a good brand?", "trust"),
        (f"Is the {product.brand} {product.name} worth it?", "trust"),
        (f"{product.brand} {product.name} reviews", "trust"),
    ]

    seen: set[str] = set()
    prompts: list[Prompt] = []
    for text, intent in out:
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        prompts.append(Prompt(id=_id(text), text=text, intent=intent))
    return prompts[:limit]
