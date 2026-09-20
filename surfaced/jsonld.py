"""schema.org markup that helps answer engines parse your product page."""
from __future__ import annotations

import json

from .models import Product


def product_jsonld(p: Product) -> dict:
    data: dict = {
        "@context": "https://schema.org", "@type": "Product", "name": p.name,
        "brand": {"@type": "Brand", "name": p.brand}, "description": p.description or p.listing_description,
        "category": p.category,
    }
    if p.url:
        data["url"] = p.url
    if p.price:
        data["offers"] = {"@type": "Offer", "price": f"{p.price:.2f}", "priceCurrency": "USD",
                          "availability": "https://schema.org/InStock"}
    if p.rating and p.review_count:
        data["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": p.rating,
                                   "reviewCount": p.review_count}
    if p.attributes:
        data["additionalProperty"] = [{"@type": "PropertyValue", "name": k, "value": v}
                                      for k, v in p.attributes.items()]
    return data


def faq_jsonld(qa: list[dict[str, str]]) -> dict:
    """Answers still containing a [VERIFY] marker are left out so unchecked text never reaches your site."""
    qa = [x for x in qa if "[VERIFY" not in x["a"]]
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": x["q"],
                            "acceptedAnswer": {"@type": "Answer", "text": x["a"]}} for x in qa]}


def script_tag(obj: dict) -> str:
    return '<script type="application/ld+json">\n' + json.dumps(obj, indent=2) + "\n</script>"
