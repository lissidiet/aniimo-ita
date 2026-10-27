"""Traduzione completa EN -> IT con Claude Haiku 5.5 tramite Message Batches API (meta' prezzo).

Richiede la variabile d'ambiente ANTHROPIC_API_KEY (oppure `ant auth login`).
Flusso:
  python seleziona.py tutto            -> dati/lotti/tutto.json (testi unici non ancora tradotti)
  python traduci.py stima              -> numero richieste e costo stimato
  python traduci.py invia              -> crea il batch, salva l'id in dati/batch.json
  python traduci.py scarica            -> se il batch e' finito, scrive dati/lotti/tutto_it.json
  python applica_lotto.py dati/lotti/tutto_it.json, poi Italiano.ps1 per installare
"""
import json
import sys
import time

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

import comune

MODELLO = "claude-haiku-5-5"
CARATTERI_PER_RICHIESTA = 6000
VOCI_PER_RICHIESTA = 120
LOTTO = comune.DATI / "lotti" / "tutto.json"
USCITA = comune.DATI / "lotti" / "tutto_it.json"
STATO = comune.DATI / "batch.json"

ISTRUZIONI = """Sei un traduttore professionista di videogiochi, dall'inglese all'italiano.
Il gioco è un open world per tutte le età in cui si catturano e allevano creature chiamate Aniimo.
Regole:
- Italiano naturale, tono leggero e amichevole; dai del "tu" al giocatore.
- Interfaccia: testi brevi e chiari (es. "Settings" -> "Impostazioni", "Claim" -> "Riscuoti").
- Non tradurre i nomi propri di Aniimo, personaggi e luoghi inventati (es. Iris, Sunia, Irelia, Bloomville).
- Termini fissi: Aniimo = Aniimo; Bloom (struttura/meccanica) = Fioritura; Pathfinder = Esploratore;
  Sanctum = Santuario; Home = Casa; Quest = Missione; Party = Gruppo; Team = Squadra; NPC = PNG.
- Mantieni IDENTICI e nello stesso numero: segnaposto come {0} {param1} %s, tag come <style=...> </style>,
  codici colore come #d89c28 e marcatori come #kHud #z, e gli a capo.
- Restituisci per ogni voce lo stesso "id" ricevuto."""

