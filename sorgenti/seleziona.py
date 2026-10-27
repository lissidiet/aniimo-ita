"""Sceglie un lotto di testi (unici) da tradurre e lo scrive in dati/lotti/<nome>.json.

Uso:  python seleziona.py iniziale      -> schermate iniziali, menu, impostazioni, creazione personaggio
      python seleziona.py tutto         -> tutti i testi non ancora tradotti
Il lotto e' una lista di {"en": testo}; chi traduce aggiunge "it".
"""
import re
import sys
import comune

# Aree della parte iniziale del gioco, per parole chiave inglesi.
AREE_INIZIALI = [
    r"\b(log ?in|log out|sign in|servers?|account|privacy|agreement|terms of|announcements?)\b",
    r"\b(start game|enter game|press any|tap to|anywhere|loading|download|network|connect|reconnect|retry|queue)\b",
    r"\b(settings?|graphics?|resolution|display|full ?screen|frame rate|fps|v-?sync|quality|shadows?|textures?|anti-?aliasing|bloom|motion blur|brightness|gamma|rendering|dlss|upscaling)\b",
    r"\b(audio|volume|sound|music|voice|language|subtitles?|vibration|sensitivity|mouse|keyboard|controller|gamepad|key ?bindings?|shortcuts?|invert|camera)\b",
    r"^(confirm|cancel|ok|yes|no|back|close|skip|continue|exit|quit|save|apply|reset|default|restore|select|claim|unlock|locked|next|previous|done|got it|details|help)[.!]?$",
    r"\b(create character|appearance|face|eyes?|eyebrows?|nose|lips?|mouth|cheeks?|jaw|chin|ears?|hair|skin|body|height|makeup|pupils?|iris|eyelids?|eyelashes|forehead|presets?|nickname)\b",
    r"\b(tutorial|prologue|how to)\b",
    r"^(bag|backpack|inventory|map|quests?|team|shop|mail|friends|achievements?|events?|rewards?|menu|profile|level|settings)$",
]


def main(nome: str):
    en = comune.carica(comune.EN_JSON)["testi"]
    memoria = comune.carica_memoria()
    unici = sorted({s for s in en.values() if s.strip() and s not in memoria})
    if nome == "iniziale":
        rx = re.compile("|".join(f"(?:{a})" for a in AREE_INIZIALI), re.I)
        unici = [s for s in unici if len(s) <= 36 and "\n" not in s and rx.search(s)]
    lotto = [{"en": s} for s in sorted(unici, key=lambda s: (len(s), s))]
    out = comune.DATI / "lotti" / f"{nome}.json"
    comune.salva(out, lotto)
    print(f"{len(lotto)} testi unici -> {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1] if len(sys.argv) > 1 else "iniziale")
