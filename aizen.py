import discord
from discord.ext import commands, tasks
from discord.utils import get
import re
import time
import random
import string
import json
from collections import defaultdict
import os
from dotenv import load_dotenv

# Load secrets
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# All Intents (required)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="a!", intents=intents, help_command=None)

# --------------------------
# ⚙️ FULL CONFIG (SAME AS WICK)
# --------------------------
DEFAULT_CONFIG = {
    "log_channel_id": None,
    "verified_role": "Verified",
    "mute_role": "Muted",
    "whitelisted_users": [],
    "whitelisted_roles": ["Owner", "Admin", "Moderator"],
    "anti_raid": {
        "enabled": True,
        "join_limit": 5,
        "time_window": 10,
        "action": "ban"
    },
    "join_gate": {
        "enabled": True,
        "min_account_age_days": 7,
        "action": "kick"
    },
    "automod": {
        "enabled": True,
        "spam_threshold": 5,
        "spam_window": 3,
        "mass_mention_limit": 5,
        "bad_words": [],
        "invite_block": True,
        "link_block": False
    },
    "anti_nuke": {
        "enabled": True,
        "protect_roles": True,
        "protect_channels": True,
        "protect_webhooks": True,
        "panic_mode": False
    },
    "verification": {
        "enabled": True,
        "type": "captcha"
    },
    "lockdown": False,
    "backups": [],
    "rescue_key": ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
}

# Load/Save config
def load_config(guild_id):
    try:
        with open(f"configs/{guild_id}.json", "r") as f:
            return json.load(f)
    except:
        return DEFAULT_CONFIG.copy()

def save_config(guild_id, data):
    os.makedirs("configs", exist_ok=True)
    with open(f"configs/{guild_id}.json", "w") as f:
        json.dump(data, f, indent=2)

# Data storage
join_tracker = defaultdict(list)
message_tracker = defaultdict(list)
captcha_codes = {}

