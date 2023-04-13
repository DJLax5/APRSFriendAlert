import os
import config as cf
from OpenRouteService import OpenRouteService
from APRS import APRS
import TelegramChatManager
import time

import telegram
import threading
import asyncio

def handleError(record):
    pass

class Demo(threading.Thread):
    def __init__(self) -> None:
        super().__init__()


    def run(self):
        time.sleep(10)
        self.send()
        
        #asyncio.run(self.bot.send_message(chat_id=402776996, text="Started"))
        

    def send(self):
        bot = telegram.Bot(token=os.getenv('TELEGRAM_TOKEN'))

        async def send_message():
            await bot.send_message(chat_id='402776996', text='Hello, world!')

        # call the asynchronous function using asyncio.run()
        asyncio.run(send_message())

if __name__ == '__main__':
    
    #ors = OpenRouteService()
    #aprs = APRS()
    D = Demo()
    D.start()
    TelegramChatManager.main()
    print("Done!")
