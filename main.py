# 🔧 FIX AUDIOOP ERROR — BLOCK IT BEFORE IT LOADS
import sys
sys.modules['audioop'] = type('fake_audioop', (), {})()

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
BOSS_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1502263569633509487/NGKjFf4EGD32m3UbuafIadrObSSiOxujGXvWcWLSQj8OEAHRcHw-X_Q0OnZOq1r8Ykvw"
RIFT_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1502264183956308130/xLuNT-iod8k245vT_jx5u4pLVCasuwtLBAT0NjaJvR3IISH5UA3pjJ43T1bph6ENyzh-"

RIFT_CYCLE = 5400    # 1h30m
BOSS_CYCLE = 7200    # 2h
WARNING_SEC = 300    # ⏰ 5 MIN BEFORE

COOLDOWNS = {
    "Bosses": 3600, "SuperBosses": 3600, "Rifts": 1800, "Raids": 7200
}

# --------------------------
# KEEP ALIVE
# --------------------------
app = Flask('')
@app.route('/')
def home(): return "Bot Online ✅"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

# --------------------------
# BOT SETUP
# --------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = False
bot = commands.Bot(command_prefix="!", intents=intents)

active_servers = {}
user_timers = {}

# --------------------------
# 📢 WEBHOOKS
# --------------------------
def send_boss_alert(message):
    try: requests.post(BOSS_WEBHOOK_URL, json={"content": message})
    except: pass

def send_rift_alert(message):
    try: requests.post(RIFT_WEBHOOK_URL, json={"content": message})
    except: pass

# --------------------------
# 🤖 SERVER TRACKER — 5 MIN WARNING
# --------------------------
async def track_server(join_link, server_start_time):
    while join_link in active_servers:
        server_age = (datetime.now() - server_start_time).total_seconds()

        until_rift = RIFT_CYCLE - (server_age % RIFT_CYCLE)
        until_boss = BOSS_CYCLE - (server_age % BOSS_CYCLE)

        # 🌀 RIFT
        if WARNING_SEC < until_rift <= WARNING_SEC + 10:
            send_rift_alert(f"🌀 **RIFT SPAWNING IN 5 MINUTES!**\n👉 **JOIN**: {join_link}")
            await asyncio.sleep(WARNING_SEC)
            if join_link in active_servers:
                send_rift_alert(f"🌀 **RIFT IS SPAWNING NOW!**\n👉 {join_link}")

        # 🚨 BOSS
        if WARNING_SEC < until_boss <= WARNING_SEC + 10:
            send_boss_alert(f"🌀 **BOSS SPAWNING IN 5 MINUTES!**\n👉 **JOIN**: {join_link}")
            await asyncio.sleep(WARNING_SEC)
            if join_link in active_servers:
                send_boss_alert(f"🚨 **BOSS IS SPAWNING NOW!**\n👉 {join_link}")

        await asyncio.sleep(15)

# --------------------------
# ⌨️ COMMANDS
# --------------------------
@bot.command()
async def addserver(ctx, join_link: str, hours: int, minutes: int):
    if join_link in active_servers:
        return await ctx.send("❌ Already tracking this server.")

    uptime_seconds = (hours * 3600) + (minutes * 60)
    start_time = datetime.now() - timedelta(seconds=uptime_seconds)
    active_servers[join_link] = start_time

    await ctx.send(f"✅ SERVER ADDED\nAlerts split to Boss/Rift channels | 5min warning active")
    asyncio.create_task(track_server(join_link, start_time))

@bot.command()
async def removeserver(ctx, join_link: str):
    if join_link in active_servers:
        del active_servers[join_link]
        await ctx.send("🗑️ Server removed.")
    else:
        await ctx.send("❌ Server not found.")

# --------------------------
# ⏰ TIMERS — PING + STATUS
# --------------------------
@bot.command()
async def timer(ctx, timer_type: str = None):
    if not timer_type or timer_type not in COOLDOWNS:
        return await ctx.send(f"❌ Usage: !timer [Bosses|SuperBosses|Rifts|Raids]")

    uid = ctx.author.id
    if uid not in user_timers: user_timers[uid] = {}
    user_timers[uid][timer_type] = datetime.now()
    end = datetime.now() + timedelta(seconds=COOLDOWNS[timer_type])

    await ctx.send(f"⏰ **{timer_type}** started! Ends <t:{int(end.timestamp())}:R>")

    await asyncio.sleep(COOLDOWNS[timer_type])

    if uid in user_timers and timer_type in user_timers[uid]:
        del user_timers[uid][timer_type]
        remaining = user_timers.get(uid, {})
        if remaining:
            list_rem = ", ".join([f"**{n}**" for n in remaining.keys()])
            extra = f"\n📌 Still running: {list_rem}"
        else:
            extra = "\n✅ All cooldowns done!"
        await ctx.send(f"🔔 <@{uid}> **{timer_type} COOLDOWN DONE!**{extra}")

@bot.command()
async def timers(ctx):
    uid = ctx.author.id
    active = user_timers.get(uid, {})
    if not active: return await ctx.send("✅ No active timers.")
    msg = "⏰ **YOUR TIMERS**\n"
    for name, start in active.items():
        end = start + timedelta(seconds=COOLDOWNS[name])
        msg += f"• {name}: Ready <t:{int(end.timestamp())}:R>\n"
    await ctx.send(msg)

# --------------------------
# START
# --------------------------
@bot.event
async def on_ready():
    print(f"✅ LOGGED IN: {bot.user} | NO AUDIOOP ERROR")

if __name__ == "__main__":
    bot.run(os.getenv("BOT_TOKEN"))