# --------------------------
# 🚀 BOT ONLINE
# --------------------------
@bot.event
async def on_ready():
    print(f"✅ Aizen is ONLINE | Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="Protecting Servers | a!help"))
    cleanup_loop.start()

# --------------------------
# 📝 LOGGING
# --------------------------
async def log_action(guild, text):
    cfg = load_config(guild.id)
    if cfg["log_channel_id"]:
        ch = guild.get_channel(int(cfg["log_channel_id"]))
        if ch:
            embed = discord.Embed(title="🔒 Aizen Security Log", description=text, color=0xff0000)
            embed.timestamp = discord.utils.utcnow()
            await ch.send(embed=embed)

# --------------------------
# 🛡️ ANTI RAID / JOIN GATE
# --------------------------
@bot.event
async def on_member_join(member):
    if member.bot:
        await anti_bot_add(member)
        return

    guild = member.guild
    cfg = load_config(guild.id)
    now = time.time()

    # Lockdown
    if cfg["lockdown"] and member.id not in cfg["whitelisted_users"]:
        await member.kick(reason="Aizen: Server LOCKED")
        await log_action(guild, f"🔒 Kicked {member} | Lockdown")
        return

    # Join Gate
    age_days = (now - member.created_at.timestamp()) / 86400
    if cfg["join_gate"]["enabled"] and age_days < cfg["join_gate"]["min_account_age_days"]:
        action = cfg["join_gate"]["action"]
        if action == "kick": await member.kick(reason="Account too new")
        if action == "ban": await member.ban(reason="Account too new")
        await log_action(guild, f"⚠️ {action.upper()} {member} | New account")
        return

    # Anti-Raid
    join_tracker[guild.id].append(now)
    join_tracker[guild.id] = [t for t in join_tracker[guild.id] if now - t < cfg["anti_raid"]["time_window"]]
    if cfg["anti_raid"]["enabled"] and len(join_tracker[guild.id]) > cfg["anti_raid"]["join_limit"]:
        action = cfg["anti_raid"]["action"]
        if action == "ban": await member.ban(reason="RAID DETECTED")
        if action == "kick": await member.kick(reason="RAID DETECTED")
        await log_action(guild, f"🚫 {action.upper()} {member} | RAID")
        return

    # Verification
    if cfg["verification"]["enabled"]:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        captcha_codes[member.id] = code
        try:
            await member.send(f"**Welcome!** Verify: `a!verify {code}`")
        except: pass

# --------------------------
# ⚙️ AUTOMOD / ANTI SPAM
# --------------------------
@bot.event
async def on_message(message):
    if message.author.bot: return
    guild = message.guild
    cfg = load_config(guild.id)
    now = time.time()

    # Only admins bypass
    if message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    # Anti-Spam
    message_tracker[message.author.id].append(now)
    message_tracker[message.author.id] = [t for t in message_tracker[message.author.id] if now - t < cfg["automod"]["spam_window"]]
    if cfg["automod"]["enabled"] and len(message_tracker[message.author.id]) > cfg["automod"]["spam_threshold"]:
        await message.channel.purge(limit=10, check=lambda m: m.author == message.author)
        await message.author.timeout(86400, reason="Spamming")
        await log_action(guild, f"⚠️ Timed out {message.author} | Spam")
        return

    # Bad Words
    for word in cfg["automod"]["bad_words"]:
        if re.search(rf"\b{word}\b", message.content.lower()):
            await message.delete()
            await log_action(guild, f"❌ Deleted message from {message.author} | Bad word")
            return

    # Anti-Invite
    if cfg["automod"]["invite_block"] and re.search(r"discord\.gg/", message.content):
        await message.delete()
        await log_action(guild, f"🚫 Deleted invite from {message.author}")
        return

    await bot.process_commands(message)

# --------------------------
# 🛡️ ANTI-NUKE
# --------------------------
@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    cfg = load_config(guild.id)
    if cfg["anti_nuke"]["enabled"]:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if not entry.user.guild_permissions.administrator and entry.user.id not in cfg["whitelisted_users"]:
                await entry.user.ban(reason="Deleted channel (Anti-Nuke)")
                await log_action(guild, f"🛡️ Banned {entry.user} | Deleted channel")

@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    cfg = load_config(guild.id)
    if cfg["anti_nuke"]["enabled"]:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if not entry.user.guild_permissions.administrator and entry.user.id not in cfg["whitelisted_users"]:
                await entry.user.ban(reason="Deleted role (Anti-Nuke)")
                await log_action(guild, f"🛡️ Banned {entry.user} | Deleted role")

# --------------------------
# 🤖 ANTI-BOT ADD
# --------------------------
async def anti_bot_add(member):
    guild = member.guild
    cfg = load_config(guild.id)
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
        if not entry.user.guild_permissions.administrator and entry.user.id not in cfg["whitelisted_users"]:
            await member.ban(reason="Unauthorized bot")
            await entry.user.ban(reason="Added bot")
            await log_action(guild, f"🚫 Banned {entry.user} + Bot {member}")

# --------------------------
# ✅ VERIFY COMMAND
# --------------------------
@bot.command()
async def verify(ctx, code=None):
    guild = ctx.guild
    cfg = load_config(guild.id)
    if ctx.author.id in captcha_codes and code == captcha_codes[ctx.author.id]:
        role = get(guild.roles, name=cfg["verified_role"])
        if role: await ctx.author.add_roles(role)
        del captcha_codes[ctx.author.id]
        await ctx.send(f"✅ {ctx.author.mention} Verified!")
    else:
        await ctx.send("❌ Wrong code.")

# --------------------------
# ⚡ ADMIN COMMANDS ONLY
# --------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 Kicked {member} | {reason}")
    await log_action(ctx.guild, f"👢 Kicked {member} | {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 Banned {member} | {reason}")
    await log_action(ctx.guild, f"🔨 Banned {member} | {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def timeout(ctx, member: discord.Member, duration: int, *, reason="No reason"):
    await member.timeout(duration * 60, reason=reason)
    await ctx.send(f"⏱️ Timed out {member} for {duration}m | {reason}")
    await log_action(ctx.guild, f"⏱️ Timed out {member} | {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def lockchannel(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 Locked {channel.mention}")
    await log_action(ctx.guild, f"🔒 Locked channel {channel}")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlockchannel(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"🔓 Unlocked {channel.mention}")
    await log_action(ctx.guild, f"🔓 Unlocked channel {channel}")

@bot.command()
@commands.has_permissions(administrator=True)
async def addrole(ctx, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await ctx.send(f"➕ Added {role.name} to {member}")
    await log_action(ctx.guild, f"➕ Added role {role} to {member}")

@bot.command()
@commands.has_permissions(administrator=True)
async def removerole(ctx, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await ctx.send(f"➖ Removed {role.name} from {member}")
    await log_action(ctx.guild, f"➖ Removed role {role} from {member}")

@bot.command()
@commands.has_permissions(administrator=True)
async def lockdown(ctx, mode: str):
    cfg = load_config(ctx.guild.id)
    cfg["lockdown"] = (mode.lower() == "on")
    save_config(ctx.guild.id, cfg)
    await ctx.send(f"🔒 Lockdown: **{'ENABLED' if cfg['lockdown'] else 'DISABLED'}**")
    await log_action(ctx.guild, f"🔒 Lockdown set to {cfg['lockdown']}")

@bot.command()
@commands.has_permissions(administrator=True)
async def panicmode(ctx, mode: str):
    cfg = load_config(ctx.guild.id)
    cfg["anti_nuke"]["panic_mode"] = (mode.lower() == "on")
    save_config(ctx.guild.id, cfg)
    await ctx.send(f"⚠️ Panic Mode: **{'ACTIVE' if cfg['anti_nuke']['panic_mode'] else 'OFF'}**")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    cfg = load_config(ctx.guild.id)
    cfg["log_channel_id"] = ctx.channel.id
    save_config(ctx.guild.id, cfg)
    await ctx.send(f"""
🧙 **AIZEN WIZARD SETUP**
✅ Auto Setup
✅ Miscellaneous
✅ AutoMod
✅ Anti-Nuke
✅ Whitelist
✅ Join Gate
✅ Join Raid
✅ Verification
🔑 Rescue Key: `{cfg['rescue_key']}`

**Done!** Full protection active.
""")

@bot.command()
@commands.has_permissions(administrator=True)
async def help(ctx):
    embed = discord.Embed(title="🤖 Aizen — Admin Commands", color=0x2ecc71)
    embed.add_field(name="`a!kick @user [reason]`", value="Kick user", inline=False)
    embed.add_field(name="`a!ban @user [reason]`", value="Ban user", inline=False)
    embed.add_field(name="`a!timeout @user minutes [reason]`", value="Timeout", inline=False)
    embed.add_field(name="`a!lockchannel / unlockchannel`", value="Lock/unlock channel", inline=False)
    embed.add_field(name="`a!addrole / removerole @user @role`", value="Manage roles", inline=False)
    embed.add_field(name="`a!lockdown on/off`", value="Lock server", inline=False)
    embed.add_field(name="`a!panicmode on/off`", value="Emergency mode", inline=False)
    embed.add_field(name="`a!setup`", value="Start setup wizard", inline=False)
    await ctx.send(embed=embed)

# --------------------------
# 🧹 CLEANUP
# --------------------------
@tasks.loop(seconds=30)
async def cleanup_loop():
    join_tracker.clear()
    message_tracker.clear()

# --------------------------
# 🚀 RUN
# --------------------------
bot.run(TOKEN)
  
