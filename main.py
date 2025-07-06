from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os
import uvicorn
from pydantic import BaseModel
import discord
from discord.ext import commands
from telegram import Bot as TelegramBot
from telegram.error import TelegramError
import httpx
import asyncio

# Load environment variables
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

app = FastAPI()

# Telegram
telegram_bot = TelegramBot(token=TELEGRAM_BOT_TOKEN)

# Discord
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Subscription Tracker (in-memory for now)
active_users = {}

# Payment Webhook Model
class NowPaymentsWebhook(BaseModel):
    payment_status: str
    price_amount: float
    pay_address: str
    order_id: str
    payment_id: str
    ipn_type: str
    payment_amount: float
    payment_currency: str
    order_description: str


@app.get("/")
def root():
    return {"message": "ProfitPilotFX backend running ✅"}


@app.post("/payment-webhook")
async def handle_payment(request: Request):
    body = await request.json()
    data = NowPaymentsWebhook(**body)

    if data.payment_status != "confirmed":
        return JSONResponse(status_code=200, content={"status": "pending"})

    user_email = data.order_description
    print(f"✅ Payment confirmed for {user_email}")

    # Give user access in Discord and Telegram
    await give_discord_access(user_email)
    await give_telegram_access(user_email)

    # Track active user session
    active_users[user_email] = {
        "paid": True,
        "timestamp": asyncio.get_event_loop().time(),
    }
    return {"status": "success"}


async def give_telegram_access(user_email):
    try:
        telegram_user_id = get_telegram_user_id(user_email)  # You will implement this lookup
        await telegram_bot.unban_chat_member(chat_id=TELEGRAM_GROUP_ID, user_id=telegram_user_id)
    except TelegramError as e:
        print(f"⚠️ Telegram error: {e}")


async def give_discord_access(user_email):
    # Discord invite will be generated
    guild = discord.utils.get(bot.guilds, id=DISCORD_GUILD_ID)
    channel = guild.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        invite = await channel.create_invite(max_uses=1, unique=True)
        print(f"Discord invite for {user_email}: {invite.url}")
    else:
        print("⚠️ Discord channel not found")


# Add endpoint to manually deactivate user after expiration
@app.post("/deactivate-user/{email}")
async def deactivate_user(email: str):
    if email not in active_users:
        raise HTTPException(status_code=404, detail="User not found")

    # Remove from tracking
    del active_users[email]
    print(f"⛔ User {email} deactivated")
    return {"status": "removed"}


# Launch both bots when server runs
@bot.event
async def on_ready():
    print(f"🤖 Discord Bot ready: {bot.user}")


def run_discord():
    asyncio.run(bot.start(DISCORD_BOT_TOKEN))


# Entry point for Uvicorn
if __name__ == "__main__":
    import threading

    # Start Discord in a separate thread
    threading.Thread(target=run_discord).start()

    # Start FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)
# Main FastAPI backend
