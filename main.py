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

# ✅ ONLY THIS CHANNEL CAN USE COMMANDS
ALLOWED_CHANNEL_ID = 1466811692372594840

COOLDOWNS = {
    "Bosses": 3600,       # 60 minutes
    "SuperBosses": 3600,  # 60 minutes
    "Rifts": 1800,        # 30 minutes
    "Raids": 7200         # 120 minutes
}

# --------------------------
# KEEP ALIVE
# --------------------------
app = Flask('')

@app.route('/')
def home():
    return "✅ BOT ONLINE"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    Thread(target=run, daemon=True).start()

keep_alive()

# --------------------------
# BOT SETUP
# --------------------------
intents = discord.Intents.all()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

active_servers = {}
user_timers = {}

# --------------------------
# CHANNEL CHECK FUNCTION
# --------------------------
def valid_channel(interaction: discord.Interaction):
    return (
        interaction.guild is not None and
        interaction.channel_id == ALLOWED_CHANNEL_ID
    )

# --------------------------
# BOT READY
# --------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ LOGGED IN AS: {bot.user}")
    print(f"✅ PYTHON VERSION RUNNING: {sys.version}")

# --------------------------
# /timer COMMAND
# --------------------------
@bot.tree.command(
    name="timer",
    description="Start a personal cooldown timer — resets if already running"
)
@app_commands.choices(t_type=[
    app_commands.Choice(name="Bosses", value="Bosses"),
    app_commands.Choice(name="SuperBosses", value="SuperBosses"),
    app_commands.Choice(name="Rifts", value="Rifts"),
    app_commands.Choice(name="Raids", value="Raids")
])
async def timer(interaction: discord.Interaction, t_type: str):

    # ❌ BLOCK DMS + WRONG CHANNELS
    if not valid_channel(interaction):
        return await interaction.response.send_message(
            "❌ You can only use this command in the designated channel.",
            ephemeral=True
        )

    user_id = interaction.user.id
    channel = interaction.channel

    duration = COOLDOWNS[t_type]
    end_time = datetime.now() + timedelta(seconds=duration)

    # Create user entry if missing
    if user_id not in user_timers:
        user_timers[user_id] = {}

    # Check if timer already existed
    restarted = t_type in user_timers[user_id]

    # Replace/reset timer
    user_timers[user_id][t_type] = end_time

    await interaction.response.send_message(
        f"⏰ **{t_type}** timer "
        f"{'RESTARTED' if restarted else 'STARTED'}!\n"
        f"Ready: <t:{int(end_time.timestamp())}:R>"
    )

    # --------------------------
    # BACKGROUND TIMER TASK
    # --------------------------
    async def wait_and_notify():
        await asyncio.sleep(duration)

        # Make sure this is still the active timer
        if user_id in user_timers and t_type in user_timers[user_id]:

            current_timer = user_timers[user_id][t_type]

            if current_timer == end_time or datetime.now() >= current_timer:

                # Remove finished timer
                del user_timers[user_id][t_type]

                # Remaining timers
                remaining = user_timers.get(user_id, {})

                if remaining:
                    rem_text = (
                        "\n📌 Still running: " +
                        ", ".join(
                            f"**{name}**"
                            for name in remaining.keys()
                        )
                    )
                else:
                    rem_text = "\n✅ All cooldowns finished!"

                # Send ping notification
                await channel.send(
                    f"🔔 <@!{user_id}> — "
                    f"**{t_type}** TIMER IS FINISHED!"
                    f"{rem_text}"
                )

    # Start detached task
    bot.loop.create_task(wait_and_notify())

# --------------------------
# /viewtimers COMMAND
# --------------------------
@bot.tree.command(
    name="viewtimers",
    description="See your active timers"
)
async def viewtimers(interaction: discord.Interaction):

    # ❌ BLOCK DMS + WRONG CHANNELS
    if not valid_channel(interaction):
        return await interaction.response.send_message(
            "❌ You can only use this command in the designated channel.",
            ephemeral=True
        )

    user_id = interaction.user.id
    timers = user_timers.get(user_id, {})

    if not timers:
        return await interaction.response.send_message(
            "❌ No active timers."
        )

    msg = "⏰ **YOUR TIMERS**\n"

    for name, end in timers.items():
        msg += (
            f"• **{name}**: "
            f"Ready <t:{int(end.timestamp())}:R>\n"
        )

    await interaction.response.send_message(msg)

# --------------------------
# START BOT
# --------------------------
bot.run(os.getenv("BOT_TOKEN"))
