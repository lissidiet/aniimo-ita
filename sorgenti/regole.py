"""Correzioni automatiche di errori ricorrenti su tutta la traduzione (memoria e versioni corte).

Ogni regola si applica solo se il testo inglese contiene il termine di partenza, cosi' non tocca
frasi in cui la parola italiana e' usata con un altro senso. Dopo la sostituzione si ricontrollano
segnaposto e, per le versioni corte, la lunghezza massima.

Uso:  python regole.py            -> mostra quante frasi cambierebbe ogni regola (prova)
      python regole.py applica    -> applica
"""
import re
import sys
from collections import Counter

import accorcia
import comune

ARTICOLI_MASCHILI = {"la": "il", "una": "un", "della": "del", "alla": "al", "nella": "nel", "sulla": "sul"}


def _articolo_un(nome: str) -> str:
    """'uno' davanti a s+consonante, z, gn, ps, x; altrimenti 'un'."""
    return "uno" if re.match(r"(?i)(s[^aeiou]|z|gn|ps|x)", nome) else "un"


def _maiuscola_come(modello: str, parola: str) -> str:
    return parola.capitalize() if modello[:1].isupper() else parola


# (termine inglese che deve comparire, regex italiana, sostituzione)
REGOLE = [
    ("Homeland", r"\bPatria\b", "Terra natia"),
    ("Homeland", r"\bpatria\b", "terra natia"),
    ("Aeolus", r"\bEolo\b", "Aeolus"),
    ("Aeon", r"\bEoni\b", "Aeon"),
    ("Aeon", r"\bEone\b", "Aeon"),
    ("Idyll", r"\b[Cc]ontinente (?:dell')?Idill(?:io|iaco)\b", "continente di Idyll"),
    ("Idyll", r"\bdell'Idillio\b", "di Idyll"),
    ("Idyll", r"\bnell'Idillio\b", "a Idyll"),
    ("Idyll", r"\ball'Idillio\b", "a Idyll"),
    ("Idyll", r"\bl'Idillio\b", "Idyll"),
    ("Idyll", r"\bIdillio\b", "Idyll"),
    ("Idyll", r"\bIdyllia\b", "Idyll"),
    ("Echoback Landing", r"\b(?:al|all'|ad|a) ?(?:l')?Approdo (?:dell'Eco|Eco|Echeggiante|Echeggio)(?: di Ritorno)?\b", "all'Approdo Echoback"),
    ("Echoback Landing", r"\bnell'Approdo (?:dell'Eco|Eco)\b", "all'Approdo Echoback"),
    ("Echoback Landing", r"\bdell'Approdo (?:dell'Eco|Eco)\b", "dell'Approdo Echoback"),
    ("Echoback Landing", r"\bdi Approdo (?:dell'Eco|Eco)\b", "dell'Approdo Echoback"),
    ("Echoback Landing", r"\bL'Approdo (?:dell'Eco|Eco)\b", "L'Approdo Echoback"),
    ("Echoback Landing", r"\bl'Approdo (?:dell'Eco|Eco)\b", "l'Approdo Echoback"),
    ("Echoback Landing", r"\bApprodo (?:dell'Eco|Eco|Echeggiante)\b", "Approdo Echoback"),
    ("Primegy", r"\b(?:la )?Primegia\b", "il Primegy"),
    ("Aromathyst", r"\bAromati(?:te|sta|sti|stia|zzo)\b", "Aromathyst"),
    ("Tumbler", r"\b(?:Capitombolo|Capovolgitore)\b", "Tumbler"),
    ("Gizmo", r"\b(?:Congegno|Gadget|Ingranaggio) (?:Nucleo|Core|nucleo)\b", "Gizmo nucleo"),
    ("Gizmo", r"\b(?:Gadget|Congegno) (?:Base|base)\b", "Gizmo base"),
    ("Gizmo", r"\b(?:Gadget|Congegno) (?:Avanzato|avanzato)\b", "Gizmo avanzato"),
    ("Training Coin", r"\bMonete d'(?:Addestramento|Allenamento|addestramento|allenamento)\b", "Monete Addestramento"),
    ("Training Coin", r"\bMonete di (?:Addestramento|Allenamento)\b", "Monete Addestramento"),
    ("Alpha", r"\bAlpha\b", "Alfa"),
    ("Flamerion", r"\bFiammerion[ei]?\b", "Flamerion"),
    # Nomi di Aniimo tradotti per sbaglio come parole comuni
    ("Pebbling", r"\bFamiglia Ciottolini\b", "Famiglia Pebbling"),
    ("Pebbling", r"\bCiottol(?:amento|atura|ato|ata|ini|ino|ina|i|o)\b", "Pebbling"),
    ("Cornet", r"\b([Ll]a|[Uu]na|[Dd]ella|[Aa]lla|[Nn]ella|[Ss]ulla) Cornetta\b",
     lambda m: _maiuscola_come(m.group(1), ARTICOLI_MASCHILI[m.group(1).lower()]) + " Cornet"),
    ("Cornet", r"\bCornett[aeio]\b", "Cornet"),
    ("Cornet", r"\bCornet acuta\b", "Cornet acuto"),
    *[(en, rx, lambda m: _maiuscola_come(m.group(0), "olo-gadget"))
      for en in ("Holo-gizmo", "holo-gizmo", "Holo-Gizmo")
      for rx in (r"\b[Gg]adget olografic[oi]\b", r"\b[Oo]lo-?[Gg](?:izmo|adget)\b")],
    ("Held Item", r"\b([Oo])ggett([oi]) (?:[Ee]quipaggiat[oi]|[Ee]quipaggiabil[ei])\b",
     lambda m: f"{m.group(1)}ggett{m.group(2)} tenut{m.group(2)}"),
    ("Biting Rune", r"\b([Rr])una (?:mordente|morsicante)\b", r"\1una morso"),
    ("Dewdrop Crystal", r"\b([Cc])ristall([oi]) di Rugiada\b", r"\1ristall\2 di rugiada"),
    ("Dewdrop Crystal", r"\b([Cc])ristall([oi]) [Rr]ugiada(?: di)?\b", r"\1ristall\2 di rugiada"),
    ("Gameplay Guide", r"\bGuida al gioco:", "Guida di gioco:"),
    ("Umbral Society", r"\bSociet[àa] (?:Ombrat[ao]|Ombros[ao]|Oscura|umbrale)\b", "Società Umbrale"),
    ("Stamps", r"\b[Ff]rancobolli\b", lambda m: _maiuscola_come(m.group(0), "timbri")),
    ("Holo-Battle Sim", r"\b([Ll]a|[Uu]na|[Dd]ella|[Aa]lla|[Nn]ella|[Ss]ulla) [Ss]imulazione (?:di )?"
     r"(?:[Bb]attaglia [Oo]lo(?:grafica)?|[Oo]lo-?[Bb]attaglia)\b",
     lambda m: _maiuscola_come(m.group(1), ARTICOLI_MASCHILI[m.group(1).lower()]) + " Simulatore Olo-Battaglia"),
    ("Holo-Battle Sim", r"\b[Ss]imulazione (?:di )?(?:[Bb]attaglia [Oo]lo(?:grafica)?|[Oo]lo-?[Bb]attaglia)\b",
     "Simulatore Olo-Battaglia"),
    ("Holo-Battle Sim", r"\b([Qq]uest|[Qq]uell|[Nn]ostr|[Vv]ostr|[Pp]rim)a Simulatore Olo-Battaglia",
     r"\1o Simulatore Olo-Battaglia"),
    ("Holo-Battle Sim", r"(Simulatore Olo-Battaglia\b[^.!?]*?\bè stat)a (complet|conclus|superat)a\b", r"\1o \2o"),
    ("Holo-Battle", r"\b[Bb]attaglia [Oo]lo(?:grafica)?\b", "Olo-Battaglia"),
    ("Holo-Battle", r"\b([Ll])a Olo-Battaglia\b", r"\1'Olo-Battaglia"),
    ("Element Resistance", r"\b([Rr])esistenza agli elementi\b", r"\1esistenza elementale"),
    ("Unlock Badge", r"^Sblocca Distintivo - ", "Sblocca distintivo - "),
    (" Avatar", r"^Sblocca l'Avatar ", "Sblocca l'avatar "),
    ("Windborn Stamps", r"\b[Tt]imbri (?:Ventoforte|Ventoserena|Ventoso)\b", "Timbri Windborn"),
    ("Season Stamps", r"\b[Tt]imbri (?:di [Ss]tagione|[Ss]tagionali)\b", "Timbri stagione"),
    ("Element Mastery", r"\b([Pp])adronanza elementare\b", r"\1adronanza elementale"),
    ("Lumin Amber", r"\b([Aa])mbra [Ll]uminosa\b", r"\1mbra Lumin"),
    ("Homeland", r"\bper Casa Mia\b", "per la Terra natia"),
    ("Homeland", r"\bCasa Mia\b", "Terra natia"),
    ("RV", r"\b([Ii]l|[Dd]el|[Aa]l|[Nn]el|[Ss]ul|[Dd]al) (?:RV|VR|[Vv]eicolo [Rr]icreativo)\b", r"\1 camper"),
    ("RV", r"\b([Pp])arco (?:RV|Camper)\b", r"\1arco camper"),
    ("Rumor:", r"^Diceria:", "Voce:"),
    ("Monthly Pass", r"\b([Aa])bbonamento [Mm]ensile|\b([Pp])assaporto [Mm]ensile",
     lambda m: _maiuscola_come(m.group(0), "pass mensile")),
    *[(en, r"\b([Mm])onet([ae]) (?:di |d')?(?:[Aa]llenamento|addestramento)\b", r"\1onet\2 Addestramento")
      for en in ("raining Coin", "raining coin")],
    ("Aniipod Maker", r"\b([Ll]a|[Dd]ella|[Aa]lla) Aniipod Maker\b",
     lambda m: _maiuscola_come(m.group(1), ARTICOLI_MASCHILI[m.group(1).lower()]) + " Costruttore di Aniipod"),
    ("Aniipod Maker", r"\bAniipod Maker\b", "Costruttore di Aniipod"),
    ("Runaway Amber", r"\b([Aa])mbra in fuga\b", r"\1mbra fuggitiva"),
    ("Mistwoods", r"\bBoschi (?:della|di) Nebbia\b", "Boschi Nebbiosi"),
    ("", r"(^|[.!?]\s+)I'Istituto", r"\1L'Istituto"),
    ("", r"\b[iI]'Istituto", "l'Istituto"),
    ("Blitzwood", r"\bBoscoscuro\b|\bBosco ?[Bb]litz\b", "Bosco Folgorante"),
    ("Rosetower", r"\bRosetorre\b", "Rosetower"),
    ("Egg Heist", r"\b[Rr]apina delle [Uu]ova\b", "Furto delle Uova"),
    ("Homeland", r"\bTerra [Nn]atale\b", "Terra natia"),
    ("Bud Ticket", r"\b[Gg]ettoni Bud\b", "Biglietti germoglio"),
    ("Dewdrop Crystal", r"\b([Cc])ristallo [Gg]occia di rugiada\b", r"\1ristallo di rugiada"),
    ("Rosetower Woods", r"\b([Nn]el|[Dd]el|[Aa]l|[Ii]l) Bosco (?:di )?(?:Rosetower|Torreroseto)\b",
     lambda m: _maiuscola_come(m.group(1), {"nel": "nei", "del": "dei", "al": "ai", "il": "i"}[m.group(1).lower()])
     + " Boschi Rosetower"),
    ("Rosetower Woods", r"\bBoschi (?:di )?(?:Rosetower|Torreroseto)\b", "Boschi Rosetower"),
    # Nomi di Aniimo al plurale: in italiano restano invariati.
    ("", r"\b(Emberpup|Pomegg|Cozite|Budsquire|Budclaw|Lavazar|Echoback|Pomawk|Hypnowl|Windglider|Jawling|Hummin)s\b",
     r"\1"),
    ("", r"\b(Susuta|Flutternym|Veilfloat|Starine|Nimbi|Fentuft|Celestis|Cubbo|Sparki|Irisal|Turbo)e?s\b", r"\1"),
    ("", r"\bPrankies\b", "Pranky"),
    ("", r"\bPopapuses\b", "Popapus"),
    ("", r"\bstarines\b", "Starine"),
    ("Boomblast Arena", r"\bArena Esplosiv[ao]\b|\bArena Esplosione\b", "Arena Boomblast"),
    ("Nimbus Fields", r"\bCampi (?:di )?Nimbo\b", "Campi Nimbus"),
    ("Berylline Vale", r"\bValle (?:di )?Beril+ina\b", "Valle di Berylline"),
    ("Tideblossom Coast", r"\bCosta (?:di )?Tideblossom\b|\bCosta (?:Fiorita|Fioritura) di [Mm]area\b",
     "Costa Tideblossom"),
    ("Zephyr Coast", r"\bCosta di Zephyr\b", "Costa Zefiro"),
    ("Home Season", r"\bStagione della Patria\b", "Stagione della Casa"),
    ("Echoback Landing", r"\b([Ii]l|[Dd]el|[Aa]l|[Nn]el) Punto di [Aa]tterraggio Echoback\b",
     lambda m: _maiuscola_come(m.group(1), {"il": "l'", "del": "dell'", "al": "all'", "nel": "nell'"}[m.group(1).lower()])
     + "Approdo Echoback"),
    ("Echoback Landing", r"\bPunto di [Aa]tterraggio Echoback\b|\bEchoback Landing\b", "Approdo Echoback"),
    ("Driftwise Meadow", r"\bPrato Deriva Saggia\b", "Prato Driftwise"),
    ("Russet Highlands", r"\bAltopiani (?:Fulvi|Rossicci)\b", "Altopiani Russet"),
    ("Bloom Festival", r"\b([Ii]l|[Dd]el|[Aa]l|[Nn]el) Festa della Fioritura\b",
     lambda m: _maiuscola_come(m.group(1), {"il": "la", "del": "della", "al": "alla", "nel": "nella"}[m.group(1).lower()])
     + " Festa della Fioritura"),
    ("Berylline", r"\bdi Valle di Berylline\b", "della Valle di Berylline"),
    ("Sea of Flowers", r"\bMare dei [Ff]iori\b", "Mare di fiori"),
    ("Rosetower Woods", r"\bForesta Torre Rosa\b|\bBoschi Rosatorre\b|\bBoschi Torrerosa\b", "Boschi Rosetower"),
    ("RV", r"\bdi RV\b", "del camper"),
    ("RV", r"\b([Ii]l tuo|[Dd]el|[Ii]l|[Aa]l) Camper\b", r"\1 camper"),
    ("Homeland", r"\bHomeland\b", "Terra natia"),
    ("Breezy Plains", r"\bBreezy Plains\b", "Pianure Ventose"),
    ("Dr. Lewis", r"\bDr\. Lewis\b", "Dott. Lewis"),
    ("Nurture", r"\b[Nn]utrimento\b", lambda m: _maiuscola_come(m.group(0), "cura")),
    ("Nurture", r"\b([Cc])oltivazione\b", r"\1ura"),
    ("Nurture", r"\b([Cc])oltivazioni\b", r"\1ure"),
    ("Nurture", r"\b([Ii]l|[Dd]el|[Aa]l|[Dd]al) (Cura)\b",
     lambda m: _maiuscola_come(m.group(1), {"il": "la", "del": "della", "al": "alla", "dal": "dalla"}[m.group(1).lower()])
     + " " + m.group(2)),
    ("Veinfruit", r"\bFrutto Vena\b", "Frutto della Vena"),
    ("Vein", r"\benergia delle Vene\b", "energia della Vena"),
    ("Prismana Flow", r"\bFlusso di Prismana\b", "Flusso Prismana"),
    ("Vein", r"\benergia Vena\b", "energia della Vena"),
    ("Prismana", r"\bPrismana (Glynsera|Melloblum|Waleetle|Inferlupa|Fenmane|Fulmintis|Magmarex|Panpanta|Glacy"
     r"|Ignitis|Luminelle|Stellarys|Scorchhowl|Hexxin|Grizbo|Blazen|Pawney|Sherro|Irisal|Sparkelf)\b", r"\1 Prismana"),
    ("", r"\bin (Cresta|Valle|Costa|Foresta) (della|delle|dei|di|Zefiro|Tideblossom)\b", r"nella \1 \2"),
    ("", r"\bin (Campi Nimbus|Boschi Rosetower|Boschi Nebbiosi)\b", r"nei \1"),
    ("", r"\bin (Altopiani Russet)\b", r"negli \1"),
    ("Glamour Star", r"\bStell[ae] del Fascino\b", "Glamour Star"),
    ("Claw Game Cooker", r"\bCuoco (?:Claw Game|Gru Acchiappapremi)\b", "Fornello Acchiappapremi"),
    ("Bouncy Brew Keg", r"\bBarile Frizzante\b|\bFusto Frizzante\b|\bBarilotto della Birra Rimbalzante\b",
     "Barile di birra rimbalzante"),
    ("Jukebox Dryer", r"\bEssiccatore a Jukebox\b", "Essiccatore Jukebox"),
    ("Carousel Mill", r"\bMulino a (?:Carosello|Giostra)\b", "Mulino a giostra"),
    ("Joy Wheel Loom", r"\bTelaio Ruota Gioiosa\b", "Telaio Ruota della gioia"),
    ("Home Coin", r"\bMonete di Casa\b", "Monete Casa"),
    ("Star Dust", r"\bPolvere Stellare\b|\bPolvere di Stelle\b", "Polvere di stelle"),
    ("Whiterose Tower", r"\bTorre Rosabianca\b", "Torre Whiterose"),
    ("Bud Ticket", r"\b([Bb])iglietto Bud\b", r"\1iglietto germoglio"),
    ("Bud Ticket", r"\b([Bb])iglietti Bud\b", r"\1iglietti germoglio"),
    ("Hatchinator", r"\bSchiudi-Hatchinator\b", "Schiuditori"),
    ("Star-Crossed Tea Party", r"\bTè (?:delle anime incrociate|dei [Dd]estini [Ii]ncrociati|delle [Ss]telle [Ii]ncrociate)\b",
     "Tè delle stelle sfortunate"),
    ("RV Park", r"\bCamper Park\b", "parco camper"),
    ("Beast Fang Ridge", r"\bCresta delle Zanne Bestiali\b", "Cresta della Zanna Bestiale"),
    ("Thousand-Fang Ridge", r"\bCresta (?:dalle )?Mille Zanne\b", "Cresta delle Mille Zanne"),
    ("Breezy Plains", r"\bPianure (?:Frizzanti|Brezzose)\b", "Pianure Ventose"),
    ("Berylline Vale", r"\bBerylline Vale\b", "Valle di Berylline"),
    ("romathyst", r"\b[Aa]romatist[ie]\b", "Aromathyst"),
    ("Rift", r"\b([Ff])rattura\b", lambda m: _maiuscola_come(m.group(0), "fenditura")),
    ("Blitzwood", r"\bBlitzwood\b", "Bosco Folgorante"),
    ("Twine Mode", r"\bModalità Twine\b", "Modalità Intreccio"),
    ("", r"\bIgnitises\b", "Ignitis"),
    ("", r"\b(Bolt|Skipp|Whelp)ies\b", r"\1y"),
    ("Windglider", r"\bAliscivolanti\b", "Windglider"),
    ("Companion Handbook", r"\b[Mm]anuale (?:del )?[Cc]ompagno\b", "Manuale del compagno"),
    ("Elite Training", r"\b([Aa])(?:ddestramento|llenamento) (?:[EÉ]lite|d'[EÉ]lite)\b", r"\1ddestramento d'élite"),
    ("Element Mastery", r"\b([Mm])aestria elementale\b",
     lambda m: _maiuscola_come(m.group(1), "padronanza elementale")),
    ("RV", r"\blivello (\d+) (?:di|del) (?:RV|camper)\b", r"livello \1 del camper"),
    ("RV", r"\bRV Liv\. ", "Camper Lv. "),
    ("Pathfinder", r"\bTracciatore\b", "Esploratore"),
    ("Polaris Institute", r"\b([Ii])l Polaris Institute\b", r"\1'Istituto Polaris"),
    ("Polaris Institute", r"\b([Dd]el|[Aa]l|[Dd]al|[Nn]el) Polaris Institute\b", r"\1l'Istituto Polaris"),
    ("Polaris Institute", r"\bPolaris Institute\b", "Istituto Polaris"),
    ("Echoback Landing", r"\bIl Approdo (?:dell'Eco|Eco|Echeggiante)\b", "L'Approdo Echoback"),
    ("Echoback Landing", r"\bil Approdo (?:dell'Eco|Eco|Echeggiante)\b", "l'Approdo Echoback"),
    ("Beast Fang Ridge", r"\bCresta (?:della |di )?Zanna (?:di |della )?Bestia(?:le)?\b", "Cresta della Zanna Bestiale"),
    ("Zephyr Coast", r"\bCosta (?:dello |di )?Zefiro\b", "Costa Zefiro"),
    ("Bloomville", r"\bFioritura ?[Vv]ille\b", "Bloomville"),
    ("Bloom Festival", r"\bFestival della Fioritura\b", "Festa della Fioritura"),
    ("Lumin Amber", r"\bAmbra (?:di )?(?:Lumen|luminosa)\b", "Ambra Lumin"),
    ("Mistwoods", r"\b([NnDdSs][eau])lle (<style=[^>]*>)?Boscaglie (?:Nebbiose|di Nebbia)\b", r"\1i \2Boschi Nebbiosi"),
    ("Mistwoods", r"\b([Ll])e (<style=[^>]*>)?Boscaglie (?:Nebbiose|di Nebbia)\b",
     lambda m: ("I " if m.group(1) == "L" else "i ") + (m.group(2) or "") + "Boschi Nebbiosi"),
    # Riparazione di una versione precedente di queste regole ("del Boschi", "l Boschi")
    ("Mistwoods", r"\b([NnDdSs][eau])l (<style=[^>]*>)?Boschi Nebbiosi\b", r"\1i \2Boschi Nebbiosi"),
    ("Mistwoods", r"\b([NnDdSs][eau])lle (<style=[^>]*>)?Boschi Nebbiosi\b", r"\1i \2Boschi Nebbiosi"),
    ("Mistwoods", r"(?<!\w)l Boschi Nebbiosi\b", "i Boschi Nebbiosi"),
    ("Mistwoods", r"\bBoscaglie (?:Nebbiose|di Nebbia)\b", "Boschi Nebbiosi"),
    ("Mistwoods", r"\bBoschi nebbiosi\b", "Boschi Nebbiosi"),
    ("Mistwoods", r"\b(Boschi Nebbiosi (?:erano|sono|sembravano) )appassite\b", r"\1appassiti"),
    ("Heartbloom", r"\b([Ii]) Heartbloom\b", lambda m: ("Gli" if m.group(1) == "I" else "gli") + " Heartbloom"),
    ("Heartbloom", r"\b([DdAaNn])ei Heartbloom\b", r"\1egli Heartbloom"),
    # Statistiche e sigle dell'interfaccia
    ("ATK", r"\bATK\b", "ATT"),
    ("M.DEF", r"\bM\.DIF\b", "DIF.M"),
    ("P.DEF", r"\b(?:P\.DIF|D\.FIS|P\.DEF)\b", "DIF.F"),
    ("M.ATK", r"\bM\.ATT\b", "ATT.M"),
    ("P.ATK", r"\bP\.ATT\b", "ATT.F"),
    ("HP", r"\bHP\b", "PS"),
    ("REGEN", r"\bRIGENERA(?:ZIONE)?\b", "REGEN"),
    ("BREAK", r"\bROTTURA\b", "BREAK"),
    ("BREAK", r"\b(?:FIORITURA|INTERRUZIONE|FRANTUMA|INFRANGI|FRATTURA)\b", "BREAK"),
    ("Placeholder", r"\(Segnaposto\)", "(segnaposto)"),
    ("Clutter", r"\bIngombro\b", "Detriti"),
    ("Twine", r"\bFusione\b", "Intreccio"),
    ("Egg Heist", r"\bFurto (?:di|delle|dell'|d') ?[Uu]ov[ao]\b", "Furto delle Uova"),
    ("Egg Emperor", r"\bImperatore (?:dell'Uovo|dell'uovo|delle uova|Uovo)\b", "Imperatore delle Uova"),
    ("Holo-Battle Sim", r"\b[Ss]imulatore (?:di|delle) [Bb]attagli[ae] [Oo]lografic[ahe]\b", "Simulatore Olo-Battaglia"),
    ("Holo-Battle Sim", r"\bsimulatore Olo-Battaglia\b", "Simulatore Olo-Battaglia"),
    ("Spirit Dust", r"\bPolvere (?:Spirituale|spirituale|Spettrale|di spirito)\b", "Polvere di Spirito"),
    # Set di arredi della Casa: un solo nome per set
    ("Timber Serenity", r"\bSerenità di Legno\b", "Serenità di legno"),
    ("Rainwashed Celadon", r"\bCeladon (?:[Ll]avato [Dd]alla [Pp]ioggia|Acqua di Pioggia|piovoso)\b", "Celadon lavato dalla pioggia"),
    ("Warmwood Whispers", r"\bSussurri di [Ll]egno caldo\b", "Sussurri di Warmwood"),
    ("Harvest Moon", r"^Harvest Moon - ", "Luna del raccolto - "),
    ("Harvest Moon", r"\bLuna della (?:[Rr]accolta|[Mm]ietitura)\b", "Luna del raccolto"),
    ("Bloom Festival", r"\bFesta della fioritura\b", "Festa della Fioritura"),
    ("Forest Dawn", r"\b(?:Foresta all'alba|Alba della [Ff]oresta|Alba nel bosco)\b", "Alba nella foresta"),
    ("Harvest Moon", r"\bLuna di [Rr]accolto\b", "Luna del raccolto"),
    ("Garden Court", r"\b(?:Corte|Cortile) del [Gg]iardino\b", "Corte del giardino"),
    ("Pale Grain", r"\b(?:Pale Grain|Grana [Pp]allida|Grano Pallido)\b", "Grano pallido"),
    ("Rainwashed Celadon", r"\bCeladon Rainwashed\b", "Celadon lavato dalla pioggia"),
    ("Starburst", r"\bStellaesplosa\b", "Starburst"),
    ("Cool Summer", r"\bEstate (?:Fresca|fantastica)\b", "Estate fresca"),
    ("Breezy Plains", r"\bPianure (?:Brezza|della Brezza|Ventose)\b", "Pianure Ventose"),
    ("Timber Serenity", r"^Timber Serenity - ", "Serenità di legno - "),
    ("Phonolfactory", r"\bTavolo [Ff]onolfattorio\b", "Tavolo fonolfattivo"),
    ("Crackle Generator", r"\bGeneratore di [Cc]repitio\b", "Generatore crepitante"),
    ("Woodworking Bench", r"\bBanco da Falegname\b", "Banco da falegname"),
    ("Building Block", r"\bBlocco da Costruzione\b", "Blocco da costruzione"),
    ("Cave Research Notes", r"\b(?:Note|Appunti) di [Rr]icerca sulla [Cc]averna\b", "Appunti di ricerca sulla caverna"),
    ("Dance Pad", r"\b(?:tappetino|pedana) da ballo\b", "pedana da ballo"),
    # Sigle: EP e SP restano in inglese come BP
    ("EP", r"\bPE\b", "EP"),
    ("SP ", r"\bPT\b", "SP"),
    ("TP Reduction", r"\bPT\b", "TP"),
    ("Lv", r"\bLiv\.(?= ?[\d%{])", "Lv."),
    ("Interaction Gesture", r"\bSblocca (?:il |l')?[Gg]esto d(?:i |')[Ii]nterazione\b", "Sblocca gesto di interazione"),
    ("Flower Pattern", r"^Motivo [Ff]iore - ", "Motivo a fiori - "),
    ("Hardwood", r"\blegno (?:pregiato|massello)\b", "legno duro"),
    ("Joy Wheel", r"\bTelaio Joy Wheel\b", "Telaio Ruota della gioia"),
    ("Aniipod Maker", r"\b(?:Creatore|Fabbrica) (?:di )?Aniipod\b", "Costruttore di Aniipod"),
    ("Holo-Battle", r"\bOlo-battaglia\b", "Olo-Battaglia"),
    ("(Level ", r"\(Livello (\d+)\)", r"(livello \1)"),
    ("Ultimate", r"\b[Uu]ltimate\b", "Suprema"),
    # Articoli rimasti al maschile/elisi dopo "Ultimate" -> "Suprema"
    ("Ultimate", r"\b([Ll])'Suprema\b", r"\1a Suprema"),
    ("Ultimate", r"\b([Dd]e|[Aa]|[Nn]e|[Dd]a|[Ss]u)ll'Suprema\b", r"\1lla Suprema"),
    ("Ultimate", r"\b([Uu])n'Suprema\b", r"\1na Suprema"),
    ("Ultimate", r"\b([Ii]l|[Dd]el|[Aa]l) Suprema\b", lambda m: {"il": "la", "Il": "La", "del": "della", "Del": "Della", "al": "alla", "Al": "Alla"}[m.group(1)] + " Suprema"),
]


