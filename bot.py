import discord
import requests
import asyncio
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
TIMEOUT = 12 * 60 * 60  # 12 hours

FLASK_SERVER_URL = "http://localhost:5000"

intents = discord.Intents.default()
intents.reactions = True
intents.messages = True
client = discord.Client(intents=intents)

data = {}

async def poll_previews():
    """Constantly check Flask server for new previews and send them to Discord."""
    global data
    while True:
        response = requests.get(f"{FLASK_SERVER_URL}/get_previews")
        print("Waiting for receiving snapshot")
        if response.status_code == 200:
            data = response.json()
            print("Polling", data)
            if data != {}:
                print("✅ Previews found! Sending to Discord...")
                await send_previews_to_discord(data)
        await asyncio.sleep(5)  # Poll every 5 seconds


async def send_previews_to_discord(previews):
    """Send preview images to Discord and wait for approval."""
    global data
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Failed to get Discord channel.")
        return

    messages = []
    for key, preview in previews.items():
        msg = await channel.send(f"📸 Preview for **{str(preview)}**", file=discord.File(preview))
        await msg.add_reaction("✅")
        messages.append((msg, key))

    # Wait for reaction
    def check(reaction, user):
        return str(reaction.emoji) == "✅" and reaction.message in [m[0] for m in messages]

    try:
        reaction, user = await client.wait_for("reaction_add", check=check, timeout=43200)  # 12 hours timeout
        approved_crop = [key for msg, key in messages if msg == reaction.message][0]
        print(f"✅ Approved crop: {approved_crop}")

        # Send approval back to Flask server
        requests.post(f"{FLASK_SERVER_URL}/approve", json={"crop": approved_crop})
        await channel.send(f"✅ **{approved_crop}** approved! Continuing encoding...")

        data = {}
    except asyncio.TimeoutError:
        await channel.send("❌ Approval timed out.")
        requests.post(f"{FLASK_SERVER_URL}/approve", json={"crop": "auto"})


async def wait_for_reaction(messages):
    """Wait for a reaction and approve the selected crop."""

    def check(reaction, user):
        return reaction.message.id in messages and str(reaction.emoji) == "✅"

    try:
        reaction, user = await client.wait_for("reaction_add", timeout=43200, check=check)  # 12-hour timeout
        approved_crop = messages[reaction.message.id]

        # Send approval to Flask
        requests.post(f"{FLASK_SERVER_URL}/approve", json={"crop": approved_crop})
        print(f"✅ Crop approved: {approved_crop}")
    except asyncio.TimeoutError:
        print("⏳ Approval timeout.")


@client.event
async def on_ready():
    print(f"✅ Bot connected as {client.user}")
    await client.loop.create_task(poll_previews())  # Start polling for previews

client.run(TOKEN)