"""
VOLT TICKETS
============
"Tickets. Orders. Done right." - VOLT Discord Solutions

Baut das Bestell-Panel mit zweistufigem Dropdown auf:

    1. Kategorie wählen  -> FiveM Bots / Discord Server / Discord Custom Bots
    2. Produkt wählen     -> abhängig von Kategorie, Preise aus products.py

Danach wird automatisch ein privates Ticket-Kanal erstellt.

WICHTIGER FIX gegenüber der alten Version:
-------------------------------------------
Der alte Bot hat beim Status-Wechsel (offen -> in Bearbeitung -> geschlossen)
`channel.edit(category=..., sync_permissions=True)` verwendet. `sync_permissions`
übernimmt IMMER die Standard-Berechtigungen der Ziel-Kategorie und überschreibt
dabei die eigens gesetzten Overwrites (privat: nur Ersteller + Staff) mit den
(oft offenen) Kategorie-Defaults - dadurch konnten plötzlich alle Mitglieder
das Ticket sehen.

Diese Version nutzt IMMER explizite `overwrites=` beim Erstellen UND bei jedem
Status-Wechsel (set_ticket_status). Es wird nirgends `sync_permissions=True`
verwendet. Die Sichtbarkeit ist dadurch bei jedem Schritt garantiert:
    @everyone         -> kein Zugriff
    Ticket-Ersteller   -> sehen + schreiben (read_message_history immer erlaubt)
    Staff-Rollen       -> sehen + schreiben + verwalten

WEITERER FIX (siehe /setup-tickets):
-------------------------------------------
Interaction-Commands müssen Discord innerhalb von 3 Sekunden bestätigen
(defer oder send_message), sonst zeigt Discord "Die Anwendung reagiert
nicht". `/setup-tickets` hat vorher erst das Panel gepostet (Datei-Upload)
und DANACH erst geantwortet - bei Verzögerung (Cold Start, Netzwerk) war
die Interaction dann schon abgelaufen. Jetzt wird zuerst `defer()`t und erst
danach gearbeitet, genau wie es `create_ticket()` in dieser Datei schon
immer richtig gemacht hat. Zusätzlich gibt es jetzt einen globalen
Error-Handler, der echte Fehler sichtbar macht statt sie zu verschlucken.
"""

import os
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from products import CATEGORIES, format_price, TERMS
import branding
from branding import VOLT_RED

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("volt-tickets")

TOKEN = os.getenv("TICKET_DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or 0)

STAFF_ROLE_NAMES = [n.strip() for n in os.getenv("STAFF_ROLE_NAMES", "Admin,Moderator,Supporter").split(",") if n.strip()]
TICKETS_OPEN_CATEGORY = os.getenv("TICKETS_OPEN_CATEGORY", "🎫 TICKETS")
TICKETS_CLOSED_CATEGORY = os.getenv("TICKETS_CLOSED_CATEGORY", "🗄️ TICKET-ARCHIV")
TICKET_LOG_CHANNEL = os.getenv("TICKET_LOG_CHANNEL", "ticket-logs")

intents = discord.Intents.default()
intents.members = True


class VoltTickets(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!ticket-", intents=intents)

    async def setup_hook(self):
        self.add_view(OrderPanelView())  # persistent (überlebt Restarts)
        if GUILD_ID:
            guild_obj = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
        else:
            await self.tree.sync()


bot = VoltTickets()


# --------------------------------------------------------------------------
# Helfer: Berechtigungen & Kategorien
# --------------------------------------------------------------------------

def staff_roles(guild: discord.Guild) -> list[discord.Role]:
    roles = []
    for name in STAFF_ROLE_NAMES:
        role = discord.utils.get(guild.roles, name=name)
        if role:
            roles.append(role)
    return roles


def build_ticket_overwrites(guild: discord.Guild, creator: discord.Member, *, can_write: bool = True):
    """Baut die Overwrites, die IMMER (bei Erstellung UND jedem Status-Wechsel)
    explizit gesetzt werden - niemals über sync_permissions."""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        creator: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=can_write,
            read_message_history=True,
            attach_files=True,
        ),
    }
    for role in staff_roles(guild):
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
        )
    return overwrites


async def ensure_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    cat = discord.utils.get(guild.categories, name=name)
    if cat is None:
        # Kategorie selbst bleibt privat per Default - einzelne Ticket-Kanäle
        # bekommen trotzdem IMMER ihre eigenen Overwrites (s.u.), damit nie
        # versehentlich über die Kategorie synchronisiert wird.
        cat = await guild.create_category(name)
    return cat


