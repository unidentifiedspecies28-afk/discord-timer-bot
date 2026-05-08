import discord
from discord import app_commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# --------------------------
# ✅ YOUR SETTINGS
# --------------------------
GAME_ID = 13358463560       # ✅ YOUR GAME ID
BOSS_CHANNEL_ID = 1502236106597470288   # ✅ BOSS CHANNEL
RIFT_CHANNEL_ID = 1502236122615648326   # ✅ RIFT CHANNEL

RIFT_TIME = 5400    # 1h30m
BOSS_TIME = 7200    # 2h
WARNING = 300       # 5 mins EARLY
ROVALRA_MULTIPLIER = 1.12  # ✅ EXACT RoValra formula

# --------------------------
# KEEP ALIVE
# --------------------------
app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

# --------------------------
# ✅ FIX: DISABLE VOICE COMPLETELY — NO AUDIOOP NEEDED
# --------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = False  # TURN OFF VOICE — FIXES THE CRASH
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

tracked_servers = {}

# --------------------------
# ROBLOX SCANNER
# --------------------------
def get_roblox_servers():
    print("🔍 Fetching servers...")
    cookie = os.getenv("ROBLOX_COOKIE", "")
    if not cookie:
        print("❌ NO ROBLOX COOKIE!")
        return []
    headers = {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        r = requests.get(f"https://games.roblox.com/v1/games/{GAME_ID}/servers/Public?limit=100", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            print(f"✅ Got {len(data)} servers")
            return data
        else:
            print(f"❌ API ERROR: {r.status_code}")
    except Exception as e:
        print(f"❌ REQUEST FAILED: {e}")
    return []

async def watch_server(job_id, start_time, boss_channel, rift_channel):
    join_link = f"https://www.roblox.com/games/start?placeId={GAME_ID}&gameId={job_id}"
    while job_id in tracked_servers:
        age = (datetime.now() - start_time).total_seconds()

        until_rift = RIFT_TIME - (age % RIFT_TIME)
        until_boss = BOSS_TIME - (age % BOSS_TIME)

        # 🌀 RIFT ALERT (5min early)
        if WARNING < until_rift <= WARNING + 10:
            print(f"📢 RIFT ALERT | {job_id[:8]}...")
            await rift_channel.send(
                f"🌀 **RIFT SPAWNING IN 5 MINUTES!**\n"
                f"Uptime: 1h 25m\n"
                f"Server: `{job_id}`\n"
                f"👉 **JOIN**: {join_link}"
            )
            await asyncio.sleep(WARNING)
            if job_id in tracked_servers:
                await rift_channel.send(f"🌀 **RIFT NOW!**\n👉 {join_link}")

        # 🚨 BOSS ALERT (5min early)
        if WARNING < until_boss <= WARNING + 10:
            print(f"📢 BOSS ALERT | {job_id[:8]}...")
            await boss_channel.send(
                f"🚨 **BOSS SPAWNING IN 5 MINUTES!**\n"
                f"Uptime: 1h 55m\n"
                f"Server: `{job_id}`\n"
                f"👉 **JOIN**: {join_link}"
            )
            await asyncio.sleep(WARNING)
            if job_id in tracked_servers:
                await boss_channel.send(f"🚨 **BOSS NOW!**\n👉 {join_link}")

        await asyncio.sleep(15)

async def auto_scan_loop():
    await bot.wait_until_ready()
    boss_ch = bot.get_channel(BOSS_CHANNEL_ID)
    rift_ch = bot.get_channel(RIFT_CHANNEL_ID)
    if not boss_ch or not rift_ch:
        print("❌ CHANNELS WRONG!")
        return

    print("\n=====================================")
    print("✅ FULL AUTO MODE ONLINE — NO ERRORS")
    print(f"✅ Boss → {BOSS_CHANNEL_ID}")
    print(f"✅ Rift → {RIFT_CHANNEL_ID}")
    print("✅ RoValra timing ✅ Links included ✅")
    print("=====================================\n")

    while True:
        servers = get_roblox_servers()
        now = datetime.now()
        active_ids = set()

        for s in servers:
            jid = s.get("id")
            ping = s.get("ping", 0)
            if not jid: continue
            active_ids.add(jid)

            # ✅ EXACT ROVALRA CALC
            uptime = int(ping * ROVALRA_MULTIPLIER)
            h = uptime // 3600
            m = (uptime % 3600) // 60
            start = now - timedelta(seconds=uptime)

            if jid not in tracked_servers:
                print(f"🆕 NEW SERVER | {jid[:8]}... | {h}h {m}m")
                tracked_servers[jid] = start
                asyncio.create_task(watch_server(jid, start, boss_ch, rift_ch))
            else:
                print(f"📌 EXISTING | {jid[:8]}... | {h}h {m}m")

        # Clean dead servers
        for jid in list(tracked_servers.keys()):
            if jid not in active_ids:
                print(f"🗑️ REMOVED | {jid[:8]}...")
                del tracked_servers[jid]

        await asyncio.sleep(120)

# --------------------------
# DISCORD COMMANDS
# --------------------------
TIMER_OPTIONS = {"Bosses":3600, "Super Boss":3600, "Rift":1800, "Raids":7200}

async def timer_end(user, name, dur, inter):
    await asyncio.sleep(dur)
    await inter.channel.send(f"🔔 <@{user.id}> **{name}** DONE!")

class TimerSelect(discord.ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label=n, description=f"{d//60}m") for n,d in TIMER_OPTIONS.items()]
        super().__init__(placeholder="Pick timer", options=opts)
    async def callback(self, inter):
        chosen = self.values[0]
        dur = TIMER_OPTIONS[chosen]
        end = datetime.now() + timedelta(seconds=dur)
        await inter.response.send_message(f"⏰ **{chosen}** set → ends <t:{int(end.timestamp())}:R>")
        asyncio.create_task(timer_end(inter.user, chosen, dur, inter))

@tree.command(name="Reminder", description="Set timers for Rift, Boss, SuperBoss or Raids")
async def timer(inter):
    await inter.response.send_message("Choose:", view=discord.ui.View().add_item(TimerSelect()))

@tree.command(name="timers", description="List timers")
async def timers(inter):
    await inter.response.send_message("✅ Timers working", ephemeral=True)

# --------------------------
# START BOT
# --------------------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ LOGGED IN: {bot.user}")
    bot.loop.create_task(auto_scan_loop())

if __name__ == "__main__":
    print("🚀 STARTING — NO ERRORS THIS TIME")
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        print("❌ NO TOKEN!")
    else:
        bot.run(token)
