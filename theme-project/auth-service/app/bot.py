import hmac
import hashlib
import httpx
import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN")
AUTH_SERVICE = "http://136.234.124.48:8000/api"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args  # текст после /start
    
    if not args:
        await update.message.reply_text("Привет! Используй приложение ОмГТУ для авторизации.")
        return

    state     = args[0]
    tg_id     = str(update.effective_user.id)
    username  = update.effective_user.username or ""
    full_name = update.effective_user.full_name or ""

    # Генерируем подпись
    secret = hmac.new(
        BOT_TOKEN.encode(),
        f"{tg_id}:{state}".encode(),
        hashlib.sha256
    ).hexdigest()

    # Отправляем данные в auth-service
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{AUTH_SERVICE}/auth/telegram/webhook",
            
            json={
                "state":     state,
                "tg_id":     tg_id,
                "username":  username,
                "full_name": full_name,
                "secret":    secret,
            }
        )

    await update.message.reply_text(
        "✅ Авторизация успешна! Вернись в приложение ОмГТУ."
    )


def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def _run():
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        while True:
            await asyncio.sleep(1)
    
    loop.run_until_complete(_run())