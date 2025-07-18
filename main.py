import os
import httpx
import asyncio
import functools
import concurrent.futures
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Telegram & Discord
from telegram import Bot as TelegramBot
from telegram.error import TelegramError

import discord
from discord.ext import commands

# ==== LOAD ENV ====
load_dotenv()

# Environment Variables
PORT = int(os.environ.get("PORT", 8000))  # Default to 8000 if PORT is not set
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
NOWPAYMENTS_API_KEY = os.environ.get("NOWPAYMENTS_API_KEY")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # Group or User ID
TELEGRAM_GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ==== MODELS ====
class NowPaymentsWebhook(BaseModel):
    payment_status: str
    price_amount: float
    pay_address: str
    order_id: str
    payment_id: str
    ipn_type: str
    payment_amount: float
    payment_currency: str
    order_description: str  # e.g., user email

# ==== STATE ====
active_users = {}  # In-memory session tracker (replace with DB for persistence)

# ==== TELEGRAM BOT ====
telegram_bot = TelegramBot(token=TELEGRAM_TOKEN)
executor = concurrent.futures.ThreadPoolExecutor()

async def send_telegram_message(message: str):
    try:
        await asyncio.get_event_loop().run_in_executor(
            executor,
            functools.partial(telegram_bot.send_message, chat_id=TELEGRAM_CHAT_ID, text=message)
        )
        logger.info(f"Telegram message sent: {message}")
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")

def get_telegram_user_id(email: str):
    # Placeholder for real user ID lookup (e.g., database query)
    return 123456789  # Replace with actual logic to map emails to Telegram user IDs

async def give_telegram_access(user_email):
    try:
        telegram_user_id = get_telegram_user_id(user_email)
        await asyncio.get_event_loop().run_in_executor(
            executor,
            functools.partial(telegram_bot.unban_chat_member, chat_id=TELEGRAM_GROUP_ID, user_id=telegram_user_id)
        )
        logger.info(f"✅ Telegram access granted to {user_email}")
    except TelegramError as e:
        logger.error(f"⚠️ Telegram error: {e}")

# ==== DISCORD BOT ====
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

discord_bot = commands.Bot(command_prefix="!", intents=intents)

@discord_bot.event
async def on_ready():
    logger.info(f"✅ Discord bot connected as {discord_bot.user}")

async def send_discord_message(message: str):
    await discord_bot.wait_until_ready()
    channel = discord_bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(message)
        logger.info(f"Discord message sent: {message}")
    else:
        logger.error("❌ Discord channel not found!")

async def give_discord_access(user_email):
    guild = discord.utils.get(discord_bot.guilds, id=DISCORD_GUILD_ID)
    channel = guild.get_channel(DISCORD_CHANNEL_ID) if guild else None
    if channel:
        invite = await channel.create_invite(max_uses=1, unique=True)
        logger.info(f"Discord invite for {user_email}: {invite.url}")
    else:
        logger.error("⚠️ Discord channel not found")

# ==== FASTAPI ROUTES ====
@app.get("/")
async def root():
    return {"message": "ProfitPilot backend running ✅"}

@app.head("/")
async def root_head():
    """
    Responds to HEAD requests for the root endpoint.
    """
    return JSONResponse(status_code=200)

@app.get("/health")
async def health_check():
    """
    Health check endpoint for Render.
    Returns a JSON response indicating the service is healthy.
    """
    return {"status": "healthy"}

@app.head("/health")
async def health_check_head():
    """
    Responds to HEAD requests for the health check endpoint.
    """
    return JSONResponse(status_code=200)

@app.post("/nowpayments-webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        webhook_data = NowPaymentsWebhook(**data)

        status = webhook_data.payment_status
        amount = webhook_data.price_amount
        currency = webhook_data.payment_currency
        user_email = webhook_data.order_description

        message = f"💰 Payment Received:\nStatus: {status}\nAmount: {amount} {currency}"

        await send_telegram_message(message)
        await send_discord_message(message)

        # Grant access if confirmed
        if status == "confirmed":
            await give_telegram_access(user_email)
            await give_discord_access(user_email)

            active_users[user_email] = {
                "paid": True,
                "timestamp": asyncio.get_event_loop().time(),
            }

        return JSONResponse(content={"status": "received"}, status_code=200)
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/deactivate-user/{email}")
async def deactivate_user(email: str):
    if email not in active_users:
        raise HTTPException(status_code=404, detail="User not found")

    del active_users[email]
    logger.info(f"⛔ User {email} deactivated")
    return {"status": "removed"}

# ==== BOT STARTUP ====
def start_discord_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(discord_bot.start(DISCORD_TOKEN))
    except Exception as e:
        logger.error(f"Discord bot failed to start: {e}")
    finally:
        loop.close()

def start_telegram_bot():
    logger.info("✅ Telegram bot initialized.")

# ==== MAIN RUN ====
if __name__ == "__main__":
    import uvicorn
    import threading

    # Start Discord bot in a separate thread
    threading.Thread(target=start_discord_bot, daemon=True).start()

    # Initialize Telegram bot
    start_telegram_bot()

    # Run FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=PORT)
