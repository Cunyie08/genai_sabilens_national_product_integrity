from __future__ import annotations
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel


class HeatmapFilters(BaseModel):
    state:      str | None  = None   # Super Admin drill-down only
    lga:        str | None  = None   # Company Admin granular filter
    subcategory: str | None = None   # nafdac_chunks.json slug
    date_from:  date | None = None
    date_to:    date | None = None


class HeatmapFeature(BaseModel):
    """One aggregated geographic unit — a state or an LGA."""
    geo_id:       str            # Matches GeoJSON NAME_1 (state) or NAME_2 (LGA)
    display_name: str            # e.g. "Lagos State" or "Alimosho LGA"
    center_lat:   float | None   # AVG of scan latitudes in this unit
    center_lng:   float | None
    total_scans:      int
    fake_count:       int
    suspicious_count: int
    authentic_count:  int
    fake_pct:         float
    combined_risk_rate: float
    risk_level: Literal["critical", "high", "medium", "low"]
    breakdown_locked: bool = False   # True = NAFDAC caller lacks quantity_breakdown approval


class HeatmapResponse(BaseModel):
    aggregation_level: Literal["state", "lga"]
    parent_geo:    str | None      # Populated when aggregation_level="lga"
    features:      list[HeatmapFeature]
    filters_applied: HeatmapFilters
    total_features: int
