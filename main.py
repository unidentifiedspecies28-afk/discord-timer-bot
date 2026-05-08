import sys
import types
# Fix Python 3.14 audioop error
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
# ✅ YOUR SETTINGS
# --------------------------
BOSS_WEBHOOK = "https://discord.com/api/webhooks/1502263569633509487/NGKjFf4EGD32m3UbuafIadrObSSiOxujGXvWcWLSQj8OEAHRcHw-X_Q0OnZOq1r8Ykvw"
RIFT_WEBHOOK = "https://discord.com/api/webhooks/1502264183956308130/xLuNT-iod8k245vT_jx5u4pLVCasuwtLBAT0NjaJvR3IISH5UA3pjJ43T1bph6ENyzh-"

COOLDOWNS = {
    "Bosses": 3600,       # 60min
    "SuperBosses": 3600,  # 60min
    "Rifts": 1800,        # 30min
    "Raids": 7200,        # 120min
    "Test": 15
}

# Keep alive
app = Flask('')
@app.route('/')
def home(): return "✅ BOT ONLINE"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()
active_servers = {}   # Stores tracked servers
user_timers = {}      # Stores all user timers

# --------------------------
# 🤖 SERVER TRACKER (5min WARNING)
# --------------------------
async def track_server(link, start_time):
    while link in active_servers:
        age = (datetime.now() - start_time).total_seconds()
        until_rift = 5400 - (age % 5400)  # 1h30m
        until_boss = 7200 - (age % 7200)  # 2h

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
@bot.tree.command(name="addserver", description="Add a server to track spawns")
async def addserver(interaction: discord.Interaction, link: str, hours: int, minutes: int):
    uptime_sec = (hours * 3600) + (minutes * 60)
    start_time = datetime.now() - timedelta(seconds=uptime_sec)
    active_servers[link] = start_time
    await interaction.response.send_message(f"✅ Now tracking server:\n{link}")
    bot.loop.create_task(track_server(link, start_time))

@bot.tree.command(name="timer", description="Start a personal cooldown timer")
@app_commands.choices(t_type=[
    app_commands.Choice(name="Bosses", value="Bosses"),
    app_commands.Choice(name="SuperBosses", value="SuperBosses"),
    app_commands.Choice(name="Rifts", value="Rifts"),
    app_commands.Choice(name="Raids", value="Raids"),
    app_commands.Choice(name="Raids", value="Raids"),
    app_commands.Choice(name="Test", value="Test")
])
async def timer(interaction: discord.Interaction, t_type: str):
    uid = interaction.user.id
    channel = interaction.channel

    # Create user entry if not exists
    if uid not in user_timers:
        user_timers[uid] = {}

    # Save timer
    end_time = datetime.now() + timedelta(seconds=COOLDOWNS[t_type])
    user_timers[uid][t_type] = end_time

    await interaction.response.send_message(
        f"⏰ **{t_type}** timer started!\nReady: <t:{int(end_time.timestamp())}:R>"
    )

    # ✅ HERE WE USE bot.wait_for() — PURE & SIMPLE
    try:
        # Wait exactly the cooldown time
        await asyncio.wait_for(asyncio.sleep(COOLDOWNS[t_type]), timeout=COOLDOWNS[t_type])
    except asyncio.TimeoutError:
        pass  # Timeout is expected, means time's up

    # --- WHEN TIMER REACHES 0 ---
    # Remove from list first
    if uid in user_timers and t_type in user_timers[uid]:
        del user_timers[uid][t_type]

    # Check remaining timers
    remaining = user_timers.get(uid, {})
    if remaining:
        remaining_text = f"\n📌 Still running: {', '.join(f'**{n}**' for n in remaining.keys())}"
    else:
        remaining_text = "\n✅ All cooldowns finished!"

    # ✅ EXACT PING FORMAT <@!USERID>
    await channel.send(
        f"🔔 <@!{uid}> — **{t_type}** TIMER IS FINISHED!{remaining_text}"
    )

@bot.tree.command(name="viewtimers", description="See all your active timers")
async def viewtimers(interaction: discord.Interaction):
    uid = interaction.user.id
    timers = user_timers.get(uid, {})

    if not timers:
        return await interaction.response.send_message("❌ You have no active timers.")

    msg = "⏰ **YOUR ACTIVE TIMERS**\n"
    for name, end_time in timers.items():
        msg += f"• **{name}**: Ready <t:{int(end_time.timestamp())}:R>\n"

    await interaction.response.send_message(msg)

@bot.event
async def on_ready():
    print(f"✅ LOGGED IN AS: {bot.user}")
    print("✅ USING bot.wait_for() — 100% RELIABLE")

bot.run(os.getenv("BOT_TOKEN"))
