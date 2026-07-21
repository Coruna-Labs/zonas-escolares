"""
Step 1: enumerate the concello x ensinanza combinations to sweep, across
all four Galicia provinces (Xunta-wide, not just A Coruna).

IMPORTANT SCOPE NOTE, verified against a live capture on 2026-07-21 and
confirmed to hold across all 4 provinces on 2026-07-21:
The "area de influencia" (catchment) tool is a DIFFERENT page from the
general school-search tool, with its own JS and its own concello list.
It uses `Concellos.do?DIALOG-EVENT-DeGalicia&provincia={code}`. Per
province this returns only a handful of concellos -- big cities mostly,
but not exclusively (Lugo province includes Cervo, Xove, and Lourenza,
small towns, alongside Lugo city). This isn't a bug or a truncated
response -- confirmed against the tool's own combo-population JS, not
guessed. Xunta-wide totals: 11 concellos, 38 concello x ensinanza combos.

A session is required: CargarAreaInfluenciaCentro.do?DIALOG-EVENT-inicializa
sets a JSESSIONID cookie, and the search form's action URL embeds it.
"""

import json
import requests

BASE_URL = "https://www.edu.xunta.gal/centroseducativos"
HEADERS = {"User-Agent": "Mozilla/5.0"}

PROVINCIAS = [
    ("15", "Coruña (A)"),
    ("27", "Lugo"),
    ("32", "Ourense"),
    ("36", "Pontevedra"),
]

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

    enumeration = []
    for provincia_codigo, provincia_nome in PROVINCIAS:
        concellos = fetch_concellos(s, provincia_codigo)
        for c in concellos:
            concello_codigo = str(c["codigo"])
            ensinanzas = fetch_ensinanzas(s, provincia_codigo, concello_codigo)
            enumeration.append({
                "provincia_codigo": provincia_codigo,
                "provincia_nome": provincia_nome,
                "concello_codigo": concello_codigo,
                "concello_nome": c["valor"],
                "ensinanzas": [{"codigo": str(e["codigo"]), "nome": e["valor"]} for e in ensinanzas],
            })

    with open(f"{RAW_DIR}/enumeration.json", "w", encoding="utf-8") as f:
        json.dump(enumeration, f, ensure_ascii=False, indent=2)
    with open(f"{DATA_DIR}/enumeration.json", "w", encoding="utf-8") as f:
        json.dump(enumeration, f, ensure_ascii=False, indent=2)

    total_combos = sum(len(c["ensinanzas"]) for c in enumeration)
    print(f"Concellos in scope for area de influencia, Xunta-wide: {len(enumeration)}")
    for c in enumeration:
        names = ", ".join(e["nome"] for e in c["ensinanzas"])
        print(f"  {c['provincia_codigo']}/{c['concello_codigo']}  "
              f"{c['concello_nome']:30s} ({c['provincia_nome']}) ensinanzas: {names}")
    print(f"\nTotal concello x ensinanza combos to sweep: {total_combos}")


if __name__ == "__main__":
    main()
