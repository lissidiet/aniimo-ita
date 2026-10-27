"""Revisione della traduzione con un modello piu' forte, guidata da un glossario.

  python revisione.py glossario [--modello opus|sonnet]  -> dati/glossario.json (modificabile a mano)
  python revisione.py prova --modello opus|sonnet        -> 40 frasi: prima / dopo, costo stimato
  python revisione.py stima --modello opus|sonnet        -> costo stimato della revisione completa
  python revisione.py completa --modello opus|sonnet     -> batch su tutto il gioco, aspetta e applica

La revisione restituisce solo le frasi da correggere. Ogni correzione viene controllata:
segnaposto identici e, per i testi con poco spazio, lunghezza entro il limite.
"""
import argparse
import json
import re
import sys
import time
from collections import Counter

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

import accorcia
import comune
import traduci

MODELLI = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5"}
# $ per milione di token (input, output), prezzi pieni; il batch costa la meta'.
PREZZI = {"opus": (4.0, 20.0), "sonnet": (2.0, 10.0)}
VOCI_PER_RICHIESTA = 150
STATO = comune.DATI / "revisione_batch.json"
REGISTRO = comune.DATI / "revisione_modifiche.json"   # {inglese: [prima, dopo]} per rileggere le correzioni

REGOLE = """Sei un revisore esperto di localizzazione di videogiochi, madrelingua italiano.
Il gioco è un open world per tutte le età in cui si catturano e allevano creature chiamate Aniimo.
Ricevi voci con il testo inglese originale ("en") e una traduzione italiana automatica ("it").
Il tuo compito: correggere la traduzione dove serve, perché suoni come un gioco localizzato
professionalmente in Italia.

Correggi:
- errori di grammatica, concordanze, articoli, preposizioni, accenti, punteggiatura italiana;
- calchi dall'inglese e scelte lessicali innaturali o sbagliate nel contesto di un videogioco;
- tono: amichevole e vivace, dai del "tu" al giocatore; dialoghi naturali e coerenti col personaggio;
- interfaccia: concisa, verbi all'imperativo o all'infinito in modo coerente con la convenzione italiana
  (pulsanti: "Conferma", "Annulla", "Riscuoti");
- coerenza con il GLOSSARIO qui sotto: usa sempre quei termini.

Non cambiare:
- segnaposto e tag: {0}, {param1}, %s, %d, <style=...>, </style>, <link=...>, <u>, <customRichText(...)>,
  codici colore #rrggbb, marcatori #kHud #z, gli a capo (\\n): stessi e nello stesso numero;
- nomi propri inventati (Aniimo, personaggi, luoghi) se non sono nel glossario;
- il significato dell'originale inglese.

Se una voce ha "max", la correzione deve stare in quel numero di byte UTF-8 (lettere accentate = 2 byte).
Restituisci SOLO le voci da modificare, con lo stesso "id". Se una traduzione è già corretta e naturale,
non includerla. Non riscrivere per gusto personale: cambia quando migliora davvero."""


def regole_con_glossario() -> str:
    gl = comune.carica(comune.GLOSSARIO, {})
    righe = "\n".join(f"{en} = {it}" for en, it in sorted(gl.items()))
    return f"{REGOLE}\n\nGLOSSARIO (inglese = italiano):\n{righe}"


# --- glossario -------------------------------------------------------------------------

def candidati_glossario(n: int = 500) -> list[str]:
    """Termini ricorrenti: sequenze di 1-3 parole con iniziale maiuscola che compaiono spesso
    dentro altre frasi e che esistono anche come testo a se' (nome di oggetto, meccanica, luogo)."""
    en = comune.carica(comune.EN_JSON)["testi"]
    unici = set(en.values())
    pulito = [re.sub(r"<[^>]*>|\{[^}]*\}|#\w+", " ", s) for s in unici]
    conta = Counter()
    # Solo a meta' frase (dopo una parola minuscola): esclude le maiuscole di inizio frase.
    rx = re.compile(r"(?<=[a-z,] )[A-Z][a-z’']+(?: (?:of |the )?[A-Z][a-z’']+){0,2}\b")
    for s in pulito:
        for m in set(rx.findall(s)):
            conta[m] += 1
    return [t for t, c in conta.most_common(4000) if t in unici and c >= 4][:n]


def glossario(modello: str):
    memoria = comune.carica_memoria()
    termini = candidati_glossario()
    voci = [{"id": str(i), "en": t, "it": memoria.get(t, "")} for i, t in enumerate(termini)]
    client = anthropic.Anthropic()
    istruzioni = (REGOLE.split("Correggi:")[0] +
                  "Ora devi fissare il GLOSSARIO: per ogni termine ricorrente scegli la traduzione italiana "
                  "migliore e definitiva (oggetti, meccaniche, statistiche, interfaccia). I nomi propri di "
                  "creature, personaggi e luoghi inventati restano in inglese, salvo nomi chiaramente "
                  "descrittivi (es. 'Home Coin' -> 'Moneta Casa'). Restituisci TUTTE le voci.")
    with client.messages.stream(
        model=MODELLI[modello], max_tokens=64000, system=istruzioni,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": traduci.SCHEMA}},
        messages=[{"role": "user", "content": json.dumps(voci, ensure_ascii=False)}],
    ) as stream:
        msg = stream.get_final_message()
    testo = next(b.text for b in msg.content if b.type == "text")
    gl = {termini[int(v["id"])]: v["it"] for v in json.loads(testo)["t"]}
    comune.salva(comune.GLOSSARIO, gl)
    print(f"Glossario: {len(gl)} termini -> {comune.GLOSSARIO}")


# --- revisione -------------------------------------------------------------------------

