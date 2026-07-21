"""
Step 1: enumerate the concello x ensinanza combinations to sweep.

IMPORTANT SCOPE NOTE, verified against a live capture on 2026-07-21:
The "area de influencia" (catchment) tool is a DIFFERENT page from the
general school-search tool, with its own JS and its own concello list.
It uses `Concellos.do?DIALOG-EVENT-DeGalicia&provincia=15`, which returns
only 3 concellos: A Coruna city, Ferrol, and Santiago de Compostela.
This is not a bug or a truncated response -- address-based catchment
zoning is a big-city feature. The other 92 concellos in the province
don't have street-level catchment boundaries in this tool at all
(confirmed against the tool's own combo-population JS, not guessed).

A session is required: CargarAreaInfluenciaCentro.do?DIALOG-EVENT-inicializa
sets a JSESSIONID cookie, and the search form's action URL embeds it.
"""

import json
import requests

BASE_URL = "https://www.edu.xunta.gal/centroseducativos"
HEADERS = {"User-Agent": "Mozilla/5.0"}
PROVINCIA_A_CORUNA = "15"

RAW_DIR = "raw"
DATA_DIR = "data"


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    # Establishes JSESSIONID, mirrors what a browser does landing on the tool.
    s.get(f"{BASE_URL}/CargarAreaInfluenciaCentro.do",
          params={"DIALOG-EVENT-inicializa": ""}, timeout=15)
    return s


def fetch_concellos(s: requests.Session, provincia: str) -> list[dict]:
    r = s.get(f"{BASE_URL}/Concellos.do",
              params={"DIALOG-EVENT-DeGalicia": "", "provincia": provincia},
              timeout=15)
    r.raise_for_status()
    return json.loads(r.text)


def fetch_ensinanzas(s: requests.Session, provincia: str, concello: str) -> list[dict]:
    r = s.get(f"{BASE_URL}/Ensinanza.do",
              params={"DIALOG-EVENT-areas": "", "provincia": provincia, "concello": concello},
              timeout=15)
    r.raise_for_status()
    return json.loads(r.text)


def main():
    s = new_session()
    concellos = fetch_concellos(s, PROVINCIA_A_CORUNA)

    enumeration = []
    for c in concellos:
        codigo = str(c["codigo"])
        ensinanzas = fetch_ensinanzas(s, PROVINCIA_A_CORUNA, codigo)
        enumeration.append({
            "concello_codigo": codigo,
            "concello_nome": c["valor"],
            "ensinanzas": [{"codigo": str(e["codigo"]), "nome": e["valor"]} for e in ensinanzas],
        })

    with open(f"{RAW_DIR}/enumeration.json", "w", encoding="utf-8") as f:
        json.dump(enumeration, f, ensure_ascii=False, indent=2)
    with open(f"{DATA_DIR}/enumeration.json", "w", encoding="utf-8") as f:
        json.dump(enumeration, f, ensure_ascii=False, indent=2)

    total_combos = sum(len(c["ensinanzas"]) for c in enumeration)
    print(f"Concellos in scope for area de influencia (provincia={PROVINCIA_A_CORUNA}): {len(enumeration)}")
    for c in enumeration:
        names = ", ".join(e["nome"] for e in c["ensinanzas"])
        print(f"  {c['concello_codigo']}  {c['concello_nome']:30s} ensinanzas: {names}")
    print(f"\nTotal concello x ensinanza combos to sweep: {total_combos}")


if __name__ == "__main__":
    main()
