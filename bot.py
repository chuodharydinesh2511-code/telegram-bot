import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pymongo import MongoClient

TOKEN = "8763905320:AAHlYidU6y51XPpoXuZoVdvm7Eh5VGSttw0"
PASSWORD = "dinesh123"
MONGO_URL = "mongodb+srv://ashishhacks4_db_user:e3zBzWLAJxOYjn9Z@cluster0.lk7mlh3.mongodb.net/?retryWrites=true&w=majority"

client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
messages_col = db["scheduled"]
groups_col = db["groups"]

authorized_users = set()
user_states = {}

# 🔐 START PANEL
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔐 Login", callback_data="login")],
        [InlineKeyboardButton("➕ Add Group", callback_data="addgroup")],
        [InlineKeyboardButton("➖ Remove Group", callback_data="removegroup")],
        [InlineKeyboardButton("📤 Schedule Message", callback_data="schedule")]
    ]
    await update.message.reply_text("Control Panel 👇", reply_markup=InlineKeyboardMarkup(keyboard))

# 🔘 BUTTON HANDLER
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "login":
        user_states[user_id] = "awaiting_password"
        await query.message.reply_text("Enter Password:")

    elif query.data == "addgroup":
        if user_id not in authorized_users:
            return await query.message.reply_text("Login first ❌")
        groups_col.update_one({"chat_id": query.message.chat.id}, {"$set": {"chat_id": query.message.chat.id}}, upsert=True)
        await query.message.reply_text("Group added ✅")

    elif query.data == "removegroup":
        if user_id not in authorized_users:
            return await query.message.reply_text("Login first ❌")
        groups_col.delete_one({"chat_id": query.message.chat.id})
        await query.message.reply_text("Group removed ❌")

    elif query.data == "schedule":
        if user_id not in authorized_users:
            return await query.message.reply_text("Login first ❌")
        user_states[user_id] = "awaiting_message"
        await query.message.reply_text("Send message to schedule")

# 🔑 HANDLE TEXT INPUT
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_states.get(user_id) == "awaiting_password":
        if update.message.text == PASSWORD:
            authorized_users.add(user_id)
            user_states[user_id] = None
            await update.message.reply_text("Login successful ✅")
        else:
            await update.message.reply_text("Wrong password ❌")

    elif user_states.get(user_id) == "awaiting_message":
        context.user_data["msg"] = update.message
        user_states[user_id] = "awaiting_time"
        await update.message.reply_text("Enter time in seconds (e.g. 60)")

    elif user_states.get(user_id) == "awaiting_time":
        try:
            seconds = int(update.message.text)
            send_time = datetime.now() + timedelta(seconds=seconds)

            msg = context.user_data["msg"]

            messages_col.insert_one({
                "chat_id": msg.chat_id,
                "message_id": msg.message_id,
                "send_time": send_time
            })

            user_states[user_id] = None
            await update.message.reply_text("Scheduled ✅")

        except:
            await update.message.reply_text("Enter valid number ❌")

# 🔁 WORKER (batch system)
async def worker(app):
    while True:
        now = datetime.now()
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

        await asyncio.sleep(30)

async def on_start(app):
    app.create_task(worker(app))

app = ApplicationBuilder().token(TOKEN).post_init(on_start).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.ALL, handle_message))

print("UI BOT RUNNING 🔥")
app.run_polling()
