import discord
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import os
from flask import Flask
from threading import Thread

# ---------------- KEEP BOT ONLINE ----------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_server():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_server)
    t.start()

keep_alive()

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Timer durations
TIMER_OPTIONS = {
    "Bosses": 60 * 60,    # 60 minutes
    "Rift": 30 * 60,      # 30 minutes
    "Raids": 2 * 60 * 60  # 2 hours
}

# Store active timers: {user_id: [ {name, end_time}, ... ]}
active_timers = {}

# ---------------- TIMER SELECT MENU ----------------
class TimerSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=name,
                description=f"Cooldown: {duration//3600}h {(duration%3600)//60}m"
            )
            for name, duration in TIMER_OPTIONS.items()
        ]
        super().__init__(placeholder="Choose a timer type...", options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen = self.values[0]
        total_seconds = TIMER_OPTIONS[chosen]
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        end_time = datetime.now() + timedelta(seconds=total_seconds)

        # Save this timer to the user's list
        user_id = interaction.user.id
        if user_id not in active_timers:
            active_timers[user_id] = []
        active_timers[user_id].append({
            "name": chosen,
            "end_time": end_time
        })

        await interaction.response.send_message(
            f"⏰ **{chosen} timer set!**\n"
            f"Duration: {hours}h {minutes}m\n"
            f"I'll notify you <t:{int(end_time.timestamp())}:R>.",
            ephemeral=False
        )

        # Wait until finished
        await asyncio.sleep(total_seconds)

        # Remove from list when done
        if user_id in active_timers:
            active_timers[user_id] = [t for t in active_timers[user_id] if t["name"] != chosen]
            # Clean up empty user entries
            if not active_timers[user_id]:
                del active_timers[user_id]

        # Send notification
        await interaction.channel.send(
            f"{interaction.user.mention} ⏰ Your **{chosen}** cooldown is finished!\n"
            f"You can now do {chosen.lower()} again!"
        )

class TimerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(TimerSelect())

# ---------------- COMMANDS ----------------
@tree.command(
    name="timer",
    description="Start a cooldown timer for Bosses, Rift or Raids"
)
async def timer(interaction: discord.Interaction):
    view = TimerView()
    await interaction.response.send_message(
        "Please select which cooldown timer you want to start:",
        view=view,
        ephemeral=False
    )

@tree.command(
    name="timers",
    description="Show all your currently active cooldown timers"
)
async def timers(interaction: discord.Interaction):
    user_id = interaction.user.id

    # If user has no timers
    if user_id not in active_timers or len(active_timers[user_id]) == 0:
        await interaction.response.send_message(
            "✅ You have no active timers running right now.",
            ephemeral=True
        )
        return

    # Build list of timers with remaining time
    lines = []
    now = datetime.now()
    for timer in active_timers[user_id]:
        remaining = timer["end_time"] - now
        # Format remaining time nicely
        h = remaining.seconds // 3600
        m = (remaining.seconds % 3600) // 60
        s = remaining.seconds % 60
        lines.append(
            f"• **{timer['name']}** — ends <t:{int(timer['end_time'].timestamp())}:R> "
            f"({h}h {m}m {s}s remaining)"
        )

    message = "⏰ **Your Active Timers:**\n" + "\n".join(lines)

    await interaction.response.send_message(message, ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

# Run bot
bot.run(os.getenv("BOT_TOKEN"))
