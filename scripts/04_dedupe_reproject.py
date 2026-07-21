"""
Step 4: dedupe, reproject, and build the final GeoJSON.

DEVIATION FROM THE ORIGINAL PLAN, found during dedupe -- worth flagging
plainly rather than silently working around it:

DISCOVERY.md assumed one catchment polygon per school, with ensinanzas
just being a list of what that one polygon covers. That's true for most
schools, but not all of them -- some (mostly IES campuses where ESO and
Bacharelato zones differ, plus a couple of CEIPs where Infantil and
Primaria zones differ) genuinely have DIFFERENT catchment polygons for
different grade levels at the same address. This isn't a parsing bug --
verified by inspecting the raw coordinate arrays directly, and originally
found in the 125-school A Coruna-only sample; see this script's own
printed output for the exact count at whatever scope was last run.

So instead of one feature per school, this script groups by
(codigo, exact geometry). Schools with a single consistent shape produce
one feature, same as the original plan. The 8 exceptions produce two
features sharing the same codigo/nome, each tagged with only the
ensinanzas that actually share that polygon. A frontend can still show
"this school" as one marker and switch/overlay the right catchment
polygon depending on which ensinanza the user is asking about.

Coordinate structure check (done before writing this script): the raw
"polygon" and "multipolygon" coordinate arrays already nest exactly like
GeoJSON's Polygon/MultiPolygon (ring array vs array-of-ring-arrays), so
no restructuring is needed -- only reprojecting each [x, y] pair and
capitalizing the type name.
"""

import json
from collections import defaultdict
from pyproj import Transformer

DATA_DIR = "data"
SRC_CRS = "EPSG:25829"
DST_CRS = "EPSG:4326"

# Sanity bounds for all of Galicia (Xunta-wide), used as an integrity
# check on the reprojected output (lon, lat), not a filter.
BBOX_LON = (-9.5, -6.5)
BBOX_LAT = (41.8, 43.9)

transformer = Transformer.from_crs(SRC_CRS, DST_CRS, always_xy=True)


def reproject_coords(coords):
    if isinstance(coords[0], (int, float)):
        lon, lat = transformer.transform(coords[0], coords[1])
        return [lon, lat]
    return [reproject_coords(c) for c in coords]


def geojson_type(raw_type: str) -> str:
    return {"polygon": "Polygon", "multipolygon": "MultiPolygon"}[raw_type]


def main():
    with open(f"{DATA_DIR}/parsed_records.json", encoding="utf-8") as f:
        records = json.load(f)

    by_code = defaultdict(list)
    for r in records:
        by_code[r["codigo"]].append(r)

    features = []
    multi_geometry_schools = []

    for codigo, rows in by_code.items():
        geom_groups = defaultdict(list)  # geometry json string -> rows sharing it
        for r in rows:
            key = json.dumps(r["coordinates"])
            geom_groups[key].append(r)

        if len(geom_groups) > 1:
            multi_geometry_schools.append(codigo)

        for geom_key, group_rows in geom_groups.items():
            first = group_rows[0]
            raw_coords = json.loads(geom_key)
            reprojected = reproject_coords(raw_coords)

            ensinanzas = sorted(
                {(r["ensinanza_codigo"], r["ensinanza_nome"]) for r in group_rows}
            )

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": geojson_type(first["geometry_type"]),
                    "coordinates": reprojected,
                },
                "properties": {
                    "codigo": codigo,
                    "nome": first["nome"],
                    "provincia_codigo": first["provincia_codigo"],
                    "provincia_nome": first["provincia_nome"],
                    "concello_codigo": first["concello_codigo"],
                    "concello_nome": first["concello_nome"],
                    "ensinanzas": [{"codigo": c, "nome": n} for c, n in ensinanzas],
                    "detail_url": first["detail_url"],
                },
            }
            features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    with open(f"{DATA_DIR}/catchments_galicia.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    # Integrity check: every reprojected coordinate should land inside Galicia.
    out_of_bounds = []

    def check_coords(coords, codigo):
        if isinstance(coords[0], (int, float)):
            lon, lat = coords
            if not (BBOX_LON[0] <= lon <= BBOX_LON[1] and BBOX_LAT[0] <= lat <= BBOX_LAT[1]):
                out_of_bounds.append((codigo, lon, lat))
            return
        for c in coords:
            check_coords(c, codigo)

    for feat in features:
        check_coords(feat["geometry"]["coordinates"], feat["properties"]["codigo"])

    print(f"Unique school codes: {len(by_code)}")
    print(f"Schools with grade-level-dependent geometry (>1 shape): {len(multi_geometry_schools)}")
    for c in multi_geometry_schools:
        print(f"  {c}  {by_code[c][0]['nome']}")
    print(f"Output features: {len(features)}")
    print(f"Coordinates out of Galicia bounding box: {len(out_of_bounds)}")
    if out_of_bounds:
        for codigo, lon, lat in out_of_bounds[:10]:
            print(f"  ! {codigo}: ({lon}, {lat})")
    print(f"\nWrote {DATA_DIR}/catchments_galicia.geojson")


if __name__ == "__main__":
    main()