def regole_dinamiche() -> list:
    """Regole costruite dal glossario: "Alfa Emberpup" -> "Emberpup Alfa" (ordine italiano)."""
    gl = comune.carica(comune.GLOSSARIO, {})
    nomi = sorted((k for k, v in gl.items() if k == v and len(k) > 3), key=len, reverse=True)
    alt = "|".join(map(re.escape, nomi))
    return [
        # Non dopo un apostrofo: "l'Alfa Bonesky" non deve diventare "l'Bonesky Alfa".
        ("Alpha", rf"(?<!['’])\bAlfa ({alt})\b", r"\1 Alfa"),
        ("Omega", rf"(?<!['’])\bOmega ({alt})\b", r"\1 Omega"),
        ("Relic", rf"^Reliquia ({alt})$", r"Reliquia di \1"),
    ]


# Colture della Casa: "Huge Colorful Shining Crystalline Potato" e varianti. Il nome si ricostruisce
# sempre nello stesso ordine (nome, aggettivi, complemento), cosi' tutte le varianti sono uniformi.
COLTURE = {  # inglese: (nome, complemento, femminile)
    "Agave": ("Agave", "", True), "Captain Spud": ("Capitan Patata", "", False),
    "Cotton": ("Cotone", "", False), "Cranberry": ("Mirtillo rosso", "", False),
    "Ginseng": ("Ginseng", "", False), "Grape": ("Uva", "", True), "Grapes": ("Uva", "", True),
    "Lavender": ("Lavanda", "", True), "Moondew Radish": ("Ravanello", "di Rugiada lunare", False),
    "Potato": ("Patata", "", True), "Pumpkin": ("Zucca", "", True), "Rice": ("Riso", "", False),
    "Rose": ("Rosa", "", True), "Sorghum": ("Sorgo", "", False), "Soybean": ("Soia", "", True),
    "Soybeans": ("Soia", "", True), "Strawberry": ("Fragola", "", True),
    "Sugarcane": ("Canna da zucchero", "", True), "Waxing Moon Pepper": ("Peperone", "della Luna crescente", False),
    "Wheat": ("Grano", "", False),
}
RE_COLTURA = re.compile(r"^((?:(?:Huge|Colorful|Shining|Sparkling|Crystalline) )+)(" + "|".join(COLTURE) + r")$")


