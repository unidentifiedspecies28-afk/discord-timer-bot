import sys
import types
# Fix Python 3.14 audioop error — DO NOT REMOVE
sys.modules['audioop'] = types.ModuleType('audioop')

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# --------------------------
# ✅ YOUR SETTINGS — EDIT THESE
# --------------------------
BOSS_WEBHOOK = "https://discord.com/api/webhooks/1502263569633509487/NGKjFf4EGD32m3UbuafIadrObSSiOxujGXvWcWLSQj8OEAHRcHw-X_Q0OnZOq1r8Ykvw"
RIFT_WEBHOOK = "https://discord.com/api/webhooks/1502264183956308130/xLuNT-iod8k245vT_jx5u4pLVCasuwtLBAT0NjaJvR3IISH5UA3pjJ43T1bph6ENyzh-"

COOLDOWNS = {
    "Bosses": 3600,       # 60 minutes
    "SuperBosses": 3600,  # 60 minutes
    "Rifts": 10,        # 30 minutes
    "Raids": 7200         # 120 minutes
}

# Keep alive — keeps bot awake
app = Flask('')
@app.route('/')
def home(): return "✅ BOT ONLINE"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

# Bot setup
intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_servers = {}
user_timers = {}

# Sync slash commands
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ LOGGED IN AS: {bot.user}")
    print("✅ READY — TIMERS WILL PING YOU EVERY TIME")

# --------------------------
# 🤖 SERVER TRACKER (5min WARNING)
# --------------------------
async def track_server(link, start_time):
    while link in active_servers:
        age = (datetime.now() - start_time).total_seconds()
        until_rift = 5400 - (age % 5400)
        until_boss = 7200 - (age % 7200)

        # Rift alerts
        if 300 < until_rift <= 315:
            requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT SPAWNS IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers:
                requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT SPAWNING NOW**\n👉 {link}"})

        # Boss alerts
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

@bot.tree.command(name="timer", description="Start a personal cooldown timer")
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

    # Save timer
    if user_id not in user_timers:
        user_timers[user_id] = {}
    user_timers[user_id][t_type] = end_time

    await interaction.response.send_message(
        f"⏰ **{t_type}** started!\nReady: <t:{int(end_time.timestamp())}:R>"
    )

    # ✅ FIXED: Task is now DETACHED — will NOT be killed by Render
    async def wait_and_notify():
        await asyncio.sleep(duration)

        # Remove from list
        if user_id in user_timers and t_type in user_timers[user_id]:
            del user_timers[user_id][t_type]

        # Check remaining
        remaining = user_timers.get(user_id, {})
        if remaining:
            rem_text = f"\n📌 Still running: {', '.join(f'**{n}**' for n in remaining.keys())}"
        else:
            rem_text = "\n✅ All cooldowns finished!"

        # ✅ EXACT PING FORMAT <@!USERID>
        await channel.send(
            f"🔔 <@!{user_id}> — **{t_type}** TIMER IS FINISHED!{rem_text}"
        )

    # Start as independent task
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
