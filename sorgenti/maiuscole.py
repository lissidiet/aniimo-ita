"""Toglie le maiuscole "all'inglese" dai titoli brevi: "Ultima Resistenza" -> "Ultima resistenza".

In italiano solo la prima parola di un titolo ha la maiuscola, salvo nomi propri e termini del gioco.
Per capire se una parola e' comune si guarda come compare dentro le frasi lunghe della traduzione:
se a meta' frase e' quasi sempre minuscola ("resistenza") e' una parola comune; se e' spesso maiuscola
("Casa", "Fioritura", "Helmut") e' un nome o un termine del gioco e resta com'e'.

Uso:  python maiuscole.py            -> prova, mostra esempi
      python maiuscole.py applica    -> applica
"""
import re
import sys
from collections import Counter

import comune
import regole

# Termini del gioco che restano maiuscoli anche se a volte compaiono minuscoli nelle frasi
PROTETTE = {"Casa", "Terra", "Fioritura", "Intreccio", "Suprema", "Esploratore", "Alfa", "Omega", "Santuario",
            "Monete", "Addestramento", "Scintille", "Viaggio", "Leggendario", "Furto", "Uova", "Olo-Battaglia",
            "Simulatore", "Istituto", "Approdo", "Boschi", "Nebbiosi", "Costa", "Stretto", "Cresta", "Altopiani",
            "Fuoco", "Acqua", "Erba", "Vento", "Luce", "Oscurità", "Fulmine", "Ghiaccio", "Spirito", "Polvere",
            "Cronache", "Cronaca", "Vena", "Ramo", "Fenditura", "Festa", "Rugiada", "Luna", "Studente", "Viandante"}
# Non dopo trattino o punto ("Olo-Battaglia", "...Rapporto"); dopo l'apostrofo si' ("d'Oro" -> "d'oro").
PAROLA = re.compile(r"(?<![\w.-])([A-ZÀ-Ý][a-zà-ÿ]+)\b")
TITOLO_EN = re.compile(r"^[A-Z0-9][\w’'.-]*(?: (?:[A-Z0-9][\w’'.-]*|of|the|and|in|on|to|for|a|an|at|with|by|from))+$")


def parole_comuni(memoria: dict) -> set:
    """Parole che a meta' delle frasi lunghe compaiono quasi sempre minuscole."""
    maiu, minu = Counter(), Counter()
    for it in memoria.values():
        if len(it.split()) < 8:
            continue
        for frase in re.split(r"[.!?:\n]\s*", it):
            parole = frase.split()
            for p in parole[1:]:
                p = p.strip("\"“”«»(),;—-…")
                if re.fullmatch(r"[A-ZÀ-Ý][a-zà-ÿ]+", p):
                    maiu[p] += 1
                elif re.fullmatch(r"[a-zà-ÿ]+", p):
                    minu[p] += 1
    comuni = {p.capitalize() for p, n in minu.items() if n >= 3 and n >= 4 * maiu[p.capitalize()]}
    propri = {p for p, n in maiu.items() if n >= 3 and n >= minu[p.lower()]}
    return comuni, propri


def correggi(en: str, it: str, comuni: set, noti: set):
    if not TITOLO_EN.match(en) or len(en.split()) > 6 or "<" in it:
        return None
    # i nomi costruiti da uno schema in regole.py hanno gia' la forma voluta
    if regole.nome_coltura(en) or any(rx.match(en) for rx, _ in regole.MODELLI):
        return None
    # ogni pezzo dopo ":" o " - " e' un titolo a se', con la sua prima maiuscola
    # Se una parola maiuscola non e' ne' comune ne' un nome noto, meglio non toccare il titolo:
    # cambiare solo meta' delle parole darebbe un risultato misto ("Distintivo onde Squarcianti").
    for pezzo in re.split(r": | - |\(|\.\.\.", it):
        for p in PAROLA.findall(pezzo)[1:]:
            if p not in comuni and p not in noti:
                return None
    pezzi = re.split(r"(: | - |\(|\.\.\.)", it)
    out = []
    for pezzo in pezzi:
        primo = [True]

        def sost(m):
            p = m.group(1)
            if primo[0]:
                primo[0] = False
                return p
            return p.lower() if p in comuni and p not in PROTETTE else p
        out.append(PAROLA.sub(sost, pezzo))
    nuovo = "".join(out)
    return nuovo if nuovo != it else None


def esegui(applica: bool):
    memoria = comune.carica_memoria()
    corte = comune.carica(comune.MEMORIA_CORTA, {})
    comuni, propri = parole_comuni(memoria)
    gl = comune.carica(comune.GLOSSARIO, {})
    noti = propri | PROTETTE | {w for k, v in gl.items() if k == v for w in v.split()}
    n, esempi = 0, []
    for dest in (memoria, corte):
        for en, it in list(dest.items()):
            nuovo = correggi(en, it, comuni, noti)
            if nuovo:
                dest[en] = nuovo
                n += 1
                if len(esempi) < 60:
                    esempi.append(f"{it!r} -> {nuovo!r}")
    print("\n".join(esempi))
    print(f"\nTitoli corretti: {n}" + ("" if applica else " (prova, niente salvato)"))
    if applica:
        comune.salva(comune.MEMORIA, memoria)
        comune.salva(comune.MEMORIA_CORTA, corte)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    esegui(len(sys.argv) > 1 and sys.argv[1] == "applica")
