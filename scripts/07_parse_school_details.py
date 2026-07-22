"""
Step 7: parse the cached detail pages from 06_scrape_school_details.py and
merge the extra fields onto catchments_galicia.geojson.

Each detail page is a read-only form, not JSON -- values live in plain
`<input value="...">` attributes (email is the one exception, rendered as
a non-selectable `<span id="correo">`, presumably to slow down copy-paste
scraping of addresses; doesn't slow down a regex). Fields extracted:

    titular              ownership ("Consellería de Educación..." for
                          public schools, a named entity for private ones)
    ensino_concertado     bool -- privately run but publicly subsidized
    enderezo              street address
    codigo_postal         postal code
    localidade            locality (can differ from concello in rural areas)
    telefono, fax, www, correo   contact fields -- www/correo are often
                                 empty strings, not every school has either

This step only adds properties to the existing features; it doesn't
touch geometry. Safe to rerun on its own once 06 has cached the pages.
"""

import glob
import html
import json
import re

RAW_DIR = "raw/detail"
DATA_DIR = "data"

FIELD_PATTERN = {
    "titular": re.compile(r'name="titular" value="([^"]*)"'),
    "enderezo": re.compile(r'name="enderezo\.enderezo" value="([^"]*)"'),
    "codigo_postal": re.compile(r'name="enderezo\.CP" value="([^"]*)"'),
    "localidade": re.compile(r'name="enderezo\.localidade\.nome" value="([^"]*)"'),
    "telefono": re.compile(r'name="contacto\.telefono" value="([^"]*)"'),
    "fax": re.compile(r'name="contacto\.fax" value="([^"]*)"'),
    "www": re.compile(r'name="contacto\.www" value="([^"]*)"'),
}
CONCERTADO_PATTERN = re.compile(
    r'name="ensinoConcertado" value="on"([^>]*)>'
)
CORREO_PATTERN = re.compile(r'<span id="correo"[^>]*>([^<]*)</span>')


def parse_detail(html_text: str) -> dict:
    fields = {}
    for key, pattern in FIELD_PATTERN.items():
        m = pattern.search(html_text)
        fields[key] = html.unescape(m.group(1)).strip() if m else ""

    concertado_m = CONCERTADO_PATTERN.search(html_text)
    fields["ensino_concertado"] = bool(concertado_m and "checked" in concertado_m.group(1))

    correo_m = CORREO_PATTERN.search(html_text)
    fields["correo"] = html.unescape(correo_m.group(1)).strip() if correo_m else ""

    return fields


def main():
    with open(f"{RAW_DIR}/detail_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)

    details_by_codigo = {}
    missing = []
    for entry in manifest:
        if entry["status"] != "ok":
            missing.append(entry["codigo"])
            continue
        with open(entry["file"], encoding="utf-8") as f:
            html_text = f.read()
        details_by_codigo[entry["codigo"]] = parse_detail(html_text)

    print(f"Parsed detail pages for {len(details_by_codigo)} schools.")
    if missing:
        print(f"Missing (fetch failed in step 6): {missing}")

    with open(f"{DATA_DIR}/catchments_galicia.geojson", encoding="utf-8") as f:
        geojson = json.load(f)

    merged, unmatched = 0, []
    for feat in geojson["features"]:
        codigo = feat["properties"]["codigo"]
        details = details_by_codigo.get(codigo)
        if details is None:
            unmatched.append(codigo)
            continue
        feat["properties"].update(details)
        merged += 1

    with open(f"{DATA_DIR}/catchments_galicia.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"Merged detail fields onto {merged} features.")
    if unmatched:
        print(f"Features with no matching detail data: {sorted(set(unmatched))}")

    # Quick sanity spot-check: how many schools have each optional field.
    have_www = sum(1 for d in details_by_codigo.values() if d["www"])
    have_correo = sum(1 for d in details_by_codigo.values() if d["correo"])
    have_concertado = sum(1 for d in details_by_codigo.values() if d["ensino_concertado"])
    print(f"\nOf {len(details_by_codigo)} schools: {have_www} have a website, "
          f"{have_correo} have an email, {have_concertado} are ensino concertado.")


if __name__ == "__main__":
    main()
