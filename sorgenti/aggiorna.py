"""Controlla la patch italiana e, se serve, la rigenera e la installa. Usato da AniimoITA.exe (aniimo_ita_app.py).

Uso:  python aggiorna.py               -> controlla, aggiorna se serve, installa
      python aggiorna.py --controlla   -> dice solo lo stato, non cambia niente
      python aggiorna.py --ripristina  -> rimette il file originale del gioco
"""
import argparse
import hashlib
import os
import subprocess
import sys

import comune
import crea_patch
import estrai

FILE_GIOCO = comune.I18N_SCIOLTI / f"Compress_{crea_patch.SLOT}.bin"
MAX_TRADUZIONI_SUBITO = 3000


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def gioco_aperto() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Aniimo.exe", "/NH"],
                         capture_output=True, text=True, creationflags=0x08000000).stdout  # senza finestra
    return "Aniimo.exe" in out


def scrivi_nel_gioco(blob: bytes) -> bool:
    try:
        FILE_GIOCO.write_bytes(blob)
        return True
    except PermissionError:
        print("ERRORE: permesso negato. Riprova con i permessi di amministratore.")
        return False


def traduci_nuovi() -> None:
    en = set(comune.carica(comune.EN_JSON)["testi"].values())
    memoria = comune.carica_memoria()
    nuovi = sorted(s for s in en if s.strip() and s not in memoria)
    print(f"Frasi senza traduzione: {len(nuovi)}")
    if not nuovi:
        return
    if not (comune.carica_chiave_api() or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("  Nessuna chiave API: queste frasi restano in inglese.")
        return
    if len(nuovi) > MAX_TRADUZIONI_SUBITO:
        print(f"  Sono piu' di {MAX_TRADUZIONI_SUBITO}: usa la traduzione batch "
              "(seleziona.py tutto, traduci.py invia / scarica). Per ora restano in inglese.")
        return
    import applica_lotto
    import traduci
    print("  Traduzione in corso con Claude...")
    tradotte, falliti = traduci.traduci_subito(nuovi)
    scartati = applica_lotto.aggiungi(memoria, tradotte)
    comune.salva(comune.MEMORIA, memoria)
    print(f"  Tradotte {len(tradotte) - len(scartati)} frasi"
          + (f", {falliti} richieste fallite (riprova piu' tardi)" if falliti else ""))


def esegui(controlla: bool = False, ripristina: bool = False) -> str:
    """Restituisce l'esito: installata, gia_ok, da_aggiornare, originale, gia_originale,
    ripristinato, gioco_aperto, permesso."""
    estrai.main()
    orig = crea_patch.originale()
    attuale = FILE_GIOCO.read_bytes()

    if ripristina:
        if attuale == orig:
            print("Il file del gioco e' gia' quello originale.")
            return "gia_originale"
        if gioco_aperto():
            print("Chiudi il gioco e riprova.")
            return "gioco_aperto"
        if scrivi_nel_gioco(orig):
            print("File originale ripristinato.")
            return "ripristinato"
        return "permesso"

    if not controlla:
        traduci_nuovi()
        import accorcia
        accorcia.esegui()
    patch, stat = crea_patch.costruisci()
    italiano = stat.get("italiano", 0) + stat.get("italiano corto", 0)
    print(f"Blocchi in italiano: {italiano}  |  in inglese: {stat.get('inglese', 0)}"
          f"  |  in russo: {stat.get('originale', 0)}")

    if attuale == patch:
        print("\nOK: la patch italiana e' installata ed e' aggiornata. Niente da fare.")
        return "gia_ok"
    if attuale == orig:
        print("\nIl gioco ha il file originale (aggiornamento o riparazione del launcher).")
    else:
        print("\nLa patch installata e' vecchia o incompleta.")
    if controlla:
        print("Avvia senza --controlla per aggiornarla.")
        return "originale" if attuale == orig else "da_aggiornare"
    if gioco_aperto():
        print("Chiudi il gioco e rilancia: il file e' in uso.")
        return "gioco_aperto"
    out = comune.DATI / "patch" / FILE_GIOCO.name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(patch)
    if scrivi_nel_gioco(patch):
        print("FATTO: patch italiana installata. Nel gioco scegli la lingua Русский.")
        return "installata"
    return "permesso"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--controlla", action="store_true")
    ap.add_argument("--ripristina", action="store_true")
    a = ap.parse_args()
    esegui(a.controlla, a.ripristina)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
