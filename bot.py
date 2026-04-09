import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

TOKEN = "8763905320:AAHlYidU6y51XPpoXuZoVdvm7Eh5VGSttw0"
PASSWORD = "1234"
MONGO_URL = "mongodb+srv://ashishhacks4_db_user:e3zBzWLAJxOYjn9Z@cluster0.lk7mlh3.mongodb.net/?retryWrites=true&w=majority"

client = MongoClient(MONGO_URL)
db = client["bot"]

groups_col = db["groups"]
messages_col = db["messages"]

authorized_users = set()

# LOGIN
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0] == PASSWORD:
        authorized_users.add(update.effective_user.id)
        await update.message.reply_text("Login Done ✅")
    else:
        await update.message.reply_text("Wrong Password ❌")

# ADD GROUP
async def addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        return await update.message.reply_text("Use in group ❌")

    groups_col.update_one({"chat_id": chat.id}, {"$set": {"chat_id": chat.id, "title": chat.title}}, upsert=True)
    await update.message.reply_text(f"Group Added ✅\n{chat.title}")

# REMOVE GROUP
async def removegroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    groups_col.delete_one({"chat_id": chat.id})
    await update.message.reply_text("Group Removed ❌")

# SHOW GROUPS
async def showgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    groups = list(groups_col.find())
    if not groups:
        return await update.message.reply_text("No groups added ❌")

    text = "📌 Groups:\n"
    for g in groups:
        text += f"- {g.get('title', 'Unknown')} ({g['chat_id']})\n"

    await update.message.reply_text(text)

# SAVE MESSAGE (QUEUE)
async def save_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authorized_users:
        return

    messages_col.insert_one({
        "chat_id": update.message.chat_id,
        "message_id": update.message.message_id,
        "time": datetime.utcnow()
    })

# BROADCAST (instant)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authorized_users:
        return await update.message.reply_text("Login first ❌")

    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to message ❌")

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

    await update.message.reply_text("Broadcast Done ✅")

# WORKER (AUTO 10 MSG / HOUR)
async def worker(app):
    while True:
        msgs = list(messages_col.find().sort("time", 1).limit(10))
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

        await asyncio.sleep(3600)

async def start_worker(app):
    app.create_task(worker(app))

app = ApplicationBuilder().token(TOKEN).post_init(start_worker).build()

app.add_handler(CommandHandler("login", login))
app.add_handler(CommandHandler("addgroup", addgroup))
app.add_handler(CommandHandler("removegroup", removegroup))
app.add_handler(CommandHandler("groups", showgroups))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(MessageHandler(filters.ALL, save_msg))

app.run_polling()
