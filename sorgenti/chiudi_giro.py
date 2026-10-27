"""Chiude un giro di revisione: pubblica la nuova versione e aggiorna GitHub.

1. pubblica_traduzione.py  -> nuova versione su Supabase (l'app la scarica da sola)
2. ROADMAP.md              -> nuova riga in "Versioni" e tabella "Avanzamento" aggiornata
3. STORIA.md               -> totali aggiornati
4. versione_patch.txt in github/sorgenti/dati, commit e push del repository pubblico

Uso:  python chiudi_giro.py "novità del giro in una frase"
"""
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import comune
import pubblica_traduzione
import revisiona

GITHUB = Path(__file__).resolve().parent.parent / "github"
AUTORE = ["-c", "user.name=lissidiet", "-c", "user.email=283813560+lissidiet@users.noreply.github.com"]


def numeri():
    coda = comune.carica(revisiona.CODA, [])
    fatti = comune.carica(revisiona.FATTI, [])
    totale = len(coda) + len(fatti)
    conta = Counter(v["g"] for v in coda)
    return len(fatti), totale, conta[2], conta[3], len(comune.carica(revisiona.REGISTRO, {}))


def it(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main():
    novita = sys.argv[1] if len(sys.argv) > 1 else "Revisione dell'interfaccia proseguita."
    sys.argv = sys.argv[:1]  # pubblica_traduzione senza argomenti: versione automatica (+1)
    pubblica_traduzione.main()
    versione = (comune.DATI / "versione_patch.txt").read_text(encoding="utf-8").strip()
    fatti, totale, interfaccia, resto, correzioni = numeri()
    perc = f"{100 * fatti / totale:.1f}".replace(".", ",")
    oggi = datetime.now().strftime("%d/%m/%Y")

    p = GITHUB / "ROADMAP.md"
    s = p.read_text(encoding="utf-8")
    s = s.replace("|---|---|---|---|\n| **", f"|---|---|---|---|\n| **v{versione}** | {oggi} | {perc}% | {novita} |\n| **", 1)
    s = re.sub(r"(\| 3\. Interfaccia \|[^|]*\|)[^|]*\|[^|]*\|",
               rf"\1 {'✅ fatto' if interfaccia == 0 else '🔄 in corso'} | rimangono {it(interfaccia)} voci |", s)
    s = re.sub(r"(\| 4\. Dialoghi e descrizioni \|[^|]*\|)[^|]*\|[^|]*\|",
               rf"\1 {'🔄 in corso' if interfaccia == 0 else '⏳ da fare'} | rimangono {it(resto)} voci |", s)
    s = re.sub(r"\| \*\*Totale revisione\*\* \|.*", f"| **Totale revisione** | voci controllate a mano | 🔄 | "
               f"**{perc}%** ({it(fatti)} / {it(totale)}) |", s)
    p.write_text(s, encoding="utf-8")

    p = GITHUB / "STORIA.md"
    s = p.read_text(encoding="utf-8")
    s = re.sub(r"Totale: \*\*.*", f"Totale: **{it(fatti)} voci su {it(totale)} ({perc}%)**, "
               f"**{it(correzioni)} correzioni manuali**. Traduzione pubblicata: **v{versione}**.", s)
    p.write_text(s, encoding="utf-8")

    (GITHUB / "sorgenti/dati/versione_patch.txt").write_text(versione, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=GITHUB, check=True)
    subprocess.run(["git", *AUTORE, "commit", "-q", "-m",
                    f"Traduzione v{versione}: revisione al {perc}%\n\n"
                    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"], cwd=GITHUB, check=True)
    subprocess.run(["git", "push", "-q"], cwd=GITHUB, check=True)
    print(f"Giro chiuso: v{versione}, revisione {perc}% ({fatti}/{totale}), GitHub aggiornato.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
