import os
import asyncio
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from groq import Groq

# ===== ENV VARIABLES =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ===== SAFETY CHECK =====
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing in Railway Variables")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY missing in Railway Variables")

# ===== GROQ CLIENT =====
client = Groq(api_key=GROQ_API_KEY)

# ===== MESSAGE HANDLER =====
async def reply_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()

    # Group: reply only if bot is mentioned
    if msg.chat.type in ["group", "supergroup"]:
        if context.bot.username.lower() not in text.lower():
            return

    await asyncio.sleep(random.randint(1, 2))

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {
                "role": "system",
                "content": "You are a chill, friendly, human-like person. Keep replies short and natural."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        temperature=0.8,
        max_tokens=80
    )

    reply = response.choices[0].message.content.strip()
    await msg.reply_text(reply)

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_ai))
    print("✅ Groq AI bot running on Railway...")
    app.run_polling()

if __name__ == "__main__":
    main()