def nome_coltura(en: str):
    m = RE_COLTURA.match(en)
    if not m:
        return None
    agg = m.group(1).split()
    nome, compl, f = COLTURE[m.group(2)]
    o = "a" if f else "o"
    prima = [w for a, w in (("Crystalline", "cristallin" + o), ("Huge", "gigante")) if a in agg]
    dopo = [w for a, w in (("Colorful", "colorat" + o), ("Shining", "splendente"), ("Sparkling", "scintillante")) if a in agg]
    agg_it = prima + ([" e ".join(dopo)] if dopo else [])
    return " ".join([nome] + agg_it + ([compl] if compl else []))


# Famiglie di nomi d'interfaccia ricostruite da uno schema fisso (stesso principio delle colture).
ELEMENTI = {"Fire": "Fuoco", "Water": "Acqua", "Grass": "Erba", "Wind": "Vento", "Earth": "Terra", "Light": "Luce",
            "Dark": "Oscurità", "Lightning": "Fulmine", "Ice": "Ghiaccio", "Magic": "magici", "Physical": "fisici"}
TIPI_CHIP = {"Amplifier": "Amplificatore", "Blink": "Scatto", "Boost": "Potenziamento",
             "Capacity Expansion": "Espansione capacità", "Damage": "Danno", "Heal": "Cura", "Protection": "Protezione",
             "Resistance": "Resistenza", "Unit": "Unità", "Vigor": "Vigore", "Weakening": "Indebolimento",
             "Weaken": "Indebolimento", "Fortitude": "Tempra", "Lighting": "Illuminazione"}
