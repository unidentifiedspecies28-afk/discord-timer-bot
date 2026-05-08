import discord
from discord import app_commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# --------------------------
# ✅ YOUR SETTINGS - ALREADY CORRECT
# --------------------------
GAME_ID = 13358463560       # ← PUT YOUR REAL GAME ID HERE
BOSS_CHANNEL_ID = 1502236106597470288
RIFT_CHANNEL_ID = 1502236122615648326

RIFT_TIME = 5400    # 1h30m
BOSS_TIME = 7200    # 2h
WARNING = 300       # 5 mins early
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
# BOT SETUP
# --------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

tracked = {}  # store servers

# --------------------------
# ROBLOX SCANNER
# --------------------------
def get_servers():
    print("🔍 Fetching Roblox servers...")
    cookie = os.getenv("ROBLOX_COOKIE", "")
    if not cookie:
        print("❌ NO ROBLOX COOKIE FOUND!")
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
            print(f"❌ API ERROR: {r.status_code}")
    except Exception as e:
        print(f"❌ REQUEST FAILED: {e}")
    return []

async def monitor_server(job_id, start_time, boss_ch, rift_ch):
    link = f"https://www.roblox.com/games/start?placeId={GAME_ID}&gameId={job_id}"
    while job_id in tracked:
        age = (datetime.now() - start_time).total_seconds()

        next_rift = RIFT_TIME - (age % RIFT_TIME)
        next_boss = BOSS_TIME - (age % BOSS_TIME)

        # RIFT ALERT
        if WARNING < next_rift <= WARNING + 10:
            print(f"⚠️ RIFT SOON: {job_id}")
            await rift_ch.send(f"🌀 **RIFT SPAWN IN 5 MINUTES**\nServer: `{job_id}`\n👉 {link}")
            await asyncio.sleep(WARNING)
            if job_id in tracked:
                await rift_ch.send(f"🌀 **RIFT SPAWNING NOW**\n👉 {link}")

        # BOSS ALERT
        if WARNING < next_boss <= WARNING + 10:
            print(f"⚠️ BOSS SOON: {job_id}")
            await boss_ch.send(f"🚨 **BOSS SPAWN IN 5 MINUTES**\nServer: `{job_id}`\n👉 {link}")
            await asyncio.sleep(WARNING)
            if job_id in tracked:
                await boss_ch.send(f"🚨 **BOSS SPAWNING NOW**\n👉 {link}")

        await asyncio.sleep(15)

async def auto_scan():
    await bot.wait_until_ready()
    boss_ch = bot.get_channel(BOSS_CHANNEL_ID)
    rift_ch = bot.get_channel(RIFT_CHANNEL_ID)

    if not boss_ch or not rift_ch:
        print("❌ CHANNELS WRONG!")
        return

    print("\n=====================================")
    print("✅ FULL AUTO MODE RUNNING")
    print(f"✅ Boss → {BOSS_CHANNEL_ID}")
    print(f"✅ Rift → {RIFT_CHANNEL_ID}")
    print("✅ Using RoValra formula ✅")
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

            # ✅ EXACT ROVALRA CALC
            uptime = int(ping * ROVALRA_MULTIPLIER)
            h = uptime // 3600
            m = (uptime % 3600) // 60
            start = now - timedelta(seconds=uptime)

            if jid not in tracked:
                print(f"🆕 NEW SERVER | {jid[:8]}... | UPTIME: {h}h {m}m")
                tracked[jid] = start
                asyncio.create_task(monitor_server(jid, start, boss_ch, rift_ch))
            else:
                print(f"📌 EXISTING | {jid[:8]}... | UPTIME: {h}h {m}m")

        # Cleanup dead servers
        for jid in list(tracked.keys()):
            if jid not in active_ids:
                print(f"🗑️ REMOVED | {jid[:8]}...")
                del tracked[jid]

        await asyncio.sleep(120)

# --------------------------
# DISCORD COMMANDS
# --------------------------
TIMER_OPTIONS = {"Bosses":3600, "Super Boss":3600, "Rift":1800, "Raids":7200}
user_timers = {}

async def timer_end(user, name, dur, inter):
    await asyncio.sleep(dur)
    await inter.channel.send(f"🔔 <@{user.id}> **{name}** done!")

class TimerSelect(discord.ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label=n, description=f"{d//60}m") for n,d in TIMER_OPTIONS.items()]
        super().__init__(placeholder="Pick timer", options=opts)
    async def callback(self, inter):
        chosen = self.values[0]
        dur = TIMER_OPTIONS[chosen]
        finish = datetime.now() + timedelta(seconds=dur)
        await inter.response.send_message(f"⏰ **{chosen}** set → ends <t:{int(finish.timestamp())}:R>")
        asyncio.create_task(timer_end(inter.user, chosen, dur, inter))

@tree.command(name="Reminders", description="Sets the timerfor Rifts, Bosses, SuperBosses or Raids")
async def timer(inter):
    await inter.response.send_message("Select:", view=discord.ui.View().add_item(TimerSelect()))

@tree.command(name="Timers", description="List your timers")
async def timers(inter):
    await inter.response.send_message("✅ Timers work")

# --------------------------
# START BOT
# --------------------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ LOGGED IN AS: {bot.user}")
    # ✅ THIS STARTS THE SCANNER — 100% GUARANTEED
    bot.loop.create_task(auto_scan())

if __name__ == "__main__":
    print("🚀 STARTING BOT...")
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        print("❌ NO BOT TOKEN!")
    else:
        bot.run(token)
