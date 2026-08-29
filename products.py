"""Zentrale Preisliste. Hier einfach anpassen, wenn sich Preise ändern -
der Rest des Bots liest automatisch aus diesem Dict."""

PRODUCTS = {
    "dashboard": {
        "emoji": "📊",
        "name": "Dashboard + Discord-Sync",
        "big": 50,
        "klein": 30,
    },
    "aufstellung": {
        "emoji": "🤖",
        "name": "Aufstellungsbot",
        "big": 45,
        "klein": 27,
    },
    "serversetup": {
        "emoji": "🔧",
        "name": "Discord-Server-Setup (Rollen/Berechtigungen)",
        "big": 25,
        "klein": 15,
    },
    "extras": {
        "emoji": "✨",
        "name": "Extras (Routenwache-Bot etc.)",
        "big": 30,
        "klein": 18,
    },
    "komplett": {
        "emoji": "🎁",
        "name": "Komplettpaket (alle 4 Leistungen)",
        "big": 140,
        "klein": 84,
    },
}

HOSTING = {"big": 10, "klein": 6}  # € / Monat, nur relevant beim Komplettpaket

TERMS = (
    "✅ **Garantie:** 30 Tage Funktionsgarantie ab Übergabe.\n"
    "✅ **Support:** 60 Tage kostenloser Support inklusive.\n"
    "💾 **Hosting:** monatliche Gebühr für laufenden Serverbetrieb (siehe oben).\n"
    "ℹ️ Bezahlung ausschließlich in Euro (OOC)."
)
