"""AniimoITA.exe: una finestra con un pulsante per mettere Aniimo in italiano.

Usa la stessa logica di aggiorna.py. I dati di traduzione stanno in %LOCALAPPDATA%\\AniimoITA:
alla prima apertura (o quando l'exe contiene una traduzione piu' nuova) vengono copiati li'.
I permessi di amministratore si chiedono solo quando serve scrivere nella cartella del gioco.
"""
import ctypes
import importlib
import io
import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

DATI = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AniimoITA"
os.environ["ANIIMO_ITA_DATI"] = str(DATI)
INCLUSI = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "dati"
FILE_PERCORSO = DATI / "percorso_gioco.txt"
FILE_AVVISO = DATI / "avvertenze_lette.txt"
VERDE, ROSSO, GRIGIO = "#1e7d32", "#b3261e", "#555555"

ESITI = {
    "installata": (VERDE, "Fatto! Il gioco è in italiano.\n"
                          "Nel gioco scegli Impostazioni → Lingua → Русский."),
    "gia_ok": (VERDE, "L'italiano è installato e aggiornato.\n"
                      "Nel gioco la lingua deve essere Русский."),
    "da_aggiornare": (ROSSO, "C'è una traduzione più nuova da installare.\n"
                             "Premi «Installa patch in italiano»."),
    "originale": (ROSSO, "Il gioco è in versione originale (di solito dopo un aggiornamento).\n"
                         "Premi «Installa patch in italiano»."),
    "gia_originale": (GRIGIO, "Il gioco è già nella versione originale."),
    "ripristinato": (GRIGIO, "Fatto: il gioco è tornato alla versione originale.\n"
                             "Nel gioco rimetti la lingua che usavi prima."),
    "gioco_aperto": (ROSSO, "Aniimo è aperto: chiudilo e premi di nuovo il pulsante."),
    "permesso": (ROSSO, "Servono i permessi di amministratore per modificare i file del gioco."),
}


# ---------------------------------------------------------------- dati e percorsi

def numero(v: str) -> tuple:
    """"1.0.3" -> (1, 0, 3); le vecchie versioni a data valgono come la piu' bassa."""
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def leggi_json(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def scrivi_json(p: Path, dati) -> None:
    p.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")


def prepara_dati() -> None:
    """Copia la traduzione inclusa nell'exe se e' piu' nuova di quella sul PC.
    Le frasi tradotte in automatico sul PC (dopo un aggiornamento) restano: la revisione inclusa ha la precedenza."""
    DATI.mkdir(parents=True, exist_ok=True)
    stampo = (INCLUSI / "versione_traduzione.txt")
    nuova = stampo.read_text(encoding="utf-8-sig").strip() if stampo.exists() else ""
    locale = DATI / "versione_traduzione.txt"
    if locale.exists() and numero(locale.read_text(encoding="utf-8-sig")) >= numero(nuova):
        return  # sul PC c'e' gia' questa traduzione o una piu' nuova (scaricata da internet)
    for nome in ("memoria.json", "memoria_corta.json", "glossario.json"):
        incluso = leggi_json(INCLUSI / nome, None)
        if incluso is None:
            continue
        unito = leggi_json(DATI / nome, {})
        unito.update(incluso)
        scrivi_json(DATI / nome, unito)
    locale.write_text(nuova, encoding="utf-8")


def versione_locale() -> str:
    p = DATI / "versione_traduzione.txt"
    return p.read_text(encoding="utf-8-sig").strip() if p.exists() else ""


def aggiorna_da_internet() -> str:
    """Scarica da Supabase la traduzione piu' recente, se ce n'e' una nuova.
    Restituisce: scaricata, ultima, offline, nessun_server."""
    import gzip
    import hashlib
    import urllib.request
    file_url = INCLUSI / "supabase_url.txt"
    if not file_url.exists():
        return "nessun_server"
    base = f"{file_url.read_text(encoding='utf-8-sig').strip().rstrip('/')}/storage/v1/object/public/aniimo-ita"
    try:
        import time  # parametro sempre diverso: evita una risposta vecchia dalla cache
        with urllib.request.urlopen(f"{base}/versione.json?t={int(time.time())}", timeout=8) as r:
            info = json.loads(r.read())
        if numero(info["versione"]) <= numero(versione_locale()):
            return "ultima"
        nuovi = {}
        for nome, impronta in info["file"].items():
            with urllib.request.urlopen(f"{base}/{nome}.gz", timeout=120) as r:
                dati = r.read()
            if hashlib.sha256(dati).hexdigest() != impronta:
                return "offline"  # download incompleto: si riprova la prossima volta
            nuovi[nome] = json.loads(gzip.decompress(dati))
    except Exception:
        return "offline"
    for nome, contenuto in nuovi.items():
        unito = leggi_json(DATI / nome, {})
        unito.update(contenuto)
        scrivi_json(DATI / nome, unito)
    (DATI / "versione_traduzione.txt").write_text(info["versione"], encoding="utf-8")
    return "scaricata"


def valido(p) -> bool:
    return bool(p) and (Path(p) / "Aniimo_Data/cvs/res/lua/LuaScripts.xdf").exists()


def trova_gioco() -> str | None:
    if FILE_PERCORSO.exists():
        p = FILE_PERCORSO.read_text(encoding="utf-8").strip()
        if valido(p):
            return p
    for lettera in "CDEFGHIJ":
        for modello in (r"{}:\Program Files (x86)\Animoo\game", r"{}:\Program Files\Animoo\game",
                        r"{}:\Animoo\game", r"{}:\Games\Animoo\game"):
            p = modello.format(lettera)
            if valido(p):
                return p
    return None


def amministratore() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def riavvia_come_admin(azione: str) -> bool:
    """Riapre l'app con i permessi di amministratore e le fa eseguire subito l'azione."""
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, f"--azione {azione}"
    else:
        exe, args = sys.executable, f'"{Path(__file__).resolve()}" --azione {azione}'
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1) > 32


