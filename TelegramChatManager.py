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
import re

CONFIG_BOT, GET_NAME = range(2)
GET_ADDR_NAME, GET_ADDR, CHECK_ADDR = range(3)
SEL_RM_ADDR = range(1)

class TelegramChatManager:
    """This Class will be a telegram bot application and handle all the communication and setup with the telegram users. It will trigger the request to follow the owner via APRS and supply a function to send messages directly to users."""
    

    def __init__(self, newRouteCallback, geocodeCallback):
        """Construct the chat manager object. It allows to handle conversations with multiple users"""
        self.bot = telegram.Bot(token=os.getenv('TELEGRAM_TOKEN')) #simple object to send single messages without conversation control

        # Create the Application and pass it your bot's token.
        self.app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

        # on different commands start different conversaions
        convStartHandler = ConversationHandler( # /start conversation
            entry_points=[CommandHandler("start", self.handleStart)],
            states={
            CONFIG_BOT:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerCheckMasterKey), CommandHandler("start", self.handleStart)], # State: This bot has no MASTER_CHATID set
            GET_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerGetName)] # We do not know the user, create a user
            },
            fallbacks=[CommandHandler("quit", self.handleQuit)]
        )
        convAddAddrHandler = ConversationHandler( # /addaddr Handler
            entry_points=[CommandHandler("addaddress", self.handleAddAddress)],
            states={
            GET_ADDR_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerGetAddrName)], # get the name for the address
            GET_ADDR:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerGetAddr)], # get the actual address
            CHECK_ADDR:[MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlerCheckAddr)], # ask weather geocoding was successfull
            },
            fallbacks=[CommandHandler("quit", self.handleQuit)]
        )

        # Add the conversation handlers
        self.app.add_handler(convStartHandler)
        self.app.add_handler(convAddAddrHandler)
        # Add the command handlers
        self.app.add_handler(CommandHandler("help", self.handleHelp))
        self.app.add_handler(CommandHandler("takeover", self.handleTakeover))
        self.app.add_handler(CommandHandler("show", self.handleShAddress))
        self.app.add_handler(CommandHandler("quit", self.handleQuit))
        self.app.add_handler(CommandHandler("chname", self.handleChName))
        self.app.add_handler(CommandHandler("verify", self.handleVerify))
        self.app.add_handler(CommandHandler("rmuser", self.handleRMuser))
        self.app.add_handler(CommandHandler("rmaddress", self.handleRmAddress))
        
        # on non command i.e message
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handleMessage))

        # store the callback functions
        self.newRoute = newRouteCallback
        self.geocode = geocodeCallback

    def execTCM(self):
        """This function will start the polling process of the Telegram bot. This function will not return."""
        self.app.run_polling()

    def sendMessage(self, chatID, message):
        """Basic function to send a message to a specific chat, this can be called from anywhere at anytime
        """
        if chatID == None or chatID == '':
            return
        message = telegram.helpers.escape_markdown(message, version=2)
        async def send_message(self, chatID, message):
            try:
                await self.bot.send_message(chat_id=chatID, text=message, parse_mode='MarkdownV2')
            except telegram.error.BadRequest as e:
                cf.log.warn('[TCM] The message could not be sent. Reason: ' + str(e))

        # call the asynchronous function using asyncio.run().
        # If anyone can get it to work otherwise, please do so. can't getz Multithreading and asnyio to work together.. 
        # It will fail, if we are already within a subroutine. then use ensure_future.
        with warnings.catch_warnings(): # disable the warning, we want to catch
            warnings.filterwarnings("ignore", message="coroutine 'TelegramChatManager.sendMessage.<locals>.send_message' was never awaited")
            try:
                asyncio.run(send_message(self, chatID, message))
            except:
                with warnings.catch_warnings(): # disable the warning, we want to catch
                    warnings.filterwarnings("ignore", message="Enable tracemalloc to get the object allocation traceback")
                    try:
                        asyncio.ensure_future(send_message(self, chatID, message))
                    except:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        asyncio.run(send_message(self, chatID, message))


    # Define a few command/conversation handlers. These usually take the two arguments update and
    # context.
    async def handleStart(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start the setup conversation after the /start command"""
        # check weather this bot has been setup:
        if cf.MASTER_CHATID != None and cf.MASTER_CHATID != '': # yes, has been setup.
            # check weather we know the user
            chatid = str(update.message.chat_id)

            if cf.USER_DATA.get(chatid): #user is known
                # greet and exit the conversation
                message = telegram.helpers.escape_markdown("Welcome back " + cf.USER_DATA[chatid]['NAME'] +"!\nYou can use /help to show the available commands.", version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.debug('[TCM] /start command by a already known user: ' + cf.USER_DATA[chatid]['NAME'])
                return ConversationHandler.END
            else: # user is not known, ask for the namne
                name = update.effective_user.first_name
                message = telegram.helpers.escape_markdown("Hello!\nI am "+ os.getenv('APRS_FOLLOW_CALL') + '\'s APRS Alert bot. Your name in Telegram is ' + name + '. Should I call you by this name? \nIf yes, respond with \'yes\', or respond with your name, if you want to be called by another name.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.info('[TCM] A new user started a chat.')
                return GET_NAME
        else: # bot has not been setup, ask for the key
            name = update.effective_user.first_name
            message = telegram.helpers.escape_markdown("Hello!\nI am "+ os.getenv('APRS_FOLLOW_CALL') + '\'s APRS Alert bot. This bot has not been configured by it\'s owner. If you are the owner please respond with the magic key, you set up in the .env file. If you are not the owner, please try again with /start once this bot has been configured.', version =2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.info('[TCM] A new user started a chat, this bot is not configured yet.')
            return CONFIG_BOT
         


    async def handlerCheckMasterKey(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """This is to be called, if the bot has not been configured yet """
        if update.message.text == os.getenv('MAGIC_KEY'): # check the key
            # strore this as the master chat
            # save to the file once a name has been obtained
            cf.MASTER_CHATID = str(update.message.chat_id)
            name = update.effective_user.first_name # get the name
            message = telegram.helpers.escape_markdown('You have succesfully identified yourself. This is now the chat to control everything.\nYour name in Telegram is ' + name + '. Should I call you by this name? \nIf yes, respond with \'yes\', or respond with your name, if you want to be called by another name.', version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.debug('[TCM] Correct Key detected for setup.')
            return GET_NAME
        else: # wrong key, keep trying
            message = telegram.helpers.escape_markdown('This is not correct. Please try again.',version = 2)
            cf.log.warn('[TCM] The supplied key is wrong. User: ' + update.effective_user.first_name)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return CONFIG_BOT



    async def handlerGetName(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """This is to be called, when the username is set """
        chatid = str(update.message.chat_id)
        if update.message.text.strip().lower() == 'yes': # user is happy with the name from telegram 
            name = update.effective_user.first_name
        else: # use user supplied name
            name = update.message.text
        # prepare the dataset 
        cf.USER_DATA[chatid] = {}
        cf.USER_DATA[chatid]['NAME'] = name
        cf.USER_DATA[chatid]['ADDRESSES'] = []
        # if this is the control chat, we already set it to be verified
        cf.USER_DATA[chatid]['VALID'] = False if chatid != cf.MASTER_CHATID else True
        cf.saveConfiguration() # store json data
        # Notify the user
        if chatid != cf.MASTER_CHATID:
            self.sendMessage(cf.MASTER_CHATID, 'A new user just joined this service. If you want to unlock ' + name +' type: \n/verify ' + name) #notify the owner
            message = telegram.helpers.escape_markdown('Hi ' + name + '! Nice to meet you!\nYou\'re now registed. Use the /help command to see what can be done by me. \n\nHowever bevor you can do anything, you\'ll need to verified by the owner. He/She just received a notification to unlock your account.', version= 2)
            cf.log.info('[TCM] A new user joined this service. ' + name + ' is not yet verified.')
        else:
            message = telegram.helpers.escape_markdown('Hi ' + name + '! Nice to meet you!\nYou\'re now registed and verified. Use the /help command to see what can be done by me.', version= 2)
            cf.log.info('[TCM] The owner has been setup, bot now operational. Name: ' + name)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        return ConversationHandler.END


    async def handleAddAddress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start the add address conversation after the /addaddress command"""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if self.geocode == None: # catch invalid setup
                message = telegram.helpers.escape_markdown('Sorry, the backend for the address configuration is not available.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.critical('[TCM] Geocoding handler is not defined!')
                return ConversationHandler.END

            # This function has the optional {name} agrument, check weather it is present
            if context.args != []:
                addrName = " ".join(context.args) # we allow for names with spaces
                message = telegram.helpers.escape_markdown('Great that you want to add a address named ' + addrName  + '\nNow please give me the address.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                context.user_data['ADDR_NAME'] = addrName
                cf.log.debug('[TCM] A new address named ' + addrName +' is in the setup process by user ' + cf.USER_DATA[chatid]['NAME'])
                return GET_ADDR # jump to the address state
            else: # optional argument is not present, ask for a name
                message = telegram.helpers.escape_markdown('Great that you want to add a address. \nNow please give me the name under which you want to store address (e.g. \'Home\').', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.debug('[TCM] A new address is in the setup process by user ' + cf.USER_DATA[chatid]['NAME'])
                return GET_ADDR_NAME

    async def handlerGetAddrName(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ In this we get the name of the address and geocode/check it """
        if await self.sanityCheck(update):
            chatid = str(update.message.chat_id)
            addrName = update.message.text
            context.user_data['ADDR_NAME'] = addrName # store the address name in the user data of telegram
            message = telegram.helpers.escape_markdown('Great that you want to add a address named ' + addrName  + '\nNow please give me the address.', version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.debug('[TCM] User ' + cf.USER_DATA[chatid]['NAME'] + ' wants to setup a address called ' + addrName)                
            return GET_ADDR
        return ConversationHandler.END
    
    async def handlerGetAddr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ In this we check weather the user is happy with this address """
        if await self.sanityCheck(update):
            chatid = str(update.message.chat_id) 
            addr = update.message.text
            # The acual address is now beeing converted to coordinates
            coords = self.geocode(addr)
            context.user_data['ADDR'] = addr
            context.user_data['COORDS'] = coords
            # make the goole maps link to check weather the coordinates are correct
            url = "https://www.google.com/maps/search/?api=1&query={},{}".format(coords[1], coords[0])
            message = telegram.helpers.escape_markdown('Ok thank you. May I strore this address?\nPlease check the link, if the coordinates match your expecxted address.\n\n' + context.user_data['ADDR_NAME']  + '\n' + context.user_data['ADDR'] + '\n' + str(coords[1]) + ', ' + str(coords[0]) + '\n\n' + url + '\n\nPlease respond with yes or no.', version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.debug('[TCM] User ' + cf.USER_DATA[chatid]['NAME'] + ' supplied the address ' + addr)
            return CHECK_ADDR
        return ConversationHandler.END

    async def handlerCheckAddr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ In this we check weather the user is happy with this address """
        if await self.sanityCheck(update):
            chatid = str(update.message.chat_id) 
            if update.message.text.strip().lower() == 'yes': # geocoding successfull
                # store the data
                temp = {'ADDR_NAME' : context.user_data['ADDR_NAME'],
                        'ADDR' :  context.user_data['ADDR'],
                        'COORDS' : context.user_data['COORDS']}
                cf.USER_DATA[chatid]['ADDRESSES'].append(temp)
                cf.saveConfiguration()
                if chatid != cf.MASTER_CHATID:
                    self.sendMessage(cf.MASTER_CHATID, 'The user ' + cf.USER_DATA[chatid]['NAME'] + ' just added the address ' + temp['ADDR_NAME'])
                message = telegram.helpers.escape_markdown('Data stored. Thank you.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.info('[TCM] The user ' + cf.USER_DATA[chatid]['NAME'] + ' just added the address ' + temp['ADDR_NAME'])
                return ConversationHandler.END
            elif update.message.text.strip().lower() == 'no': # geocoding gone wrong
                message = telegram.helpers.escape_markdown('Ok, please give me the correct address.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.debug('[TCM] Geocoding resulted in a different location than expected by the user.')
                return GET_ADDR
            else:
                message = telegram.helpers.escape_markdown('Please only respond with yes or no.', version= 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return CHECK_ADDR
        return ConversationHandler.END
        
    async def handleRmAddress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start the remove address conversation after the /rmaddress command"""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if chatid == cf.MASTER_CHATID: # if this is the master chat, we can modify all users addresses
                if context.args == []: # missing coordinates
                    message = telegram.helpers.escape_markdown('Syntax for this command is /rmaddress [USERNAME] [ID] where [ID] is the number of the address you want to remove. To see that number use /show.',version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
                    return
                try:
                    name = " ".join(context.args[0:-1]) # build the name (allow for spaces)
                    ix = int(context.args[-1]) -1 # get the index of the address
                    id = self.getIDbyName(name) 
                    if id == None: # wrong name
                        message = telegram.helpers.escape_markdown('Sorry, there is no user named ' + name,version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        return 
                    if len(id) > 1: # multiple users with the same name.... Hopefully never happens
                        message = telegram.helpers.escape_markdown('Sorry, there are multiple user named ' + name + '. During development, this has been seen as possible, but intentionally ignored. Please notify the users to change their name to something unique. Use /chname for that.',version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.warn('[TCM] There are multiple user named ' + name +'. Cannot identify the user to remove the address.')
                        return
                    id = id[0]
                    if ix >= len(cf.USER_DATA[id]['ADDRESSES']): # check weather the address index exits
                        message = telegram.helpers.escape_markdown('Sorry, there is no address with ID ' + str(ix+1), version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        return
                    
                    message = telegram.helpers.escape_markdown('Address ' + cf.USER_DATA[id]['ADDRESSES'][ix]['ADDR_NAME'] + ' deleted.', version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
                    cf.log.info('[TCM] The control chat just removed address ' + cf.USER_DATA[id]['ADDRESSES'][ix]['ADDR_NAME'] + ' from user ' + name)
                    cf.USER_DATA[id]['ADDRESSES'].pop(ix) # actually delete the address
                    cf.saveConfiguration() 
                    
                except:
                    message = telegram.helpers.escape_markdown('Sorry I could not get what you were saying. The Syntax for this command is /rmaddress [USERNAME] [ID] where [ID] is the number of the address you want to remove. To see that number use /show.', version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')

            else: # just a regular user
                if context.args == []: # wrong syntagx
                    message = telegram.helpers.escape_markdown('Syntax for this command is /rmaddress [ID] where [ID] is the number of the address you want to remove. To see that number use /show.',version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
                    return
                try:
                    ix = int(context.args[0]) - 1 # get the id
                    if ix >= len(cf.USER_DATA[chatid]['ADDRESSES']): # check weather the id is valid
                        message = telegram.helpers.escape_markdown('Sorry, there is no address with ID ' + str(ix+1), version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        return
                    message = telegram.helpers.escape_markdown('Address ' + cf.USER_DATA[chatid]['ADDRESSES'][ix]['ADDR_NAME'] + ' deleted.', version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
                    cf.log.info('[TCM] User ' + cf.USER_DATA[chatid]['NAME'] + ' just deleted address ' + cf.USER_DATA[chatid]['ADDRESSES'][ix]['ADDR_NAME'])
                    cf.USER_DATA[chatid]['ADDRESSES'].pop(ix) # actually delete the address
                    cf.saveConfiguration()
                except:
                    message = telegram.helpers.escape_markdown('Sorry I could not get what you were saying. The Syntax for this command is /rmaddress [ID] where [ID] is the number of the address you want to remove. To see that number use /show.', version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')




    async def handleShAddress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /show is issued."""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            msg = '' # build the message of all addresses 
            if chatid == cf.MASTER_CHATID: # and also all users if this is the main chat
                msg = 'As you are the owner of this bot, you will see all stored data. \nUsers will only see the addresses they have added.\n\n'
                for userid in cf.USER_DATA.keys():
                    msg = msg + 'USER: ' + cf.USER_DATA[userid]['NAME'] + '\n'
                    if not cf.USER_DATA[userid]['VALID']:
                        msg = msg + 'Not verified.\n\n'
                    elif cf.USER_DATA[chatid]['ADDRESSES'] == []:
                        msg = msg + 'No addresses defined!\n\n'
                    else:
                        msg = msg + self.getAddressesStr(userid)
                cf.log.debug('[TCM] The control chat just requested all data.')
            else:
                if cf.USER_DATA[chatid]['ADDRESSES'] == []:
                    msg = 'Here are your stored addresses: \n\n'
                    msg = msg + self.getAddressesStr(chatid)
                else:
                    msg = 'You have no addresses defined. Please do so by using /addaddress' 
                cf.log.debug('[TCM] The user '+ cf.USER_DATA[chatid]['NAME']+ ' just requested his/her data.')

            message = telegram.helpers.escape_markdown(msg, version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')

    async def handleHelp(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            # Just build the help message
            msg = 'Here is a list of commands:\nAttributes with [ ] are mandatory, attributes with { } are optional. \n\n'
            msg += '/help \t- displays this help message \n'
            msg += '/takeover [KEY] \t- If you are the owner of this bot, you can make this chat the control chat using the setup Key \n'
            msg += '/show \t- displays all stored data \n'
            msg += '/chname [NEWNAME] \t- changes your name  \n'
            msg += '/quit \t- stops the current conversation / background process \n'
            msg += '/addaddress {NAME} \t- Allows you to define addresses as destination \n' 
            if chatid != cf.MASTER_CHATID:
                msg += '/rmaddress [ID] \t- Allows you to remove the address with the specified ID \n' 
                cf.log.debug('[TCM] The user '+ cf.USER_DATA[chatid]['NAME']+ ' just requested help.')
            else:
                msg += '/rmaddress [NAME] [ID] \t- Allows you to remove the address with the specified ID from the specified user \n' 
                msg += '\nHere are the special control commands:\n'
                msg += '/rmuser [NAME] \t- deletes the user\n'
                msg += '/verify [NAME] \t- verifys the user so they can use this bot\n'
                msg += '\n'
                msg += 'To start the APRS follow process, use:\n'
                msg += 'en route to [NAME] {alert [USER-NAME]} \n'
                msg += '[NAME] can be either a username (if they have only one address defined) or an address name. You can alert multiple users by seperating them by comma. If the \'alert\' tag is specified, the owner of the address is not notified by default.\n'
                cf.log.debug('[TCM] The control chat just requested help.')
            msg += '\nHave fun!'
            message = telegram.helpers.escape_markdown(msg, version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')

    async def handleMessage(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ The default message handler. Whenever a simple message is sent outside of a conversation. We just use it for the "enroute" command"""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):

            if chatid == cf.MASTER_CHATID:
                if self.newRoute == None: # callback is not set!

                    cf.log.critical('[TCM] The callback for new routes is not set, stopping here!')
                    return
                
                # first, check if the enroute command is detected
                pattern = r"^(en.?route to|enroute to) (.+?)(?: alert ((?:[^,]+(?:, )?)+))?$"
                match = re.match(pattern, update.message.text)
                if match: # yes, the string matches the regex                    
                    name = match.group(2) # get the nam 
                    # first try to find the user with that name
                    ids = self.getIDbyName(name)
                    destID = None
                    coords = None
                    alertees = []
                    msg = ''
                    if ids == None: # ok there is no user with that name. Try to get the address by this name
                        users, ix = self.getIDbyAddrName(name)
                        if len(users) > 1: # oh no, multiple same name addresses have been defined, lets deal with that
                            msg = 'Multiple users have defined a address called ' + name 
                            msg += '\n'
                            for i in range(len(users)):
                                msg+= str(i+1) + '. ' + cf.USER_DATA[users[i]]['NAME']  + ', ' +cf.USER_DATA[users[i]]['ADDRESSES'][ix[i]]['ADDR'] + '\n'
                            msg += '\nPlease respond just with the number infront of the user you want to select.'
                            # store the matched string for the next response
                            context.user_data['FOLLOW_MULTIPLE_USERS'] = True
                            context.user_data['FOLLOW_USERS'] = users
                            context.user_data['FOLLOW_IXS'] = ix
                            context.user_data['FOLLOW_ALERTEES'] = match.group(3) if match.group(3) else ''

                            message = telegram.helpers.escape_markdown(msg,version = 2)
                            await update.message.reply_text(message, parse_mode='MarkdownV2')
                            cf.log.debug('[TCM] More than one address named ' + name + ' found. Asking for the corret one.')
                            return
                        elif len(users) == 1: # address found, use that as the destination
                            destID = users[0]
                            coords = cf.USER_DATA[destID]['ADDRESSES'][ix[0]]['COORDS']
                        else: # not found
                            message = telegram.helpers.escape_markdown('Couldn\'t find user or address ' + name,version = 2)
                            await update.message.reply_text(message, parse_mode='MarkdownV2')
                            return
                    else:
                        if len(ids) > 1: # more than one user with that name, hopefully never happens
                            message = telegram.helpers.escape_markdown('There are multiple users called ' + name + '. During development, this has been seen as possible, but intentionally ignored. Please notify the users to change their name to something unique. Use /chname for that.',version = 2)
                            await update.message.reply_text(message, parse_mode='MarkdownV2')
                            cf.log.warn('[TCM] There are multiple users named ' + name + '. Cannot decide to which to go.')
                            return
                        ids = ids[0] # user found
                        # check weather the user has exactly one address defined
                        if len(cf.USER_DATA[ids]['ADDRESSES']) != 1:
                            message = telegram.helpers.escape_markdown('User ' + name + ' has not exactly one address defined. Use the en-route command with the address name instread.',version = 2)
                            await update.message.reply_text(message, parse_mode='MarkdownV2')
                            return
                        # great destination found!
                        destID = ids
                        coords = cf.USER_DATA[destID]['ADDRESSES'][0]['COORDS']
                    # was the "alert" tag mentioned? If yes, build the user list to notify, if not juts noitify the owner of the address
                    alertee_names = match.group(3).split(", ") if match.group(3) else []
                    if alertee_names == []:
                        alertees.append(destID) # not specified, just notify the owner of the desitnation address
                    else: # specified, find the users to alert
                        for alertee in alertee_names:
                            destID = self.getIDbyName(alertee)
                            if destID != None: # for once multiple users with the same name do not bother us!
                                alertees = alertees + destID
                        if len(alertee_names) > len(alertees): # but, some users could not be found, don't do anything
                            # NOTE: Rare exception may occurr: One user is not found and one username exists twice. That passes this check, but hopefully never happens
                            message = telegram.helpers.escape_markdown('Couldn\'t find all the users you requested! Please try again, I won\'t do anything.',version = 2)
                            await update.message.reply_text(message, parse_mode='MarkdownV2')
                            return
                    self.newRoute(coords, alertees) # message parsed successfully
                    message = telegram.helpers.escape_markdown('Great! The following process started! From now on, your APRS data beeing tracked.',version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
                    cf.log.info('[TCM] Suceccfully parsed message ' + update.message.text)

                # regex does not match, but matched once bevor, get the address ID we found
                elif context.user_data.get('FOLLOW_MULTIPLE_USERS') and context.user_data['FOLLOW_MULTIPLE_USERS'] == True:
                    context.user_data['FOLLOW_MULTIPLE_USERS'] == False
                    try:
                        new_ix = int(update.message.text) - 1 # try to get the id the user selected
                        destID = context.user_data['FOLLOW_USERS'][new_ix]
                        coords = cf.USER_DATA[destID]['ADDRESSES'][context.user_data['FOLLOW_IXS'][new_ix]]['COORDS']
                        if context.user_data['FOLLOW_ALERTEES'] == '': # no alert tag was found
                            alertees = [destID]
                        else: # there are alertees to be defined
                            for alertee in alertee_names:
                                destID = self.getIDbyName(alertee)
                                if destID != None: # for once multiple users with the same name do not bother us!
                                    alertees = alertees + destID
                            if len(alertee_names) > len(alertees):  # but, some users could not be found, don't do anything
                                # NOTE: Rare exception may occurr: One user is not found and one username exists twice. That passes this check, but hopefully never happens
                                # fall out of conversation
                                message = telegram.helpers.escape_markdown('Couldn\'t find all the users you requested! Please try again, I won\'t do anything.',version = 2)
                                await update.message.reply_text(message, parse_mode='MarkdownV2')
                                return
                        # route successfully parsed!
                        self.newRoute(coords, alertees)
                        message = telegram.helpers.escape_markdown('Great! The following process started! From now on, your APRS data is beeing tracked.',version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        return
                    except Exception as e:
                        context.user_data['FOLLOW_MULTIPLE_USERS'] = True
                        message = telegram.helpers.escape_markdown('Sorry couldn\'t parse your digit. Please only respond with the single digit infront of the user.',version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.debug('[TCM] Couldn\'t parse response. Reason: ' + str(e))
                        return
                else: # anything else as a message
                    message = telegram.helpers.escape_markdown('Couldn\'t parese your message. To activate the following process, pleas start your command with \'en route to\' \nSee /help to see all possible commands.',version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
            else:
                message = telegram.helpers.escape_markdown('Please see /help to see all possible commands.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')

    async def handleTakeover(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ Use the takeover command to change the master chat id"""
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):

            if chatid == cf.MASTER_CHATID: # nothing to do
                message = telegram.helpers.escape_markdown('This is already the control chat. There is nothing to takeover.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.debug('[TCM] Masterchat tried /takeover.')
            else: # potential takeover
                try:
                    if context.args[0] == os.getenv('MAGIC_KEY'): # successfull
                        # notify the previous owner
                        self.sendMessage(cf.MASTER_CHATID, 'There was a successfull takeover. This chat is no longer the control chat. \nTakeover by: ' + cf.USER_DATA[chatid]['NAME'] + ' / ' + str(update.effective_user.full_name))
                        cf.MASTER_CHATID = chatid # change the master chatid 
                        cf.saveConfiguration()
                        message = telegram.helpers.escape_markdown('Ok, takeover complete. This is now the control chat.', version= 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.info('[TCM] Successful takeover to ' + cf.USER_DATA[chatid]['NAME'])
                    else:
                        self.sendMessage(cf.MASTER_CHATID, 'There was a failed takeover attempt. \nAttempt by: ' + cf.USER_DATA[chatid]['NAME'] + ' / ' + str(update.effective_user.full_name))
                        message = telegram.helpers.escape_markdown('Wrong key. This attempt will be reported.', version= 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.warn('[TCM] Failed takeover attempt by ' + cf.USER_DATA[chatid]['NAME'])
                except: # wrong syntax used
                        message = telegram.helpers.escape_markdown('The syntax for this command is /takeover [KEY]. Please try again.', version= 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')

    async def handleQuit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ Handle to Quit command."""
        if await self.sanityCheck(update):
            message = telegram.helpers.escape_markdown('Process aborted.', version= 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            chatid = str(update.message.chat_id)
            if chatid == cf.MASTER_CHATID:
                self.newRoute(None, None) # delete the route
                context.user_data['FOLLOW_MULTIPLE_USERS'] = False # Fall out of conversation
            cf.log.debug('[TCM] User ' + cf.USER_DATA[chatid]['NAME'] + ' quitted a process/conversation.' )
        # Just to be sure, end convcersation regardless of sanity check
        return ConversationHandler.END # fall out of conversation

    async def handleChName(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the change name command """
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if context.args == []: # wrong syntax
                message = telegram.helpers.escape_markdown('The syntax for this command is /chname [NAME]. Please try again.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            name = " ".join(context.args) # we allow for spaces in the name
            cf.log.info('[TCM] User ' + cf.USER_DATA[chatid]['NAME'] + ' changed its name to ' + name)
            cf.USER_DATA[chatid]['NAME'] = name # update name
            cf.saveConfiguration()
            message = telegram.helpers.escape_markdown('Ok, from now on I will call you ' + name,version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return
        
    async def handleVerify(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ handle the validate command """
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if chatid != cf.MASTER_CHATID: # check privileges 
                message = telegram.helpers.escape_markdown('Sorry this command ís only accessible to the owner.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return 
            if context.args == []: # check syntax
                message = telegram.helpers.escape_markdown('The syntax for this command is /verify [NAME]. Please try again.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            name = " ".join(context.args)
            ci = self.getIDbyName(name) # try to find the name
            if ci != None:
                    if len(ci) > 1:
                        message = telegram.helpers.escape_markdown('There are multiple users named ' + cf.USER_DATA[ci]['NAME'] + '. During development, this has been seen as possible, but intentionally ignored. Please notify the users to change their name to something unique. Use /chname for that.',version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.warn('[TCM] Cannot verify user by name, there are multiple users with the same name.')
                        return
                    ci = ci[0]
                    if cf.USER_DATA[ci]['VALID'] == True:
                        message = telegram.helpers.escape_markdown(cf.USER_DATA[ci]['NAME'] + ' is already verified.',version = 2)
                        await update.message.reply_text(message, parse_mode='MarkdownV2')
                        cf.log.debug('[TCM] User ' + cf.USER_DATA[ci]['NAME'] + ' is already verified.')
                        return
                    cf.USER_DATA[ci]['VALID'] = True
                    cf.saveConfiguration()
                    self.sendMessage(ci, 'You have now been verified. You can use all features now. See /help for that. \nI suggest you add a address by usuing /addaddress')
                    message = telegram.helpers.escape_markdown(cf.USER_DATA[ci]['NAME'] + ' is now verified.',version = 2)
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
                    cf.log.info('[TCM] User ' + cf.USER_DATA[ci]['NAME'] + ' is now verified.')
                    return

            else: # name not found
                message = telegram.helpers.escape_markdown('Sorry, there is no user ' +name +'. \nUse /show to see all stored data.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.debug('[TCM] Cannot verify user ' + name + '. User not found.')
                return

                    
    async def handleRMuser(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ handle the remove user command """
        chatid = str(update.message.chat_id)
        if await self.sanityCheck(update):
            if chatid != cf.MASTER_CHATID: # check privileges
                message = telegram.helpers.escape_markdown('Sorry this command ís only accessible to the owner.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            if context.args == []: # check syntax
                message = telegram.helpers.escape_markdown('The syntax for this command is /rmuser [NAME] /nUse /show to see all data.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            name = " ".join(context.args)
            id = self.getIDbyName(name)
            if id == None:
                message = telegram.helpers.escape_markdown('The user ' + name + ' is unknown.' ,version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.debug('[TCM] Cannot delete user ' + name + '. User not found.')
                return
            if len(id) > 1:
                message = telegram.helpers.escape_markdown('There are multiple users named ' + name + '. During development, this has been seen possible, but intentionally ignored. Please notify the users to change their name to something unique. Use /chname for that.',version = 2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                cf.log.warn('[TCM] Cannot verify user by name, there are multiple users with the same name.')
                return
            id = id[0]
            if id == chatid:
                message = telegram.helpers.escape_markdown('You can\'t delete yourself.',version = 2)
                cf.log.debug('[TCM] User ' + name + ' tried to delete itself.')
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                return
            del cf.USER_DATA[id]
            cf.saveConfiguration()
            message = telegram.helpers.escape_markdown('The user ' + name + ' is deleted.' ,version = 2)
            cf.log.info('[TCM] User ' + name + ' deleted.')
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            return
            

    
    async def sanityCheck(self, update):
        """This is a sanity check to only allow command to run, if the bot and user have been setup correctly"""
        if cf.MASTER_CHATID == None or cf.MASTER_CHATID == '': # no control chat
            message = telegram.helpers.escape_markdown('This bot is not configured. Use /start to configure.',version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.warn('[TCM] Sanity check failed, no control chat defined.')
            return False
        if not cf.USER_DATA.get(str(update.message.chat_id)): # user unknown
            message = telegram.helpers.escape_markdown('OOPS!\nIt seems that I don\'t know you. Please use /start first.',version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.warn('[TCM] Sanity check failed, unknown user.')
            return False
        if cf.USER_DATA[str(update.message.chat_id)]['VALID'] == False: # user not verified
            message = telegram.helpers.escape_markdown('OOPS!\nIt seems that the owner did not verify your account.',version = 2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            cf.log.warn('[TCM] Sanity check failed, user not verified.')
            return False
        cf.log.debug('[TCM] Sanity check passed.')
        return True

       
    def getAddressesStr(self, userid):
        """Simple function to build a text block based on the addresses by a user"""
        msg = ''
        for i in range(len(cf.USER_DATA[userid]['ADDRESSES'])):
            msg = msg + str(i+1) + ':\n'
            msg = msg + cf.USER_DATA[userid]['ADDRESSES'][i]['ADDR_NAME'] + '\n'
            msg = msg + cf.USER_DATA[userid]['ADDRESSES'][i]['ADDR'] + '\n'
            msg = msg + str(cf.USER_DATA[userid]['ADDRESSES'][i]['COORDS'][1]) + ', ' + str(cf.USER_DATA[userid]['ADDRESSES'][i]['COORDS'][0]) + '\n\n'
        return msg
    
    def getIDbyName(self, name):
        """Function used to find the chatid by the users name"""
        users = []
        for ci in cf.USER_DATA.keys():
            if cf.USER_DATA[ci]['NAME'] == name:
                users.append(ci) # multiple users with the same name possible
        if users == []:
            return None
        return users
    def getIDbyAddrName(self, addrName):
        """Function used to find the chatids and indices of an address by the address name. """
        users = []
        ix = []
        for ci in cf.USER_DATA.keys():
            for i in range(len(cf.USER_DATA[ci]['ADDRESSES'])):
                if cf.USER_DATA[ci]['ADDRESSES'][i]['ADDR_NAME'] == addrName: # multiple same name addresses are possible
                    users.append(ci)
                    ix.append(i)
        return users, ix



