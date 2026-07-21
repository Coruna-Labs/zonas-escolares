# MisEducativos — data pipeline

Scraper + parser that turns the Xunta's "área de influencia" (school catchment)
tool into a clean GeoJSON file. See [DISCOVERY.md](DISCOVERY.md) for the
original investigation this was built from — this README documents what
actually happened when that plan met live data, including two corrections.

## Important scope correction

DISCOVERY.md's title says "scoped to A Coruña province," implying all ~95
concellos. **That's not how the catchment tool works.** The área de
influencia feature is a separate page from the general school-search tool,
with its own concello list, and it only supports address-based catchment
lookup for **3 cities: A Coruña, Ferrol, and Santiago de Compostela.**
The other 92 concellos in the province don't have this feature at all —
confirmed against the tool's own JavaScript, not assumed. This makes sense:
street-level catchment zoning is a big-city need; rural concellos typically
have one school per area.

**Practical effect for the frontend:** `MAX_BOUNDS`/`SERVICE_AREA` should be
scoped to these 3 cities, not the whole province, and any copy that says
"A Coruña province" should say "A Coruña, Ferrol e Santiago" (or similar)
instead — otherwise the tool will look broken when someone clicks anywhere
else on the map.

## Second correction: catchments can vary by grade level

The plan assumed one catchment polygon per school. For 117 of 125 schools
that's true. But **8 schools have genuinely different catchment shapes for
different ensinanza levels** at the same building — mostly IES campuses
where the ESO zone differs from the Bacharelato zone, plus two CEIPs where
Infantil differs from Primaria. Verified by comparing raw coordinate arrays
directly, not a parsing artifact. The output GeoJSON reflects this: those 8
schools produce two features (same `codigo`/`nome`, different geometry and
`ensinanzas` list) instead of one.

## Pipeline

Run in order from the project root, with the venv active:

```
source venv/bin/activate
python3 scripts/01_enumerate.py          # concellos + ensinanza codes in scope
python3 scripts/02_sweep.py              # POST search for all 12 combos, cache raw HTML
python3 scripts/03_parse.py              # extract per-school records from cached HTML
python3 scripts/04_dedupe_reproject.py   # dedupe, reproject 25829->4326, write GeoJSON
```

Each script reads the previous script's output from `data/` — nothing
re-hits the server except `02_sweep.py`, and that only runs 12 requests
total (3 concellos x 4 ensinanza levels each: Infantil, Primaria, ESO,
Bacharelato — every concello in scope happens to offer all 4).

### Output

`data/catchments_a_coruna_cities.geojson` — 133 features covering 125
unique schools. Each feature:

```json
{
  "type": "Feature",
  "geometry": {"type": "Polygon" | "MultiPolygon", "coordinates": [...]},
  "properties": {
    "codigo": "15004976",
    "nome": "CEIP Curros Enríquez",
    "concello_codigo": "15030",
    "concello_nome": "Coruña (A)",
    "ensinanzas": [{"codigo": "22", "nome": "Educación infantil"}, ...],
    "detail_url": "https://www.edu.xunta.gal/centroseducativos/CargarDetalleCentro.do?codigo=15004976"
  }
}
```

Coordinates are EPSG:4326 (lon, lat), ready for MapLibre.

## Verification performed

- **Endpoint verification against live JS**, not documentation: found and
  fixed two wrong guesses from DISCOVERY.md (see corrections above and
  script docstrings for `01_enumerate.py`).
- **10-result cap check**: cross-checked `checkCentro[]` checkbox codes
  against `areaJSON` blocks in all 12 raw responses — exact 1:1 match every
  time (e.g. 44/44 for A Coruña primaria), confirming the display cap
  doesn't truncate the underlying data.
- **Bounding-box check**: every reprojected coordinate (all 133 features)
  falls inside Galicia's lon/lat envelope.
- **Independent spot-check**: for 3 schools (one per concello), fetched the
  school's own detail page for its street address, geocoded that address
  independently via the ArcGIS geocoder, and confirmed the point falls
  inside that school's own parsed catchment polygon — checked against both
  the raw EPSG:25829 geometry and the final reprojected EPSG:4326 GeoJSON.
  All 6 polygon variants (including both shapes for the 2 multi-geometry
  schools in the sample) passed.

## Directory layout

```
scripts/    numbered pipeline steps, run in order
raw/        cached raw HTML responses + JSON enumeration (don't re-scrape to iterate the parser)
data/       parsed/deduped/final output, safe to regenerate from raw/
venv/       Python virtualenv (requests, pyproj, shapely)
requirements.txt
```

## Known limitations / open questions for later

- Only verified against provincia=15 (A Coruña). Lugo/Ourense/Pontevedra
  were not swept — if this becomes multi-province, re-run `01_enumerate.py`
  with those provincia codes and confirm the same 3-city pattern holds
  before assuming it does.
- The geocoder spot-check used exact matches from a 3-school sample. It's
  strong evidence the pipeline is sound, not a school-by-school guarantee
  — worth a visual pass against the official map for a few more schools
  before publishing publicly.
