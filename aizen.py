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

# ✅ CREATE FOLDER AUTOMATICALLY — FIXES CRASH
os.makedirs("configs", exist_ok=True)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="a!", intents=intents, help_command=None)

# --------------------------
# CONFIG FUNCTIONS
# --------------------------
def load_config(guild_id):
    try:
        with open(f"configs/{guild_id}.json", "r") as f:
            return json.load(f)
    except:
        # Load default config
        with open("configs/config.json", "r") as f:
            default_cfg = json.load(f)
        # Save default for this server
        with open(f"configs/{guild_id}.json", "w") as f:
            json.dump(default_cfg, f, indent=2)
        return default_cfg

def save_config(guild_id, data):
    with open(f"configs/{guild_id}.json", "w") as f:
        json.dump(data, f, indent=2)

# --------------------------
# TRACKERS
# --------------------------
join_tracker = defaultdict(list)
message_tracker = defaultdict(list)
captcha_codes = {}

# --------------------------
# BOT ONLINE
# --------------------------
@bot.event
async def on_ready():
    print(f"✅ AIZEN ONLINE | Logged in as: {bot.user}")
    print(f"✅ Total Servers: {len(bot.guilds)}")
    await bot.change_presence(activity=discord.Game(name="🛡️ Protecting Servers | a!help"))
    cleanup_loop.start()

# --------------------------
# LOGGING SYSTEM
# --------------------------
async def log_action(guild, text):
    cfg = load_config(guild.id)
    if cfg["log_channel_id"]:
        try:
            log_channel = guild.get_channel(int(cfg["log_channel_id"]))
            if log_channel:
                embed = discord.Embed(title="🔒 AIZEN SECURITY LOG", description=text, color=0xff0000)
                embed.timestamp = discord.utils.utcnow()
                await log_channel.send(embed=embed)
        except:
            pass

# --------------------------
# ANTI RAID / JOIN GATE
# --------------------------
@bot.event
async def on_member_join(member):
    if member.bot:
        # ✅ ANTI UNAUTHORIZED BOT ADD
        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            if not entry.user.guild_permissions.administrator and entry.user.id not in load_config(member.guild.id)["whitelisted_users"]:
                try: await member.ban(reason="❌ Unauthorized Bot")
                except: pass
                try: await entry.user.ban(reason="❌ Added Unauthorized Bot")
                except: pass
                await log_action(member.guild, f"🚫 Banned User: {entry.user} | Banned Bot: {member} | Reason: Unauthorized Bot")
        return

    guild = member.guild
    cfg = load_config(guild.id)
    now = time.time()

    # ✅ LOCKDOWN CHECK
    if cfg["lockdown"] and member.id not in cfg["whitelisted_users"]:
        try: await member.kick(reason="🔒 SERVER LOCKED")
        except: pass
        await log_action(guild, f"🔒 Kicked {member} | Server Lockdown Active")
        return

    # ✅ JOIN GATE / NEW ACCOUNT CHECK
    account_age_days = (now - member.created_at.timestamp()) / 86400
    if cfg["join_gate"]["enabled"] and account_age_days < cfg["join_gate"]["min_account_age_days"]:
        action = cfg["join_gate"]["action"]
        try:
            if action == "kick": await member.kick(reason="⚠️ Account too new")
            if action == "ban": await member.ban(reason="⚠️ Account too new")
        except: pass
        await log_action(guild, f"⚠️ {action.upper()} {member} | Account Age: {round(account_age_days,1)} days | Required: {cfg['join_gate']['min_account_age_days']} days")
        return

    # ✅ ANTI RAID / MASS JOIN
    join_tracker[guild.id].append(now)
    join_tracker[guild.id] = [t for t in join_tracker[guild.id] if now - t < cfg["anti_raid"]["time_window"]]
    if cfg["anti_raid"]["enabled"] and len(join_tracker[guild.id]) > cfg["anti_raid"]["join_limit"]:
        action = cfg["anti_raid"]["action"]
        try:
            if action == "ban": await member.ban(reason="🚨 RAID DETECTED")
            if action == "kick": await member.kick(reason="🚨 RAID DETECTED")
        except: pass
        await log_action(guild, f"🚨 RAID DETECTED | {action.upper()} {member} | {len(join_tracker[guild.id])} joins in {cfg['anti_raid']['time_window']}s")
        return

    # ✅ VERIFICATION SYSTEM
    if cfg["verification"]["enabled"]:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        captcha_codes[member.id] = code
        try:
            await member.send(f"""
✅ **VERIFICATION REQUIRED**
Type this in server: `a!verify {code}`
This proves you are NOT a bot.
""")
        except:
            pass

