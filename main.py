import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import requests
import sys
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# --------------------------
# ✅ YOUR SETTINGS — EDIT THESE
# --------------------------
BOSS_WEBHOOK = "YOUR_BOSS_WEBHOOK_URL"
RIFT_WEBHOOK = "YOUR_RIFT_WEBHOOK_URL"

COOLDOWNS = {
    "Bosses": 3600,       # 60 minutes
    "SuperBosses": 3600,  # 60 minutes
    "Rifts": 1800,        # 30 minutes
    "Raids": 7200         # 120 minutes
}

# Keep alive — keeps bot awake
app = Flask('')
@app.route('/')
def home(): return "✅ BOT ONLINE"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

# Bot setup — FULL INTENTS ENABLED
intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_servers = {}
user_timers = {}  # Structure: { user_id: { timer_name: end_time } }

# Sync slash commands + show Python version
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ LOGGED IN AS: {bot.user}")
    print(f"✅ PYTHON VERSION RUNNING: {sys.version}")

# --------------------------
# 🤖 SERVER TRACKER (5min WARNING)
# --------------------------
async def track_server(link, start_time):
    while link in active_servers:
        age = (datetime.now() - start_time).total_seconds()
        until_rift = 5400 - (age % 5400)  # 1h30m cycle
        until_boss = 7200 - (age % 7200)  # 2h cycle

        # 🌀 RIFT ALERTS
        if 300 < until_rift <= 315:
            requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT SPAWNS IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers:
                requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT SPAWNING NOW**\n👉 {link}"})

        # 🚨 BOSS ALERTS
        if 300 < until_boss <= 315:
            requests.post(BOSS_WEBHOOK, json={"content": f"🚨 **BOSS SPAWNS IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers:
                requests.post(BOSS_WEBHOOK, json={"content": f"🚨 **BOSS SPAWNING NOW**\n👉 {link}"})

        await asyncio.sleep(15)

# --------------------------
# 📝 SLASH COMMANDS
# --------------------------
@bot.tree.command(name="addserver", description="Add server to track spawns")
async def addserver(interaction: discord.Interaction, link: str, hours: int, minutes: int):
    uptime_sec = (hours * 3600) + (minutes * 60)
    start_time = datetime.now() - timedelta(seconds=uptime_sec)
    active_servers[link] = start_time
    await interaction.response.send_message(f"✅ Now tracking:\n{link}")
    bot.loop.create_task(track_server(link, start_time))

@bot.tree.command(name="timer", description="Start a personal cooldown timer — resets if already running")
@app_commands.choices(t_type=[
    app_commands.Choice(name="Bosses", value="Bosses"),
    app_commands.Choice(name="SuperBosses", value="SuperBosses"),
    app_commands.Choice(name="Rifts", value="Rifts"),
    app_commands.Choice(name="Raids", value="Raids")
])
async def timer(interaction: discord.Interaction, t_type: str):
    user_id = interaction.user.id
    channel = interaction.channel
    duration = COOLDOWNS[t_type]
    end_time = datetime.now() + timedelta(seconds=duration)

    # Create user entry if not exists
    if user_id not in user_timers:
        user_timers[user_id] = {}

    # ✅ FIX: REPLACE / RESET IF ALREADY EXISTS (no duplicates)
    user_timers[user_id][t_type] = end_time

    await interaction.response.send_message(
        f"⏰ **{t_type}** timer {'RESTARTED' if t_type in user_timers[user_id] else 'STARTED'}!\nReady: <t:{int(end_time.timestamp())}:R>"
    )

    # ✅ DETACHED TASK — RUNS INDEPENDENTLY
    async def wait_and_notify():
        await asyncio.sleep(duration)

        # ✅ ONLY TRIGGER IF THIS IS STILL THE CURRENT SAVED TIMER (prevents old duplicate triggers)
        if user_id in user_timers and t_type in user_timers[user_id]:
            # Double-check: if saved time matches our end time OR time is up
            if user_timers[user_id][t_type] == end_time or datetime.now() >= user_timers[user_id][t_type]:
                # Remove it
                del user_timers[user_id][t_type]

                # Check remaining timers
                remaining = user_timers.get(user_id, {})
                if remaining:
                    rem_text = f"\n📌 Still running: {', '.join(f'**{n}**' for n in remaining.keys())}"
                else:
                    rem_text = "\n✅ All cooldowns finished!"

                # ✅ EXACT PING FORMAT <@!USERID>
                await channel.send(
                    f"🔔 <@!{user_id}> — **{t_type}** TIMER IS FINISHED!{rem_text}"
                )

    # Start independent task
    bot.loop.create_task(wait_and_notify())

@bot.tree.command(name="viewtimers", description="See your active timers")
async def viewtimers(interaction: discord.Interaction):
    user_id = interaction.user.id
    timers = user_timers.get(user_id, {})

    if not timers:
        return await interaction.response.send_message("❌ No active timers.")

    msg = "⏰ **YOUR TIMERS**\n"
    for name, end in timers.items():
        msg += f"• **{name}**: Ready <t:{int(end.timestamp())}:R>\n"

    await interaction.response.send_message(msg)

bot.run(os.getenv("BOT_TOKEN"))
