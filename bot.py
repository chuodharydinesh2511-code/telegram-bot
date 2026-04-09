import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

TOKEN = "8763905320:AAHlYidU6y51XPpoXuZoVdvm7Eh5VGSttw0"
PASSWORD = "dinesh123"
MONGO_URL = "mongodb+srv://ashishhacks4_db_user:e3zBzWLAJxOYjn9Z@cluster0.lk7mlh3.mongodb.net/?retryWrites=true&w=majority"

client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
messages_col = db["scheduled"]
groups_col = db["groups"]

authorized_users = set()

# LOGIN
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0] == PASSWORD:
        authorized_users.add(update.effective_user.id)
        await update.message.reply_text("Login success ✅")
    else:
        await update.message.reply_text("Wrong password ❌")

def is_auth(user_id):
    return user_id in authorized_users

# ADD GROUP
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id): return
    groups_col.update_one({"chat_id": update.effective_chat.id}, {"$set": {"chat_id": update.effective_chat.id}}, upsert=True)
    await update.message.reply_text("Group added ✅")

# REMOVE GROUP
async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id): return
    groups_col.delete_one({"chat_id": update.effective_chat.id})
    await update.message.reply_text("Group removed ❌")

# SCHEDULE MESSAGE
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id): return

    try:
        seconds = int(context.args[0])
        send_time = datetime.utcnow() + timedelta(seconds=seconds)

        messages_col.insert_one({
            "chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "send_time": send_time
        })

        await update.message.reply_text(f"Scheduled in {seconds} sec ⏳")

    except:
        await update.message.reply_text("Use: /schedule 3600")

# WORKER (10 messages batch + interval)
async def worker(app):
    while True:
        now = datetime.utcnow()

        msgs = list(messages_col.find({"send_time": {"$lte": now}}).limit(10))

        for msg in msgs:
            groups = groups_col.find()

            for g in groups:
                try:
                    await app.bot.copy_message(
                        chat_id=g["chat_id"],
                        from_chat_id=msg["chat_id"],
                        message_id=msg["message_id"]
                    )
                except:
                    pass

            messages_col.delete_one({"_id": msg["_id"]})

        await asyncio.sleep(30)  # interval (change kar sakta hai)

# START BACKGROUND TASK
async def on_start(app):
    app.create_task(worker(app))

app = ApplicationBuilder().token(TOKEN).post_init(on_start).build()

app.add_handler(CommandHandler("login", login))
app.add_handler(CommandHandler("addgroup", add_group))
app.add_handler(CommandHandler("removegroup", remove_group))
app.add_handler(CommandHandler("schedule", schedule))

print("ULTRA PRO BOT RUNNING 🔥")
app.run_polling()
