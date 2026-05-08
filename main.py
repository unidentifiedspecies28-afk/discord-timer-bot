import discord
from discord.ext import commands
import asyncio
import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# --------------------------
# ✅ YOUR SETTINGS — EDIT THESE!
# --------------------------
BOSS_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1502263569633509487/NGKjFf4EGD32m3UbuafIadrObSSiOxujGXvWcWLSQj8OEAHRcHw-X_Q0OnZOq1r8Ykvw"   # Boss channel webhook
RIFT_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1502264183956308130/xLuNT-iod8k245vT_jx5u4pLVCasuwtLBAT0NjaJvR3IISH5UA3pjJ43T1bph6ENyzh-"   # Rift channel webhook

# Timings (DO NOT CHANGE THESE)
RIFT_CYCLE = 5400    # 1 hour 30 minutes (full cycle)
BOSS_CYCLE = 7200    # 2 hours (full cycle)
WARNING_SEC = 300    # ⏰ 5 MINUTES BEFORE — EXACTLY WHAT YOU WANTED

# Personal Timer Cooldowns
COOLDOWNS = {
    "Bosses": 3600,       # 60min
    "SuperBosses": 3600,  # 60min
    "Rifts": 1800,        # 30min
    "Raids": 7200         # 120min
}

# --------------------------
# KEEP ALIVE (Render requirement)
# --------------------------
app = Flask('')
@app.route('/')
def home(): return "Bot Online ✅"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): Thread(target=run, daemon=True).start()
keep_alive()

# --------------------------
# BOT SETUP — NO AUDIOOP ERROR
# --------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = False  # ✅ DISABLES VOICE — FIXES CRASH
bot = commands.Bot(command_prefix="!", intents=intents)

# Storage
active_servers = {}  # { join_link : start_time }
user_timers = {}     # { user_id: { timer_name: start_time } }

# --------------------------
# 📢 WEBHOOK SENDER
# --------------------------
def send_boss_alert(message):
    try:
        requests.post(BOSS_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"Boss Webhook Error: {e}")

def send_rift_alert(message):
    try:
        requests.post(RIFT_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"Rift Webhook Error: {e}")

# --------------------------
# 🤖 SERVER TRACKER — 5 MIN WARNING
# --------------------------
async def track_server(join_link, server_start_time):
    """Runs forever, alerts 5min before + NOW"""
    while join_link in active_servers:
        # How long has this server been alive
        server_age = (datetime.now() - server_start_time).total_seconds()

        # Time until NEXT event
        until_rift = RIFT_CYCLE - (server_age % RIFT_CYCLE)
        until_boss = BOSS_CYCLE - (server_age % BOSS_CYCLE)

        # ==========================
        # 🌀 RIFT — 5 MIN BEFORE → NOW
        # ==========================
        if WARNING_SEC < until_rift <= WARNING_SEC + 10:
            send_rift_alert(
                f"🌀 **RIFT SPAWNING IN 5 MINUTES!**\n"
                f"👉 **JOIN SERVER**: {join_link}"
            )
            await asyncio.sleep(WARNING_SEC)  # Wait full 5 mins
            if join_link in active_servers:
                send_rift_alert(
                    f"🌀 **RIFT IS SPAWNING NOW!**\n"
                    f"👉 **JOIN SERVER**: {join_link}"
                )

        # ==========================
        # 🚨 BOSS — 5 MIN BEFORE → NOW
        # ==========================
        if WARNING_SEC < until_boss <= WARNING_SEC + 10:
            send_boss_alert(
                f"🚨 **BOSS SPAWNING IN 5 MINUTES!**\n"
                f"👉 **JOIN SERVER**: {join_link}"
            )
            await asyncio.sleep(WARNING_SEC)  # Wait full 5 mins
            if join_link in active_servers:
                send_boss_alert(
                    f"🚨 **BOSS IS SPAWNING NOW!**\n"
                    f"👉 **JOIN SERVER**: {join_link}"
                )

        await asyncio.sleep(15)  # Check every 15s

