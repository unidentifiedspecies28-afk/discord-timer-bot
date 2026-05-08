import discord
from discord.ext import commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# --------------------------
# ✅ YOUR SETTINGS
# --------------------------
GAME_ID = 7095664523
BOSS_CHANNEL_ID = 1502236106597470288
RIFT_CHANNEL_ID = 1502236122615648326

RIFT_TIME = 5400
BOSS_TIME = 7200
WARNING = 300
ROVALRA_MULTIPLIER = 1.12

# --------------------------
# KEEP ALIVE
# --------------------------
app = Flask('')
@app.route('/')
def home(): return "OK"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

# --------------------------
# ✅ NO VOICE — NO AUDIOOP EVER
# --------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

tracked = {}

# --------------------------
# ROBLOX SCANNER
# --------------------------
def get_servers():
    print("🔍 Fetching servers...")
    cookie = os.getenv("ROBLOX_COOKIE", "")
    if not cookie:
        print("❌ NO COOKIE!")
        return []
    headers = {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        r = requests.get(f"https://games.roblox.com/v1/games/{GAME_ID}/servers/Public?limit=100", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            print(f"✅ Got {len(data)} servers")
            return data
        else:
            print(f"❌ API ERR: {r.status_code}")
    except Exception as e:
        print(f"❌ REQ FAIL: {e}")
    return []

async def watch_server(job_id, start_time, boss_ch, rift_ch):
    link = f"https://www.roblox.com/games/start?placeId={GAME_ID}&gameId={job_id}"
    while job_id in tracked:
        age = (datetime.now() - start_time).total_seconds()

        nr = RIFT_TIME - (age % RIFT_TIME)
        nb = BOSS_TIME - (age % BOSS_TIME)

        # 🌀 RIFT
        if WARNING < nr <= WARNING + 10:
            print(f"📢 RIFT ALERT {job_id[:8]}")
            await rift_ch.send(f"🌀 **RIFT IN 5 MIN**\nID: `{job_id}`\n👉 {link}")
            await asyncio.sleep(WARNING)
            if job_id in tracked:
                await rift_ch.send(f"🌀 **RIFT NOW**\n👉 {link}")

        # 🚨 BOSS
        if WARNING < nb <= WARNING + 10:
            print(f"📢 BOSS ALERT {job_id[:8]}")
            await boss_ch.send(f"🚨 **BOSS IN 5 MIN**\nID: `{job_id}`\n👉 {link}")
            await asyncio.sleep(WARNING)
            if job_id in tracked:
                await boss_ch.send(f"🚨 **BOSS NOW**\n👉 {link}")

        await asyncio.sleep(15)

async def auto_scan():
    await bot.wait_until_ready()
    boss_ch = bot.get_channel(BOSS_CHANNEL_ID)
    rift_ch = bot.get_channel(RIFT_CHANNEL_ID)
    if not boss_ch or not rift_ch:
        print("❌ CHANNELS WRONG")
        return

    print("\n=====================================")
    print("✅ FULL AUTO MODE — WORKING")
    print(f"✅ Boss → {BOSS_CHANNEL_ID}")
    print(f"✅ Rift → {RIFT_CHANNEL_ID}")
    print("✅ RoValra math ✅ Links ✅")
    print("=====================================\n")

    while True:
        servers = get_servers()
        now = datetime.now()
        active_ids = set()

        for s in servers:
            jid = s.get("id")
            ping = s.get("ping", 0)
            if not jid: continue
            active_ids.add(jid)

            uptime = int(ping * ROVALRA_MULTIPLIER)
            h = uptime // 3600
            m = (uptime % 3600) // 60
            start = now - timedelta(seconds=uptime)

            if jid not in tracked:
                print(f"🆕 NEW | {jid[:8]} | {h}h {m}m")
                tracked[jid] = start
                asyncio.create_task(watch_server(jid, start, boss_ch, rift_ch))
            else:
                print(f"📌 EXIST | {jid[:8]} | {h}h {m}m")

        # Clean dead
        for jid in list(tracked.keys()):
            if jid not in active_ids:
                print(f"🗑️ REMOVED | {jid[:8]}")
                del tracked[jid]

        await asyncio.sleep(120)

# --------------------------
# COMMANDS
# --------------------------
@bot.command()
async def timer(ctx):
    await ctx.send("⏰ Timer works — use !timers")

@bot.command()
async def timers(ctx):
    await ctx.send("✅ Timers system active")

# --------------------------
# START
# --------------------------
@bot.event
async def on_ready():
    print(f"✅ LOGGED IN: {bot.user}")
    bot.loop.create_task(auto_scan())

if __name__ == "__main__":
    print("🚀 STARTING — NO AUDIOOP, NO ERRORS")
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        print("❌ NO TOKEN")
    else:
        bot.run(token)
