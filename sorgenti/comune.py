"""Funzioni condivise: percorsi, lettura dei testi del gioco, protezione dei segnaposto."""
import json
import re
import zipfile
from pathlib import Path

import os
# Cartella dei dati di traduzione; l'app AniimoITA.exe la sposta in %LOCALAPPDATA%\AniimoITA.
DATI = Path(os.environ.get("ANIIMO_ITA_DATI") or Path(__file__).parent / "dati")
# Cartella "game" di Aniimo. Se il gioco e' installato altrove, scrivi il percorso in dati/percorso_gioco.txt.
_PERCORSO = DATI / "percorso_gioco.txt"
GIOCO = Path(_PERCORSO.read_text(encoding="utf-8").strip() if _PERCORSO.exists()
             else r"C:\Program Files (x86)\Animoo\game")
XDF = GIOCO / "Aniimo_Data/cvs/res/lua/LuaScripts.xdf"
I18N_ZIP = "xfs/luascripts/Data/I18N/"
I18N_SCIOLTI = GIOCO / "Aniimo_Data/cvs/res/lua/LuaScripts/Data/I18N"

EN_JSON = DATI / "en.json"            # {id: testo inglese}
MEMORIA = DATI / "memoria.json"       # {testo inglese: testo italiano}, sopravvive agli aggiornamenti
GLOSSARIO = DATI / "glossario.json"   # {termine inglese: termine italiano}, rivedibile a mano
MEMORIA_CORTA = DATI / "memoria_corta.json"  # {testo inglese: italiano accorciato} se lo spazio non basta
VECCHIO_IT_JSON = DATI / "it.json"   # formato precedente {id: italiano}, convertito in memoria

# Segnaposto e markup che devono restare identici nella traduzione:
# {0} {param1}, <style=...> </style>, colori #d89c28, marcatori #kHud #z, \n.
RE_SEGNAPOSTO = re.compile(
    r"\{[^{}\s]{1,24}\}"
    r"|</?[A-Za-z][^<>]{0,40}>"
    r"|#[0-9a-fA-F]{6}(?![0-9a-zA-Z])"
    r"|#[0-9a-fA-F]{6}(?=[A-Za-z])"
    r"|#k[A-Za-z]+|#z|#playerName#?"
    r"|\n"
)


def carica_chiave_api() -> bool:
    """Se ANTHROPIC_API_KEY non e' nell'ambiente (es. finestra aperta prima di setx),
    la legge dalle variabili utente di Windows. Restituisce True se la chiave c'e'."""
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            os.environ["ANTHROPIC_API_KEY"] = winreg.QueryValueEx(k, "ANTHROPIC_API_KEY")[0]
        return True
    except OSError:
        return False


def segnaposto(testo: str) -> list[str]:
    return sorted(RE_SEGNAPOSTO.findall(testo))


def leggi_lingua(codice: str = "en", sorgente: str = "zip") -> tuple[int, dict[str, str]]:
    """Legge Compress_<codice>.bin + NewTextMap_<codice>.json (sola lettura).

    Restituisce (versione, {id: testo}). La mappa contiene id -> [offset, lunghezza]
    in byte, con offset contato dall'inizio del file (header di 4 byte compreso).
    """
    if sorgente == "zip":
        with zipfile.ZipFile(XDF) as z:
            blob = z.read(f"{I18N_ZIP}Compress_{codice}.bin")
            mappa = json.loads(z.read(f"{I18N_ZIP}NewTextMap_{codice}.json"))
    else:
        blob = (I18N_SCIOLTI / f"Compress_{codice}.bin").read_bytes()
        with zipfile.ZipFile(XDF) as z:
            mappa = json.loads(z.read(f"{I18N_ZIP}NewTextMap_{codice}.json"))
    versione = mappa.pop("_version")
    mappa.pop("_count", None)
    testi = {k: blob[o:o + n].decode("utf-8") for k, (o, n) in mappa.items()}
    return versione, testi


def carica_memoria() -> dict[str, str]:
    memoria = carica(MEMORIA, {})
    if not memoria and VECCHIO_IT_JSON.exists():
        en = carica(EN_JSON)["testi"]
        memoria = {en[k]: s for k, s in carica(VECCHIO_IT_JSON).items() if k in en}
        salva(MEMORIA, memoria)
        VECCHIO_IT_JSON.unlink()
    return memoria


def carica(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def salva(p: Path, dati) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
