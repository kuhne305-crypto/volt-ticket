"""
VOLT TICKETS
============
"Tickets. Orders. Done right." - VOLT Discord Solutions

Bestell-Flow: ein persistenter Button "🛒 Bestellung starten" postet bei
jedem Klick ein FRISCH aus dem Store (store.py) gebautes Kategorie-Dropdown -
neue Kategorien/Produkte, die per Slash-Command hinzugefügt wurden, sind
dadurch SOFORT live, ohne den Bot neu zu starten oder das Panel neu zu posten.

Privacy-Fix: set_ticket_status() setzt bei jedem Status-Wechsel IMMER
explizite overwrites= (nie sync_permissions=True) - ein Ticket sehen
ausschließlich: Ersteller, Rollen aus STAFF_ROLE_NAMES, der Bot selbst.
"""

import os
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import store
import branding
from branding import VOLT_RED

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
branding.quiet_discord_logs()
log = logging.getLogger("volt-tickets")

TOKEN = os.getenv("DISCORD_TOKEN")
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
        self.add_view(OrderButtonView())
        if GUILD_ID:
            guild_obj = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
        else:
            await self.tree.sync()


bot = VoltTickets()


def staff_roles(guild: discord.Guild) -> list[discord.Role]:
    return [r for r in (discord.utils.get(guild.roles, name=n) for n in STAFF_ROLE_NAMES) if r]


def is_staff(member: discord.Member) -> bool:
    return any(r.name in STAFF_ROLE_NAMES for r in member.roles) or member.guild_permissions.administrator


def build_ticket_overwrites(guild: discord.Guild, creator: discord.Member, *, can_write: bool = True):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        creator: discord.PermissionOverwrite(view_channel=True, send_messages=can_write, read_message_history=True, attach_files=True),
    }
    for role in staff_roles(guild):
        overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)
    return overwrites


async def ensure_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    cat = discord.utils.get(guild.categories, name=name)
    if cat is None:
        cat = await guild.create_category(name)
    return cat


async def set_ticket_status(channel: discord.TextChannel, status: str, creator: discord.Member):
    """status: 'open' | 'closed'. IMMER explizite Overwrites, NIE sync_permissions."""
    guild = channel.guild
    if status == "open":
        category = await ensure_category(guild, TICKETS_OPEN_CATEGORY)
        overwrites = build_ticket_overwrites(guild, creator, can_write=True)
    elif status == "closed":
        category = await ensure_category(guild, TICKETS_CLOSED_CATEGORY)
        overwrites = build_ticket_overwrites(guild, creator, can_write=False)
    else:
        raise ValueError("Unbekannter Status: " + status)
    await channel.edit(category=category, overwrites=overwrites, reason=f"Ticket-Status: {status}")


@bot.event
async def on_ready():
    log.info("VOLT TICKETS eingeloggt als %s", bot.user)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Tickets. Orders. Done right. ⚡"))


# ---------------------------------------------------------------------------
# UI: Bestell-Button -> live gebaute Dropdowns -> Ticket
# ---------------------------------------------------------------------------

class ProductSelect(discord.ui.Select):
    def __init__(self, category_key: str, category: dict):
        options = [
            discord.SelectOption(
                label=p["name"], value=key, emoji=p.get("emoji") or None,
                description=f'{store.format_price(p["klein"])} / {store.format_price(p["big"])}'[:100],
            )
            for key, p in category["products"].items()
        ][:25]
        super().__init__(placeholder="2️⃣ Produkt auswählen...", options=options or [discord.SelectOption(label="Keine Produkte hinterlegt", value="none")])
        self.category_key = category_key

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("In dieser Kategorie sind noch keine Produkte hinterlegt.", ephemeral=True)
        await create_ticket(interaction, self.category_key, self.values[0])


class ProductSelectView(discord.ui.View):
    def __init__(self, category_key: str, category: dict):
        super().__init__(timeout=180)
        self.add_item(ProductSelect(category_key, category))


class CategorySelect(discord.ui.Select):
    def __init__(self, categories: dict):
        options = [
            discord.SelectOption(label=data["label"], value=key, emoji=data.get("emoji") or None, description=data["beschreibung"][:100])
            for key, data in categories.items()
        ][:25]
        super().__init__(placeholder="1️⃣ Kategorie auswählen...", options=options or [discord.SelectOption(label="Noch keine Kategorien angelegt", value="none")])
        self.categories = categories

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("Es ist noch keine Kategorie hinterlegt.", ephemeral=True)
        category_key = self.values[0]
        category = self.categories[category_key]
        await interaction.response.send_message(
            f"Alles klar - wähle jetzt ein Produkt aus **{category['label']}**:",
            view=ProductSelectView(category_key, category),
            ephemeral=True,
        )


