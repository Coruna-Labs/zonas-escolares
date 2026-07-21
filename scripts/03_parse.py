"""
Step 3: parse each cached raw HTML response into per-school records.

Each response embeds records in a single repeating JS block inside the
cargarDatos() function:

    area = {};
    areaJSON ={"type":"...","coordinates":[...],"crs":{...epsg:25829...}};
    area.graphics = calculaGraficoArea (i, areaJSON);
    area.name= 'CEIP Cidade Vella';
    area.codigo ='15004991';
    areasInfluencia [area.codigo] = area;

Cross-checked against the separate checkCentro[] checkbox list for all
raw files (see raw/sweep_manifest.json combos): checkbox codes and
areaJSON codes are an exact 1:1 match in every file, confirming the
10-result display cap is UI-only, not a data truncation, and that the
areaJSON regex isn't missing or double-counting anything. Originally
verified against the 12 A Coruna-only combos, re-confirmed against the
full 38-combo Xunta-wide sweep.
"""

import json
import re
import glob

RAW_DIR = "raw"
DATA_DIR = "data"

RECORD_PATTERN = re.compile(
    r"areaJSON =(\{.*?\"crs\":\{\"type\":\"name\",\"properties\":\{\"name\":\"epsg:25829\"\}\}\});\s*"
    r"area\.graphics = calculaGraficoArea \(i, areaJSON\);\s*"
    r"area\.name= '((?:[^'\\]|\\.)*)';\s*"
    r"area\.codigo ='((?:[^'\\]|\\.)*)';",
    re.DOTALL
)


def unescape_js_string(s: str) -> str:
    return s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")


def parse_file(path: str, provincia_codigo: str, provincia_nome: str,
                concello_codigo: str, concello_nome: str,
                ensinanza_codigo: str, ensinanza_nome: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        html = f.read()

    records = []
    for geo_raw, name_raw, codigo in RECORD_PATTERN.findall(html):
        geometry = json.loads(geo_raw)
        records.append({
            "codigo": codigo,
            "nome": unescape_js_string(name_raw),
            "provincia_codigo": provincia_codigo,
            "provincia_nome": provincia_nome,
            "concello_codigo": concello_codigo,
            "concello_nome": concello_nome,
            "ensinanza_codigo": ensinanza_codigo,
            "ensinanza_nome": ensinanza_nome,
            "geometry_type": geometry["type"],
            "coordinates": geometry["coordinates"],
            "crs": geometry["crs"]["properties"]["name"],
            "detail_url": f"https://www.edu.xunta.gal/centroseducativos/CargarDetalleCentro.do?codigo={codigo}",
        })
    return records


def main():
    with open(f"{RAW_DIR}/sweep_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)

    all_records = []
    for entry in manifest:
        if entry["status"] != "ok":
            print(f"SKIPPING failed combo: {entry['concello_codigo']}/{entry['ensinanza_codigo']}")
            continue
        records = parse_file(
            entry["file"],
            entry["provincia_codigo"], entry["provincia_nome"],
            entry["concello_codigo"], entry["concello_nome"],
            entry["ensinanza_codigo"], entry["ensinanza_nome"],
        )
        print(f"{entry['file']}: parsed {len(records)} records "
              f"({entry['concello_nome']}, {entry['provincia_nome']} / {entry['ensinanza_nome']})")
        all_records.extend(records)

    with open(f"{DATA_DIR}/parsed_records.json", "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\nTotal parsed records (school x ensinanza rows, pre-dedupe): {len(all_records)}")
    unique_codes = {r["codigo"] for r in all_records}
    print(f"Unique school codes: {len(unique_codes)}")


if __name__ == "__main__":
    main()
