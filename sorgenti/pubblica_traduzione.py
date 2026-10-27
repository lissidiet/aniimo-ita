"""Carica su Supabase la traduzione attuale, da cui AniimoITA.exe scarica gli aggiornamenti.

Serve una sola volta per ogni nuova versione della traduzione (es. dopo un giro di revisione).
Legge dal PC (mai da file del repository):
  SUPABASE_URL          es. https://xxxx.supabase.co   (anche in dati/supabase_url.txt)
  SUPABASE_SERVICE_KEY  chiave service_role, solo nelle variabili utente di Windows

Nel contenitore pubblico "aniimo-ita" mette:
  versione.json                         {versione, data, frasi, file: {nome: sha256}}
  memoria.json.gz, memoria_corta.json.gz, glossario.json.gz

Ogni pubblicazione ha un numero di versione (dati/versione_patch.txt): senza argomenti l'ultima cifra
sale di uno (1.0.0 -> 1.0.1); con un argomento si sceglie il numero (es. 1.1.0).

Uso:  python pubblica_traduzione.py [versione]
"""
import gzip
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

import comune

CONTENITORE = "aniimo-ita"
FILE = ("memoria.json", "memoria_corta.json", "glossario.json")


def variabile(nome: str) -> str:
    if os.environ.get(nome):
        return os.environ[nome]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, nome)[0]
    except OSError:
        return ""


def chiama(metodo: str, url: str, chiave: str, corpo: bytes | None = None, tipo: str = "application/json",
           extra: dict | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=corpo, method=metodo, headers={
        "Authorization": f"Bearer {chiave}", "apikey": chiave, "Content-Type": tipo, **(extra or {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def online_versione(url: str) -> str:
    try:
        with urllib.request.urlopen(f"{url}/storage/v1/object/public/{CONTENITORE}/versione.json", timeout=15) as r:
            return json.loads(r.read())["versione"]
    except Exception:
        return ""


def main():
    url = variabile("SUPABASE_URL")
    file_url = comune.DATI / "supabase_url.txt"
    if not url and file_url.exists():
        url = file_url.read_text(encoding="utf-8").strip()
    chiave = variabile("SUPABASE_SERVICE_KEY")
    if not url or not chiave:
        sys.exit("Mancano SUPABASE_URL (o dati/supabase_url.txt) e/o SUPABASE_SERVICE_KEY.")
    url = url.rstrip("/")

    # contenitore pubblico (se esiste gia' va bene lo stesso)
    stato, risposta = chiama("POST", f"{url}/storage/v1/bucket", chiave,
                             json.dumps({"id": CONTENITORE, "name": CONTENITORE, "public": True}).encode())
    if stato not in (200, 201) and b"already exists" not in risposta and b"Duplicate" not in risposta:
        sys.exit(f"Errore nel creare il contenitore: {stato} {risposta[:200]!r}")

    file_versione = comune.DATI / "versione_patch.txt"
    if len(sys.argv) > 1:
        versione = sys.argv[1].lstrip("v")
    else:  # la versione gia' pubblicata e' quella nel file: la prossima sale di uno
        pubblicata = online_versione(url)
        parti = [int(x) for x in file_versione.read_text(encoding="utf-8").strip().split(".")]
        if pubblicata == ".".join(map(str, parti)):
            parti[-1] += 1
        versione = ".".join(map(str, parti))
    impronte = {}
    for nome in FILE:
        dati = gzip.compress((comune.DATI / nome).read_bytes(), 9)
        impronte[nome] = hashlib.sha256(dati).hexdigest()
        stato, risposta = chiama("POST", f"{url}/storage/v1/object/{CONTENITORE}/{nome}.gz", chiave, dati,
                                 "application/gzip", {"x-upsert": "true", "cache-control": "max-age=60"})
        if stato not in (200, 201):
            sys.exit(f"Errore nel caricare {nome}: {stato} {risposta[:200]!r}")
        print(f"  caricato {nome}.gz ({len(dati) // 1024} KB)")

    info = {"versione": versione, "data": datetime.now().strftime("%d/%m/%Y"),
            "frasi": len(comune.carica_memoria()), "file": impronte}
    stato, risposta = chiama("POST", f"{url}/storage/v1/object/{CONTENITORE}/versione.json", chiave,
                             json.dumps(info).encode(), "application/json",
                             {"x-upsert": "true", "cache-control": "max-age=60"})
    if stato not in (200, 201):
        sys.exit(f"Errore nel caricare versione.json: {stato} {risposta[:200]!r}")
    file_versione.write_text(versione, encoding="utf-8")
    print(f"Pubblicata la traduzione v{versione}: {url}/storage/v1/object/public/{CONTENITORE}/versione.json")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