class CategorySelectView(discord.ui.View):
    def __init__(self, categories: dict):
        super().__init__(timeout=180)
        self.add_item(CategorySelect(categories))


class OrderButtonView(discord.ui.View):
    """Persistenter Button - Klick baut die Auswahl FRISCH aus dem Store,
    dadurch sind neu hinzugefügte Kategorien/Produkte sofort live."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bestellung starten", style=discord.ButtonStyle.success, emoji="🛒", custom_id="volt_order_button")
    async def start_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        categories = store.load()
        if not categories:
            return await interaction.response.send_message("Aktuell ist noch keine Kategorie hinterlegt. Ein Admin kann das mit `/kategorie-hinzufuegen` anlegen.", ephemeral=True)
        await interaction.response.send_message("1️⃣ Wähle deine Kategorie:", view=CategorySelectView(categories), ephemeral=True)


async def create_ticket(interaction: discord.Interaction, category_key: str, product_key: str):
    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = interaction.guild
    creator = interaction.user
    categories = store.load()
    category = categories.get(category_key)
    product = category["products"].get(product_key) if category else None
    if not category or not product:
        return await interaction.followup.send("❌ Dieses Produkt existiert nicht mehr - bitte erneut versuchen.", ephemeral=True)

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
    embed.add_field(name="Kategorie", value=category["label"], inline=True)
    embed.add_field(name="Preis (klein)", value=store.format_price(product["klein"]), inline=True)
    embed.add_field(name="Preis (groß)", value=store.format_price(product["big"]), inline=True)
    embed.add_field(name="Bedingungen", value=store.TERMS, inline=False)
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
        await log_channel.send(f"🎫 Neues Ticket {channel.mention} von {creator.mention} ({category['label']} → {product['name']})")

    await interaction.followup.send(f"✅ Dein Ticket wurde erstellt: {channel.mention}", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self, creator_id: int):
        super().__init__(timeout=None)
        self.creator_id = creator_id

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.danger, custom_id="ticket_close", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.id == self.creator_id or is_staff(interaction.user)):
            return await interaction.response.send_message("❌ Das darfst nur der Ersteller oder das Team.", ephemeral=True)
        creator = interaction.guild.get_member(self.creator_id)
        await set_ticket_status(interaction.channel, "closed", creator)
        await interaction.response.send_message("🔒 Ticket geschlossen. Nur noch das Team kann hier schreiben.", view=None)

    @discord.ui.button(label="Wieder öffnen", style=discord.ButtonStyle.success, custom_id="ticket_reopen", emoji="🔓")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Nur das Team kann Tickets wieder öffnen.", ephemeral=True)
        creator = interaction.guild.get_member(self.creator_id)
        await set_ticket_status(interaction.channel, "open", creator)
        await interaction.response.send_message("🔓 Ticket wieder geöffnet.", view=None)


# ---------------------------------------------------------------------------
# Slash-Commands: Panel + Kategorien/Produkte live verwalten
# ---------------------------------------------------------------------------

@bot.tree.command(name="setup-tickets", description="[Admin] Postet den Bestell-Button in diesen Kanal (einmalig nötig)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ VOLT TICKETS - Bestellung starten",
        description=(
            "Klick auf den Button, um eine Bestellung zu starten.\n"
            "Du wählst dann Schritt für Schritt Kategorie & Produkt - "
            "es wird automatisch ein privates Ticket für dich erstellt."
        ),
        color=VOLT_RED,
    )
    embed, file = branding.with_banner(embed, branding.TICKETS_BANNER, branding.TICKETS_FOOTER)
    await interaction.channel.send(embed=embed, file=file, view=OrderButtonView())
    await interaction.response.send_message("✅ Bestell-Panel gepostet. Kategorien/Produkte kannst du jederzeit per Command ändern - das Panel muss dafür NICHT neu gepostet werden.", ephemeral=True)


async def category_autocomplete(interaction: discord.Interaction, current: str):
    data = store.load()
    return [app_commands.Choice(name=f"{v['label']}", value=k) for k, v in data.items() if current.lower() in v["label"].lower() or current.lower() in k][:25]


async def product_autocomplete(interaction: discord.Interaction, current: str):
    data = store.load()
    category_key = interaction.namespace.kategorie
    if not category_key or category_key not in data:
        return []
    return [app_commands.Choice(name=p["name"], value=k) for k, p in data[category_key]["products"].items() if current.lower() in p["name"].lower()][:25]


@bot.tree.command(name="kategorie-hinzufuegen", description="[Admin] Legt eine neue Bestell-Kategorie an (z.B. Fraktionsboards, Dashboards)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(name="Anzeigename der Kategorie", emoji="Ein Emoji dafür", beschreibung="Kurze Beschreibung fürs Dropdown")
async def kategorie_hinzufuegen(interaction: discord.Interaction, name: str, emoji: str, beschreibung: str):
    key = store.add_category(name, emoji, beschreibung)
    await interaction.response.send_message(f"✅ Kategorie **{emoji} {name}** angelegt (`{key}`). Ist ab sofort im Bestell-Button sichtbar.", ephemeral=True)


@bot.tree.command(name="kategorie-entfernen", description="[Admin] Entfernt eine Bestell-Kategorie (inkl. aller ihrer Produkte!)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.autocomplete(kategorie=category_autocomplete)
async def kategorie_entfernen(interaction: discord.Interaction, kategorie: str):
    ok = store.remove_category(kategorie)
    if ok:
        await interaction.response.send_message(f"🗑️ Kategorie `{kategorie}` (inkl. Produkte) entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Diese Kategorie wurde nicht gefunden.", ephemeral=True)


@bot.tree.command(name="kategorien-liste", description="Zeigt alle aktuellen Bestell-Kategorien")
async def kategorien_liste(interaction: discord.Interaction):
    data = store.load()
    if not data:
        return await interaction.response.send_message("Aktuell ist keine Kategorie hinterlegt.", ephemeral=True)
    embed = discord.Embed(title="📋 Bestell-Kategorien", color=VOLT_RED)
    for key, v in data.items():
        embed.add_field(name=f"{v.get('emoji','')} {v['label']} (`{key}`)", value=f"{v['beschreibung']}\n{len(v['products'])} Produkt(e)", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="produkt-hinzufuegen", description="[Admin] Fügt ein Produkt zu einer Kategorie hinzu")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.autocomplete(kategorie=category_autocomplete)
@app_commands.describe(
    kategorie="In welche Kategorie?", name="Produktname", emoji="Ein Emoji dafür",
    preis_klein="Preis 'klein' in Euro (leer lassen = auf Anfrage)",
    preis_gross="Preis 'groß' in Euro (leer lassen = auf Anfrage)",
    beschreibung="Kurze Beschreibung, erscheint im Ticket",
)
async def produkt_hinzufuegen(interaction: discord.Interaction, kategorie: str, name: str, emoji: str, beschreibung: str, preis_klein: int = None, preis_gross: int = None):
    key = store.add_product(kategorie, name, emoji, preis_klein, preis_gross, beschreibung)
    if key is None:
        return await interaction.response.send_message("❌ Diese Kategorie wurde nicht gefunden.", ephemeral=True)
    await interaction.response.send_message(f"✅ Produkt **{emoji} {name}** zu `{kategorie}` hinzugefügt ({store.format_price(preis_klein)} / {store.format_price(preis_gross)}).", ephemeral=True)


@bot.tree.command(name="produkt-entfernen", description="[Admin] Entfernt ein Produkt aus einer Kategorie")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.autocomplete(kategorie=category_autocomplete, produkt=product_autocomplete)
async def produkt_entfernen(interaction: discord.Interaction, kategorie: str, produkt: str):
    ok = store.remove_product(kategorie, produkt)
    if ok:
        await interaction.response.send_message(f"🗑️ Produkt `{produkt}` aus `{kategorie}` entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Produkt oder Kategorie nicht gefunden.", ephemeral=True)


@bot.tree.command(name="produkte-liste", description="Zeigt alle Produkte einer Kategorie mit Preisen")
@app_commands.autocomplete(kategorie=category_autocomplete)
async def produkte_liste(interaction: discord.Interaction, kategorie: str):
    data = store.load()
    if kategorie not in data:
        return await interaction.response.send_message("❌ Diese Kategorie wurde nicht gefunden.", ephemeral=True)
    cat = data[kategorie]
    embed = discord.Embed(title=f"{cat.get('emoji','')} {cat['label']}", description=cat["beschreibung"], color=VOLT_RED)
    for k, p in cat["products"].items():
        embed.add_field(name=f"{p.get('emoji','')} {p['name']} (`{k}`)", value=f"{store.format_price(p['klein'])} / {store.format_price(p['big'])}\n{p.get('beschreibung','')}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


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


@setup_tickets.error
@kategorie_hinzufuegen.error
@kategorie_entfernen.error
@produkt_hinzufuegen.error
@produkt_entfernen.error
@ticket_add.error
@ticket_remove.error
async def on_tickets_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Dieser Command ist nur für Administratoren.", ephemeral=True)
    else:
        log.exception("Fehler in VOLT TICKETS-Command", exc_info=error)
        msg = "❌ Es ist ein Fehler aufgetreten."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN fehlt in der .env Datei!")
    bot.run(TOKEN)