SCHEMA = {
    "type": "object",
    "properties": {
        "t": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "it": {"type": "string"}},
                "required": ["id", "it"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["t"],
    "additionalProperties": False,
}


def gruppi(testi: list[str] | None = None):
    if testi is None:
        testi = [x["en"] for x in comune.carica(LOTTO)]
    gruppo, n = [], 0
    for i, s in enumerate(testi):
        if gruppo and (n + len(s) > CARATTERI_PER_RICHIESTA or len(gruppo) >= VOCI_PER_RICHIESTA):
            yield gruppo
            gruppo, n = [], 0
        gruppo.append((str(i), s))
        n += len(s)
    if gruppo:
        yield gruppo


def richiesta(num: int, gruppo) -> Request:
    voci = json.dumps([{"id": i, "en": s} for i, s in gruppo], ensure_ascii=False)
    return Request(
        custom_id=f"g{num}",
        params=MessageCreateParamsNonStreaming(
            model=MODELLO,
            max_tokens=16000,
            system=ISTRUZIONI,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": f"Traduci queste voci:\n{voci}"}],
        ),
    )


def traduci_subito(testi: list[str], paralleli: int = 6) -> tuple[dict[str, str], int]:
    """Traduzione immediata (senza batch) per pochi testi, es. dopo un aggiornamento del gioco.

    Restituisce ({inglese: italiano}, numero di richieste fallite).
    """
    from concurrent.futures import ThreadPoolExecutor

    client = anthropic.Anthropic()

    def una(gruppo):
        params = richiesta(0, gruppo)["params"]
        msg = client.messages.create(**params)
        if msg.stop_reason != "end_turn":
            return {}
        testo = next((b.text for b in msg.content if b.type == "text"), "")
        voci = {i: s for i, s in gruppo}
        return {voci[v["id"]]: v["it"] for v in json.loads(testo)["t"] if v["id"] in voci}

    risultato, falliti = {}, 0
    with ThreadPoolExecutor(paralleli) as pool:
        for fut in [pool.submit(una, g) for g in gruppi(testi)]:
            try:
                risultato.update(fut.result())
            except (anthropic.APIError, json.JSONDecodeError, KeyError):
                falliti += 1
    return risultato, falliti


def stima():
    gs = list(gruppi())
    car = sum(len(s) for g in gs for _, s in g)
    tok_in = car / 3.5 + len(gs) * 500
    tok_out = car / 3.0
    # Haiku 5.5: $0.10 / $0.50 per milione di token; Batch API -50%.
    costo = (tok_in * 0.10 + tok_out * 0.50) / 1e6 * 0.5
    print(f"{len(gs)} richieste, {car} caratteri, costo stimato ~${costo:.2f}")


def invia():
    client = anthropic.Anthropic()
    reqs = [richiesta(n, g) for n, g in enumerate(gruppi())]
    batch = client.messages.batches.create(requests=reqs)
    comune.salva(STATO, {"id": batch.id})
    print(f"Batch creato: {batch.id} ({len(reqs)} richieste). Di solito finisce entro un'ora.")


def scarica():
    client = anthropic.Anthropic()
    bid = comune.carica(STATO)["id"]
    batch = client.messages.batches.retrieve(bid)
    if batch.processing_status != "ended":
        c = batch.request_counts
        print(f"Ancora in corso: {c.processing} in elaborazione, {c.succeeded} completate.")
        return
    testi = [x["en"] for x in comune.carica(LOTTO)]
    risultato, falliti = comune.carica(USCITA, {}), []
    for r in client.messages.batches.results(bid):
        if r.result.type != "succeeded":
            falliti.append(r.custom_id)
            continue
        msg = r.result.message
        if msg.stop_reason != "end_turn":
            falliti.append(r.custom_id)
            continue
        testo = next((b.text for b in msg.content if b.type == "text"), "")
        for voce in json.loads(testo)["t"]:
            i = int(voce["id"])
            if 0 <= i < len(testi):
                risultato[testi[i]] = voce["it"]
    comune.salva(USCITA, risultato)
    print(f"Traduzioni salvate: {len(risultato)} -> {USCITA}")
    if falliti:
        print(f"Richieste fallite ({len(falliti)}): rilancia seleziona.py tutto + invia per riprovare.")


def completa():
    """Invia il batch (se non gia' inviato), aspetta la fine, scarica e aggiorna la memoria."""
    client = anthropic.Anthropic()
    if not STATO.exists():
        invia()
    bid = comune.carica(STATO)["id"]
    while client.messages.batches.retrieve(bid).processing_status != "ended":
        time.sleep(60)
    scarica()
    import applica_lotto
    memoria = comune.carica_memoria()
    scartati = applica_lotto.aggiungi(memoria, comune.carica(USCITA, {}))
    comune.salva(comune.MEMORIA, memoria)
    print(f"Memoria: {len(memoria)} testi; scartati per segnaposto: {len(scartati)}")
    STATO.unlink()


def pilota():
    """Prova su 40 testi presi qua e la' dal lotto, senza batch: controlla modello, formato e segnaposto."""
    testi = [x["en"] for x in comune.carica(LOTTO)]
    campione = testi[:: max(1, len(testi) // 40)][:40]
    tradotte, falliti = traduci_subito(campione)
    for s in campione:
        it = tradotte.get(s, "<<MANCANTE>>")
        ok = "" if comune.segnaposto(s) == comune.segnaposto(it) else "  !! SEGNAPOSTO"
        print(f"{s!r}\n   -> {it!r}{ok}")
    print(f"\n{len(tradotte)}/{len(campione)} tradotte, richieste fallite: {falliti}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if not comune.carica_chiave_api():
        sys.exit("Manca ANTHROPIC_API_KEY.")
    {"stima": stima, "invia": invia, "scarica": scarica, "pilota": pilota, "completa": completa}[sys.argv[1] if len(sys.argv) > 1 else "stima"]()
