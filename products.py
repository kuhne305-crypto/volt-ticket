"""
Zentrale Preisliste - in drei Bestell-Kategorien gegliedert.

Einfach hier anpassen, wenn sich Preise/Produkte ändern - Ticket-Bot und
Preisliste-Kanal lesen automatisch aus diesem Dict.

Jedes Produkt hat:
    emoji        - wird im Dropdown & in Embeds angezeigt
    name         - Anzeigename
    big          - Preis "groß" (z.B. großer Server / große Community)
    klein        - Preis "klein" (z.B. kleiner Server / Einstieg)
    beschreibung - kurze Erklärung, erscheint im Ticket-Embed

Kategorien = das oberste Dropdown im Bestell-Ticket. Jede Kategorie hat
einen Anzeigenamen, ein Emoji und ein eigenes Produkte-Dict.
"""

# ---------------------------------------------------------------------------
# Kategorie 1: FiveM Bots  (bestehende, von dir bereits festgelegte Preise)
# ---------------------------------------------------------------------------
FIVEM_BOTS = {
    "dashboard": {
        "emoji": "📊",
        "name": "Dashboard + Discord-Sync",
        "big": 50,
        "klein": 30,
        "beschreibung": "Web-Dashboard für euren Server, live mit Discord synchronisiert.",
    },
    "aufstellung": {
        "emoji": "🤖",
        "name": "Aufstellungsbot",
        "big": 45,
        "klein": 27,
        "beschreibung": "Automatische Aufstellungs-/Abmeldungsverwaltung inkl. Sanktionssystem.",
    },
    "serversetup": {
        "emoji": "🔧",
        "name": "Discord-Server-Setup (Rollen/Berechtigungen)",
        "big": 25,
        "klein": 15,
        "beschreibung": "Vollständige Rollen- & Berechtigungsstruktur für euren Discord.",
    },
    "extras": {
        "emoji": "✨",
        "name": "Extras (Routenwache-Bot etc.)",
        "big": 30,
        "klein": 18,
        "beschreibung": "Zusatzsysteme wie Routenwache, Gangwar, Lager u.a. - nach Bedarf.",
    },
    "komplett": {
        "emoji": "🎁",
        "name": "Komplettpaket (alle 4 Leistungen)",
        "big": 140,
        "klein": 84,
        "beschreibung": "Alle vier Leistungen im Bundle - spart gegenüber Einzelbuchung.",
    },
}
FIVEM_HOSTING = {"big": 10, "klein": 6}  # € / Monat, nur beim Komplettpaket relevant

# ---------------------------------------------------------------------------
# Kategorie 2: Discord Server (Aufbau/Design eines kompletten Servers)
# TODO: echte Preise eintragen - aktuell nur Platzhalter!
# ---------------------------------------------------------------------------
DISCORD_SERVER = {
    "basic": {
        "emoji": "🥉",
        "name": "Basic Server-Aufbau",
        "big": None,    # TODO: Preis eintragen
        "klein": None,  # TODO: Preis eintragen
        "beschreibung": "Grundstruktur: Kategorien, Kanäle, Basis-Rollen & Berechtigungen.",
    },
    "premium": {
        "emoji": "🥈",
        "name": "Premium Server-Aufbau",
        "big": None,    # TODO: Preis eintragen
        "klein": None,  # TODO: Preis eintragen
        "beschreibung": "Wie Basic, zusätzlich Design/Banner, Emojis, Willkommens-System.",
    },
    "komplett": {
        "emoji": "🏆",
        "name": "Komplett-Server (inkl. Bots & Design)",
        "big": None,    # TODO: Preis eintragen
        "klein": None,  # TODO: Preis eintragen
        "beschreibung": "Kompletter Server inkl. passender Bots, Design und Struktur.",
    },
}

# ---------------------------------------------------------------------------
# Kategorie 3: Discord Custom Bots (individuelle Bot-Entwicklung)
# TODO: echte Preise eintragen - aktuell nur Platzhalter!
# ---------------------------------------------------------------------------
DISCORD_CUSTOM_BOTS = {
    "einfach": {
        "emoji": "🧩",
        "name": "Einfacher Custom-Bot",
        "big": None,    # TODO: Preis eintragen
        "klein": None,  # TODO: Preis eintragen
        "beschreibung": "Kleiner Bot mit 1-2 Funktionen (z.B. ein einzelnes System).",
    },
    "mittel": {
        "emoji": "⚙️",
        "name": "Custom-Bot mittlerer Umfang",
        "big": None,    # TODO: Preis eintragen
        "klein": None,  # TODO: Preis eintragen
        "beschreibung": "Mehrere zusammenhängende Funktionen/Systeme in einem Bot.",
    },
    "individuell": {
        "emoji": "🛠️",
        "name": "Individuelle Anfrage",
        "big": None,
        "klein": None,
        "beschreibung": "Passt keine der Optionen? Beschreib uns im Ticket, was du brauchst.",
    },
}

# ---------------------------------------------------------------------------
# Kategorien-Übersicht fürs oberste Bestell-Dropdown
# ---------------------------------------------------------------------------
CATEGORIES = {
    "fivem_bots": {
        "label": "FiveM Bots",
        "emoji": "🚓",
        "beschreibung": "Aufstellungsbot, Dashboard, Server-Setup & mehr für FiveM-Server.",
        "products": FIVEM_BOTS,
    },
    "discord_server": {
        "label": "Discord Server",
        "emoji": "🖥️",
        "beschreibung": "Kompletter Aufbau/Design eines Discord-Servers.",
        "products": DISCORD_SERVER,
    },
    "discord_custom_bots": {
        "label": "Discord Custom Bots",
        "emoji": "🤖",
        "beschreibung": "Individuell entwickelte Discord-Bots nach deinen Wünschen.",
        "products": DISCORD_CUSTOM_BOTS,
    },
}

TERMS = (
    "✅ **Garantie:** 30 Tage Funktionsgarantie ab Übergabe.\n"
    "✅ **Support:** 60 Tage kostenloser Support inklusive.\n"
    "💾 **Hosting:** monatliche Gebühr für laufenden Serverbetrieb, sofern zutreffend.\n"
    "ℹ️ Bezahlung ausschließlich in Euro."
)


def format_price(value) -> str:
    """None -> 'auf Anfrage', sonst '12 €'."""
    if value is None:
        return "auf Anfrage"
    return f"{value} €"
