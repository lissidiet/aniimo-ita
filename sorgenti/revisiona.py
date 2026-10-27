"""Revisione manuale a blocchi (fatta da Claude Code in sessione, senza API).

  python revisiona.py prepara           -> crea la coda di revisione in ordine di priorita'
  python revisiona.py prossimo [N]      -> mostra il blocco successivo (N voci, default 150)
  python revisiona.py applica FILE      -> applica le correzioni {numero: nuovo italiano} del blocco
  python revisiona.py stato             -> avanzamento

Priorita' della coda:
  1. frasi in cui un nome proprio (Aniimo, personaggi, luoghi) e' stato tradotto o storpiato;
  2. interfaccia: testi brevi (<= 40 caratteri), prima quelli usati da piu' id;
  3. tutto il resto (dialoghi, descrizioni, missioni), prima quelli usati da piu' id.
Ogni voce mostra inglese, italiano attuale e, per le versioni corte, il limite in byte.
"""
import json
import re
import sys
from collections import Counter

import accorcia
import comune

CARTELLA = comune.DATI / "revisione"
CODA = CARTELLA / "coda.json"
CORRENTE = CARTELLA / "corrente.json"
FATTI = CARTELLA / "fatti.json"
REGISTRO = CARTELLA / "modifiche.json"   # {chiave: [prima, dopo]}

# Parole del glossario uguali in inglese e italiano che NON sono nomi propri.
NON_NOMI = {"Area", "Set", "Bonus", "Info", "Menu", "Formula", "Max", "Chat", "Arena", "Boss",
            "Top", "Avatar", "Outfit", "Emote", "Omega", "Bloom"}


def chiave(en: str, tipo: str) -> str:
    return en + (" [corta]" if tipo == "corta" else "")


def prepara():
    en_ids = comune.carica(comune.EN_JSON)["testi"]
    uso = Counter(en_ids.values())
    memoria = comune.carica_memoria()
    corte = comune.carica(comune.MEMORIA_CORTA, {})
    limiti = accorcia.limiti_per_testo()
    glossario = comune.carica(comune.GLOSSARIO, {})
    nomi = [k for k, v in glossario.items() if k == v and len(k) > 3 and k not in NON_NOMI]
    rx_nomi = re.compile(r"\b(" + "|".join(map(re.escape, sorted(nomi, key=len, reverse=True))) + r")\b")
    fatti = set(comune.carica(FATTI, []))

    def gruppo(s: str) -> int:
        it = memoria[s]
        if any(n not in it for n in set(rx_nomi.findall(s))):
            return 1
        return 2 if len(s) <= 40 else 3

    voci = []
    for s in memoria:
        if s not in uso:
            continue
        g = gruppo(s)
        voci.append({"en": s, "tipo": "lunga", "g": g})
        if s in corte and s in limiti:
            voci.append({"en": s, "tipo": "corta", "g": g, "max": limiti[s]})
    voci = [v for v in voci if chiave(v["en"], v["tipo"]) not in fatti]
    voci.sort(key=lambda v: (v["g"], -uso[v["en"]], len(v["en"]), v["en"]))
    comune.salva(CODA, voci)
    conta = Counter(v["g"] for v in voci)
    print(f"Coda: {len(voci)} voci da rivedere  |  gruppo 1 (nomi): {conta[1]}  "
          f"gruppo 2 (interfaccia): {conta[2]}  gruppo 3 (resto): {conta[3]}")


def prossimo(n: int = 150):
    coda = comune.carica(CODA, [])
    memoria = comune.carica_memoria()
    corte = comune.carica(comune.MEMORIA_CORTA, {})
    blocco = coda[:n]
    comune.salva(CORRENTE, blocco)
    gl = comune.carica(comune.GLOSSARIO, {})
    for i, v in enumerate(blocco):
        it = (corte if v["tipo"] == "corta" else memoria)[v["en"]]
        extra = f"\tmax={v['max']}" if "max" in v else ""
        print(f"{i}\t{json.dumps(v['en'], ensure_ascii=False)}\t{json.dumps(it, ensure_ascii=False)}{extra}")
    nomi_usati = sorted({k for k, val in gl.items() if k == val and any(k in v["en"] for v in blocco)})
    if nomi_usati:
        print("# nomi propri presenti (restano invariati):", ", ".join(nomi_usati))
    print(f"# blocco di {len(blocco)} voci, gruppo {blocco[0]['g'] if blocco else '-'}; restano {len(coda)} in coda")


def applica(percorso: str, solo_prime: int | None = None):
    """Chiude il blocco corrente (o solo le prime N voci: le altre tornano in testa alla coda)."""
    blocco = comune.carica(CORRENTE, [])[:solo_prime]
    correzioni = comune.carica(comune.Path(percorso), {})
    memoria = comune.carica_memoria()
    corte = comune.carica(comune.MEMORIA_CORTA, {})
    registro = comune.carica(REGISTRO, {})
    fatti = comune.carica(FATTI, [])
    applicate, scartate = 0, []
    for i, v in enumerate(blocco):
        nuovo = correzioni.get(str(i))
        if nuovo is not None:
            dest = corte if v["tipo"] == "corta" else memoria
            if isinstance(nuovo, list):
                # Sostituzioni mirate [[vecchio, nuovo], ...] sul testo attuale (per testi lunghi).
                testo = dest[v["en"]]
                for vecchio, sost in nuovo:
                    if vecchio not in testo:
                        scartate.append((i, f"non trovato: {vecchio!r}"))
                    testo = testo.replace(vecchio, sost)
                nuovo = testo
            if comune.segnaposto(nuovo) != comune.segnaposto(v["en"]):
                scartate.append((i, "segnaposto"))
                continue
            if "max" in v and len(nuovo.encode()) > v["max"]:
                scartate.append((i, f"{len(nuovo.encode())} > {v['max']} byte"))
                continue
            registro[chiave(v["en"], v["tipo"])] = [dest[v["en"]], nuovo]
            dest[v["en"]] = nuovo
            applicate += 1
        fatti.append(chiave(v["en"], v["tipo"]))
    if scartate:
        print("SCARTATE (blocco non chiuso, correggi e riapplica):", scartate)
        return
    comune.salva(comune.MEMORIA, memoria)
    comune.salva(comune.MEMORIA_CORTA, corte)
    comune.salva(REGISTRO, registro)
    comune.salva(FATTI, fatti)
    comune.salva(CODA, comune.carica(CODA, [])[len(blocco):])
    CORRENTE.unlink()
    stato()
    print(f"Blocco chiuso: {applicate} correzioni su {len(blocco)} voci.")


def stato():
    coda = comune.carica(CODA, [])
    fatti = comune.carica(FATTI, [])
    totale = len(coda) + len(fatti)
    conta = Counter(v["g"] for v in coda)
    print(f"Revisionate {len(fatti)}/{totale} ({100 * len(fatti) / max(totale, 1):.1f}%)  |  "
          f"in coda: nomi {conta[1]}, interfaccia {conta[2]}, resto {conta[3]}  |  "
          f"correzioni totali: {len(comune.carica(REGISTRO, {}))}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    azione = sys.argv[1] if len(sys.argv) > 1 else "stato"
    if azione == "prepara":
        prepara()
    elif azione == "prossimo":
        prossimo(int(sys.argv[2]) if len(sys.argv) > 2 else 150)
    elif azione == "applica":
        applica(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
    else:
        stato()
