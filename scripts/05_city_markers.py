"""
Step 5: derive one representative marker point per concello, for the
Galicia-wide overview where individual catchment polygons are too small
to see. Centroid is computed from the union of that concello's own
catchment polygons (already-reprojected EPSG:4326 data) -- no separate
geocoding needed, no risk of drifting from the data we already verified.
"""

import json
from collections import defaultdict
from shapely.geometry import shape

DATA_DIR = "data"


def main():
    with open(f"{DATA_DIR}/catchments_galicia.geojson", encoding="utf-8") as f:
        geojson = json.load(f)

    by_concello = defaultdict(list)
    for feat in geojson["features"]:
        p = feat["properties"]
        by_concello[p["concello_codigo"]].append(feat)

    markers = []
    for concello_codigo, feats in by_concello.items():
        p0 = feats[0]["properties"]
        geoms = [shape(f["geometry"]) for f in feats]
        union = geoms[0]
        for g in geoms[1:]:
            union = union.union(g)
        centroid = union.centroid

        school_codes = {f["properties"]["codigo"] for f in feats}

        markers.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [centroid.x, centroid.y]},
            "properties": {
                "concello_codigo": concello_codigo,
                "concello_nome": p0["concello_nome"],
                "provincia_codigo": p0["provincia_codigo"],
                "provincia_nome": p0["provincia_nome"],
                "school_count": len(school_codes),
            },
        })

    markers.sort(key=lambda m: m["properties"]["concello_nome"])

    out = {"type": "FeatureCollection", "features": markers}
    with open(f"{DATA_DIR}/city_markers.geojson", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(markers)} city markers to {DATA_DIR}/city_markers.geojson")
    for m in markers:
        p = m["properties"]
        lon, lat = m["geometry"]["coordinates"]
        print(f"  {p['concello_nome']:28s} ({p['provincia_nome']:12s}) "
              f"{p['school_count']:3d} schools  [{lon:.4f}, {lat:.4f}]")


if __name__ == "__main__":
    main()
