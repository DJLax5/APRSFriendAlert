import config as cf
import telegram
import os
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, ForceReply
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
from typing import Dict
import asyncio

class TelegramChatManager:
    """This Class will be a telegram bot application and handle all the communication and setup with the telegram users. It will trigger the request to follow the owner via APRS and supply a function to send messages directly to users."""

    def __init__(self, newRouteCallback, geocodeCallback):
        self.bot = telegram.Bot(token=os.getenv('TELEGRAM_TOKEN')) #simple objcet to send single messages without conversation control

        # Create the Application and pass it your bot's token.
        self.app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

        # on different commands - answer in Telegram
        self.app.add_handler(CommandHandler("start", self.handleStart))
        self.app.add_handler(CommandHandler("help", self.handleHelp))

        # on non command i.e message - echo the message on Telegram
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handleMessage))

        self.newRoute = newRouteCallback
        self.geocode = geocodeCallback

    def execTCM(self):
        """This function will start the polling process of the Telegram bot. This function will not return."""
        self.app.run_polling()

    def sendMessage(self, chatID, message):
        """Basic function to send a message to a specific chat
        """
        if chatID == None or chatID == '':
            return
        async def send_message(self, chatID, message):
            await self.bot.send_message(chat_id=chatID, text=message, parse_mode='MarkdownV2')

        # call the asynchronous function using asyncio.run()
        asyncio.run(send_message(self, chatID, message))

    # Define a few command handlers. These usually take the two arguments update and
    # context.
    async def handleStart(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        user = update.effective_user
        await update.message.reply_html(
            rf"Hi {user.mention_html()}!",
            reply_markup=ForceReply(selective=True),
        )


    async def handleHelp(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        print(update.message.chat_id)
        await update.message.reply_text("Help!")


    async def handleMessage(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Echo the user message."""
        await update.message.reply_text(update.message.text)


       



