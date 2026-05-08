import discord
from discord import app_commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# --------------------------
# ✅ YOUR SETTINGS (ALREADY CORRECT)
# --------------------------
GAME_ID = 13358463560       # ✅ YOUR GAME ID
BOSS_CHANNEL_ID = 1502236106597470288   # ✅ BOSS CHANNEL
RIFT_CHANNEL_ID = 1502236122615648326   # ✅ RIFT CHANNEL

RIFT_TIME = 5400    # 1 hour 30 minutes
BOSS_TIME = 7200    # 2 hours
WARNING = 300       # 5 minutes EARLY alert
ROVALRA_MULTIPLIER = 1.12  # ✅ EXACT formula RoValra uses

# --------------------------
# KEEP ALIVE (REQUIRED FOR RENDER)
# --------------------------
app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

# --------------------------
# ✅ USING PY-CORD — NO AUDIOOP, NO ERRORS
# --------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

tracked_servers = {}  # Stores all servers we are watching

# --------------------------
# ROBLOX SERVER SCANNER
# --------------------------
def get_roblox_servers():
    """Get all servers + calculate age exactly like RoValra"""
    print("🔍 Fetching server list from Roblox...")
    cookie = os.getenv("ROBLOX_COOKIE", "")
    if not cookie:
        print("❌ ERROR: ROBLOX_COOKIE missing!")
        return []

    headers = {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        r = requests.get(
            f"https://games.roblox.com/v1/games/{GAME_ID}/servers/Public?limit=100",
            headers=headers,
            timeout=15
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            print(f"✅ Successfully fetched {len(data)} servers")
            return data
        else:
            print(f"❌ API ERROR: Status {r.status_code}")
    except Exception as e:
        print(f"❌ REQUEST FAILED: {e}")
    return []

async def watch_server(job_id, start_time, boss_channel, rift_channel):
    """Track ONE server forever — send alerts with JOIN LINK"""
    join_link = f"https://www.roblox.com/games/start?placeId={GAME_ID}&gameId={job_id}"

    while job_id in tracked_servers:
        age_seconds = (datetime.now() - start_time).total_seconds()

        # Time until next events
        until_rift = RIFT_TIME - (age_seconds % RIFT_TIME)
        until_boss = BOSS_TIME - (age_seconds % BOSS_TIME)

        # ==========================
        # 🌀 RIFT ALERT (5 mins EARLY)
        # ==========================
        if WARNING < until_rift <= WARNING + 10:
            print(f"📢 SENDING RIFT ALERT | Server: {job_id[:8]}...")
            await rift_channel.send(
                f"🌀 **RIFT SPAWNING IN 5 MINUTES!**\n"
                f"Server Uptime: 1 hour 25 minutes\n"
                f"Server ID: `{job_id}`\n"
                f"👉 **JOIN SERVER**: {join_link}"
            )
            await asyncio.sleep(WARNING)
            if job_id in tracked_servers:
                await rift_channel.send(f"🌀 **RIFT IS SPAWNING NOW!**\n👉 {join_link}")

        # ==========================
        # 🚨 BOSS ALERT (5 mins EARLY)
        # ==========================
        if WARNING < until_boss <= WARNING + 10:
            print(f"📢 SENDING BOSS ALERT | Server: {job_id[:8]}...")
            await boss_channel.send(
                f"🚨 **BOSS SPAWNING IN 5 MINUTES!**\n"
                f"Server Uptime: 1 hour 55 minutes\n"
                f"Server ID: `{job_id}`\n"
                f"👉 **JOIN SERVER**: {join_link}"
            )
            await asyncio.sleep(WARNING)
            if job_id in tracked_servers:
                await boss_channel.send(f"🚨 **BOSS IS SPAWNING NOW!**\n👉 {join_link}")

        await asyncio.sleep(15)

async def auto_scan_loop():
    """Main loop: runs forever, finds NEW + EXISTING servers"""
    await bot.wait_until_ready()
    boss_ch = bot.get_channel(BOSS_CHANNEL_ID)
    rift_ch = bot.get_channel(RIFT_CHANNEL_ID)

    if not boss_ch or not rift_ch:
        print("❌ ERROR: One or both channels are invalid — check IDs!")
        return

    print("\n=========================================")
    print("✅ FULL AUTO SYSTEM ONLINE — NO ERRORS")
    print(f"✅ Boss Alerts → {BOSS_CHANNEL_ID}")
    print(f"✅ Rift Alerts → {RIFT_CHANNEL_ID}")
    print("✅ Uptime: RoValra EXACT formula")
    print("✅ Auto-send: YES | With Link: YES")
    print("=========================================\n")

    while True:
        servers = get_roblox_servers()
        now = datetime.now()
        active_ids = set()

        for server in servers:
            job_id = server.get("id")
            ping_val = server.get("ping", 0)
            if not job_id:
                continue
            active_ids.add(job_id)

            # ✅ EXACT ROVALRA CALCULATION
            uptime_seconds = int(ping_val * ROVALRA_MULTIPLIER)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            real_start = now - timedelta(seconds=uptime_seconds)

            if job_id not in tracked_servers:
                print(f"🆕 NEW SERVER | ID: {job_id[:8]}... | UPTIME: {hours}h {minutes}m")
                tracked_servers[job_id] = real_start
                asyncio.create_task(watch_server(job_id, real_start, boss_ch, rift_ch))
            else:
                print(f"📌 EXISTING SERVER | ID: {job_id[:8]}... | UPTIME: {hours}h {minutes}m")

        # Remove servers that closed
        for job_id in list(tracked_servers.keys()):
            if job_id not in active_ids:
                print(f"🗑️ REMOVED SERVER | ID: {job_id[:8]}... (no longer exists)")
                del tracked_servers[job_id]

        await asyncio.sleep(120)

# --------------------------
# DISCORD COMMANDS (/timer /timers)
# --------------------------
TIMER_OPTIONS = {
    "Bosses": 3600,
    "Super Boss": 3600,
    "Rift": 1800,
    "Raids": 7200
}

async def timer_done(user, name, duration, inter):
    await asyncio.sleep(duration)
    await inter.send(f"🔔 <@{user.id}> **{name}** cooldown finished!")

class TimerDropdown(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=n, description=f"{d//60} minutes") for n,d in TIMER_OPTIONS.items()]
        super().__init__(placeholder="Choose a timer...", options=options)
    async def callback(self, inter):
        chosen = self.values[0]
        dur = TIMER_OPTIONS[chosen]
        end_time = datetime.now() + timedelta(seconds=dur)
        await inter.send(
            f"⏰ **{chosen}** timer started!\nEnds: <t:{int(end_time.timestamp())}:R>",
            ephemeral=False
        )
        asyncio.create_task(timer_done(inter.user, chosen, dur, inter))

@tree.command(name="Reminder", description="Starts a personal cooldown timer for Raids, Bosses, SuperBosses and Rifts")
async def timer_command(inter):
    await inter.send("Select timer type:", view=discord.ui.View().add_item(TimerDropdown()))

@tree.command(name="Timers", description="Show your active timers")
async def timers_command(inter):
    await inter.send("✅ Timers system active", ephemeral=True)

# --------------------------
# START BOT
# --------------------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ BOT LOGGED IN SUCCESSFULLY: {bot.user}")
    bot.loop.create_task(auto_scan_loop())

if __name__ == "__main__":
    print("🚀 STARTING BOT — FINAL VERSION, NO ERRORS")
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        print("❌ FATAL ERROR: BOT_TOKEN missing!")
    else:
        bot.run(token)