# --------------------------
# AUTOMOD / ANTI SPAM
# --------------------------
@bot.event
async def on_message(message):
    if message.author.bot or message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    guild = message.guild
    cfg = load_config(guild.id)
    now = time.time()

    # ✅ SPAM DETECTION
    message_tracker[message.author.id].append(now)
    message_tracker[message.author.id] = [t for t in message_tracker[message.author.id] if now - t < cfg["automod"]["spam_window"]]
    if cfg["automod"]["enabled"] and len(message_tracker[message.author.id]) > cfg["automod"]["spam_threshold"]:
        try:
            await message.channel.purge(limit=15, check=lambda m: m.author == message.author)
            await message.author.timeout(86400, reason="⚠️ Spamming")
        except: pass
        await log_action(guild, f"⚠️ Timed out {message.author} | Spamming detected")
        return

    # ✅ BAD WORDS FILTER
    for word in cfg["automod"]["bad_words"]:
        if re.search(rf"\b{re.escape(word)}\b", message.content.lower()):
            try: await message.delete()
            except: pass
            await log_action(guild, f"❌ Deleted message from {message.author} | Bad word used")
            return

    # ✅ DISCORD INVITE BLOCK
    if cfg["automod"]["invite_block"] and re.search(r"(discord\.gg|discordapp\.com/invite)/", message.content.lower()):
        try: await message.delete()
        except: pass
        await log_action(guild, f"🚫 Deleted invite link from {message.author}")
        return

    # ✅ MASS MENTION PROTECTION
    if len(message.mentions) > cfg["automod"]["mass_mention_limit"]:
        try:
            await message.delete()
            await message.author.kick(reason="⚠️ Mass mention")
        except: pass
        await log_action(guild, f"⚠️ Kicked {message.author} | Mass mention ({len(message.mentions)} mentions)")
        return

    await bot.process_commands(message)

# --------------------------
# ANTI NUKE PROTECTION
# --------------------------
@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    cfg = load_config(guild.id)
    if cfg["anti_nuke"]["enabled"]:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if not entry.user.guild_permissions.administrator and entry.user.id not in cfg["whitelisted_users"]:
                try: await entry.user.ban(reason="🛡️ ANTI-NUKE: Deleted channel")
                except: pass
                await log_action(guild, f"🛡️ Banned {entry.user} | Deleted channel: {channel.name}")

@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    cfg = load_config(guild.id)
    if cfg["anti_nuke"]["enabled"]:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if not entry.user.guild_permissions.administrator and entry.user.id not in cfg["whitelisted_users"]:
                try: await entry.user.ban(reason="🛡️ ANTI-NUKE: Deleted role")
                except: pass
                await log_action(guild, f"🛡️ Banned {entry.user} | Deleted role: {role.name}")

@bot.event
async def on_webhook_create(webhook):
    guild = webhook.guild
    cfg = load_config(guild.id)
    if cfg["anti_nuke"]["enabled"] and cfg["anti_nuke"]["protect_webhooks"]:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
            if not entry.user.guild_permissions.administrator and entry.user.id not in cfg["whitelisted_users"]:
                try:
                    await webhook.delete(reason="🛡️ ANTI-NUKE: Unauthorized webhook")
                    await entry.user.ban(reason="🛡️ ANTI-NUKE: Created webhook")
                except: pass
                await log_action(guild, f"🛡️ Banned {entry.user} | Unauthorized webhook created")

@bot.event
async def on_member_ban(guild, user):
    cfg = load_config(guild.id)
    if cfg["anti_nuke"]["enabled"]:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if not entry.user.guild_permissions.administrator and entry.user.id not in cfg["whitelisted_users"]:
                try: await entry.user.ban(reason="🛡️ ANTI-NUKE: Mass ban")
                except: pass
                await log_action(guild, f"🛡️ Banned {entry.user} | Mass ban detected")

# --------------------------
# VERIFICATION COMMAND
# --------------------------
@bot.command()
async def verify(ctx, code=None):
    guild = ctx.guild
    cfg = load_config(guild.id)
    if ctx.author.id in captcha_codes and code == captcha_codes[ctx.author.id]:
        role = get(guild.roles, name=cfg["verified_role"])
        if role:
            try: await ctx.author.add_roles(role)
            except: pass
        del captcha_codes[ctx.author.id]
        await ctx.send(f"✅ {ctx.author.mention} **VERIFIED!** Access granted.")
        await log_action(guild, f"✅ {ctx.author} verified successfully")
    else:
        await ctx.send("❌ Wrong or expired code. Check your DMs.")

