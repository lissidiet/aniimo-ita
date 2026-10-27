"""Estrae i testi inglesi del gioco in dati/en.json (sola lettura dei file del gioco)."""
import sys
import comune


def main():
    versione, testi = comune.leggi_lingua("en")
    comune.salva(comune.EN_JSON, {"_version": versione, "testi": testi})
    unici = len(set(testi.values()))
    print(f"Versione testi {versione}: {len(testi)} id, {unici} testi unici -> {comune.EN_JSON}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
