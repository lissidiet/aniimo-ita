# Crea AniimoITA.exe con la traduzione attuale dentro. Risultato in dati\build\dist\AniimoITA.exe.
$qui = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $qui
$build = Join-Path $qui "dati\build"
$inclusi = "$build\inclusi"
Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $inclusi | Out-Null
# Solo italiano: {impronta della frase inglese: italiano}. Il testo del gioco non entra nell'exe.
& .venv\Scripts\python.exe -c "import json,sys,comune; from pathlib import Path; d=Path(sys.argv[1]); [(d/n).write_text(json.dumps(comune.pacchetto(comune.carica(s,{})),ensure_ascii=False),encoding='utf-8') for n,s in ((comune.PACCHETTO_MEMORIA,comune.MEMORIA),(comune.PACCHETTO_CORTA,comune.MEMORIA_CORTA))]" $inclusi
if (Test-Path "dati\supabase_url.txt") { Copy-Item "dati\supabase_url.txt" $inclusi }  # indirizzo pubblico degli aggiornamenti
# Numero di versione della traduzione inclusa: lo stesso pubblicato su Supabase (pubblica_traduzione.py).
Copy-Item "dati\versione_patch.txt" "$inclusi\versione_traduzione.txt"
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name AniimoITA `
    --icon (Join-Path $qui "aniimo_ita.ico") --add-data "$inclusi;dati" --add-data "$(Join-Path $qui 'aniimo_ita.ico');." `
    --hidden-import traduci --hidden-import accorcia --hidden-import applica_lotto `
    --workpath "$build\lavoro" --distpath "$build\dist" --specpath $build (Join-Path $qui "aniimo_ita_app.py")
Pop-Location
