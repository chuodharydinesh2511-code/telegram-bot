import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# ========= CONFIG =========
TOKEN = "8763905320:AAEJMfgMW6C6PR1xj1bmMWHTqymOkMi7jVM"
PASSWORD = "1234"
MONGO_URL = "mongodb+srv://ashishhacks4_db_user:e3zBzWLAJxOYjn9Z@cluster0.lk7mlh3.mongodb.net/?retryWrites=true&w=majorityL"

# ========= DB =========
client = MongoClient(MONGO_URL)
db = client["ultra_bot"]

groups_col = db["groups"]
messages_col = db["messages"]
settings_col = db["settings"]

# ========= MEMORY =========
authorized_users = set()
worker_running = False

# ========= LOGIN =========
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0] == PASSWORD:
        authorized_users.add(update.effective_user.id)
        await update.message.reply_text("✅ Login successful")
    else:
        await update.message.reply_text("❌ Wrong password")

# ========= ADD GROUP =========
async def addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type not in ["group", "supergroup"]:
        return await update.message.reply_text("❌ Use in group")

    groups_col.update_one(
        {"chat_id": chat.id},
        {"$set": {"chat_id": chat.id, "title": chat.title}},
        upsert=True
    )

    await update.message.reply_text(f"✅ Group added: {chat.title}")

# ========= REMOVE GROUP =========
async def removegroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    groups_col.delete_one({"chat_id": chat.id})
    await update.message.reply_text("❌ Group removed")

# ========= SHOW GROUPS =========
async def groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = list(groups_col.find())

    if not data:
        return await update.message.reply_text("❌ No groups added")

    text = "📌 Groups List:\n\n"
    for g in data:
        text += f"• {g.get('title','Unknown')} ({g['chat_id']})\n"

    await update.message.reply_text(text)

# ========= SAVE MESSAGE (FIXED QUEUE) =========
async def save_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in authorized_users:
        return

    if update.message:
        messages_col.insert_one({
            "chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "time": datetime.utcnow(),
            "seq": datetime.utcnow().timestamp()  # 🔥 PERFECT ORDER FIX
        })

# ========= START POSTING =========
async def start_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in authorized_users:
        return await update.message.reply_text("❌ Login first")

    settings_col.update_one(
        {"_id": "status"},
        {"$set": {"posting": True}},
        upsert=True
    )

    await update.message.reply_text("🚀 Auto posting started")

# ========= STOP POSTING =========
async def stop_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings_col.update_one(
        {"_id": "status"},
        {"$set": {"posting": False}},
        upsert=True
    )

    await update.message.reply_text("⛔ Posting stopped")

# ========= BROADCAST =========
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in authorized_users:
        return await update.message.reply_text("❌ Login first")

    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to message")

    msg = update.message.reply_to_message
    groups = list(groups_col.find())

    for g in groups:
        try:
            await context.bot.copy_message(
                chat_id=g["chat_id"],
                from_chat_id=msg.chat_id,
                message_id=msg.message_id
            )
        except:
            pass

    await update.message.reply_text("✅ Broadcast sent")

# ========= WORKER (FINAL FIXED) =========
async def worker(app):
    global worker_running

    if worker_running:
        return  # prevent duplicate worker

    worker_running = True

    await asyncio.sleep(5)

    while True:
        setting = settings_col.find_one({"_id": "status"})

        if setting and setting.get("posting"):
            msgs = list(messages_col.find().sort("seq", 1).limit(10))  # 🔥 ORDER FIX
            groups = list(groups_col.find())

            for msg in msgs:
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

        await asyncio.sleep(120)  # ⏱ 1 hour

# ========= START =========
async def on_start(app):
    app.create_task(worker(app))

# ========= MAIN =========
import asyncio

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("addgroup", addgroup))
    app.add_handler(CommandHandler("removegroup", removegroup))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("start_posting", start_posting))
    app.add_handler(CommandHandler("stop_posting", stop_posting))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.ALL, save_msg))

    # start worker AFTER bot starts
    async def start_worker(app):
        await asyncio.sleep(5)
        asyncio.create_task(worker(app))

    app.post_init = start_worker

    print("🔥 BOT RUNNING 🔥")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
 from telegram.ext import ApplicationBuilder

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("login", login))
app.add_handler(CommandHandler("addgroup", addgroup))
app.add_handler(CommandHandler("removegroup", removegroup))
app.add_handler(CommandHandler("groups", groups))
app.add_handler(CommandHandler("start_posting", start_posting))
app.add_handler(CommandHandler("stop_posting", stop_posting))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(MessageHandler(filters.ALL, save_msg))

# ✅ Worker start after bot starts
async def start_worker(app):
    await asyncio.sleep(5)
    asyncio.create_task(worker(app))

app.post_init = start_worker

print("🔥 BOT RUNNING 🔥")

# ✅ FINAL RUN (NO asyncio.run)
app.run_polling(drop_pending_updates=True)
