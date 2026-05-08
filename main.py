import discord
from discord import app_commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
import logging

# ---------------- CONFIGURATION ----------------
GAME_ID = 13358463560 
BOSS_CHANNEL_ID = 1502236106597470288
RIFT_CHANNEL_ID = 1502236122615648326

RIFT_SPAWN = 5400
BOSS_SPAWN = 7200
WARNING_EARLY = 300
ROVALRA_MULTIPLIER = 1.12

# ---------------- LOGGING (SO YOU SEE EVERYTHING) ----------------
logging.basicConfig(level=logging.INFO)
app = Flask('')

@app.route('/')
def home():
    print("✅ Keep-alive ping received")
    return "Bot is alive!"

def run_server():
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    except Exception as e:
        print(f"❌ Flask Error: {e}")

def keep_alive():
    Thread(target=run_server).start()
    print("✅ Keep-alive server started")

keep_alive()

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

TIMER_OPTIONS = {
    "Bosses": 60 * 60,
    "Super Boss": 60 * 60,
    "Rift": 30 * 60,
    "Raids": 2 * 60 * 60
}
active_tasks = {}
end_times = {}
tracked_servers = {}

# ---------------- PERSONAL TIMERS ----------------
async def run_timer(user_id, name, duration, interaction):
    try:
        await asyncio.sleep(duration)
        await interaction.channel.send(f"🔔 <@{user_id}> Your **{name}** cooldown is finished! Go go go!")
        if user_id in active_tasks and name in active_tasks[user_id]:
            del active_tasks[user_id][name]
            del end_times[user_id][name]
    except:
        pass

class TimerSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, description=f"{duration//60}m") for name, duration in TIMER_OPTIONS.items()]
        super().__init__(placeholder="Choose timer...", options=options)

    async def callback(self, interaction):
        chosen = self.values[0]
        duration = TIMER_OPTIONS[chosen]
        user_id = interaction.user.id
        if user_id in active_tasks and chosen in active_tasks[user_id]:
            active_tasks[user_id][chosen].cancel()
            status = f"🔄 **{chosen}** restarted"
        else:
            status = f"⏰ **{chosen}** set"
        finish = datetime.now() + timedelta(seconds=duration)
        if user_id not in active_tasks:
            active_tasks[user_id] = {}
            end_times[user_id] = {}
        end_times[user_id][chosen] = finish
        active_tasks[user_id][chosen] = asyncio.create_task(run_timer(user_id, chosen, duration, interaction))
        await interaction.response.send_message(f"{status}\nEnds <t:{int(finish.timestamp())}:R>", ephemeral=False)

class TimerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(TimerSelect())

@tree.command(name="timer", description="Start timer")
async def timer(interaction):
    await interaction.response.send_message("Select:", view=TimerView())

@tree.command(name="timers", description="Show timers")
async def timers(interaction):
    u = interaction.user.id
    if u not in end_times or not end_times[u]:
        await interaction.response.send_message("✅ No active timers", ephemeral=True)
        return
    txt = "⏰ Timers:\n"
    for n, t in end_times[u].items():
        txt += f"• {n} → <t:{int(t.timestamp())}:R>\n"
    await interaction.response.send_message(txt, ephemeral=True)

# ---------------- ROBLOX SCANNER ----------------
def get_roblox_servers():
    print("🔍 Fetching Roblox servers...")
    cookie = os.getenv("ROBLOX_COOKIE", "")
    if not cookie:
        print("❌ ROBLOX_COOKIE NOT FOUND IN ENV VARS!")
        return []
    headers = {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(f"https://games.roblox.com/v1/games/{GAME_ID}/servers/Public?limit=100", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            print(f"✅ Found {len(data)} servers")
            return data
        else:
            print(f"❌ Roblox API Error: {r.status_code} | {r.text[:200]}")
    except Exception as e:
        print(f"❌ Request failed: {e}")
    return []

async def auto_scan():
    await bot.wait_until_ready()
    boss_ch = bot.get_channel(BOSS_CHANNEL_ID)
    rift_ch = bot.get_channel(RIFT_CHANNEL_ID)
    if not boss_ch or not rift_ch:
        print("❌ CHANNELS NOT FOUND — CHECK IDS!")
        return
    print("✅ === FULL AUTO MODE STARTED ===")
    print(f"✅ Boss: {BOSS_CHANNEL_ID} | Rift: {RIFT_CHANNEL_ID}")
    print("✅ Using RoValra formula: ping × 1.12")

    while True:
        servers = get_roblox_servers()
        now = datetime.now()
        active_ids = set()

        for srv in servers:
            jid = srv.get("id")
            ping = srv.get("ping", 0)
            if not jid:
                continue
            active_ids.add(jid)

            # ✅ EXACT ROVALRA CALC
            uptime_sec = int(ping * ROVALRA_MULTIPLIER)
            h = uptime_sec // 3600
            m = (uptime_sec % 3600) // 60
            start_time = now - timedelta(seconds=uptime_sec)

            if jid not in tracked_servers:
                print(f"🆕 NEW SERVER | ID: {jid[:8]}... | UPTIME: {h}h {m}m")
                tracked_servers[jid] = start_time
                asyncio.create_task(lifecycle(jid, start_time, boss_ch, rift_ch))
            else:
                print(f"📌 EXISTING | ID: {jid[:8]}... | UPTIME: {h}h {m}m")

        # Remove dead servers
        for jid in list(tracked_servers.keys()):
            if jid not in active_ids:
                print(f"🗑️ REMOVED | ID: {jid[:8]}... (gone)")
                del tracked_servers[jid]

        await asyncio.sleep(120)

async def lifecycle(jid, start, boss_ch, rift_ch):
    link = f"https://www.roblox.com/games/start?placeId={GAME_ID}&gameId={jid}"
    while jid in tracked_servers:
        age = (datetime.now() - start).total_seconds()

        nr = RIFT_SPAWN - (age % RIFT_SPAWN)
        nb = BOSS_SPAWN - (age % BOSS_SPAWN)

        # RIFT WARNING
        if WARNING_EARLY < nr <= WARNING_EARLY + 30:
            print(f"⚠️ RIFT SOON | {jid[:8]}...")
            await rift_ch.send(f"🌀 **RIFT SPAWN SOON — 5 MIN!**\nID: `{jid}`\n👉 {link}")
            await asyncio.sleep(WARNING_EARLY)
            if jid in tracked_servers:
                await rift_ch.send(f"🌀 **RIFT SPAWNING NOW!**\n👉 {link}")

        # BOSS WARNING
        if WARNING_EARLY < nb <= WARNING_EARLY + 30:
            print(f"⚠️ BOSS SOON | {jid[:8]}...")
            await boss_ch.send(f"🚨 **BOSS SPAWN SOON — 5 MIN!**\nID: `{jid}`\n👉 {link}")
            await asyncio.sleep(WARNING_EARLY)
            if jid in tracked_servers:
                await boss_ch.send(f"🚨 **BOSS SPAWNING NOW!**\n👉 {link}")

        await asyncio.sleep(30)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ BOT LOGGED IN AS: {bot.user}")
    bot.loop.create_task(auto_scan())

# ---------------- RUN ----------------
if __name__ == "__main__":
    print("🚀 STARTING BOT...")
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        print("❌ BOT_TOKEN MISSING!")
    else:
        bot.run(token)
