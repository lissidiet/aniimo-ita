"""Unisce uno o piu' file di traduzione {inglese: italiano} nella memoria (dati/memoria.json).

Le traduzioni che perdono o aggiungono segnaposto ({0}, <style>, #colore, \\n ...) vengono scartate.

Uso:  python applica_lotto.py dati/lotti/iniziale_it_1.json [altri file...]
"""
import sys

import comune


def aggiungi(memoria: dict, traduzioni: dict) -> list[tuple[str, str]]:
    """Aggiunge alla memoria; restituisce le coppie scartate."""
    scartati = []
    for s_en, s_it in traduzioni.items():
        if comune.segnaposto(s_en) != comune.segnaposto(s_it):
            scartati.append((s_en, s_it))
        else:
            memoria[s_en] = s_it
    return scartati


def main(percorsi: list[str]):
    memoria = comune.carica_memoria()
    prima = len(memoria)
    scartati = []
    for p in percorsi:
        scartati += aggiungi(memoria, comune.carica(comune.Path(p)))
    comune.salva(comune.MEMORIA, memoria)
    en = set(comune.carica(comune.EN_JSON)["testi"].values())
    print(f"Memoria: {prima} -> {len(memoria)} testi  |  testi del gioco coperti: "
          f"{len(en & memoria.keys())} / {len(en)}")
    for a, b in scartati:
        print("  segnaposto diversi, scartato:", repr(a), "->", repr(b))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
