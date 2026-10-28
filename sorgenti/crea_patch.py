"""Costruisce il file di testo italiano dentro lo "slot" di una lingua esistente.

Il gioco legge i testi da Compress_<lingua>.bin usando una mappa id -> [offset, lunghezza]
che sta in un archivio con checksum: la mappa NON si tocca. Si riscrive solo il contenuto
di ogni span, con la stessa lunghezza in byte, riempiendo lo spazio avanzato.
Lo slot russo e' il piu' capiente tra quelli con alfabeto compatibile (cirillico = 2 byte
per lettera), quindi quasi tutto l'italiano ci sta.

Si parte sempre dalla copia originale dentro LuaScripts.xdf (mai dal file sciolto, che
potrebbe essere una patch vecchia).

Per ogni span:  italiano se c'e' e ci sta  ->  altrimenti inglese se ci sta  ->  altrimenti originale.

Uso:  python crea_patch.py [--slot ru_RU] [--riempi spazi|zwsp] [--verifica]
Output: dati/patch/Compress_<slot>.bin (stessa dimensione dell'originale).
"""
import argparse
import json
import sys
import zipfile
from collections import defaultdict

import comune

SLOT = "ru_RU"
ZWSP = "​".encode()  # zero width space, 3 byte


def riempimento(n: int, modo: str) -> bytes:
    if modo == "zwsp":
        return ZWSP * (n // 3) + b" " * (n % 3)
    return b" " * n


def originale(slot: str = SLOT) -> bytes:
    with zipfile.ZipFile(comune.XDF) as z:
        return z.read(f"{comune.I18N_ZIP}Compress_{slot}.bin")


def costruisci(slot: str = SLOT, modo: str = "spazi", solo_originale: bool = False):
    blob = bytearray(originale(slot))
    with zipfile.ZipFile(comune.XDF) as z:
        mappa = json.loads(z.read(f"{comune.I18N_ZIP}NewTextMap_{slot}.json"))
    mappa.pop("_version"), mappa.pop("_count", None)

    en = comune.carica(comune.EN_JSON)["testi"]
    memoria = {} if solo_originale else comune.carica_memoria()
    corte = {} if solo_originale else comune.carica_memoria_corta()

    span = defaultdict(list)
    for k, (o, n) in mappa.items():
        span[(o, n)].append(k)

    stat = defaultdict(int)
    for (o, n), ids in span.items():
        scelta = None
        if not solo_originale:
            candidati = [(memoria.get(en.get(k)), "italiano") for k in ids]
            candidati += [(corte.get(en.get(k)), "italiano corto") for k in ids]
            candidati += [(en.get(k), "inglese") for k in ids]
            for testo, nome in candidati:
                if testo is None:
                    continue
                b = testo.encode("utf-8")
                if len(b) <= n:
                    scelta = (b, nome)
                    break
                stat[f"{nome} troppo lungo"] += 1
        if scelta is None:
            stat["originale"] += 1
            continue
        b, nome = scelta
        blob[o:o + n] = b + riempimento(n - len(b), modo)
        stat[nome] += 1

    return bytes(blob), dict(stat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default=SLOT)
    ap.add_argument("--riempi", default="spazi", choices=["spazi", "zwsp"])
    ap.add_argument("--verifica", action="store_true",
                    help="ricostruisce senza traduzioni e controlla che il file sia identico")
    a = ap.parse_args()

    if a.verifica:
        blob, _ = costruisci(a.slot, a.riempi, solo_originale=True)
        ok = blob == originale(a.slot)
        print("Verifica ricostruzione:", "OK, identico byte per byte" if ok else "ERRORE")
        sys.exit(0 if ok else 1)

    blob, stat = costruisci(a.slot, a.riempi)
    out = comune.DATI / "patch" / f"Compress_{a.slot}.bin"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    print(f"Patch scritta: {out}")
    for k, v in sorted(stat.items()):
        print(f"  span {k}: {v}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
