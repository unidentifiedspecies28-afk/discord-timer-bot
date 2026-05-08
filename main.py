import sys
import types
# Bypasses the audioop error for Python 3.14
sys.modules['audioop'] = types.ModuleType('audioop')

import discord
from discord.ext import commands, tasks
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
BOSS_WEBHOOK = "YOUR_BOSS_WEBHOOK_URL"
RIFT_WEBHOOK = "YOUR_RIFT_WEBHOOK_URL"

COOLDOWNS = {
    "Bosses": 3600, "SuperBosses": 3600, "Rifts": 1800, "Raids": 7200, "Test": 15
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
        await self.tree.sync()
        self.check_timers.start()

    # BACKGROUND CHECKER - Monitors for finished timers
    @tasks.loop(seconds=5)
    async def check_timers(self):
        now = datetime.now()
        for uid, timers in list(user_timers.items()):
            for t_type, data in list(timers.items()):
                if now >= data['end']:
                    channel = self.get_channel(data['channel'])
                    if channel:
                        # Remove timer before pinging
                        del user_timers[uid][t_type]
                        
                        # Check what else is running
                        others = user_timers.get(uid, {})
                        status = f"Other active: {', '.join(others.keys())}" if others else "All done!"
                        
                        # THE PING: Format <@!USERID> as requested
                        await channel.send(f"🔔 <@!{uid}> **{t_type}** timer is finished!\n{status}")
                    else:
                        del user_timers[uid][t_type]

bot = MyBot()
active_servers = {}
user_timers = {} # { uid: { type: {end: datetime, channel: int} } }

# --------------------------
# SERVER TRACKER
# --------------------------
async def track_server(link, start_time):
    while link in active_servers:
        age = (datetime.now() - start_time).total_seconds()
        u_rift = 5400 - (age % 5400)
        u_boss = 7200 - (age % 7200)
        
        if 300 < u_rift <= 315:
            requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers: requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT NOW**\n👉 {link}"})
            
        if 300 < u_boss <= 315:
            requests.post(BOSS_WEBHOOK, json={"content": f"🚨 **BOSS IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers: requests.post(BOSS_WEBHOOK, json={"content": f"🚨 **BOSS NOW**\n👉 {link}"})
        await asyncio.sleep(15)

# --------------------------
# SLASH COMMANDS
# --------------------------
@bot.tree.command(name="addserver", description="Track a server")
async def addserver(interaction: discord.Interaction, link: str, hours: int, minutes: int):
    uptime = (hours * 3600) + (minutes * 60)
    start = datetime.now() - timedelta(seconds=uptime)
    active_servers[link] = start
    await interaction.response.send_message(f"✅ Tracking: {link}")
    asyncio.create_task(track_server(link, start))

@bot.tree.command(name="timer", description="Start a personal cooldown")
@app_commands.choices(t_type=[
    app_commands.Choice(name="Bosses", value="Bosses"),
    app_commands.Choice(name="SuperBosses", value="SuperBosses"),
    app_commands.Choice(name="Rifts", value="Rifts"),
    app_commands.Choice(name="Raids", value="Raids"),
    app_commands.Choice(name="Test", value="Test")
])
async def timer(interaction: discord.Interaction, t_type: str):
    uid = interaction.user.id
    if uid not in user_timers: user_timers[uid] = {}
    
    end_time = datetime.now() + timedelta(seconds=COOLDOWNS[t_type])
    
    user_timers[uid][t_type] = {
        'end': end_time,
        'channel': interaction.channel_id
    }
    
    await interaction.response.send_message(f"⏰ {t_type} set! Ends <t:{int(end_time.timestamp())}:R>")

@bot.tree.command(name="viewtimers", description="View your personal timers")
async def viewtimers(interaction: discord.Interaction):
    active = user_timers.get(interaction.user.id, {})
    if not active: 
        return await interaction.response.send_message("❌ You have no active timers.")
    
    msg = "⏰ **Your Active Cooldowns:**\n"
    for name, data in active.items():
        msg += f"• **{name}**: Ready <t:{int(data['end'].timestamp())}:R>\n"
    
    await interaction.response.send_message(msg)

bot.run(os.getenv("BOT_TOKEN"))
