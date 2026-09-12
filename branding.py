"""
VOLT - zentrales Branding.

Farben & Assets an einer Stelle, damit alle drei Bots (Setup/Mod/Tickets)
konsistent aussehen. Diese Datei liegt identisch in jedem der drei
Bot-Ordner (volt-setup/, volt-mod/, volt-tickets/), da jeder Ordner ein
eigenständiges Railway-Deployment ist.
"""

import os
import discord

VOLT_RED = discord.Color.from_rgb(224, 17, 17)
VOLT_BLACK = discord.Color.from_rgb(10, 10, 10)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

ICON = os.path.join(ASSETS_DIR, "volt_icon.png")
MAIN_BANNER = os.path.join(ASSETS_DIR, "volt_main_banner.png")        # nur in volt-setup vorhanden
ADMIN_BANNER = os.path.join(ASSETS_DIR, "volt_admin_banner.png")      # nur in volt-mod vorhanden
TICKETS_BANNER = os.path.join(ASSETS_DIR, "volt_tickets_banner.png")  # nur in volt-tickets vorhanden

ADMIN_FOOTER = "VOLT MOD • Server Protection. Full Control."
TICKETS_FOOTER = "VOLT TICKETS • Tickets. Orders. Done right."
MAIN_FOOTER = "VOLT Discord Solutions"


def banner_file(path: str) -> discord.File:
    return discord.File(path, filename=os.path.basename(path))


def with_banner(embed: discord.Embed, path: str, footer: str | None = None) -> tuple[discord.Embed, discord.File]:
    file = banner_file(path)
    embed.set_image(url=f"attachment://{os.path.basename(path)}")
    if footer and not embed.footer:
        embed.set_footer(text=footer)
    return embed, file


def with_icon_thumbnail(embed: discord.Embed) -> tuple[discord.Embed, discord.File]:
    file = banner_file(ICON)
    embed.set_thumbnail(url=f"attachment://{os.path.basename(ICON)}")
    return embed, file


def quiet_discord_logs():
    """Reduziert das Grundrauschen von discord.py in der Railway-Konsole -
    nur eigene INFO-Logs bleiben sichtbar, discord.py selbst nur WARNING+."""
    import logging
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
