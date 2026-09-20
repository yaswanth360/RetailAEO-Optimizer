from pathlib import Path

import pytest

from surfaced.models import Product

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "product.yaml"


@pytest.fixture()
def product() -> Product:
    return Product.from_yaml(EXAMPLE)
