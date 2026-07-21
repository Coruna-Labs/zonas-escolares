# MisEducativos — Project Brief

## What this is
A clean, user-friendly rebuild of the Xunta de Galicia's área de influencia (school catchment zone) tool, scoped to A Coruña province to start. Part of Coruña Labs. This file is the handoff from an investigation done in chat — everything below was verified against real page captures (view-source of actual search results), not guessed or assumed from documentation.

## Why
The official tool (https://www.edu.xunta.gal/centroseducativos/) buries genuinely useful public data — school locations, catchment polygons, address-to-catchment lookup — behind bureaucratic friction: three mandatory filters before anything displays, a hard 10-result display cap, and the useful "search by address" feature hidden behind a checkbox. Goal: free the useful 20% from the archaic 80%. Enter an address or click the map, immediately see the school catchment.

## The core finding: no separate polygon API
There is no WFS/WMS/GeoJSON endpoint serving catchment geometry. The polygons are baked directly into the server-rendered HTML as literal JavaScript on every search response. This is good news — it means a scripted HTTP scrape + parse, not a scraping saga.

### The search request
`POST /centroseducativos/CargarAreaInfluenciaCentro.do?DIALOG-EVENT-buscarCentros`

Required fields:
- `filtroProvincia` — e.g. `15` = A Coruña
- `filtroConcello` — concello code
- `filtroEnsinanza` — ensinanza (school type/stage) code

No CSRF token or ViewState field — just plain hidden inputs (`codigo`, `buscarEnArea`, `x`, `y`) alongside the visible filters.

**Unverified, test first:** whether this POST needs a session cookie (`jsessionid`) from a prior GET, or works as a stateless request. Try both — a `requests.Session()` doing a GET then the POST is the safe default if cookies turn out to matter.

### The search response
For each matched school, the HTML embeds:
- A checkbox: `checkCentro[n]`, `value` = school code (e.g. `15004976`), label = school name (e.g. "CEIP Curros Enríquez"), linking to `/centroseducativos/CargarDetalleCentro.do?codigo={code}` (full address/contact detail page)
- `areasInfluencia['{codigo}'] = area` where `area.name`, `area.codigo`, and `area.graphics` (built from the geometry below)
- `areaJSON = {"type":"multipolygon"|"polygon","coordinates":[[[...]]]}` — literal coordinate arrays, one per matched school

**Coordinate system: EPSG:25829** (ETRS89 / UTM zone 29N). Reproject to EPSG:4326 for MapLibre (`sf::st_transform()` in R, `pyproj`/`shapely` in Python).

### School point markers are NOT a separate live API
There's a `FeatureLayer` titled "Colexios de Galicia" in the code that looks like it could be a live remote source — it isn't. It's built client-side from a local `source` array (`colexios`) that in the capture we inspected wasn't populated at all (likely only populated in some search modes). Don't rely on it. Use the checkbox code + name + detail-page link instead for point/identity data.

### Enumeration endpoints (for building the concello × ensinanza sweep)
- `GET Concellos.do?DIALOG-EVENT-DeGalicia&provincia=15` → list of `{codigo, valor}` concellos in A Coruña province
- `GET Ensinanza.do?DIALOG-EVENT-areas&provincia=15&concello={concello_code}` → list of `{codigo, valor}` valid ensinanza types for that concello

Both are plain GETs, no form submission needed — use these to enumerate before sweeping.

### Bonus: public geocoder (for our own address-search UI later)
`GET https://ideg2.xunta.gal/arcgis/rest/services/Geocoder/GeocodeServer/findAddressCandidates?f=pjson&address={addr}&city={city}&subRegion={province}&outSR=25829&Region=Galicia&maxLocations=1`
Public, cookie-less, standard ArcGIS geocoder response shape.

## Open items to verify early (cheap — do before the full sweep)
1. Session/cookie requirement on the search POST (see above).
2. **The 10-result cap** — when a concello × ensinanza combo matches more than 10 schools, does the server still embed all of them in `areaJSON`/`areasInfluencia` (just skip auto-drawing), or does it truncate the underlying data too? Test against a concello known to have many schools. Compare count of `checkCentro[]` entries to count of `areaJSON` blocks.
3. Confirm every checkbox has a matching `areaJSON` 1:1, and figure out a reliable way to tell `multipolygon` vs `polygon` apart when parsing (the `type` field in `areaJSON` itself should suffice, but verify against a few real examples).

## Build sequence
1. **Enumerate** — pull all concello codes for provincia=15, then valid ensinanza codes per concello.
2. **Sweep** — for each concello × ensinanza combination, POST the search and save the *raw HTML response to disk* before parsing anything. Caching raw responses means the parser can be iterated on without re-hitting the server.
3. **Parse** — extract each `checkCentro[n]` (code, name, detail link) and its matching `areaJSON` block. One record per school: `{codigo, nome, tipo_ensino, concello, geometry}`.
4. **Dedupe** — a school will appear across multiple ensinanza sweeps (e.g. a CEIP offering both Infantil and Primaria). Dedupe by `codigo`, union the covered ensinanzas.
5. **Reproject** — 25829 → 4326.
6. **Output** — clean GeoJSON, one feature per school catchment. Properties: `codigo`, `nome`, `concello`, `ensinanzas[]`.
7. **Spot-check** — before building any frontend, manually compare a handful of parsed polygons against the official site to confirm the geometry is right.

Only move to the MapLibre frontend once the data pipeline is verified.

## Frontend — Coruña Labs map-template conventions (once data is solid)
- Single HTML file per tool
- Masthead with gradient fade (no card)
- Language via `?lang=` param + localStorage (not separate path trees) — Galician default, `?lang=es` / `?lang=en` for Spanish/English
- MapLibre GL 4.7.1 via cdnjs
- CARTO Positron basemap
- `SERVICE_AREA`/`MAX_BOUNDS` + minZoom for camera constraints, scoped to A Coruña province initially
- Native MapLibre popup for simple callouts; docked panel for data-heavy callouts — this tool is data-heavy (school name, catchment, address, link to official detail page), so likely docked panel
- Zoom control bottom-left, desktop only
- Visual identity: Space Grotesk display, Inter body, near-monochrome palette — Atlantic blue `#1B4965`, Galería glass `#5C8AA3`, Grass `#6B8F71` accents
- Tone: quiet, institutional, European — no self-promotion
- Reference the `coruna-labs/map-template` repo if available in the project folder; ask Allen for the URL if not

## How to work with Allen
- Comfortable with code, not a professional dev — explain slightly above his level, skip unnecessary jargon.
- Honesty over polish: never fake or interpolate data. If a sweep combo fails or looks incomplete, say so plainly rather than silently skipping it.
- Verify, don't guess: everything above was reverse-engineered from real page captures, not official documentation — treat it as a strong, tested hypothesis to confirm against live responses, not as gospel. Check actual API/response shapes before assuming.
- This scraping stage is intentionally in **Python** (requests + regex/json parsing) even though R is the default pipeline language for Coruña Labs projects — Allen is picking Python up deliberately here, so plain, well-commented code is appreciated over cleverness.
- Work incrementally: enumerate first, verify against a single concello before running the full province sweep, cache raw responses so a parser bug doesn't cost a re-scrape.
