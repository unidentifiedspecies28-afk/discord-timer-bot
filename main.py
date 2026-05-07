import discord
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import os
from flask import Flask
from threading import Thread

# Keep bot online
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

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

TIMER_OPTIONS = {
    "Bosses": 60 * 60,
    "Rift": 30 * 60,
    "Raids": 2 * 60 * 60
}

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

        await interaction.response.send_message(
            f"⏰ **{chosen} timer set!**\n"
            f"Duration: {hours}h {minutes}m\n"
            f"I'll notify you <t:{int(end_time.timestamp())}:R>.",
            ephemeral=False
        )

        await asyncio.sleep(total_seconds)

        await interaction.channel.send(
            f"{interaction.user.mention} ⏰ Your **{chosen}** cooldown is finished!\n"
            f"You can now do {chosen.lower()} again!"
        )

class TimerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(TimerSelect())

@tree.command(
    name="Reminder",
    description="Start a cooldown timer for Bosses, Rift or Raids"
)
async def timer(interaction: discord.Interaction):
    view = TimerView()
    await interaction.response.send_message(
        "Please select which cooldown timer you want to start:",
        view=view,
        ephemeral=False
    )

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

bot.run(os.getenv("BOT_TOKEN"))
