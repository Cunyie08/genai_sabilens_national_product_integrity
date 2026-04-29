"""
Local reverse geocoder using GADM Nigeria LGA GeoJSON.

An STRtree spatial index is built at process startup and cached via lru_cache.
All lookups are in-process point-in-polygon checks (~1-5 ms each) with no
external HTTP calls, no API keys, and no rate limits.

GADM property names used:
  NAME_1 → Nigerian State  (e.g. "Lagos")
  NAME_2 → LGA             (e.g. "AlimoshoNorth" → normalised to "Alimosho North")
"""
from __future__ import annotations

import json
import logging
import pathlib
import re
from functools import lru_cache
from typing import Optional

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

logger = logging.getLogger(__name__)

_LGA_PATH = (
    pathlib.Path(__file__).parent.parent
    / "admin" / "assets" / "nigeria_lgas.json"
)


def _normalize(name: str) -> str:
    """'AbaNorth' → 'Aba North'.  Already-spaced names pass through unchanged."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).strip()


@lru_cache(maxsize=1)
def _build_index() -> tuple:
    """
    Parses the LGA GeoJSON once and returns a 4-tuple:
        (STRtree | None, list[Geometry], list[state_str], list[lga_str])

    Cached for the lifetime of the process — first call is ~1-2 s,
    every subsequent call returns immediately.
    """
    if not _LGA_PATH.exists():
        logger.error(
            "nigeria_lgas.json not found at %s — reverse geocoding disabled", _LGA_PATH
        )
        return None, [], [], []

    try:
        raw = json.loads(_LGA_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to parse nigeria_lgas.json: %s", exc)
        return None, [], [], []

    geoms: list = []
    states: list[str] = []
    lgas: list[str] = []

    for feat in raw.get("features", []):
        props = feat.get("properties", {})
        try:
            geom = shape(feat["geometry"])
        except Exception:
            continue
        geoms.append(geom)
        states.append(props.get("NAME_1", ""))
        lgas.append(_normalize(props.get("NAME_2", "")))

    if not geoms:
        logger.error("No valid geometries found in nigeria_lgas.json")
        return None, [], [], []

    index = STRtree(geoms)
    logger.info("Geocoder index ready: %d LGA polygons", len(geoms))
    return index, geoms, states, lgas


def reverse_geocode(
    latitude: float, longitude: float
) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (state, lga) for the given WGS-84 coordinates.
    Returns (None, None) if the point falls outside all known LGA polygons
    or if the index could not be built.

    Note: Shapely Point takes (longitude, latitude) — not (lat, lng).
    """
    index, geoms, states, lgas = _build_index()
    if index is None:
        return None, None

    point = Point(longitude, latitude)

    # STRtree.query(..., predicate="within") uses the spatial index to find
    # only geometries whose interior contains the point — O(log n).
    hits = index.query(point, predicate="within")
    if len(hits) == 0:
        return None, None

    idx = int(hits[0])
    return states[idx] or None, lgas[idx] or None