# --------------------------
# ⌨️ COMMANDS — ADD / REMOVE SERVER
# --------------------------
@bot.command()
async def addserver(ctx, join_link: str, hours: int, minutes: int):
    """Add server ONCE: !addserver [link] [uptime_hours] [uptime_minutes]"""
    if join_link in active_servers:
        return await ctx.send("❌ This server is already being tracked!")

    # Calculate actual start time
    uptime_seconds = (hours * 3600) + (minutes * 60)
    start_time = datetime.now() - timedelta(seconds=uptime_seconds)

    # Save & start tracking
    active_servers[join_link] = start_time
    await ctx.send(
        f"✅ **SERVER ADDED SUCCESSFULLY**\n"
        f"🔗 Link: {join_link}\n"
        f"⏱ Starting Uptime: {hours}h {minutes}m\n"
        f"📢 Alerts will go to **Boss / Rift channels**\n"
        f"⚠️ **Announces 5 minutes before every spawn!**"
    )
    asyncio.create_task(track_server(join_link, start_time))

@bot.command()
async def removeserver(ctx, join_link: str):
    """Stop tracking: !removeserver [link]"""
    if join_link in active_servers:
        del active_servers[join_link]
        await ctx.send("🗑️ Server removed from tracking. No more alerts.")
    else:
        await ctx.send("❌ Server not found in list.")

# --------------------------
# ⏰ PERSONAL TIMERS — PING + STATUS
# --------------------------
@bot.command()
async def timer(ctx, timer_type: str = None):
    """Start timer: !timer Bosses / SuperBosses / Rifts / Raids"""
    if not timer_type or timer_type not in COOLDOWNS:
        opts = " | ".join(COOLDOWNS.keys())
        return await ctx.send(f"❌ Usage: `!timer [{opts}]`")

    user_id = ctx.author.id
    if user_id not in user_timers:
        user_timers[user_id] = {}

    # Save timer
    user_timers[user_id][timer_type] = datetime.now()
    end_time = datetime.now() + timedelta(seconds=COOLDOWNS[timer_type])

    await ctx.send(
        f"⏰ **{timer_type} TIMER STARTED**\n"
        f"⌛ Ends: <t:{int(end_time.timestamp())}:R>"
    )

    # Wait for cooldown
    await asyncio.sleep(COOLDOWNS[timer_type])

    # Remove & notify
    if user_id in user_timers and timer_type in user_timers[user_id]:
        del user_timers[user_id][timer_type]

        # Check what else is running
        remaining = user_timers.get(user_id, {})
        if remaining:
            list_remaining = ", ".join([f"**{name}**" for name in remaining.keys()])
            extra = f"\n📌 You still have: {list_remaining} running."
        else:
            extra = "\n✅ All your cooldowns are finished!"

        await ctx.send(f"🔔 <@{user_id}> **{timer_type} COOLDOWN DONE!**{extra}")

@bot.command()
async def timers(ctx):
    """Show all your active timers"""
    user_id = ctx.author.id
    active = user_timers.get(user_id, {})

    if not active:
        return await ctx.send("✅ You have **no active timers** running.")

    msg = "⏰ **YOUR ACTIVE TIMERS**\n"
    for name, start_time in active.items():
        end_time = start_time + timedelta(seconds=COOLDOWNS[name])
        msg += f"• **{name}** → Ends <t:{int(end_time.timestamp())}:R>\n"

    await ctx.send(msg)

# --------------------------
# START BOT
# --------------------------
@bot.event
async def on_ready():
    print(f"✅ LOGGED IN AS: {bot.user}")
    print("✅ SYSTEM READY: 5min warnings | Split channels | Timers")

if __name__ == "__main__":
    print("🚀 STARTING BOT — FINAL VERSION")
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        print("❌ MISSING BOT TOKEN!")
    else:
        bot.run(token)
