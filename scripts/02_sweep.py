"""
Step 2: sweep every concello x ensinanza combo and save the raw HTML
response to disk before parsing anything, per DISCOVERY.md's caching
rule -- if the parser has a bug later, we don't want to re-hit the server.
"""

import json
import time
import requests

BASE_URL = "https://www.edu.xunta.gal/centroseducativos"
HEADERS = {"User-Agent": "Mozilla/5.0"}
PROVINCIA_A_CORUNA = "15"

RAW_DIR = "raw"
DATA_DIR = "data"
DELAY_SECONDS = 1.5  # polite pacing -- this is a small, 12-request sweep


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(f"{BASE_URL}/CargarAreaInfluenciaCentro.do",
          params={"DIALOG-EVENT-inicializa": ""}, timeout=15)
    return s


def search(s: requests.Session, provincia: str, concello: str, ensinanza: str) -> str:
    payload = {
        "codigo": "",
        "buscarEnArea": "N",
        "x": "",
        "y": "",
        "filtroProvincia": provincia,
        "filtroConcello": concello,
        "filtroEnsinanza": ensinanza,
        "filtroTipoCentro": "",
    }
    r = s.post(f"{BASE_URL}/CargarAreaInfluenciaCentro.do",
               params={"DIALOG-EVENT-buscarCentros": ""},
               data=payload, timeout=30)
    r.raise_for_status()
    return r.text


def main():
    with open(f"{DATA_DIR}/enumeration.json", encoding="utf-8") as f:
        enumeration = json.load(f)

    s = new_session()
    results = []
    for c in enumeration:
        concello_codigo = c["concello_codigo"]
        for e in c["ensinanzas"]:
            ensinanza_codigo = e["codigo"]
            fname = f"{RAW_DIR}/search_{concello_codigo}_{ensinanza_codigo}.html"
            print(f"Fetching concello={concello_codigo} ({c['concello_nome']}) "
                  f"ensinanza={ensinanza_codigo} ({e['nome']}) ...", end=" ")
            try:
                html = search(s, PROVINCIA_A_CORUNA, concello_codigo, ensinanza_codigo)
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"OK ({len(html)} bytes) -> {fname}")
                results.append({
                    "concello_codigo": concello_codigo,
                    "concello_nome": c["concello_nome"],
                    "ensinanza_codigo": ensinanza_codigo,
                    "ensinanza_nome": e["nome"],
                    "file": fname,
                    "status": "ok",
                })
            except Exception as exc:
                print(f"FAILED: {exc}")
                results.append({
                    "concello_codigo": concello_codigo,
                    "concello_nome": c["concello_nome"],
                    "ensinanza_codigo": ensinanza_codigo,
                    "ensinanza_nome": e["nome"],
                    "file": None,
                    "status": f"error: {exc}",
                })
            time.sleep(DELAY_SECONDS)

    with open(f"{RAW_DIR}/sweep_manifest.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    failed = [r for r in results if r["status"] != "ok"]
    print(f"\nSweep complete: {len(results) - len(failed)}/{len(results)} combos OK.")
    if failed:
        print("FAILED combos (see raw/sweep_manifest.json):")
        for r in failed:
            print(f"  {r['concello_codigo']} / {r['ensinanza_codigo']}: {r['status']}")


if __name__ == "__main__":
    main()
