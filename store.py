"""
Speichert die Bestell-Kategorien & Produkte als JSON-Datei - komplett ohne
Code-Änderung über Slash-Commands verwaltbar (siehe bot.py:
/kategorie-hinzufuegen, /kategorie-entfernen, /produkt-hinzufuegen, ...).

WICHTIG für Railway: der Dateipfad liegt im Container-Dateisystem. Ohne
"Volume" wird die Datei bei jedem Redeploy auf den Startzustand (siehe
DEFAULT_DATA unten) zurückgesetzt! Für dauerhafte Speicherung in Railway
unter dem Service "Settings -> Volumes" ein Volume anlegen und DATA_PATH per
Env-Variable auf den Mount-Pfad zeigen lassen (z.B. /data/categories.json).
"""

import json
import os
from pathlib import Path

DATA_PATH = Path(os.getenv("DATA_PATH", "data/categories.json"))

DEFAULT_DATA = {
    "fivem_bots": {
        "label": "FiveM Bots",
        "emoji": "🚓",
        "beschreibung": "Aufstellungsbot, Dashboard, Server-Setup & mehr für FiveM-Server.",
        "products": {
            "dashboard": {"emoji": "📊", "name": "Dashboard + Discord-Sync", "klein": 30, "big": 50, "beschreibung": "Web-Dashboard für euren Server, live mit Discord synchronisiert."},
            "aufstellung": {"emoji": "🤖", "name": "Aufstellungsbot", "klein": 27, "big": 45, "beschreibung": "Automatische Aufstellungs-/Abmeldungsverwaltung inkl. Sanktionssystem."},
            "serversetup": {"emoji": "🔧", "name": "Discord-Server-Setup (Rollen/Berechtigungen)", "klein": 15, "big": 25, "beschreibung": "Vollständige Rollen- & Berechtigungsstruktur für euren Discord."},
            "extras": {"emoji": "✨", "name": "Extras (Routenwache-Bot etc.)", "klein": 18, "big": 30, "beschreibung": "Zusatzsysteme wie Routenwache, Gangwar, Lager u.a. - nach Bedarf."},
            "komplett": {"emoji": "🎁", "name": "Komplettpaket (alle 4 Leistungen)", "klein": 84, "big": 140, "beschreibung": "Alle vier Leistungen im Bundle - spart gegenüber Einzelbuchung."},
        },
    },
}

TERMS = (
    "✅ **Garantie:** 30 Tage Funktionsgarantie ab Übergabe.\n"
    "✅ **Support:** 60 Tage kostenloser Support inklusive.\n"
    "ℹ️ Bezahlung ausschließlich in Euro."
)


def _save(data: dict):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load() -> dict:
    if not DATA_PATH.exists():
        _save(DEFAULT_DATA)
        return json.loads(json.dumps(DEFAULT_DATA))
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def format_price(value) -> str:
    return "auf Anfrage" if value is None else f"{value} €"


def slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")[:80] or "kategorie"


def add_category(label: str, emoji: str, beschreibung: str) -> str:
    data = load()
    key = slugify(label)
    base_key = key
    i = 2
    while key in data:
        key = f"{base_key}-{i}"
        i += 1
    data[key] = {"label": label, "emoji": emoji, "beschreibung": beschreibung, "products": {}}
    _save(data)
    return key


def remove_category(key: str) -> bool:
    data = load()
    if key not in data:
        return False
    del data[key]
    _save(data)
    return True


def add_product(category_key: str, name: str, emoji: str, klein, big, beschreibung: str) -> str | None:
    data = load()
    if category_key not in data:
        return None
    product_key = slugify(name)
    base_key = product_key
    i = 2
    while product_key in data[category_key]["products"]:
        product_key = f"{base_key}-{i}"
        i += 1
    data[category_key]["products"][product_key] = {
        "name": name, "emoji": emoji, "klein": klein, "big": big, "beschreibung": beschreibung,
    }
    _save(data)
    return product_key


def remove_product(category_key: str, product_key: str) -> bool:
    data = load()
    if category_key not in data or product_key not in data[category_key]["products"]:
        return False
    del data[category_key]["products"][product_key]
    _save(data)
    return True