# --------------------------
# ADMIN COMMANDS
# --------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try: await member.kick(reason=reason)
    except: pass
    await ctx.send(f"👢 Kicked {member.mention} | Reason: {reason}")
    await log_action(ctx.guild, f"👢 Kicked {member} | By: {ctx.author} | Reason: {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    try: await member.ban(reason=reason)
    except: pass
    await ctx.send(f"🔨 Banned {member.mention} | Reason: {reason}")
    await log_action(ctx.guild, f"🔨 Banned {member} | By: {ctx.author} | Reason: {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
    try: await member.timeout(minutes * 60, reason=reason)
    except: pass
    await ctx.send(f"⏱️ Timed out {member.mention} for {minutes}min | Reason: {reason}")
    await log_action(ctx.guild, f"⏱️ Timed out {member} | By: {ctx.author} | Duration: {minutes}min | Reason: {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def lockchannel(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    try: await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    except: pass
    await ctx.send(f"🔒 Locked {channel.mention}")
    await log_action(ctx.guild, f"🔒 Locked channel: {channel.name} | By: {ctx.author}")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlockchannel(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    try: await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    except: pass
    await ctx.send(f"🔓 Unlocked {channel.mention}")
    await log_action(ctx.guild, f"🔓 Unlocked channel: {channel.name} | By: {ctx.author}")

@bot.command()
@commands.has_permissions(administrator=True)
async def addrole(ctx, member: discord.Member, role: discord.Role):
    try: await member.add_roles(role)
    except: pass
    await ctx.send(f"➕ Added role **{role.name}** to {member.mention}")
    await log_action(ctx.guild, f"➕ Added role {role.name} to {member} | By: {ctx.author}")

@bot.command()
@commands.has_permissions(administrator=True)
async def removerole(ctx, member: discord.Member, role: discord.Role):
    try: await member.remove_roles(role)
    except: pass
    await ctx.send(f"➖ Removed role **{role.name}** from {member.mention}")
    await log_action(ctx.guild, f"➖ Removed role {role.name} from {member} | By: {ctx.author}")

@bot.command()
@commands.has_permissions(administrator=True)
async def lockdown(ctx, mode: str):
    cfg = load_config(ctx.guild.id)
    cfg["lockdown"] = mode.lower() == "on"
    save_config(ctx.guild.id, cfg)
    status = "✅ **ENABLED**" if cfg["lockdown"] else "❌ **DISABLED**"
    await ctx.send(f"🔒 LOCKDOWN MODE: {status}")
    await log_action(ctx.guild, f"🔒 Lockdown {status} | By: {ctx.author}")

@bot.command()
@commands.has_permissions(administrator=True)
async def panicmode(ctx, mode: str):
    cfg = load_config(ctx.guild.id)
    cfg["anti_nuke"]["panic_mode"] = mode.lower() == "on"
    save_config(ctx.guild.id, cfg)
    status = "⚠️ **ACTIVE — FULL PROTECTION**" if cfg["anti_nuke"]["panic_mode"] else "✅ **OFF**"
    await ctx.send(f"⚠️ PANIC MODE: {status}")
    await log_action(ctx.guild, f"⚠️ Panic Mode {status} | By: {ctx.author}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    cfg = load_config(ctx.guild.id)
    cfg["log_channel_id"] = ctx.channel.id
    save_config(ctx.guild.id, cfg)
    await ctx.send(f"""
🧙 **AIZEN WIZARD SETUP COMPLETE**
✅ Auto Setup
✅ AutoMod / Anti-Spam
✅ Anti-Nuke / Anti-Raid
✅ Join Gate / Verification
✅ Logging Enabled here
🔑 Rescue Key: `{cfg['rescue_key']}`

**ALL SYSTEMS ACTIVE**
""")

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🤖 AIZEN — COMMANDS", color=0x2ecc71)
    embed.add_field(name="`a!verify CODE`", value="Verify yourself", inline=False)
    embed.add_field(name="`a!kick @user [reason]`", value="Kick user", inline=False)
    embed.add_field(name="`a!ban @user [reason]`", value="Ban user", inline=False)
    embed.add_field(name="`a!timeout @user MINUTES [reason]`", value="Timeout user", inline=False)
    embed.add_field(name="`a!lockchannel / unlockchannel`", value="Lock/unlock channel", inline=False)
    embed.add_field(name="`a!addrole / removerole @user @role`", value="Manage roles", inline=False)
    embed.add_field(name="`a!lockdown on/off`", value="Lock entire server", inline=False)
    embed.add_field(name="`a!panicmode on/off`", value="Emergency max protection", inline=False)
    embed.add_field(name="`a!setup`", value="Quick setup wizard", inline=False)
    await ctx.send(embed=embed)

# --------------------------
# CLEANUP LOOP
# --------------------------
@tasks.loop(seconds=30)
async def cleanup_loop():
    join_tracker.clear()
    message_tracker.clear()

# --------------------------
# RUN BOT
# --------------------------
bot.run(TOKEN)
                
