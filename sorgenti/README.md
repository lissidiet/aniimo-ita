# File tecnici

Questa cartella non serve per giocare: per usare la patch basta `AniimoITA.exe` (vedi il README principale).

| File | A cosa serve |
|---|---|
| `aniimo_ita_app.py` | l'app con i due pulsanti (diventa `AniimoITA.exe`) |
| `crea_exe.ps1` | crea `AniimoITA.exe` con la traduzione attuale |
| `pubblica_traduzione.py` | pubblica online una nuova versione della traduzione (l'app la scarica da sola) |
| `aggiorna.py`, `crea_patch.py`, `estrai.py`, `comune.py` | costruzione e installazione della patch |
| `traduci.py`, `seleziona.py`, `applica_lotto.py`, `accorcia.py` | traduzione delle frasi nuove |
| `revisiona.py`, `regole.py`, `maiuscole.py` | revisione e coerenza della traduzione |
| `dati/` | numero di versione e indirizzo degli aggiornamenti. I file della traduzione non sono nel repository: contengono i testi del gioco e si scaricano dall'app |
| `GLOSSARIO.md` | scelte di traduzione |

Nuova versione della traduzione: `python pubblica_traduzione.py` (il numero sale da solo, es. 1.0.0 → 1.0.1),
poi `crea_exe.ps1` se si vuole anche un exe nuovo. Le chiavi Supabase stanno solo nelle variabili di Windows.
