# MisEducativos

An open map of school catchment zones (*áreas de influencia*) across Galicia.
Enter an address or pick a school, see exactly which zone it falls in,
color-coded by education level.

**Data:** [Xunta de Galicia, Centros educativos](https://www.edu.xunta.gal/centroseducativos/) (official source)

---

## What it shows

346 schools across the 11 concellos where the Xunta's own tool supports
address-based catchment lookup, spanning all 4 Galician provinces (A Coruña,
Ferrol, Santiago de Compostela; Lugo, Cervo, Xove, Lourenzá; Ourense; Vigo,
Pontevedra, Marín). Each school's zone is drawn as a colored ring outline for
every education level it covers (Infantil, Primaria, ESO, Bacharelato), since
a fair number of schools, IES campuses especially, have a genuinely different
shape per level, not one shape for the whole building.

A permanent rail lists every school, grouped by city, with the same colored
chips as the map. The legend chips double as filters: click one to isolate
that education level everywhere at once. Search an address and the rail
narrows to whatever matches, with the non-matching zones fading into the
background; click any result to drill in, or back out to the full list
without losing your place. Available in Galician (default), Spanish, and
English.

---

## The data pipeline

There's no public API for catchment geometry. The Xunta's tool bakes it
directly into the server-rendered HTML of a search response, as literal
JavaScript. The pipeline is a scripted scrape of that response, not a
scraping saga:

```
  Xunta de Galicia (edu.xunta.gal/centroseducativos)
  ┌───────────────────────────────────────────────┐
  │  POST search: concello × ensinanza, 38 combos  │
  │  → raw HTML, one areaJSON block per school      │
  └───────────────────────┬───────────────────────┘
                           │
                  Python · requests
                           │
                           ▼
              raw/  (cached HTML + JSON,
              so the parser can be redone
              without re-hitting the server)
                           │
                  Python · regex/json parsing
                           │
                           ▼
              data/parsed_records.json
              one row per school × ensinanza
                           │
              Python · dedupe by (codigo, geometry)
                           │
                           ▼
              Python · pyproj  (EPSG:25829 → 4326)
                           │
                           ▼
         data/catchments_galicia.geojson
         420 features, 346 unique schools
                           │
              Python · shapely  (per-concello union + centroid)
                           │
                           ▼
              data/city_markers.geojson
              one overview marker per concello
                           │
                           ▼
              index.html · MapLibre GL
              rail + search + ring-outline styling
```

### Two corrections the plan needed once it met live data

**Scope isn't a province, it's a fixed list of 11 concellos.** The original
brief assumed "A Coruña province" as a starting scope, implying dozens of
concellos. That's not how the catchment tool works in either direction:
address-based lookup only exists for 11 concellos total, confirmed against
the tool's own JavaScript, not assumed. Going Xunta-wide from there added
only 8 more concellos and 26 more search combos on top of the original
scope (genuinely cheap), which is why the project covers all of Galicia
rather than staying province-scoped.

**Catchments can vary by grade level at the same school.** The plan assumed
one polygon per school. Most follow that, but 72 of 346 schools, mostly IES
campuses where the ESO zone differs from the Bacharelato zone, plus a few
CEIPs where Infantil differs from Primaria, have genuinely different
shapes per level at the same building. Verified by comparing raw coordinate
arrays directly, not a parsing artifact. Those schools produce two GeoJSON
features (same `codigo`/`nome`, different geometry and `ensinanzas` list)
instead of one, and the frontend renders each level's ring independently
rather than picking one "dominant" shape to show.

### Run it yourself

```bash
source venv/bin/activate
python3 scripts/01_enumerate.py          # concellos + ensinanza codes, all 4 provinces
python3 scripts/02_sweep.py              # POST search for all 38 combos, cache raw HTML
python3 scripts/03_parse.py              # extract per-school records from cached HTML
python3 scripts/04_dedupe_reproject.py   # dedupe, reproject 25829->4326, write GeoJSON
python3 scripts/05_city_markers.py       # per-concello centroid markers for the overview
```

Each script reads the previous one's output from `data/`; nothing re-hits
the server except `02_sweep.py`, and that's still only 38 requests total for
the entire region. Then serve the folder and open `index.html`:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

### Output

`data/catchments_galicia.geojson` holds 420 features covering 346 unique schools:

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

---

## Verification performed

- **Endpoint verification against live JS**, not documentation: confirmed
  the search POST fields and response shape by inspecting real page
  captures, not the tool's own help text.
- **10-result display cap check**: cross-checked `checkCentro[]` checkbox
  codes against `areaJSON` blocks in all 38 raw responses, an exact 1:1 match
  every time (e.g. 85/85 for Vigo infantil), confirming the Xunta site's
  10-result display cap doesn't truncate the underlying data it sends. One
  combo (Lugo/Bacharelato) legitimately returned zero schools, confirmed by
  inspecting the raw response body, not a fetch error.
- **Bounding-box check**: every reprojected coordinate, across all 420
  features, falls inside Galicia's lon/lat envelope.
- **Independent spot-check**: for 5 schools spread across A Coruña, Ferrol,
  Santiago, Vigo, and Ourense, fetched the school's own detail page for its
  street address, geocoded that address independently via the ArcGIS
  geocoder, and checked whether the point falls inside that school's own
  parsed catchment polygon. 4 of 5 landed exactly inside (0.0 distance,
  including both shapes for 2 multi-geometry schools). The Ourense case was
  inconclusive rather than failing: the geocoder fell back to a
  low-confidence, citywide match rather than resolving the exact street,
  landing about 5m outside the boundary, a geocoder precision limit on that
  one address rather than a sign the polygon or reprojection is wrong.

---

## On the Xunta's own tool

The Xunta already publishes this data through its own *Centros educativos*
tool, and it remains the authoritative source. MisEducativos doesn't
replace it, just removes the friction around it: three mandatory filters
before anything displays, a hard 10-result cap on what's shown, and an
address-search feature that exists but is hidden behind a checkbox most
visitors never find. Enter an address or click a school, see the catchment
immediately.

---

## Directory layout

```
index.html             the whole frontend: masthead, rail, search, map
DISCOVERY.md           the original investigation this pipeline was built from
scripts/               numbered pipeline steps, run in order
raw/                   cached raw HTML responses + JSON enumeration (don't re-scrape to iterate the parser)
data/                  parsed/deduped/final GeoJSON output, safe to regenerate from raw/
venv/                  Python virtualenv (requests, pyproj, shapely)
requirements.txt
```

## Known limitations / open questions for later

- The Ourense spot-check should be redone with a higher-confidence address
  match before treating that concello's data as fully verified. The miss
  looked like a geocoder issue, but it's only one data point.
- We don't know *why* the 11-concello list is what it is (not simply "the
  biggest city per province": Cervo, Xove, and Lourenzá break that theory).
  Worth keeping in mind if the Xunta ever adds more concellos to the tool;
  nothing here should assume the list of 11 is permanent.
- School markers show catchment zones, not the school building's own
  location. The pipeline doesn't yet capture or geocode each school's real
  address, only its zone geometry.

---

## Built with

- **[MapLibre GL JS](https://maplibre.org/)**: the map renderer (open source)
- **[CARTO Positron](https://carto.com/basemaps/)**: basemap tiles
- **Python** with `requests`, `pyproj`, `shapely`: the scraping and
  reprojection pipeline
- **[Xunta de Galicia](https://www.edu.xunta.gal/centroseducativos/)**: the
  Centros educativos tool, source of every catchment polygon and school record
- **Xunta's ArcGIS geocoder**: address search and the spot-check verification
- **[Claude](https://www.anthropic.com/)** (Anthropic): used as a tool to
  work out the scraping pipeline and the map front end

---

## About

MisEducativos is a project of [Coruña Labs](https://corunalabs.org), a
small, independent, non-profit civic-tech lab for Galicia. It works in
Galician (default), Spanish, and English.

Data © Xunta de Galicia, reused under its terms. Map © CARTO, © OpenStreetMap
contributors.

*Datos, mapas e cidade. Ferramentas cívicas para Galicia.*