def voci_da_rivedere() -> list[dict]:
    """Una voce per testo inglese: la traduzione lunga e, se esiste, quella corta con il suo limite."""
    memoria = comune.carica_memoria()
    corte = comune.carica(comune.MEMORIA_CORTA, {})
    limiti = accorcia.limiti_per_testo()
    en = sorted({s for s in comune.carica(comune.EN_JSON)["testi"].values() if s in memoria})
    voci = []
    for s in en:
        voci.append({"en": s, "it": memoria[s], "tipo": "lunga"})
        if s in corte and s in limiti:
            voci.append({"en": s, "it": corte[s], "tipo": "corta", "max": limiti[s]})
    return voci


def gruppi(voci):
    for i in range(0, len(voci), VOCI_PER_RICHIESTA):
        yield voci[i:i + VOCI_PER_RICHIESTA]


def params(modello: str, gruppo: list[dict]) -> dict:
    righe = [{"id": str(i), "en": v["en"], "it": v["it"], **({"max": v["max"]} if "max" in v else {})}
             for i, v in enumerate(gruppo)]
    return dict(
        model=MODELLI[modello], max_tokens=16000,
        system=[{"type": "text", "text": regole_con_glossario(), "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": traduci.SCHEMA}},
        messages=[{"role": "user", "content": "Rivedi queste voci:\n" + json.dumps(righe, ensure_ascii=False)}],
    )


def valide(gruppo: list[dict], testo: str) -> list[tuple[dict, str]]:
    risposte = {v["id"]: v["it"] for v in json.loads(testo).get("t", [])}
    ok = []
    for i, v in enumerate(gruppo):
        nuovo = risposte.get(str(i))
        if not nuovo or nuovo == v["it"]:
            continue
        if comune.segnaposto(nuovo) != comune.segnaposto(v["en"]):
            continue
        if "max" in v and len(nuovo.encode()) > v["max"]:
            continue
        ok.append((v, nuovo))
    return ok


def applica(correzioni: list[tuple[dict, str]]):
    memoria = comune.carica_memoria()
    corte = comune.carica(comune.MEMORIA_CORTA, {})
    registro = comune.carica(REGISTRO, {})
    for v, nuovo in correzioni:
        (corte if v["tipo"] == "corta" else memoria)[v["en"]] = nuovo
        registro[v["en"] + (" [corta]" if v["tipo"] == "corta" else "")] = [v["it"], nuovo]
    comune.salva(comune.MEMORIA, memoria)
    comune.salva(comune.MEMORIA_CORTA, corte)
    comune.salva(REGISTRO, registro)


def testo_risposta(msg) -> str | None:
    if msg.stop_reason != "end_turn":
        return None
    return next((b.text for b in msg.content if b.type == "text"), None)


def prova(modello: str):
    voci = voci_da_rivedere()
    campione = voci[:: max(1, len(voci) // VOCI_PER_RICHIESTA)][:VOCI_PER_RICHIESTA]
    msg = anthropic.Anthropic().messages.create(**params(modello, campione))
    testo = testo_risposta(msg)
    corr = valide(campione, testo) if testo else []
    for v, nuovo in corr:
        print(f"EN:   {v['en']!r}\nPRIMA {v['it']!r}\nDOPO  {nuovo!r}\n")
    u = msg.usage
    pin, pout = PREZZI[modello]
    costo = ((u.input_tokens + (u.cache_creation_input_tokens or 0) * 1.25
              + (u.cache_read_input_tokens or 0) * 0.1) * pin + u.output_tokens * pout) / 1e6
    print(f"{modello}: {len(corr)}/{len(campione)} corrette | costo prova ${costo:.3f} "
          f"| stima tutto il gioco (batch) ~${costo * len(voci) / len(campione) * 0.5:.0f}")


def completa(modello: str):
    client = anthropic.Anthropic()
    voci = voci_da_rivedere()
    gs = list(gruppi(voci))
    if not STATO.exists():
        reqs = [Request(custom_id=f"r{n}", params=MessageCreateParamsNonStreaming(**params(modello, g)))
                for n, g in enumerate(gs)]
        batch = client.messages.batches.create(requests=reqs)
        comune.salva(STATO, {"id": batch.id, "modello": modello})
        print(f"Batch di revisione creato: {batch.id} ({len(reqs)} richieste).")
    bid = comune.carica(STATO)["id"]
    while (b := client.messages.batches.retrieve(bid)).processing_status != "ended":
        c = b.request_counts
        print(f"  in corso: {c.succeeded + c.errored}/{len(gs)} completate", flush=True)
        time.sleep(120)
    correzioni, falliti = [], 0
    for r in client.messages.batches.results(bid):
        testo = testo_risposta(r.result.message) if r.result.type == "succeeded" else None
        if testo is None:
            falliti += 1
            continue
        try:
            correzioni += valide(gs[int(r.custom_id[1:])], testo)
        except (json.JSONDecodeError, KeyError):
            falliti += 1
    applica(correzioni)
    STATO.unlink()
    print(f"Correzioni applicate: {len(correzioni)} | richieste fallite: {falliti}")
    print(f"Elenco prima/dopo: {REGISTRO}")
    print("Ora chiudi il gioco e lancia 'Aniimo Italiano' per installare.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("azione", choices=["glossario", "prova", "stima", "completa"])
    ap.add_argument("--modello", choices=list(MODELLI), default="opus")
    a = ap.parse_args()
    if not comune.carica_chiave_api():
        sys.exit("Manca ANTHROPIC_API_KEY.")
    if a.azione == "stima":
        voci = voci_da_rivedere()
        print(f"{len(voci)} voci, {len(list(gruppi(voci)))} richieste. Per il costo usa 'prova'.")
    else:
        {"glossario": glossario, "prova": prova, "completa": completa}[a.azione](a.modello)
