import os
from dotenv import load_dotenv
import logging
import json

def loadConfiguration():
    """ Function used to load the userdata"""
    
    # load the json data
    try:
        with open(os.getenv('CONFIG_FILE_PATH')) as f:
            data = json.loads(f.read())
        if data.get('CONTROL_CHATID') != None and data.get('USER_DATA') != None:
            return data
        else:
            log.warn('[CONFIG] The user data is not present. If this is the first start of the bot, this is expected.')
            return None
    except Exception as e:
        log.warn('[CONFIG] The user data is not present. If this is the first start of the bot, this is expected.')
        return None
            
def saveConfiguration():
    try:
        data = {}
        data['CONTROL_CHATID'] = MASTER_CHATID
        data['USER_DATA'] = USER_DATA
        with open(os.getenv('CONFIG_FILE_PATH'), 'w') as f:
            f.write(json.dumps(data))
        log.debug('[CONFIG] Configuration file written.')
    except Exception as e:
        log.error('[CONFIG] Writing data file failed. Reason: ' + str(e))

def setupLogging():
    # Set up the logger with file and console handlers
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create a console handler and set its level to WARNING
    console_handler = logging.StreamHandler()
    console_handler.setLevel(os.getenv('CONSOLE_LOGGING_LEVEL'))
    console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

    # Create a file handler and set its level to DEBUG
    file_handler = logging.FileHandler(os.getenv('LOG_FILE_PATH'), mode='a')
    file_handler.setLevel(os.getenv('FILE_LOGGING_LEVEL'))
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='[%d.%m.%y %H:%M:%S]'))

    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


# Run the confiuration, will be executed on first import, only once
load_dotenv() # load the .env keys
log = setupLogging()
data = loadConfiguration()
if data == None:
    MASTER_CHATID = ""
    USER_DATA = {}
else:
    MASTER_CHATID = data['CONTROL_CHATID']
    USER_DATA = data['USER_DATA']
    log.debug(USER_DATA)
del data # free up namespace
log.info('[CONFIG] Sytsem Started, Configuration loaded!')