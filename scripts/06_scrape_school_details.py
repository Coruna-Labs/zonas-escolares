"""
Step 6: fetch each school's own detail page and cache it to disk.

Every school in catchments_galicia.geojson carries a detail_url (already
captured during the 02_sweep.py/03_parse.py steps, one per checkCentro[]
entry). That page is a separate, richer record per school: full street
address and postal code, phone, fax, official website, email, ownership
type ("titular"), and whether the school is ensino concertado (privately
run but publicly subsidized). None of that rides along on the catchment
search response, so it takes a second request per school, not a bigger
first one.

346 unique schools -> 346 requests. Same caching rule as 02_sweep.py: save
every raw response to disk before parsing anything, so 07_parse_school_
details.py can be fixed and rerun without hitting the server again.
"""

import json
import os
import time
import requests

RAW_DIR = "raw/detail"
DATA_DIR = "data"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DELAY_SECONDS = 1.0  # 346 requests -- lighter pacing than 02_sweep.py's, still deliberately not zero


def main():
    with open(f"{DATA_DIR}/catchments_galicia.geojson", encoding="utf-8") as f:
        geojson = json.load(f)

    # A school can appear as 2 features (see 04_dedupe_reproject.py's
    # multi-geometry note) but its detail page is the same either way --
    # dedupe by codigo before fetching.
    by_codigo = {}
    for feat in geojson["features"]:
        p = feat["properties"]
        by_codigo[p["codigo"]] = p["detail_url"]

    os.makedirs(RAW_DIR, exist_ok=True)
    s = requests.Session()
    s.headers.update(HEADERS)

    results = []
    codigos = sorted(by_codigo)
    for i, codigo in enumerate(codigos, 1):
        url = by_codigo[codigo]
        fname = f"{RAW_DIR}/{codigo}.html"
        print(f"[{i}/{len(codigos)}] Fetching {codigo} ...", end=" ")
        try:
            r = s.get(url, timeout=20)
            r.raise_for_status()
            with open(fname, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"OK ({len(r.text)} bytes)")
            results.append({"codigo": codigo, "file": fname, "status": "ok"})
        except Exception as exc:
            print(f"FAILED: {exc}")
            results.append({"codigo": codigo, "file": None, "status": f"error: {exc}"})
        time.sleep(DELAY_SECONDS)

    with open(f"{RAW_DIR}/detail_manifest.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    failed = [r for r in results if r["status"] != "ok"]
    print(f"\nDetail scrape complete: {len(results) - len(failed)}/{len(results)} schools OK.")
    if failed:
        print("FAILED schools (see raw/detail/detail_manifest.json):")
        for r in failed:
            print(f"  {r['codigo']}: {r['status']}")


if __name__ == "__main__":
    main()