LIVELLI_CHIP = {"Basic": "base", "Common": "comune", "Intermediate": "intermedio", "Advanced": "avanzato",
                "Low-Level": "di basso livello", "Low-level": "di basso livello", "Mid-Grade": "di grado medio",
                "Mid-grade": "di grado medio", "High-Grade": "di grado alto", "Low-Grade": "di grado basso",
                "Medium-Grade": "di grado medio", "Mid-Level": "di livello medio", "Experimental": "sperimentale"}
AGG_UOVA = {"Prismana": "Prismana", "Shining": "splendente", "Perfect": "perfetto", "Incredible": "incredibile"}
NON_NOMI_UOVA = {"Beach", "Forest", "Blossom", "Grassland", "Highland", "Healing", "Support", "Wonder", "Rare"}


def _uovo(m, gl, it):
    nome = m.group(2)
    if nome in NON_NOMI_UOVA:
        return None
    if nome in ("BREAK", "DPS", "REGEN"):
        return f"Uovo {nome} {AGG_UOVA[m.group(1)]}"
    return f"Uovo di {gl.get(nome, nome)} {AGG_UOVA[m.group(1)]}"


_NOMI_ANIIMO = set()


def nomi_aniimo() -> set:
    """Nomi di Aniimo riconosciuti dalle voci "Umbral X", "X Family", "Alpha X" del gioco."""
    if not _NOMI_ANIIMO:
        for en in comune.carica_memoria():
            m = re.match(r"^(?:Umbral ([A-Z][a-z]+)|([A-Z][a-z]+) Family|Alpha ([A-Z][a-z]+))$", en)
            if m:
                _NOMI_ANIIMO.add(m.group(1) or m.group(2) or m.group(3))
        _NOMI_ANIIMO.difference_update({"Egg", "Area", "Route", "Trial", "First", "Form", "Home", "Team", "Royal"})
    return _NOMI_ANIIMO


