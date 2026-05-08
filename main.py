import sys
# 1. FIXED: This part fixes the 'audioop' crash so the bot stays online
import types
sys.modules['audioop'] = types.ModuleType('audioop')

import discord
from discord.ext import commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# --------------------------
# 2. CONFIG: Paste your Webhooks here
# --------------------------
BOSS_WEBHOOK = "YOUR_BOSS_WEBHOOK_URL"
RIFT_WEBHOOK = "YOUR_RIFT_WEBHOOK_URL"

COOLDOWNS = {
    "Bosses": 3600,       # 1 Hour
    "SuperBosses": 3600,  # 1 Hour
    "Rifts": 1800,        # 30 Mins
    "Raids": 7200         # 2 Hours
}

# Keep Alive for Render
app = Flask('')
@app.route('/')
def home(): return "Bot is Online"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_servers = {}
user_timers = {}

# --------------------------
# 3. SERVER ANNOUNCER (5m Warnings)
# --------------------------
async def track_server(link, start_time):
    while link in active_servers:
        age = (datetime.now() - start_time).total_seconds()
        
        # Rift: 1h30m (5400s) | Boss: 2h (7200s)
        u_rift = 5400 - (age % 5400)
        u_boss = 7200 - (age % 7200)

        # Rift Alert 5m before
        if 300 < u_rift <= 315:
            requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers:
                requests.post(RIFT_WEBHOOK, json={"content": f"🌀 **RIFT NOW**\n👉 {link}"})

        # Boss Alert 5m before
        if 300 < u_boss <= 315:
            requests.post(BOSS_WEBHOOK, json={"content": f"🚨 **BOSS IN 5 MIN**\n👉 {link}"})
            await asyncio.sleep(300)
            if link in active_servers:
                requests.post(BOSS_WEBHOOK, json={"content": f"🚨 **BOSS NOW**\n👉 {link}"})

        await asyncio.sleep(15)

@bot.command()
async def addserver(ctx, link: str, hours: int, minutes: int):
    """Adds a server once and repeats alerts forever"""
    uptime = (hours * 3600) + (minutes * 60)
    start = datetime.now() - timedelta(seconds=uptime)
    active_servers[link] = start
    await ctx.send(f"✅ Tracking: {link}\nAlerts split to Boss/Rift channels with 5m warnings.")
    asyncio.create_task(track_server(link, start))

# --------------------------
# 4. PERSONAL TIMERS (Pings & Checks)
# --------------------------
@bot.command()
async def timer(ctx, t_type: str = None):
    if not t_type or t_type not in COOLDOWNS:
        return await ctx.send(f"Usage: !timer [Bosses|SuperBosses|Rifts|Raids]")
    
    uid = ctx.author.id
    if uid not in user_timers: user_timers[uid] = {}
    user_timers[uid][t_type] = datetime.now()
    
    end = datetime.now() + timedelta(seconds=COOLDOWNS[t_type])
    await ctx.send(f"⏰ {t_type} set! Ready <t:{int(end.timestamp())}:R>")
    
    await asyncio.sleep(COOLDOWNS[t_type])
    
    if uid in user_timers and t_type in user_timers[uid]:
        del user_timers[uid][t_type]
        others = user_timers.get(uid, {})
        # FIXED: This pings the user and tells them if others are running
        status = f"\nKeep going! Other active: {', '.join(others.keys())}" if others else "\nAll your cooldowns are done!"
        await ctx.send(f"🔔 <@{uid}> **{t_type} DONE!**{status}")

@bot.command()
async def timers(ctx):
    active = user_timers.get(ctx.author.id, {})
    if not active: return await ctx.send("No active timers.")
    msg = "\n".join([f"• {n}: <t:{int((s + timedelta(seconds=COOLDOWNS[n])).timestamp())}:R>" for n, s in active.items()])
    await ctx.send(f"⏰ **Your Timers:**\n{msg}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(os.getenv("BOT_TOKEN"))
