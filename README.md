# MisEducativos — data pipeline

Scraper + parser that turns the Xunta's "área de influencia" (school catchment)
tool into a clean GeoJSON file, covering all of Galicia. See
[DISCOVERY.md](DISCOVERY.md) for the original investigation this was built
from — this README documents what actually happened when that plan met live
data, including a few corrections along the way.

## Scope: Xunta-wide, but that means 11 concellos, not 313

DISCOVERY.md's title says "scoped to A Coruña province," implying all ~95
concellos in that one province. **That's not how the catchment tool works,
in either direction.** The área de influencia feature is a separate page
from the general school-search tool, with its own concello list, and address
-based catchment lookup only exists for a short list of concellos —
confirmed against the tool's own JavaScript, not assumed:

| Provincia | Concellos covered |
|---|---|
| A Coruña | A Coruña, Ferrol, Santiago de Compostela |
| Lugo | Lugo, Cervo, Xove, Lourenzá |
| Ourense | Ourense |
| Pontevedra | Vigo, Pontevedra, Marín |

**11 concellos total, across all 4 provinces** — not every provincial
capital gets the feature (no entry for Ourense's smaller neighbors), and it's
not purely a "big city" rule either (Cervo, Xove, and Lourenzá are small Lugo
towns, included alongside Lugo city for reasons the tool doesn't explain).
This makes the earlier "province, not Xunta-wide" framing backwards in
practice: going Xunta-wide added only 8 more concellos and 26 more search
combos on top of the original 3/12 — genuinely cheap, which is why we did it.

**Practical effect for the frontend:** `MAX_BOUNDS`/`SERVICE_AREA` can't be a
single bounding box spanning all 11 concellos — they're scattered across the
whole region with a lot of empty land between them. The UI needs a way to
communicate "is my town covered" clearly (search that names what it found
even when out of scope, not a silent failure) — see the frontend-planning
discussion for the current approach (a concello switcher, sized for ~11
items, not the 3-item segmented pill that worked for the original scope).

## Second correction: catchments can vary by grade level

The plan assumed one catchment polygon per school. Most schools follow that,
but **72 of 346 schools have genuinely different catchment shapes for
different ensinanza levels** at the same building — mostly IES campuses
where the ESO zone differs from the Bacharelato zone (Vigo alone accounts for
most of these, likely because of how many private "CPR Plurilingüe" schools
it has), plus some CEIPs where Infantil differs from Primaria. Verified by
comparing raw coordinate arrays directly, not a parsing artifact. The output
GeoJSON reflects this: those schools produce two features (same
`codigo`/`nome`, different geometry and `ensinanzas` list) instead of one.

## Pipeline

Run in order from the project root, with the venv active:

```
source venv/bin/activate
python3 scripts/01_enumerate.py          # concellos + ensinanza codes, all 4 provinces
python3 scripts/02_sweep.py              # POST search for all 38 combos, cache raw HTML
python3 scripts/03_parse.py              # extract per-school records from cached HTML
python3 scripts/04_dedupe_reproject.py   # dedupe, reproject 25829->4326, write GeoJSON
```

Each script reads the previous script's output from `data/` — nothing
re-hits the server except `02_sweep.py`, and that's still only 38 requests
total for the entire region.

### Output

`data/catchments_galicia.geojson` — 420 features covering 346 unique
schools. Each feature:

```json
{
  "type": "Feature",
  "geometry": {"type": "Polygon" | "MultiPolygon", "coordinates": [...]},
  "properties": {
    "codigo": "15004976",
    "nome": "CEIP Curros Enríquez",
    "provincia_codigo": "15",
    "provincia_nome": "Coruña (A)",
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
  fixed two wrong guesses from DISCOVERY.md (see script docstrings for
  `01_enumerate.py`).
- **10-result cap check**: cross-checked `checkCentro[]` checkbox codes
  against `areaJSON` blocks in all 38 raw responses — exact 1:1 match every
  time (e.g. 85/85 for Vigo infantil), confirming the display cap doesn't
  truncate the underlying data. One combo (Lugo/Bacharelato) legitimately
  returned zero schools — confirmed by inspecting the raw response body
  (empty `cargarDatos()` function), not a fetch error.
- **Bounding-box check**: every reprojected coordinate (all 420 features)
  falls inside Galicia's lon/lat envelope.
- **Independent spot-check**: for 5 schools spread across A Coruña, Ferrol,
  Santiago, Vigo, and Ourense, fetched the school's own detail page for its
  street address, geocoded that address independently via the ArcGIS
  geocoder, and checked whether the point falls inside that school's own
  parsed catchment polygon. 4 of 5 landed exactly inside (0.0 distance,
  including both shapes for 2 multi-geometry schools). The Ourense case was
  inconclusive, not failing: the geocoder fell back to a low-confidence,
  citywide match (score 82 vs. 99+ for the others) rather than resolving the
  exact street, landing about 5m outside the boundary — a geocoder precision
  limit on that one address, not a sign our polygon or reprojection is wrong.

## Directory layout

```
scripts/    numbered pipeline steps, run in order
raw/        cached raw HTML responses + JSON enumeration (don't re-scrape to iterate the parser)
data/       parsed/deduped/final output, safe to regenerate from raw/
venv/       Python virtualenv (requests, pyproj, shapely)
requirements.txt
```

## Known limitations / open questions for later

- The Ourense spot-check should be redone with a higher-confidence address
  match before treating that concello's data as fully verified — the miss
  looked like a geocoder issue, but it's only one data point.
- We don't know *why* the 11-concello list is what it is (not simply "the
  biggest city per province" — Cervo/Xove/Lourenzá break that theory). Worth
  keeping in mind if the Xunta ever adds more concellos to the tool; nothing
  here should assume the list of 11 is permanent.