async def set_ticket_status(channel: discord.TextChannel, status: str, creator: discord.Member):
    """status: 'open' | 'closed'. Setzt IMMER explizite Overwrites, nie sync_permissions."""
    guild = channel.guild
    if status == "open":
        category = await ensure_category(guild, TICKETS_OPEN_CATEGORY)
        overwrites = build_ticket_overwrites(guild, creator, can_write=True)
    elif status == "closed":
        category = await ensure_category(guild, TICKETS_CLOSED_CATEGORY)
        overwrites = build_ticket_overwrites(guild, creator, can_write=False)
    else:
        raise ValueError("Unbekannter Status: " + status)

    # sync_permissions bewusst NICHT gesetzt (Default: False) -> die Kategorie
    # kann die hier gesetzten Overwrites nicht überschreiben.
    await channel.edit(category=category, overwrites=overwrites, reason=f"Ticket-Status: {status}")


# --------------------------------------------------------------------------
# UI: Bestell-Panel (2-stufiges Dropdown) + Ticket-Ansicht
# --------------------------------------------------------------------------

class ProductSelect(discord.ui.Select):
    def __init__(self, category_key: str):
        category = CATEGORIES[category_key]
        options = [
            discord.SelectOption(
                label=data["name"],
                value=key,
                emoji=data.get("emoji"),
                description=f'{format_price(data["klein"])} / {format_price(data["big"])}',
            )
            for key, data in category["products"].items()
        ]
        super().__init__(placeholder="2️⃣ Produkt auswählen...", options=options, custom_id=f"product_select:{category_key}")
        self.category_key = category_key

    async def callback(self, interaction: discord.Interaction):
        product_key = self.values[0]
        await create_ticket(interaction, self.category_key, product_key)


class ProductSelectView(discord.ui.View):
    def __init__(self, category_key: str):
        super().__init__(timeout=180)
        self.add_item(ProductSelect(category_key))


class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=data["label"], value=key, emoji=data.get("emoji"), description=data["beschreibung"][:100])
            for key, data in CATEGORIES.items()
        ]
        super().__init__(placeholder="1️⃣ Kategorie auswählen...", options=options, custom_id="order_category_select")

    async def callback(self, interaction: discord.Interaction):
        category_key = self.values[0]
        await interaction.response.send_message(
            f"Alles klar - wähle jetzt ein Produkt aus **{CATEGORIES[category_key]['label']}**:",
            view=ProductSelectView(category_key),
            ephemeral=True,
        )


class OrderPanelView(discord.ui.View):
    """Persistent View - läuft nicht ab, überlebt Bot-Neustarts (custom_id fest)."""

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CategorySelect())


class TicketControlView(discord.ui.View):
    """Buttons im Ticket-Kanal selbst: Schließen / Wieder öffnen."""

    def __init__(self, creator_id: int):
        super().__init__(timeout=None)
        self.creator_id = creator_id

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.danger, custom_id="ticket_close", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.id == self.creator_id or any(r.name in STAFF_ROLE_NAMES for r in interaction.user.roles)):
            return await interaction.response.send_message("❌ Das darfst nur der Ersteller oder das Team.", ephemeral=True)
        creator = interaction.guild.get_member(self.creator_id)
        await set_ticket_status(interaction.channel, "closed", creator)
        await interaction.response.send_message("🔒 Ticket geschlossen. Nur noch das Team kann hier schreiben.", view=None)

    @discord.ui.button(label="Wieder öffnen", style=discord.ButtonStyle.success, custom_id="ticket_reopen", emoji="🔓")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.name in STAFF_ROLE_NAMES for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur das Team kann Tickets wieder öffnen.", ephemeral=True)
        creator = interaction.guild.get_member(self.creator_id)
        await set_ticket_status(interaction.channel, "open", creator)
        await interaction.response.send_message("🔓 Ticket wieder geöffnet.", view=None)


