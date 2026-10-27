# Cosa è stato fatto finora

Cronologia del progetto, ottobre 2026.

## 1. Patch e primo test
- Individuati i testi del gioco e preparata una patch che mette l'italiano al posto del russo, senza toccare
  nient'altro del gioco.
- Primo test in gioco: schermate iniziali e menu principale in italiano.
- Creata l'app **AniimoITA.exe**: due pulsanti, controllo automatico, aggiornamenti scaricati da soli,
  anche dopo gli aggiornamenti del gioco. Include il ripristino della lingua originale.

## 2. Traduzione completa
- Tradotte automaticamente con Claude (Anthropic) **circa 51.700 frasi**: interfaccia, oggetti, abilità,
  missioni, dialoghi, descrizioni.
- Segnaposto, colori e formattazione del gioco (`{0}`, `<style>`, a capo…) vengono controllati frase per frase:
  le traduzioni che li rompono sono scartate e ritradotte.
- Dove lo spazio del gioco è troppo piccolo si usa una **versione accorciata** dell'italiano.
- Risultato: praticamente tutto il gioco in italiano. Restano in russo solo 5 descrizioni di abilità.

## 3. Glossario
- Preparato un glossario dei termini ricorrenti (nomi di Aniimo, luoghi, meccaniche, statistiche) per avere
  sempre la stessa traduzione dello stesso termine. Vedi [sorgenti/GLOSSARIO.md](sorgenti/GLOSSARIO.md).

## 4. Revisione manuale (in corso)
Revisione voce per voce, a blocchi, in ordine di importanza:

| Fase | Contenuto | Stato |
|---|---|---|
| Nomi propri | Aniimo, personaggi, luoghi | ✅ completata |
| Interfaccia | menu, pulsanti, oggetti, arredi, abilità (testi brevi) | 🔄 in corso, ~48% |
| Resto | dialoghi, descrizioni, missioni | ⏳ da fare |

Totale: **20.544 voci su 52.837 (38,9%)**, **4.049 correzioni manuali**. Traduzione pubblicata: **v1.0.6**.

Esempi di errori corretti:
- "Best Offense is Defense" era tradotto al contrario ("La miglior difesa è l'attacco");
- "Zoom out" era "Ingrandisci" → ora "Riduci";
- nomi di Aniimo tradotti come parole comuni (Pebbling → "Ciottolino", Cornet → "Cornetta") → riportati ai nomi;
- "BREAK" tradotto in cinque modi diversi → sempre BREAK;
- sigle uniformate: ATT, DIF.F, DIF.M, PS, EP, SP, TP.

## 5. Coerenza automatica
Oltre alla revisione a mano, regole automatiche uniformano su tutto il gioco circa 3.000 frasi, per esempio:
- **colture**: "Patata gigante colorata e splendente", sempre nello stesso ordine;
- **uova, chip, pietre energetiche, bonus**: un unico schema per ogni famiglia di oggetti;
- **Aniimo varianti**: "Emberpup Alfa", "Glacy Prismana", "Pawney umbrale";
- **set di arredi**: un solo nome per set ("Serenità di legno", "Alba nella foresta"…);
- **maiuscole**: tolte le maiuscole all'inglese dai titoli ("Ultima Resistenza" → "Ultima resistenza").

## Prossimi passi
- Finire la revisione dell'interfaccia (~16.000 voci).
- Rivedere dialoghi e descrizioni (~24.600 voci).
- Capire da dove vengono alcune scritte rimaste in inglese nel font decorativo delle caselle bloccate del menu.
