"""
Resolves nafdac_chunks.json subcategory slugs to canonical name strings.

The 6 subcategories in data/processed/nafdac_chunks.json are:
  beverages
  cereals_and_cereal_products
  cosmetics
  fats_and_oils_and_fat_emulsions
  salts_spices_soups_sauces_salads_and_seasoning
  sweeteners

Slugs are accepted case-insensitively and with spaces or underscores.
The resolved name is used to filter ProductCategory.name in DB queries.
"""
from __future__ import annotations

import json
import re
import pathlib
from functools import lru_cache

from fastapi import HTTPException

_CHUNKS_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / "data" / "processed" / "nafdac_chunks.json"
)


def _to_slug(name: str) -> str:
    """'Cereals and Cereal Products' → 'cereals_and_cereal_products'"""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


@lru_cache(maxsize=1)
def _load() -> dict[str, str]:
    """Returns {slug: original_category_name}. Cached for process lifetime."""
    try:
        raw = json.loads(_CHUNKS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    result: dict[str, str] = {}
    for chunk in raw:
        name = (chunk.get("subcategory") or "").strip()
        if name:
            result[_to_slug(name)] = name
    return result


def all_slugs() -> list[str]:
    return sorted(_load().keys())


def resolve_subcategory(slug: str | None) -> str | None:
    """
    Returns the canonical subcategory name (e.g. 'Beverages') for a given slug.
    Returns None if slug is None/empty.
    Raises HTTP 400 for unrecognised slugs.
    """
    if not slug:
        return None
    key = _to_slug(slug)
    name = _load().get(key)
    if name is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown subcategory '{slug}'. Valid values: {all_slugs()}",
        )
    return name