async def create_ticket(interaction: discord.Interaction, category_key: str, product_key: str):
    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = interaction.guild
    creator = interaction.user
    category_data = CATEGORIES[category_key]
    product = category_data["products"][product_key]

    existing = discord.utils.get(guild.text_channels, name=f"ticket-{creator.name}".lower()[:90])
    if existing:
        return await interaction.followup.send(f"Du hast bereits ein offenes Ticket: {existing.mention}", ephemeral=True)

    ticket_category = await ensure_category(guild, TICKETS_OPEN_CATEGORY)
    overwrites = build_ticket_overwrites(guild, creator, can_write=True)

    channel = await guild.create_text_channel(
        name=f"ticket-{creator.name}"[:90],
        category=ticket_category,
        overwrites=overwrites,
        reason=f"Neues Bestell-Ticket von {creator}",
        topic=f"Ticket von {creator.id} | Kategorie: {category_key} | Produkt: {product_key}",
    )

    embed = discord.Embed(
        title=f"{product.get('emoji', '🛒')} Neue Bestellung: {product['name']}",
        description=product.get("beschreibung", ""),
        color=VOLT_RED,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Kategorie", value=category_data["label"], inline=True)
    embed.add_field(name="Preis (klein)", value=format_price(product["klein"]), inline=True)
    embed.add_field(name="Preis (groß)", value=format_price(product["big"]), inline=True)
    embed.add_field(name="Bedingungen", value=TERMS, inline=False)
    embed.set_thumbnail(url=f"attachment://{os.path.basename(branding.ICON)}")
    embed.set_footer(text=f"Erstellt von {creator} • {branding.TICKETS_FOOTER}", icon_url=creator.display_avatar.url)

    mentions = " ".join(r.mention for r in staff_roles(guild)) or ""
    await channel.send(
        content=f"{creator.mention} {mentions}".strip(),
        embed=embed,
        file=branding.banner_file(branding.ICON),
        view=TicketControlView(creator.id),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )

    log_channel = discord.utils.get(guild.text_channels, name=TICKET_LOG_CHANNEL)
    if log_channel:
        await log_channel.send(f"🎫 Neues Ticket {channel.mention} von {creator.mention} ({category_data['label']} → {product['name']})")

    await interaction.followup.send(f"✅ Dein Ticket wurde erstellt: {channel.mention}", ephemeral=True)


# --------------------------------------------------------------------------
# Slash-Commands
# --------------------------------------------------------------------------

@bot.tree.command(name="setup-tickets", description="[Admin] Postet das Bestell-Panel in diesen Kanal")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    # WICHTIG: zuerst deferren, dann erst den (potenziell langsamen) Datei-Upload
    # machen - sonst läuft die Interaction ab -> "Die Anwendung reagiert nicht".
    await interaction.response.defer(ephemeral=True, thinking=True)

    embed = discord.Embed(
        title="⚡ VOLT TICKETS - Bestellung starten",
        description=(
            "Wähle unten zuerst deine **Kategorie**, danach das gewünschte **Produkt**.\n"
            "Es wird automatisch ein privates Ticket für dich erstellt - "
            "nur du und unser Team können es sehen."
        ),
        color=VOLT_RED,
    )
    for data in CATEGORIES.values():
        embed.add_field(name=f"{data.get('emoji', '')} {data['label']}", value=data["beschreibung"], inline=False)
    embed, file = branding.with_tickets_banner(embed)
    await interaction.channel.send(embed=embed, file=file, view=OrderPanelView())
    await interaction.followup.send("✅ Bestell-Panel gepostet.", ephemeral=True)


@bot.tree.command(name="ticket-add", description="[Team] Fügt eine Person zu diesem Ticket hinzu")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_add(interaction: discord.Interaction, member: discord.Member):
    await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
    await interaction.response.send_message(f"➕ {member.mention} wurde zum Ticket hinzugefügt.")


@bot.tree.command(name="ticket-remove", description="[Team] Entfernt eine Person aus diesem Ticket")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_remove(interaction: discord.Interaction, member: discord.Member):
    await interaction.channel.set_permissions(member, overwrite=None)
    await interaction.response.send_message(f"➖ {member.mention} wurde aus dem Ticket entfernt.")


# -------------------------------------------------------- globaler Error-Handler
# Vorher gab es HIER GAR KEINEN Handler - Fehler (z.B. abgelaufene Interaction,
# fehlende Berechtigung, fehlende Datei) wurden einfach verschluckt und man
# sah nur Discords generisches "Die Anwendung reagiert nicht" / gar nichts.

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Dir fehlt die nötige Berechtigung für diesen Befehl."
    else:
        log.exception("Fehler in Ticket-Command", exc_info=error)
        original = getattr(error, "original", error)
        short_error = f"{type(original).__name__}: {original}"[:1500]
        msg = f"❌ Es ist ein Fehler aufgetreten:\n```\n{short_error}\n```"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        # Interaction ist bereits abgelaufen -> wenigstens ins Log schreiben
        log.warning("Konnte Fehlermeldung nicht mehr an Discord senden (Interaction abgelaufen).")


@bot.event
async def on_ready():
    log.info("VOLT TICKETS eingeloggt als %s", bot.user)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Tickets. Orders. Done right. ⚡"))


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN / TICKET_DISCORD_TOKEN fehlt in der .env Datei!")
    bot.run(TOKEN)