MODELLI = [
    (re.compile(r"^(" + "|".join(ELEMENTI) + r") Damage Boost$"), lambda m, gl, it: f"Aumento danni {ELEMENTI[m.group(1)]}"),
    (re.compile(r"^Damage Boost$"), lambda m, gl, it: "Aumento danni"),
    (re.compile(r"^Prismana ([A-Z][a-z]+)$"),
     lambda m, gl, it: f"{m.group(1)} Prismana" if m.group(1) in nomi_aniimo() else None),
    (re.compile(r"^(" + "|".join(ELEMENTI) + r")-type Resistance$"), lambda m, gl, it: f"Resistenza al tipo {ELEMENTI[m.group(1)]}"),
    (re.compile(r"^Pure Essence of (" + "|".join(ELEMENTI) + r")$"), lambda m, gl, it: f"Essenza pura di {ELEMENTI[m.group(1)]}"),
    (re.compile(r"^(" + "|".join(ELEMENTI) + r")-type Boost$"), lambda m, gl, it: f"Bonus tipo {ELEMENTI[m.group(1)]}"),
    (re.compile(r"^Essence of (" + "|".join(ELEMENTI) + r")$"), lambda m, gl, it: f"Essenza di {ELEMENTI[m.group(1)]}"),
    (re.compile(r"^(?:(Free|Paid|Premium) Companion Handbook|Companion Handbook (Free|Paid|Premium|premium))"
                r" (?:Level|Tier|level) (\d+)$"),
     lambda m, gl, it: "Manuale del compagno "
                       + {"Free": "gratuito", "Paid": "a pagamento"}.get(m.group(1) or m.group(2), "premium")
                       + f" - livello {m.group(3)}"),
    (re.compile(r"^Unlocks at (Kitchen|Crafting) Module Level (\d+)$"),
     lambda m, gl, it: f"Si sblocca al livello {m.group(2)} del Modulo "
                       + ("cucina" if m.group(1) == "Kitchen" else "di creazione")),
    (re.compile(r"^([A-Z][a-z]+)-Inspired Garden Fence$"),
     lambda m, gl, it: f"Recinto da giardino ispirato a {m.group(1)}" if m.group(1) in it else None),
    (re.compile(r"^(" + "|".join(ELEMENTI) + r")-type Damage$"),
     lambda m, gl, it: f"Danno di tipo {ELEMENTI[m.group(1)]}" if m.group(1) not in ("Magic", "Physical") else None),
    (re.compile(r"^(" + "|".join(ELEMENTI) + r")-type Aniimo$"),
     lambda m, gl, it: f"Aniimo di tipo {ELEMENTI[m.group(1)]}" if m.group(1) not in ("Magic", "Physical") else None),
    (re.compile(r"^Audience Member (\d+)$"), lambda m, gl, it: f"Spettatore {m.group(1)}"),
    (re.compile(r"^Encounter a Prismana Form ([A-Z][a-z]+)(\.?)$"),
     lambda m, gl, it: f"Incontra {_articolo_un(m.group(1))} {m.group(1)} in forma Prismana{m.group(2)}"),
    (re.compile(r"^Twine with ([A-Z][a-z]+) and approach ([A-Z][a-z]+)(\.?)$"),
     lambda m, gl, it: f"Intreccia con {m.group(1)} e avvicinati a {m.group(2)}{m.group(3)}"),
    (re.compile(r"^Own 1 Sparkling Prismana ([A-Z][a-z]+)(\.?)$"),
     lambda m, gl, it: f"Possiedi 1 {m.group(1)} Prismana scintillante{m.group(2)}"),
    (re.compile(r"^Increases gusto by (\d+)%$"), lambda m, gl, it: f"Aumenta Gusto del {m.group(1)}%"),
    (re.compile(r"^Damage Amp \+(\d+)%$"), lambda m, gl, it: f"Amplificazione danni +{m.group(1)}%"),
    # "Alpha Cheekie" / "Cheekie Alpha" -> "Cheekie Alfa" anche per nomi che il glossario non conosce
    # (solo se il nome e' gia' rimasto inglese nella traduzione: "Unknown Alpha" non e' un nome)
    (re.compile(r"^(?:(Alpha|Omega) ([A-Z][a-z]+)|([A-Z][a-z]+) (Alpha|Omega))$"),
     lambda m, gl, it: f"{m.group(2) or m.group(3)} {'Alfa' if (m.group(1) or m.group(4)) == 'Alpha' else 'Omega'}"
     if re.search(r"\b" + (m.group(2) or m.group(3)) + r"\b", it) else None),
    (re.compile(r"^(Illusory )?(" + "|".join(LIVELLI_CHIP) + r") (" + "|".join(TIPI_CHIP) + r") Chip$"),
     lambda m, gl, it: f"Chip {TIPI_CHIP[m.group(3)]} {LIVELLI_CHIP[m.group(2)]}" + (" illusorio" if m.group(1) else "")),
    (re.compile(r"^(" + "|".join(AGG_UOVA) + r") ([A-Z][A-Za-z]+) Egg$"), _uovo),
    (re.compile(r"^(" + "|".join(LIVELLI_CHIP) + r") (Pulse|Harmonic) Energy Stone$"),
     lambda m, gl, it: f"Pietra energetica {'pulsante' if m.group(2) == 'Pulse' else 'armonica'} {LIVELLI_CHIP[m.group(1)]}"),
]


