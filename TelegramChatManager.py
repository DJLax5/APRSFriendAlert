import config as cf
import telegram
import warnings
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from typing import Dict
import asyncio

CONFIG_BOT, GET_NAME = range(2)
GET_ADDR_NAME, GET_ADDR, CHECK_ADDR = range(3)
SEL_RM_ADDR = range(1)

class TelegramChatManager:
    """This Class will be a telegram bot application and handle all the communication and setup with the telegram users. It will trigger the request to follow the owner via APRS and supply a function to send messages directly to users."""
    

    def __init__(self, newRouteCallback, geocodeCallback):
        self.bot = telegram.Bot(token=os.getenv('TELEGRAM_TOKEN')) #simple object to send single messages without conversation control

        # Create the Application and pass it your bot's token.
        self.app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

        # on different commands start different conversaions
        convStartHandler = ConversationHandler(
            entry_points=[CommandHandler("start", self.handleStart)],
            states={
            CONFIG_BOT:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerCheckMasterKey), CommandHandler("start", self.handleStart)],
            GET_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerGetName)]
            },
            fallbacks=[CommandHandler("quit", self.handleQuit)]
        )
        convAddAddrHandler = ConversationHandler(
            entry_points=[CommandHandler("addaddress", self.handleAddAddress)],
            states={
            GET_ADDR_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerGetAddrName)],
            GET_ADDR:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerGetAddr)],
            CHECK_ADDR:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerCheckAddr)],
            },
            fallbacks=[CommandHandler("quit", self.handleQuit)]
        )
        convRmAddrHandler = ConversationHandler(
            entry_points=[CommandHandler("rmaddress", self.handleRmAddress)],
            states={
            SEL_RM_ADDR:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerSelRmAddr)],
            },
            fallbacks=[CommandHandler("quit", self.handleQuit)]
        )

        self.app.add_handler(convStartHandler)
        self.app.add_handler(convAddAddrHandler)
        self.app.add_handler(convRmAddrHandler)
        
        self.app.add_handler(CommandHandler("help", self.handleHelp))
        self.app.add_handler(CommandHandler("takeover", self.handleTakeover))
        self.app.add_handler(CommandHandler("show", self.handleShAddress))
        self.app.add_handler(CommandHandler("quit", self.handleQuit))
        self.app.add_handler(CommandHandler("chname", self.handleChName))
        self.app.add_handler(CommandHandler("verify", self.handleVerify))
        self.app.add_handler(CommandHandler("rmuser", self.handleRMuser))
        
        # on non command i.e message
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
        message = telegram.helpers.escape_markdown(message, version=2)
        async def send_message(self, chatID, message):
            try:
                await self.bot.send_message(chat_id=chatID, text=message, parse_mode='MarkdownV2')
            except telegram.error.BadRequest as e:
                cf.log.warn('[TCM] The message could not be sent. ChatID is wrong.')

        # call the asynchronous function using asyncio.run().
        # It will fail, if we are already within a subroutine. then use ensure_future.
        with warnings.catch_warnings(): # disable the warning, we want to catch
            warnings.filterwarnings("ignore", message="coroutine 'TelegramChatManager.sendMessage.<locals>.send_message' was never awaited")
            try:
                asyncio.run(send_message(self, chatID, message))
            except:
                asyncio.ensure_future(send_message(self, chatID, message))

    # Define a few command/conversation handlers. These usually take the two arguments update and
    # context.
    async def handleStart(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start the setup conversation after the /start command"""
        # check weather this bot has been setup:
        if cf.MASTER_CHATID != None and cf.MASTER_CHATID != '': # yes, has been setup.
            # check weather we know the user
            chatid = str(update.message.chat_id)

            if cf.USER_DATA.get(chatid):
                message = telegram.helpers.escape_markdown("Welcome back " + cf.USER_DATA[chatid]['NAME'] +"!\nYou can use /help to show the available commands.", version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return ConversationHandler.END
            else:
                name = update.effective_user.first_name
                message = telegram.helpers.escape_markdown("Hello!\nI am "+ os.getenv('APRS_FOLLOW_CALL') + '\'s APRS Alert bot. Your name in Telegram is ' + name + '. Should I call you by this name? \nIf yes, respond with \'yes\', or respond with your name, if you want to be called by another name.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return GET_NAME
        else: # nope has not been setup
            name = update.effective_user.first_name
            message = telegram.helpers.escape_markdown("Hello!\nI am "+ os.getenv('APRS_FOLLOW_CALL') + '\'s APRS Alert bot. This bot has not been configured by it\'s owner. If you are the owner please respond with the magic key, you set up in the .env file. If you are not the owner, please try again with /start once this bot has been configured.', version =2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return CONFIG_BOT
         


    async def handlerCheckMasterKey(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """This is to be called, if the bot has not been configured yet """
        if update.message.text == os.getenv('MAGIC_KEY'):
            cf.MASTER_CHATID = str(update.message.chat_id)
            name = update.effective_user.first_name
            message = telegram.helpers.escape_markdown('You have succesfully identified yourself. This is now the chat to control everything.\nYour name in Telegram is ' + name + '. Should I call you by this name? \nIf yes, respond with \'yes\', or respond with your name, if you want to be called by another name.', version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return GET_NAME
        else:
            message = telegram.helpers.escape_markdown('This is not correct. Please try again.',version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return CONFIG_BOT



    async def handlerGetName(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """This is to be called, when the username is set """
        chatid = str(update.message.chat_id)
        if update.message.text.strip().lower() == 'yes':
            name = update.effective_user.first_name
        else:
            name = update.message.text
        cf.USER_DATA[chatid] = {}
        cf.USER_DATA[chatid]['NAME'] = name
        cf.USER_DATA[chatid]['ADDRESSES'] = []
        cf.USER_DATA[chatid]['VALID'] = False if chatid != cf.MASTER_CHATID else True
        cf.saveConfiguration()
        if chatid != cf.MASTER_CHATID:
            self.sendMessage(cf.MASTER_CHATID, 'A new user just joined this service. If you want to unlock ' + name +' type: \n/verify ' + name)
            message = telegram.helpers.escape_markdown('Hi ' + name + '! Nice to meet you!\nYou\'re now registed. Use the /help command to see what can be done by me. \n\nHowever bevor you can do anything, you\'ll need to verified by the owner. He/She just received a notification to unlock your account.', version= 2)
        else:
            message = telegram.helpers.escape_markdown('Hi ' + name + '! Nice to meet you!\nYou\'re now registed and verified. Use the /help command to see what can be done by me.', version= 2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        return ConversationHandler.END


    async def handleAddAddress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start the add address conversation after the /addaddress command"""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if self.geocode == None:
                message = telegram.helpers.escape_markdown('Sorry, the backend for the address configuration is not available.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.critical('[TCM] Geocoding handler is not defined!')
                return ConversationHandler.END
            cf.log.debug(context.args)
            if context.args != []:
                addrName = " ".join(context.args)
                message = telegram.helpers.escape_markdown('Great that you want to add a address named ' + addrName  + '\nNow please give me the address.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                context.user_data['ADDR_NAME'] = addrName
                return GET_ADDR
            else:
                message = telegram.helpers.escape_markdown('Great that you want to add a address. \nNow please give me the name under which you want to store address (e.g. \'Home\').', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return GET_ADDR_NAME

    async def handlerGetAddrName(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ In this we get the name of the address and geocode/check it """
        chatid = str(update.message.chat_id)
        addrName = update.message.text
        context.user_data['ADDR_NAME'] = addrName
        message = telegram.helpers.escape_markdown('Great that you want to add a address named ' + addrName  + '\nNow please give me the address.', version= 2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        return GET_ADDR
    
    async def handlerGetAddr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ In this we check weather the user is happy with this address """
        chatid = str(update.message.chat_id) 
        addr = update.message.text
        coords = self.geocode(addr)
        context.user_data['ADDR'] = addr
        context.user_data['COORDS'] = coords
        url = "https://www.google.com/maps/search/?api=1&query={},{}".format(coords[1], coords[0])
        message = telegram.helpers.escape_markdown('Ok thank you. May I strore this address?\n\n' + context.user_data['ADDR_NAME']  + '\n' + context.user_data['ADDR'] + '\n' + str(coords[1]) + ', ' + str(coords[0]) + '\n\n' + url + '\n\nPlease respond with yes or no.', version= 2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        return CHECK_ADDR

    async def handlerCheckAddr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ In this we check weather the user is happy with this address """
        chatid = str(update.message.chat_id) 
        if update.message.text.strip().lower() == 'yes':
            temp = {'ADDR_NAME' : context.user_data['ADDR_NAME'],
                    'ADDR' :  context.user_data['ADDR'],
                    'COORDS' : context.user_data['COORDS']}
            cf.USER_DATA[chatid]['ADDRESSES'].append(temp)
            cf.saveConfiguration()
            message = telegram.helpers.escape_markdown('Data stored. Thank you.', version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return ConversationHandler.END
        elif update.message.text.strip().lower() == 'no':
            message = telegram.helpers.escape_markdown('Ok, please give me the correct address.', version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return GET_ADDR
        else:
            message = telegram.helpers.escape_markdown('Please only respond with yes or no.', version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return CHECK_ADDR
        
    async def handleRmAddress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start the remove address conversation after the /rmaddress command"""
        cf.log.error('[TCM] Sorry this command is not implemented yet. (handleRmAddress)')
    async def handlerSelRmAddr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ Here we check which address to remove """
        cf.log.error('[TCM] Sorry this command is not implemented yet. (handlerSelRmAddr)')

    async def handleShAddress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /show is issued."""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            msg = ''
            if chatid == cf.MASTER_CHATID:
                msg = 'As you are the owner of this bot, you will see all stored data. \nUsers will only see the addresses they have added.\n\n'
                j = 1
                for userid in cf.USER_DATA.keys():
                    msg = msg + str(j) + '.\n'
                    msg = msg + 'USER: ' + cf.USER_DATA[userid]['NAME'] + '\n'
                    if not cf.USER_DATA[userid]['VALID']:
                        msg = msg + 'Not verified.\n\n'
                    elif cf.USER_DATA[chatid]['ADDRESSES'] == []:
                        msg = msg + 'No addresses defined!\n\n'
                    else:
                        msg = msg + self.getAddressesStr(userid)
                    j = j + 1
            else:
                if cf.USER_DATA[chatid]['ADDRESSES'] == []:
                    msg = 'Here are your stored addresses: \n\n'
                    msg = msg + self.getAddressesStr(chatid)
                else:
                    msg = 'You have no addresses defined. Please do so by using /addaddress' 

            message = telegram.helpers.escape_markdown(msg, version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')

    async def handleHelp(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        cf.log.error('[TCM] Sorry this command is not implemented yet. (handleHelp)')


    async def handleMessage(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ The default message handler. Whenever a simple message is sent outside of a conversation."""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):

            if chatid == cf.MASTER_CHATID:
                if update.message.text.strip().lower().startswith("en-route to") or update.message.text.strip().lower().startswith("en route to") or update.message.text.strip().lower().startswith("enroute to"):
                    message = telegram.helpers.escape_markdown('The string syntax is not yet implemented.',version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
                else:
                    message = telegram.helpers.escape_markdown('To activate the following process, pleas start your command with \'en route to\' \nSee /help to see all possible commands.',version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
            else:
                message = telegram.helpers.escape_markdown('Please see /help to see all possible commands.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')

    async def handleTakeover(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ Use the takeover command to change the master chat id"""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):

            if chatid == cf.MASTER_CHATID:
                message = telegram.helpers.escape_markdown('This is already the control chat. There is nothing to takeover.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
            else:
                try:
                    if context.args[0] == os.getenv('MAGIC_KEY'): # successfull
                        self.sendMessage(cf.MASTER_CHATID, 'There was a successfull takeover. This chat is no longer the control chat. \nTakeover by: ' + cf.USER_DATA[chatid]['NAME'] + ' / ' + str(update.effective_user.full_name))
                        cf.MASTER_CHATID = chatid
                        cf.saveConfiguration()
                        message = telegram.helpers.escape_markdown('Ok, takeover complete. This is now the control chat.', version= 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.info('[TCM] Successful takeover to ' + cf.USER_DATA[chatid]['NAME'])
                    else:
                        self.sendMessage(cf.MASTER_CHATID, 'There was a failed takeover attempt. \nAttempt by: ' + cf.USER_DATA[chatid]['NAME'] + ' / ' + str(update.effective_user.full_name))
                        message = telegram.helpers.escape_markdown('Wrong key. This attempt will be reported!', version= 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.warn('[TCM] Failed takeover attempt by ' + cf.USER_DATA[chatid]['NAME'])
                except:
                        message = telegram.helpers.escape_markdown('The syntax for this command is /takeover [KEY]. Please try again.', version= 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')




 

    async def handleQuit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ Handle to Quit command."""
        message = telegram.helpers.escape_markdown('Process aborted.', version= 2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        return ConversationHandler.END

    async def handleChName(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the change name command """
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if context.args == []:
                message = telegram.helpers.escape_markdown('The syntax for this command is /chname [NAME]. Please try again.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            name = " ".join(context.args)
            cf.USER_DATA[chatid]['NAME'] = name
            cf.saveConfiguration()
            message = telegram.helpers.escape_markdown('Ok, from now on I will call you ' + name,version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return
    async def handleVerify(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ handle the validate command """
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if chatid != cf.MASTER_CHATID:
                message = telegram.helpers.escape_markdown('Sorry this command ís only accessible to the owner.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            if context.args == []:
                message = telegram.helpers.escape_markdown('The syntax for this command is /verify [NAME]. Please try again.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            name = " ".join(context.args)
            ci = self.getIDbyName(name)
            if ci != None:
                    if len(ci) > 1:
                        message = telegram.helpers.escape_markdown('There are multiple users named ' + cf.USER_DATA[ci]['NAME'] + '. During development, this has been seen possible, but intentionally ignored. Please notify the users to change their name to something unique. Use /chname for that.',version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.warn('[TCM] Cannot verify user by name, there are multiple users with the same name.')
                        return
                    ci = ci[0]
                    if cf.USER_DATA[ci]['VALID'] == True:
                        message = telegram.helpers.escape_markdown(cf.USER_DATA[ci]['NAME'] + ' is already verified.',version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        return
                    cf.USER_DATA[ci]['VALID'] = True
                    cf.saveConfiguration()
                    self.sendMessage(ci, 'You have now been verified. You can use all features now. See /help for that. \nI suggest you add a address by usuing /addaddress')
                    message = telegram.helpers.escape_markdown(cf.USER_DATA[ci]['NAME'] + ' is now verified.',version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
                    return

            else: 
                message = telegram.helpers.escape_markdown('Sorry, there is no user ' +name +'. \nUse /show to see all stored data.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return

                    
    async def handleRMuser(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ handle the remove user command """
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if chatid != cf.MASTER_CHATID:
                message = telegram.helpers.escape_markdown('Sorry this command ís only accessible to the owner.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            if context.args == []:
                message = telegram.helpers.escape_markdown('The syntax for this command is /rmuser [NAME] /nUse /show to see all data.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            id = self.getIDbyName(" ".join(context.args))
            if id == None:
                message = telegram.helpers.escape_markdown('The user ' + " ".join(context.args) + ' is unknown.' ,version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            if len(id) > 1:
                message = telegram.helpers.escape_markdown('There are multiple users named ' + " ".join(context.args) + '. During development, this has been seen possible, but intentionally ignored. Please notify the users to change their name to something unique. Use /chname for that.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.warn('[TCM] Cannot verify user by name, there are multiple users with the same name.')
                return
            id = id[0]
            if id == chatid:
                message = telegram.helpers.escape_markdown('You can\'t delete yourself.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            del cf.USER_DATA[id]
            cf.saveConfiguration()
            message = telegram.helpers.escape_markdown('The user ' + " ".join(context.args) + ' is deleted.' ,version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return
            

    
    async def sanityCheck(self, update):
        if cf.MASTER_CHATID == None or cf.MASTER_CHATID == '':
            message = telegram.helpers.escape_markdown('This bot is not configured. Use /start to configure.',version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.warn('[TCM] Sanity check failed, no control chat defined.')
            return False
        if not cf.USER_DATA.get(str(update.message.chat_id)):
            message = telegram.helpers.escape_markdown('OOPS!\nIt seems that I don\'t know you. Please use /start first.',version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.warn('[TCM] Sanity check failed, unknown user.')
            return False
        if cf.USER_DATA[str(update.message.chat_id)]['VALID'] == False:
            message = telegram.helpers.escape_markdown('OOPS!\nIt seems that the owner did not verify your account.',version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.warn('[TCM] Sanity check failed, user not verified.')
            return False
        cf.log.debug('[TCM] Sanity check passed.')
        return True

       
    def getAddressesStr(self, userid):
        msg = ''
        for i in range(len(cf.USER_DATA[userid]['ADDRESSES'])):
            msg = msg + str(i+1) + '.\n'
            msg = msg + cf.USER_DATA[userid]['ADDRESSES'][i]['ADDR_NAME'] + '\n'
            msg = msg + cf.USER_DATA[userid]['ADDRESSES'][i]['ADDR'] + '\n'
            msg = msg + str(cf.USER_DATA[userid]['ADDRESSES'][i]['COORDS'][1]) + ', ' + str(cf.USER_DATA[userid]['ADDRESSES'][i]['COORDS'][1]) + '\n\n'
        return msg
    
    def getIDbyName(self, name):
        users = []
        for ci in cf.USER_DATA.keys():
            if cf.USER_DATA[ci]['NAME'] == name:
                users.append(ci)
        if users == []:
            return None
        return users
    def getIDbyAddrName(self, addrName):
        users = []
        ix = []
        for ci in cf.USER_DATA.keys():
            for i in range(len(cf.USER_DATA[ci]['ADDRESSES'])):
                if cf.USER_DATA[ci]['ADDRESSES'][i]['ADDR_NAME'] == addrName:
                    users.append(ci)
                    ix.append(i)
        return users, ix



