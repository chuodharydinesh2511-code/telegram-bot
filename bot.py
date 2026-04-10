import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# ========= CONFIG =========
TOKEN = "8763905320:AAGSCeneXt4X5VGTqcReeuq1VP9ktgLRrPs"
PASSWORD = "1234"
MONGO_URL = "mongodb+srv://ashishhacks4_db_user:e3zBzWLAJxOYjn9Z@cluster0.lk7mlh3.mongodb.net/?retryWrites=true&w=majority"

# ========= DB =========
client = MongoClient(MONGO_URL)
db = client["ultra_bot"]

groups_col = db["groups"]
messages_col = db["messages"]
settings_col = db["settings"]

# prevent duplicate save
messages_col.create_index(
    [("chat_id", 1), ("message_id", 1)],
    unique=True
)

# ========= MEMORY =========
authorized_users = set()
processing_lock = asyncio.Lock()

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
    groups_col.delete_one({"chat_id": update.effective_chat.id})
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

# ========= SAVE MESSAGE =========
async def save_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in authorized_users:
        return

    msg = update.message
    if not msg:
        return

    if msg.edit_date:
        return

    exists = messages_col.find_one({
        "chat_id": msg.chat_id,
        "message_id": msg.message_id
    })
    if exists:
        return

    try:
        messages_col.insert_one({
            "chat_id": msg.chat_id,
            "message_id": msg.message_id,
            "seq": datetime.utcnow().timestamp()
        })
    except:
        pass

# ========= START =========
async def start_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in authorized_users:
        return await update.message.reply_text("❌ Login first")
    settings_col.update_one(
        {"_id": "status"},
        {"$set": {"posting": True, "last_sent": None}},
        upsert=True
    )
    await update.message.reply_text("🚀 Auto posting started")

# ========= STOP =========
async def stop_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings_col.update_one(
        {"_id": "status"},
        {"$set": {"posting": False}},
        upsert=True
    )
    await update.message.reply_text("⛔ Posting stopped")

# ========= SEND NOW =========
async def send_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with processing_lock:
        msgs = list(messages_col.find().sort("seq", 1).limit(10))
        if not msgs:
            return await update.message.reply_text("❌ Queue empty")
        groups = list(groups_col.find())
        sent = 0
        for msg in msgs:
            for g in groups:
                try:
                    await context.bot.copy_message(
                        chat_id=g["chat_id"],
                        from_chat_id=msg["chat_id"],
                        message_id=msg["message_id"]
                    )
                except:
                    pass
            messages_col.delete_one({"_id": msg["_id"]})
            sent += 1
        await update.message.reply_text(f"✅ Sent {sent} messages")

# ========= CLEAR =========
async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages_col.delete_many({})
    await update.message.reply_text("🗑️ Queue cleared")

# ========= STATUS =========
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    setting = settings_col.find_one({"_id": "status"})
    queue = messages_col.count_documents({})
    posting = setting.get("posting", False) if setting else False
    last_sent = setting.get("last_sent") if setting else None
    interval = setting.get("interval_sec", 3600) if setting else 3600

    if queue == 0:
        next_time = "No content in queue"
    elif not last_sent:
        next_time = "Ready soon"
    else:
        elapsed = (datetime.utcnow() - last_sent).total_seconds()
        remaining = max(interval - elapsed, 0)
        next_time = str(timedelta(seconds=int(remaining)))

    await update.message.reply_text(
        f"📊 Status\nPosting: {'🟢 ON' if posting else '🔴 OFF'}\nQueue: {queue}\nNext: {next_time}"
    )

# ========= SET INTERVAL =========
async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    minutes = int(context.args[0])
    settings_col.update_one(
        {"_id": "status"},
        {"$set": {"interval_sec": minutes * 60}},
        upsert=True
    )
    await update.message.reply_text(f"⏱ Interval set to {minutes} min")

# ========= BROADCAST =========
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply required")
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

# ========= HELP =========
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📌 *Available Commands:*\n\n"
        "/login <password>\n"
        "/addgroup\n"
        "/removegroup\n"
        "/groups\n"
        "/start_posting\n"
        "/stop_posting\n"
        "/broadcast\n"
        "/sendnow\n"
        "/clear\n"
        "/status\n"
        "/setinterval <minutes>\n"
        "/help"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ========= WORKER (FIXED) =========
async def worker(app):
    while True:
        setting = settings_col.find_one({"_id": "status"})
        if setting and setting.get("posting"):
            async with processing_lock:
                msgs = list(messages_col.find().sort("seq", 1).limit(10))
                groups = list(groups_col.find())

                if not msgs:
                    await asyncio.sleep(10)
                    continue

                interval = setting.get("interval_sec", 3600)
                last_sent = setting.get("last_sent")

                if not last_sent:
                    last_sent = datetime.utcnow() - timedelta(seconds=interval)

                elapsed = (datetime.utcnow() - last_sent).total_seconds()

                if elapsed >= interval:
                    for msg in msgs:
                        deleted = messages_col.find_one_and_delete({"_id": msg["_id"]})
                        if not deleted:
                            continue

                        for g in groups:
                            try:
                                await app.bot.copy_message(
                                    chat_id=g["chat_id"],
                                    from_chat_id=msg["chat_id"],
                                    message_id=msg["message_id"]
                                )
                            except:
                                pass

                    settings_col.update_one(
                        {"_id": "status"},
                        {"$set": {"last_sent": datetime.utcnow()}}
                    )

        await asyncio.sleep(10)

# ========= MAIN =========
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("addgroup", addgroup))
    app.add_handler(CommandHandler("removegroup", removegroup))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("start_posting", start_posting))
    app.add_handler(CommandHandler("stop_posting", stop_posting))
    app.add_handler(CommandHandler("sendnow", send_now))
    app.add_handler(CommandHandler("clear", clear_queue))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("setinterval", set_interval))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(MessageHandler(filters.ALL, save_msg))

    await app.initialize()
    await app.start()

    asyncio.create_task(worker(app))

    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
