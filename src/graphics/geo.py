"""Loads real country boundary polygons (Natural Earth 110m, cached at
assets/geo/world.geojson) for actual coastline shapes in route maps, no geopandas/cartopy dependency, just plain matplotlib Polygon patches
plotted in lon/lat (equirectangular) since a true projection is overkill
for a stylized documentary map.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GEOJSON_PATH = REPO_ROOT / "assets" / "geo" / "world.geojson"


@functools.lru_cache(maxsize=1)
def load_country_polygons() -> list[list[tuple[float, float]]]:
    """Returns a flat list of exterior rings (each a list of (lon, lat)
    tuples) across every country/multipolygon, holes ignored, fine at
    this zoom level for a schematic map."""
    data = json.loads(GEOJSON_PATH.read_text())
    rings: list[list[tuple[float, float]]] = []

    for feature in data["features"]:
        geom = feature["geometry"]
        if geom["type"] == "Polygon":
            polygons = [geom["coordinates"]]
        elif geom["type"] == "MultiPolygon":
            polygons = geom["coordinates"]
        else:
            continue
        for poly in polygons:
            exterior = poly[0]  # first ring is the exterior; skip holes
            rings.append([(pt[0], pt[1]) for pt in exterior])

    return rings


def rings_in_view(lon_min: float, lon_max: float, lat_min: float, lat_max: float) -> list[list[tuple[float, float]]]:
    """Cheap bbox-overlap filter so we don't hand matplotlib 177 countries
    when a map only shows a few."""
    out = []
    for ring in load_country_polygons():
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        if max(lons) < lon_min or min(lons) > lon_max or max(lats) < lat_min or min(lats) > lat_max:
            continue
        out.append(ring)
    return out
