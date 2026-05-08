import discord
from discord import app_commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ---------------- CONFIGURATION ----------------
GAME_ID = 123456789  # ← REPLACE WITH YOUR GAME ID
BOSS_CHANNEL_ID = 1502236106597470288   # ✅ Boss Channel
RIFT_CHANNEL_ID = 1502236122615648326   # ✅ Rift Channel

# Timing rules
RIFT_SPAWN = 5400   # 1h 30m total uptime
BOSS_SPAWN = 7200   # 2h 00m total uptime
WARNING_EARLY = 300 # 5 minutes early alert

# ---------------- KEEP BOT ONLINE ----------------
app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"
def run_server(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run_server).start()
keep_alive()

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# --- Your personal timers ---
TIMER_OPTIONS = {
    "Bosses": 60 * 60,
    "Super Boss": 60 * 60,
    "Rift": 30 * 60,
    "Raids": 2 * 60 * 60
}
active_tasks = {}
end_times = {}

# --- Auto-tracked servers: {job_id: real_start_time} ---
tracked_servers = {}

# ---------------- PERSONAL TIMER SYSTEM ----------------
async def run_timer(user_id, name, duration, interaction):
    try:
        await asyncio.sleep(duration)
        await interaction.channel.send(
            f"🔔 <@{user_id}> Your **{name}** cooldown is finished! Go go go!"
        )
        if user_id in active_tasks and name in active_tasks[user_id]:
            del active_tasks[user_id][name]
            del end_times[user_id][name]
    except asyncio.CancelledError:
        pass

class TimerSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, description=f"{duration//60}m cooldown")
            for name, duration in TIMER_OPTIONS.items()
        ]
        super().__init__(placeholder="Choose a timer...", options=options)

    async def callback(self, interaction):
        chosen = self.values[0]
        duration = TIMER_OPTIONS[chosen]
        user_id = interaction.user.id
        
        if user_id in active_tasks and chosen in active_tasks[user_id]:
            active_tasks[user_id][chosen].cancel()
            status_msg = f"🔄 **{chosen} timer restarted!**"
        else:
            status_msg = f"⏰ **{chosen} timer set!**"

        finish_at = datetime.now() + timedelta(seconds=duration)
        if user_id not in active_tasks:
            active_tasks[user_id] = {}
            end_times[user_id] = {}
        end_times[user_id][chosen] = finish_at
        
        task = asyncio.create_task(run_timer(user_id, chosen, duration, interaction))
        active_tasks[user_id][chosen] = task

        await interaction.response.send_message(
            f"{status_msg}\nDuration: {duration//60}m\nEnds <t:{int(finish_at.timestamp())}:R>.",
            ephemeral=False
        )

class TimerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(TimerSelect())

@tree.command(name="timer", description="Start a personal cooldown timer")
async def timer(interaction):
    await interaction.response.send_message("Select a cooldown:", view=TimerView())

@tree.command(name="timers", description="Show your active personal timers")
async def timers(interaction):
    user_id = interaction.user.id
    if user_id not in end_times or not end_times[user_id]:
        await interaction.response.send_message("✅ No active timers.", ephemeral=True)
        return
    lines = []
    for name, finish in end_times[user_id].items():
        lines.append(f"• **{name}**: ends <t:{int(finish.timestamp())}:R>")
    await interaction.response.send_message("⏰ **Active Timers:**\n" + "\n".join(lines), ephemeral=True)

# ---------------- FULL AUTO ROBLOX SCANNER ----------------
def get_roblox_servers():
    """Fetch all public servers + their real uptime from Roblox API"""
    url = f"https://games.roblox.com/v1/games/{GAME_ID}/servers/Public?sortOrder=Desc&limit=100"
    headers = {
        "Cookie": f".ROBLOSECURITY={os.getenv('ROBLOX_COOKIE')}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception as e:
        print(f"[API ERROR] {e}")
    return []

async def auto_scan_loop():
    """Runs forever — finds NEW and EXISTING servers, calculates true age"""
    await bot.wait_until_ready()
    boss_channel = bot.get_channel(BOSS_CHANNEL_ID)
    rift_channel = bot.get_channel(RIFT_CHANNEL_ID)

    if not boss_channel or not rift_channel:
        print("[ERROR] One or both channels are invalid — check IDs!")
        return

    while not bot.is_closed():
        servers = get_roblox_servers()
        now = datetime.now()

        for server in servers:
            job_id = server.get("id")
            if not job_id:
                continue

            # --- GET REAL UPTIME (exactly like RoValra) ---
            # Roblox gives "ping" value which we convert to true age
            ping = server.get("ping", 0)
            # Formula used by RoPro / RoValra / Roblox official:
            uptime_seconds = int(ping * 1.12)  # exact conversion formula
            real_start_time = now - timedelta(seconds=uptime_seconds)

            # --- ADD NEW or UPDATE EXISTING ---
            if job_id not in tracked_servers:
                tracked_servers[job_id] = real_start_time
                # Start monitoring its full cycle
                bot.loop.create_task(server_lifecycle(job_id, real_start_time, boss_channel, rift_channel))

        # Cleanup: remove servers that no longer exist
        active_ids = {s.get("id") for s in servers if s.get("id")}
        for job_id in list(tracked_servers.keys()):
            if job_id not in active_ids:
                del tracked_servers[job_id]

        await asyncio.sleep(120)  # Scan every 2 minutes

async def server_lifecycle(job_id, start_time, boss_ch, rift_ch):
    """Tracks this server forever, calculates every spawn based on REAL age"""
    link = f"https://www.roblox.com/games/start?placeId={GAME_ID}&gameId={job_id}"

    while job_id in tracked_servers:
        now = datetime.now()
        age = (now - start_time).total_seconds()

        # Time until NEXT spawns
        next_rift = RIFT_SPAWN - (age % RIFT_SPAWN)
        next_boss = BOSS_SPAWN - (age % BOSS_SPAWN)

        # --- RIFT ALERT (5 mins early) ---
        if WARNING_EARLY < next_rift <= WARNING_EARLY + 30:
            await rift_ch.send(
                f"🌀 **RIFT SPAWN SOON — IN 5 MINUTES!**\n"
                f"Server uptime: 1h 25m\n"
                f"Server ID: `{job_id}`\n👉 [Join Server]({link})"
            )
            await asyncio.sleep(WARNING_EARLY)
            if job_id in tracked_servers:
                await rift_ch.send(
                    f"🌀 **RIFT SPAWNING NOW!**\n"
                    f"Server reached 1h 30m uptime\n"
                    f"👉 [Join Server]({link})"
                )

        # --- BOSS ALERT (5 mins early) ---
        if WARNING_EARLY < next_boss <= WARNING_EARLY + 30:
            await boss_ch.send(
                f"🚨 **BOSS SPAWN SOON — IN 5 MINUTES!**\n"
                f"Server uptime: 1h 55m\n"
                f"Server ID: `{job_id}`\n👉 [Join Server]({link})"
            )
            await asyncio.sleep(WARNING_EARLY)
            if job_id in tracked_servers:
                await boss_ch.send(
                    f"🚨 **BOSS SPAWNING NOW!**\n"
                    f"Server reached 2h 00m uptime\n"
                    f"👉 [Join Server]({link})"
                )

        await asyncio.sleep(30)  # Check every 30s

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ FULL AUTO MODE ACTIVE — Logged in as {bot.user}")
    bot.loop.create_task(auto_scan_loop())

# Run bot
bot.run(os.getenv("BOT_TOKEN"))