def esegui(applica: bool):
    REGOLE.extend(regole_dinamiche())
    memoria = comune.carica_memoria()
    colture = 0
    for s_en in memoria:
        nuovo = nome_coltura(s_en)
        if nuovo and memoria[s_en] != nuovo:
            colture += 1
            if colture <= 5:
                print(f"coltura: {s_en!r} -> {nuovo!r}")
            memoria[s_en] = nuovo
    print(f"Colture uniformate: {colture}")
    # "Umbral X" da solo: il nome dell'Aniimo resta inglese, l'aggettivo va dopo.
    umbrali, glossario = 0, comune.carica(comune.GLOSSARIO, {})
    for s_en in memoria:
        m = re.match(r"^Umbral (?:(Alpha|Omega) )?([A-Z][a-z]+)$", s_en)
        nome = m and glossario.get(m.group(2), m.group(2))
        if m and m.group(1):
            nome += " Alfa" if m.group(1) == "Alpha" else " Omega"
        if m and memoria[s_en] != f"{nome} umbrale":
            memoria[s_en] = f"{nome} umbrale"
            umbrali += 1
    print(f"Varianti umbrali uniformate: {umbrali}")
    da_modello = 0
    for s_en in memoria:
        for rx, fn in MODELLI:
            m = rx.match(s_en)
            nuovo = m and fn(m, glossario, memoria[s_en])
            if nuovo and memoria[s_en] != nuovo:
                if da_modello < 8:
                    print(f"modello: {s_en!r} -> {nuovo!r}")
                memoria[s_en] = nuovo
                da_modello += 1
    print(f"Nomi da schema (danni, chip, uova): {da_modello}\n")
    corte = comune.carica(comune.MEMORIA_CORTA, {})
    limiti = accorcia.limiti_per_testo()
    conta, esempi, cambiate = Counter(), {}, 0
    compilate = [(en, re.compile(rx), sost) for en, rx, sost in REGOLE]
    for dest, tipo in ((memoria, "lunga"), (corte, "corta")):
        for s_en, s_it in list(dest.items()):
            nuovo = s_it
            for i, (en, rx, sost) in enumerate(compilate):
                if en in s_en and rx.search(nuovo):
                    prima = nuovo
                    nuovo = rx.sub(sost, nuovo)
                    if nuovo != prima:
                        conta[i] += 1
                        esempi.setdefault(i, (prima, nuovo))
            if nuovo == s_it:
                continue
            if comune.segnaposto(nuovo) != comune.segnaposto(s_en):
                continue
            if tipo == "corta" and len(nuovo.encode()) > limiti.get(s_en, 10**9):
                continue
            dest[s_en] = nuovo
            cambiate += 1
    for i, n in sorted(conta.items()):
        prima, dopo = esempi[i]
        print(f"[{n:5}] {REGOLE[i][1]}  ->  {REGOLE[i][2]}\n        es.: {prima[:90]!r}\n          -> {dopo[:90]!r}")
    print(f"\nFrasi modificate: {cambiate}" + ("" if applica else " (prova, niente salvato)"))
    if applica:
        comune.salva(comune.MEMORIA, memoria)
        comune.salva(comune.MEMORIA_CORTA, corte)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    esegui(len(sys.argv) > 1 and sys.argv[1] == "applica")
