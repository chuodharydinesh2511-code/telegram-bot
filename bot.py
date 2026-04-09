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
        {"$set": {"chat_id": chat.id, "title": chat.title, "last_sent": None}},
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
        queue_count = messages_col.count_documents({"chat_id": g["chat_id"]})
        text += f"• {g.get('title','Unknown')} ({g['chat_id']}) | Queue: {queue_count} messages\n"
    await update.message.reply_text(text)

# ========= SAVE MESSAGE =========
async def save_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in authorized_users:
        return
    if update.message:
        messages_col.insert_one({
            "chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "time": datetime.utcnow(),
            "seq": datetime.utcnow().timestamp()
        })

# ========= START POSTING =========
async def start_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in authorized_users:
        return await update.message.reply_text("❌ Login first")
    settings_col.update_one({"_id": "status"}, {"$set": {"posting": True}}, upsert=True)
    await update.message.reply_text("🚀 Auto posting started")

# ========= STOP POSTING =========
async def stop_posting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings_col.update_one({"_id": "status"}, {"$set": {"posting": False}}, upsert=True)
    await update.message.reply_text("⛔ Posting stopped")

# ========= BROADCAST =========
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in authorized_users:
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

# ========= NEXT POST INFO =========
async def next_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    posts = []
    now = datetime.utcnow()
    for g in groups_col.find():
        last_sent = g.get("last_sent")
        interval = g.get("interval_sec", 3600)
        queue_count = messages_col.count_documents({"chat_id": g["chat_id"]})
        if last_sent:
            remaining = max(0, interval - (now - last_sent).total_seconds())
        else:
            remaining = 0
        posts.append(f"• {g['title']}: Next in {int(remaining//60)} min | Queue: {queue_count}")
    text = "⏱ Next posts:\n\n" + "\n".join(posts) if posts else "❌ No groups added"
    await update.message.reply_text(text)

# ========= WORKER =========
async def worker(app):
    global worker_running
    if worker_running:
        return
    worker_running = True
    await asyncio.sleep(5)
    while True:
        setting = settings_col.find_one({"_id": "status"})
        if setting and setting.get("posting"):
            groups = list(groups_col.find())
            for g in groups:
                msgs = list(messages_col.find({"chat_id": g["chat_id"]}).sort("seq", 1).limit(10))
                for msg in msgs:
                    try:
                        await app.bot.copy_message(
                            chat_id=g["chat_id"],
                            from_chat_id=msg["chat_id"],
                            message_id=msg["message_id"]
                        )
                        messages_col.delete_one({"_id": msg["_id"]})
                        groups_col.update_one({"chat_id": g["chat_id"]}, {"$set": {"last_sent": datetime.utcnow()}})
                    except:
                        pass
        await asyncio.sleep(3600)  # 1 hour interval

# ========= HELP =========
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Commands:*\n\n"
        "/login <password> — Login\n"
        "/addgroup — Add group (in group chat)\n"
        "/removegroup — Remove group (in group chat)\n"
        "/groups — List groups\n"
        "/start_posting — Start auto posting\n"
        "/stop_posting — Stop posting\n"
        "/broadcast — Reply to message to broadcast\n"
        "/next_post — Check next post timing & queue\n"
    )
    await update.message.reply_text(text)

# ========= MAIN =========
async def main():
    print("🔥 BOT STARTING 🔥")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("addgroup", addgroup))
    app.add_handler(CommandHandler("removegroup", removegroup))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("start_posting", start_posting))
    app.add_handler(CommandHandler("stop_posting", stop_posting))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("next_post", next_post))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.ALL, save_msg))

    await app.initialize()
    await app.start()
    asyncio.create_task(worker(app))
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
