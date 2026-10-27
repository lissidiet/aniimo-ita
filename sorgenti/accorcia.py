"""Recupera i testi rimasti fuori dalla patch.

1. Testi senza traduzione (es. scartati per segnaposto): ritradotti, con un secondo tentativo.
2. Testi la cui traduzione non entra nello spazio dello slot: Claude ne scrive una versione
   piu' corta entro il limite di byte, salvata in dati/memoria_corta.json.

Uso:  python accorcia.py
"""
import json
import sys
from collections import defaultdict

import anthropic

import applica_lotto
import comune
import crea_patch
import traduci

ISTRUZIONI_CORTE = traduci.ISTRUZIONI + """
Questa volta ogni voce ha un limite di spazio "max" in byte UTF-8 (lettere accentate = 2 byte).
Scrivi una versione italiana PIU' CORTA che stia nel limite: abbrevia, togli parole superflue,
usa sinonimi brevi; per l'interfaccia vanno bene abbreviazioni chiare (es. "Impost.").
Il significato deve restare lo stesso. Segnaposto e tag restano identici."""


def limiti_per_testo() -> dict[str, int]:
    """{testo inglese: byte disponibili} per i testi la cui traduzione non entra."""
    with crea_patch.zipfile.ZipFile(comune.XDF) as z:
        mappa = json.loads(z.read(f"{comune.I18N_ZIP}NewTextMap_{crea_patch.SLOT}.json"))
    mappa.pop("_version"), mappa.pop("_count", None)
    en = comune.carica(comune.EN_JSON)["testi"]
    memoria = comune.carica_memoria()
    limiti = {}
    for k, (_, n) in mappa.items():
        s = en.get(k)
        it = memoria.get(s)
        if it is not None and len(it.encode()) > n:
            limiti[s] = min(n, limiti.get(s, n))
    return limiti


def accorcia(limiti: dict[str, int], corte: dict[str, str]) -> int:
    client = anthropic.Anthropic()
    memoria = comune.carica_memoria()
    da_fare = [s for s in limiti if s not in corte]
    nuove = 0
    for tentativo in range(2):
        gruppi = [da_fare[i:i + 60] for i in range(0, len(da_fare), 60)]
        rimasti = []

        def una(gruppo):
            voci = [{"id": str(i), "en": s, "it_attuale": memoria[s], "max": limiti[s]}
                    for i, s in enumerate(gruppo)]
            msg = client.messages.create(
                model=traduci.MODELLO, max_tokens=16000, system=ISTRUZIONI_CORTE,
                output_config={"effort": "low",
                               "format": {"type": "json_schema", "schema": traduci.SCHEMA}},
                messages=[{"role": "user", "content": "Accorcia queste traduzioni:\n"
                           + json.dumps(voci, ensure_ascii=False)}])
            testo = next((b.text for b in msg.content if b.type == "text"), "{}")
            return gruppo, {int(v["id"]): v["it"] for v in json.loads(testo).get("t", [])}

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(6) as pool:
            for fut in [pool.submit(una, g) for g in gruppi]:
                try:
                    gruppo, risposte = fut.result()
                except (anthropic.APIError, json.JSONDecodeError):
                    continue
                for i, s in enumerate(gruppo):
                    it = risposte.get(i)
                    if (it and len(it.encode()) <= limiti[s]
                            and comune.segnaposto(it) == comune.segnaposto(s)):
                        corte[s] = it
                        nuove += 1
                    else:
                        rimasti.append(s)
        da_fare = rimasti
        if not da_fare:
            break
    comune.salva(comune.MEMORIA_CORTA, corte)
    return nuove


def mancanti() -> int:
    en = {s for s in comune.carica(comune.EN_JSON)["testi"].values() if s.strip()}
    memoria = comune.carica_memoria()
    prima = len(memoria)
    for _ in range(2):
        nuovi = sorted(en - memoria.keys())
        if not nuovi:
            break
        tradotte, _ = traduci.traduci_subito(nuovi)
        applica_lotto.aggiungi(memoria, tradotte)
    comune.salva(comune.MEMORIA, memoria)
    return len(memoria) - prima


def esegui() -> None:
    if not comune.carica_chiave_api():
        print("Nessuna chiave API: salto il recupero dei testi mancanti.")
        return
    print(f"Testi senza traduzione recuperati: {mancanti()}")
    corte = comune.carica(comune.MEMORIA_CORTA, {})
    limiti = limiti_per_testo()
    da_fare = sum(s not in corte for s in limiti)
    print(f"Traduzioni troppo lunghe: {len(limiti)} (da accorciare: {da_fare})")
    if da_fare:
        print(f"  Versioni corte create: {accorcia(limiti, corte)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    esegui()