# ---------------------------------------------------------------- lavoro in background

class Scrittore(io.TextIOBase):
    def __init__(self, coda):
        self.coda = coda

    def write(self, s):
        if s:
            self.coda.put(("log", s))
        return len(s)


def lavora(azione: str, coda: queue.Queue) -> None:
    vecchio = sys.stdout
    sys.stdout = Scrittore(coda)
    try:
        import comune, crea_patch, estrai, aggiorna  # noqa: E401
        for m in (comune, crea_patch, estrai, aggiorna):  # rilegge il percorso del gioco
            importlib.reload(m)
        if azione != "ripristina":
            coda.put(("online", aggiorna_da_internet()))
        esito = aggiorna.esegui(controlla=azione == "controlla", ripristina=azione == "ripristina")
        coda.put(("fine", esito))
    except Exception as e:  # mostrato all'utente in modo leggibile
        coda.put(("errore", f"{type(e).__name__}: {e}"))
    finally:
        sys.stdout = vecchio


# ---------------------------------------------------------------- finestra

class App(tk.Tk):
    def __init__(self, azione_iniziale: str | None):
        super().__init__()
        self.title("Aniimo in italiano")
        # Su schermi ad alta risoluzione testi e finestra si ingrandiscono in proporzione
        dpi = self.winfo_fpixels("1i")
        self.tk.call("tk", "scaling", dpi / 72)
        f = dpi / 96
        self.geometry(f"{int(560 * f)}x{int(470 * f)}")
        self.resizable(False, False)
        try:
            self.iconbitmap(str(Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "aniimo_ita.ico"))
        except tk.TclError:
            pass
        self.coda: queue.Queue = queue.Queue()
        self.occupato = False
        self.dettagli = ""
        self.online = "nessun_server"
        self.ultimo_esito = ""
        stile = ttk.Style(self)
        stile.configure("Grande.TButton", font=("Segoe UI", 13, "bold"), padding=10)
        stile.configure("TButton", font=("Segoe UI", 10), padding=8)

        cornice = ttk.Frame(self, padding=18)
        cornice.pack(fill="both", expand=True)
        ttk.Label(cornice, text="Aniimo in italiano", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        # Versione: rossa se la patch nel gioco e' vecchia o assente, verde se e' l'ultima
        self.versione = tk.Label(cornice, text="Controllo della versione in corso…",
                                 font=("Segoe UI", 9), fg=GRIGIO, anchor="w")
        self.versione.pack(anchor="w", pady=(0, 12))

        passi = ("1. Chiudi Aniimo.\n"
                 "2. Premi «Installa patch in italiano».\n"
                 "3. Apri Aniimo: Impostazioni → Lingua → Русский.\n"
                 "Dopo ogni aggiornamento del gioco riapri questa app e ripeti.")
        ttk.Label(cornice, text=passi, font=("Segoe UI", 10), justify="left").pack(anchor="w", pady=(0, 12))

        self.btn_italiano = ttk.Button(cornice, text="Installa patch in italiano", style="Grande.TButton",
                                       command=lambda: self.avvia("installa"))
        self.btn_italiano.pack(fill="x")
        self.btn_originale = ttk.Button(cornice, text="Ripristina lingua originale", command=self.chiedi_ripristino)
        self.btn_originale.pack(fill="x", pady=(8, 0))

        self.barra = ttk.Progressbar(cornice, mode="indeterminate")  # visibile solo mentre lavora
        self.stato = tk.Label(cornice, text="", font=("Segoe UI", 10, "bold"), justify="left",
                              anchor="w", wraplength=int(510 * f))
        self.stato.pack(fill="x", pady=(12, 0))

        piede = ttk.Frame(cornice)
        piede.pack(side="bottom", fill="x")
        ttk.Label(piede, text="Attenzione: modificare i file non è consentito dal regolamento di Aniimo. "
                              "Usi la patch a tuo rischio.", foreground=ROSSO, wraplength=int(510 * f),
                  font=("Segoe UI", 8)).pack(anchor="w")
        riga = ttk.Frame(piede)
        riga.pack(fill="x", pady=(6, 0))
        self.etichetta_percorso = ttk.Label(riga, text="", foreground=GRIGIO, font=("Segoe UI", 8))
        self.etichetta_percorso.pack(side="left", fill="x", expand=True)
        cambia = tk.Label(riga, text="Cambia cartella del gioco", fg="#1a5fb4", cursor="hand2",
                          font=("Segoe UI", 8, "underline"))
        cambia.pack(side="right")
        cambia.bind("<Button-1>", lambda e: self.scegli_cartella())

        self.after(100, lambda: self.inizio(azione_iniziale))

    # ---------------------------------------------------------- avvio
    def inizio(self, azione_iniziale):
        DATI.mkdir(parents=True, exist_ok=True)
        if not FILE_AVVISO.exists():
            ok = messagebox.askokcancel(
                "Prima di iniziare",
                "Questa è una traduzione amatoriale e non ufficiale.\n\n"
                "Modificare i file di Aniimo NON è consentito dal regolamento del gioco: "
                "l'account potrebbe essere sanzionato. La patch cambia solo i testi, "
                "ma la usi a tuo rischio.\n\n"
                "Puoi tornare al gioco originale in qualsiasi momento.\n\nVuoi continuare?")
            if not ok:
                self.destroy()
                return
            FILE_AVVISO.write_text("ok", encoding="utf-8")
        try:
            prepara_dati()
        except Exception as e:
            self.mostra(ROSSO, f"Non riesco a preparare i dati di traduzione: {e}")
            return
        percorso = trova_gioco()
        if not percorso:
            self.mostra(ROSSO, "Non trovo Aniimo. Premi «Cambia cartella del gioco» e scegli la cartella "
                               "«game» (quella che contiene «Aniimo_Data»).")
            self.etichetta_percorso.config(text="Cartella del gioco non trovata")
            self.versione.config(text=f"Patch v{versione_locale() or '?'}", fg=GRIGIO)
            return
        self.imposta_percorso(percorso)
        self.avvia(azione_iniziale or "controlla")

    def imposta_percorso(self, p: str):
        FILE_PERCORSO.write_text(p, encoding="utf-8")
        self.etichetta_percorso.config(text=f"Gioco: {p}")

    def scegli_cartella(self):
        if self.occupato:
            return
        p = filedialog.askdirectory(title="Scegli la cartella «game» di Aniimo")
        if not p:
            return
        p = str(Path(p))
        if not valido(p) and valido(Path(p) / "game"):
            p = str(Path(p) / "game")
        if not valido(p):
            messagebox.showerror("Cartella sbagliata",
                                 "In questa cartella non c'è Aniimo.\nScegli la cartella «game» "
                                 "che contiene «Aniimo_Data».")
            return
        self.imposta_percorso(p)
        self.avvia("controlla")

    # ---------------------------------------------------------- versione
    def mostra_versione(self, esito: str):
        attuale = versione_locale() or "?"
        file_installata = DATI / "versione_installata.txt"
        if esito in ("gia_ok", "installata"):
            file_installata.write_text(attuale, encoding="utf-8")
        elif esito in ("gia_originale", "ripristinato"):
            file_installata.unlink(missing_ok=True)
        installata = file_installata.read_text(encoding="utf-8").strip() if file_installata.exists() else ""
        nota = " (offline: aggiornamenti non controllati)" if self.online == "offline" else ""
        if esito in ("gia_ok", "installata"):
            ultima = " · ultima versione" if self.online in ("ultima", "scaricata") else ""
            self.versione.config(text=f"Patch v{attuale} installata{ultima}{nota}", fg=VERDE)
        elif esito == "da_aggiornare":
            vecchia = f"v{installata}" if installata and installata != attuale else "una versione vecchia"
            self.versione.config(text=f"Nel gioco c'è la patch {vecchia} · disponibile v{attuale}{nota}", fg=ROSSO)
        elif esito in ("originale", "gia_originale", "ripristinato"):
            self.versione.config(text=f"Patch non installata · disponibile v{attuale}{nota}", fg=ROSSO)

    # ---------------------------------------------------------- azioni
    def chiedi_ripristino(self):
        if messagebox.askyesno("Ripristina lingua originale",
                               "Rimettere i testi originali del gioco?\n"
                               "Potrai rimettere l'italiano quando vuoi."):
            self.avvia("ripristina")

    def avvia(self, azione: str):
        if self.occupato or not FILE_PERCORSO.exists():
            return
        if azione in ("installa", "ripristina") and not amministratore():
            if riavvia_come_admin(azione):
                self.destroy()
            else:
                self.mostra(ROSSO, "Serve il permesso di amministratore per modificare i file del gioco. "
                                   "Riprova e rispondi «Sì» alla richiesta di Windows.")
            return
        self.occupato = True
        self.dettagli = ""
        for b in (self.btn_italiano, self.btn_originale):
            b.state(["disabled"])
        self.barra.pack(fill="x", pady=(12, 0), before=self.stato)
        self.barra.start(12)
        testi = {"installa": "Installazione patch in corso…",
                 "controlla": "Controllo in corso…", "ripristina": "Ripristino lingua originale in corso…"}
        self.mostra(GRIGIO, testi[azione])
        threading.Thread(target=lavora, args=(azione, self.coda), daemon=True).start()
        self.after(150, lambda: self.ascolta(azione))

    def ascolta(self, azione):
        try:
            while True:
                tipo, valore = self.coda.get_nowait()
                if tipo == "log":
                    self.dettagli += valore
                elif tipo == "online":
                    self.online = valore
                elif tipo == "fine":
                    self.ultimo_esito = valore
                    self.mostra_versione(valore)
                    if azione == "controlla" and valore in ("gia_ok", "da_aggiornare", "originale"):
                        testo = {"gia_ok": (VERDE, "Tutto pronto: il gioco è in italiano."),
                                 "da_aggiornare": (ROSSO, "Premi «Installa patch in italiano» per installare la versione nuova."),
                                 "originale": (ROSSO, "Premi «Installa patch in italiano» per mettere il gioco in italiano.")}
                        self.fine(*testo[valore])
                    else:
                        self.fine(*ESITI.get(valore, (GRIGIO, valore)))
                    return
                else:
                    self.fine(ROSSO, "Qualcosa non ha funzionato. Chiudi Aniimo e riprova.")
                    messagebox.showerror("Errore", f"{valore}\n\n{self.dettagli[-1500:]}")
                    return
        except queue.Empty:
            pass
        self.after(150, lambda: self.ascolta(azione))

    def fine(self, colore, testo):
        self.barra.stop()
        self.barra.pack_forget()
        self.occupato = False
        for b in (self.btn_italiano, self.btn_originale):
            b.state(["!disabled"])
        if self.ultimo_esito in ("gia_ok", "installata"):  # gia' all'ultima versione: niente da installare
            self.btn_italiano.config(text="Ultima versione già installata")
            self.btn_italiano.state(["disabled"])
        else:
            self.btn_italiano.config(text="Installa patch in italiano")
        self.mostra(colore, testo)

    def mostra(self, colore, testo):
        self.stato.config(text=testo, fg=colore)


def main():
    azione = None
    if "--azione" in sys.argv:
        i = sys.argv.index("--azione")
        azione = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(azione).mainloop()


if __name__ == "__main__":
    main()
