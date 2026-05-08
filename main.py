import sys
import types
# Bypasses the audioop error for Python 3.14
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
# CONFIG
# --------------------------
BOSS_WEBHOOK = "https://discord.com/api/webhooks/1502263569633509487/NGKjFf4EGD32m3UbuafIadrObSSiOxujGXvWcWLSQj8OEAHRcHw-X_Q0OnZOq1r8Ykvw"
RIFT_WEBHOOK = "https://discord.com/api/webhooks/1502264183956308130/xLuNT-iod8k245vT_jx5u4pLVCasuwtLBAT0NjaJvR3IISH5UA3pjJ43T1bph6ENyzh-"
"

COOLDOWNS = {
    "Bosses": 3600, "SuperBosses": 3600, "Rifts": 1800, "Raids": 7200
}

app = Flask('')
@app.route('/')
def home(): return "Bot Online"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # This makes the slash commands appear in Discord
        await self.tree.sync()

bot = MyBot()
active_servers = {}
user_timers = {}

# --------------------------
# SERVER ANNOUNCER (5m Warning)
# --------------------------
async def track_server(link, start_time):
    while link in active_servers:
        age = (datetime.now() - start_time).total_seconds()
        u_rift = 5400 - (age % 5400)
        u_boss = 7200 - (age % 7200)

        # Rift Alert
        if 300 < u_rift <= 315:
            requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers:
                requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT NOW**\n👉 {link}"})

        # Boss Alert
        if 300 < u_boss <= 315:
            requests.post(BOSS_WEBHOOK, json={"content": f"🚨 **BOSS IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers:
                requests.post(BOSS_WEBHOOK, json={"content": f"🚨 **BOSS NOW**\n👉 {link}"})
        await asyncio.sleep(15)

# --------------------------
# SLASH COMMANDS
# --------------------------
@bot.tree.command(name="addserver", description="Track a new server")
async def addserver(interaction: discord.Interaction, link: str, hours: int, minutes: int):
    uptime = (hours * 3600) + (minutes * 60)
    start = datetime.now() - timedelta(seconds=uptime)
    active_servers[link] = start
    await interaction.response.send_message(f"✅ Tracking: {link}")
    asyncio.create_task(track_server(link, start))

@bot.tree.command(name="timer", description="Start a personal cooldown timer")
@app_commands.choices(t_type=[
    app_commands.Choice(name="Bosses", value="Bosses"),
    app_commands.Choice(name="SuperBosses", value="SuperBosses"),
    app_commands.Choice(name="Rifts", value="Rifts"),
    app_commands.Choice(name="Raids", value="Raids")
])
async def timer(interaction: discord.Interaction, t_type: str):
    uid = interaction.user.id
    if uid not in user_timers: user_timers[uid] = {}
    user_timers[uid][t_type] = datetime.now()
    
    end = datetime.now() + timedelta(seconds=COOLDOWNS[t_type])
    
    # Confirming the timer started
    await interaction.response.send_message(f"⏰ {t_type} set! Ready <t:{int(end.timestamp())}:R>")
    
    # Wait for the cooldown
    await asyncio.sleep(COOLDOWNS[t_type])
    
    # Check if timer is still valid
    if uid in user_timers and t_type in user_timers[uid]:
        del user_timers[uid][t_type]
        others = user_timers.get(uid, {})
        
        # STATUS MESSAGE
        if others:
            status = f"Keep going! Your other active timers: **{', '.join(others.keys())}**"
        else:
            status = "All your cooldowns are finished!"
            
        # THE PING: Sends a message mentioning you directly
        await interaction.channel.send(f"🔔 <@{uid}> **Your {t_type} cooldown is DONE!**\n{status}")

@bot.tree.command(name="timers", description="View your active timers")
async def timers(interaction: discord.Interaction):
    active = user_timers.get(interaction.user.id, {})
    if not active: 
        return await interaction.response.send_message("No active timers.")
    msg = "\n".join([f"• {n}: <t:{int((s + timedelta(seconds=COOLDOWNS[n])).timestamp())}:R>" for n, s in active.items()])
    await interaction.response.send_message(f"⏰ **Your Active Timers:**\n{msg}")

bot.run(os.getenv("BOT_TOKEN"))
