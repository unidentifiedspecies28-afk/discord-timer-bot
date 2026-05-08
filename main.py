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
def home(): return "Bot is alive!"

def run_server():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    Thread(target=run_server).start()

keep_alive()

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Added "Super Boss" to the list
TIMER_OPTIONS = {
    "Bosses": 60 * 60,
    "Super Boss": 60 * 60,
    "Rift": 30 * 60,
    "Raids": 2 * 60 * 60
}

active_tasks = {}
end_times = {}

async def run_timer(user_id, name, duration, interaction):
    """The actual background countdown"""
    try:
        await asyncio.sleep(duration)
        
        # This line pings the user correctly
        await interaction.channel.send(
            f"🔔 <@{user_id}> Your **{name}** cooldown is finished!"
        )
        
        # Cleanup
        if user_id in active_tasks and name in active_tasks[user_id]:
            del active_tasks[user_id][name]
            del end_times[user_id][name]
            
    except asyncio.CancelledError:
        pass

# ---------------- TIMER SELECT MENU ----------------
class TimerSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, description=f"{duration//60}m cooldown")
            for name, duration in TIMER_OPTIONS.items()
        ]
        super().__init__(placeholder="Choose a timer...", options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen = self.values[0]
        duration = TIMER_OPTIONS[chosen]
        user_id = interaction.user.id
        
        # If timer exists, cancel the old one first
        if user_id in active_tasks and chosen in active_tasks[user_id]:
            active_tasks[user_id][chosen].cancel()
            status_msg = f"🔄 **{chosen} timer restarted!**"
        else:
            status_msg = f"⏰ **{chosen} timer set!**"

        finish_at = datetime.now() + timedelta(seconds=duration)
        
        if user_id not in active_tasks:
            active_tasks[user_id] = {}
            end_times[user_id] = {}
            
        end_times[user_id][chosen] = finish_at
        
        task = asyncio.create_task(run_timer(user_id, chosen, duration, interaction))
        active_tasks[user_id][chosen] = task

        await interaction.response.send_message(
            f"{status_msg}\nDuration: {duration//60}m\nEnds <t:{int(finish_at.timestamp())}:R>.",
            ephemeral=False
        )

class TimerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(TimerSelect())

# ---------------- COMMANDS ----------------
@tree.command(name="timer", description="Start a cooldown timer")
async def timer(interaction: discord.Interaction):
    await interaction.response.send_message("Select a cooldown:", view=TimerView())

@tree.command(name="timers", description="Show your active timers")
async def timers(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in end_times or not end_times[user_id]:
        await interaction.response.send_message("✅ No active timers.", ephemeral=True)
        return

    lines = []
    for name, finish in end_times[user_id].items():
        lines.append(f"• **{name}**: ends <t:{int(finish.timestamp())}:R>")

    await interaction.response.send_message("⏰ **Active Timers:**\n" + "\n".join(lines), ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online: {bot.user}")

bot.run(os.getenv("BOT_TOKEN"))
