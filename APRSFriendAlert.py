import config as cf
from OpenRouteService import OpenRouteService
from APRS import APRS
from tests.dummyAPRS import dummyAPRS
from TelegramChatManager import TelegramChatManager
import logging
import os
import numpy as np
from time import sleep


class APRSFriendAlert:
    """The main class for the whole application. It provides the requred logic."""


    class ErrorHandler(logging.Handler):
        """ An inner class which provides the error handler to also send messages to telegram."""
        def __init__(self, messageCallback, level = 'ERROR') -> None:
            """Here you define a function to be called with a chat ID and message and a logging level"""
            super().__init__()
            self.messageCallback = messageCallback # store callback function
            try:
                self.level = int(logging.getLevelName(level)) # try to get the level, revert to 'ERROR' if it fails
            except:
                self.level = 40
                cf.log.error('[AFA] Could not determine the logging-level for telegram messages. Default: ERROR')

        def emit(self, record):
            """ The function which is called on each logging event, pushes the errors and worse to telegram"""
            if record.levelno >= self.level: # record passt the threshold
                try:
                    self.messageCallback(cf.MASTER_CHATID,'\0001F6A7 LOGGING EVENT \0001F6A7\n[' + record.levelname + '] ' + record.message)
                except: # this exception is not needed, the error is logged anyways
                    pass
    

    def __init__(self, dummy=False):
        """Constructor for the basic logic of this bot. This Object holds all subroutines/objects needed to work. """

        # Flags
        self.following = False
        self.dest = None
        self.alertees = None
        self.ALERT_TIMES = [-1, 60, 30, 10, 1] # the intervals during which the alertees are alerted. -1 means the inital away time, regardless of how far that is
        self.alertState = [False, False, False, False, False, False]
        self.toStr = 'you'

        # Setup the API Bouncers 
        self.ors = OpenRouteService()
        if dummy:
            self.aprs = dummyAPRS(self.newAPRSData)
        else:
            self.aprs = APRS(self.newAPRSData)
        self.tcm = TelegramChatManager(self.routeUpdate, self.ors.geocode)
        cf.log.addHandler(self.ErrorHandler(self.tcm.sendMessage, os.getenv('TELEGRAM_LOGGING_LEVEL'))) # now add the telegram error handler
        
    def main(self):
        """This function starts the telegram conversation handler. This function will not return, as long as the bot is running."""
        self.tcm.execTCM()

    @staticmethod
    def getTimeStr(time):
        """Basic methond to convert minutes into a string in h and mins."""
        hours, minutes = divmod(round(time), 60)
        if hours == 0:
            output_str = f"{minutes} min"
        elif minutes == 0:
            output_str = f"{hours} h"
        else:
            output_str = f"{hours} h and {minutes} min"
        return output_str
    

    def newAPRSData(self, coords):
        """This function gets called by the APRS Thread. New data is available and we can check the traveltime to the destionation and notiofy the users."""
        if not self.following: # following stopped by someone, stop the aprs thread
            self.aprs.stop() 
            return
        cf.log.debug('[AFA] New APRS Data!')
        # now chech how long it takes from the current position to the destination
        response = self.ors.getRouteSummary(coords, self.dest) 
        if response != None:
            # extract the distance and time 
            distance = np.round(response[0],1)
            time = response[1]
            timeStr = APRSFriendAlert.getTimeStr(time)

            # now check weather we have to alert somebody
            if self.alertState[0] == False: # the initial alert. Notify master an the clients
                self.alertState[0] = True # set the flag for inital alert
                self.alertState[1:] = [round(time) <= alert_time for alert_time in self.ALERT_TIMES[1:]] # set all flags for longer times. This route will not need every alert

                if all(self.alertState): # we've arrived at the desitination already!?
                    self.tcm.sendMessage(cf.MASTER_CHATID, 'OOPS! \nIt seems you\'re already at your destination \U0001F3C1 \nI won\'t do anything further.')
                    self.aprs.stop()
                    self.following = False
                    return
                # Ok now send the messages
                self.tcm.sendMessage(cf.MASTER_CHATID, '\U0001F698 EN-ROUTE \U0001F698 \n' + os.getenv('APRS_FOLLOW_CALL') + ' is now beeing followed. Your route is ' + str(distance) + ' km long and will take ' + timeStr + '.')
                for alertee in self.alertees:
                    self.tcm.sendMessage(alertee, 'Great! \U0001F698\n'+ os.getenv('APRS_FOLLOW_CALL') + ' is on its way to '+ self.toStr +'!\n' + os.getenv('APRS_FOLLOW_CALL') + ' is currently ' + str(distance) + ' km and ' + timeStr + ' away.'  )
                cf.log.info('Follow Process is started, first packet arrived successfully!')

            else:
                # now get the next index of the time we have to wait for. 
                # if the self.alertState is [True, True, False, False, False] nextAlertIx will be 2
                nextAlertIx = np.where(self.alertState)[0][-1] + 1 
                # now check if the next time falls below the alert threshold
                if round(time) <= self.ALERT_TIMES[nextAlertIx]:
                    message = ''
                    self.alertState[1:] = [round(time) <= alert_time for alert_time in self.ALERT_TIMES[1:]] # set the flag(s) if we skipped a alert
                    if all(self.alertState): # are we there yet?
                        message = '\U0001F6A8 ' + os.getenv('APRS_FOLLOW_CALL') + ' arrived! \U0001F3C1'
                        self.tcm.sendMessage(cf.MASTER_CHATID, 'You\'ve arrived at your destination! \U0001F3C1')
                        self.aprs.stop()
                        self.following = False
                        cf.log.info('[AFA] You have arrived at your desitination. Stopping processes...')
                    else:
                        message = '\U0001F697 ' + os.getenv('APRS_FOLLOW_CALL') + ' is currently ' + str(distance) + ' km and ' + timeStr + ' away.'
                    
                    # message is built, send it 
                    for alertee in self.alertees:
                        self.tcm.sendMessage(alertee, message)
                    cf.log.debug('[AFA] Messages have been set. Time to destination ' + timeStr)
                else:
                    cf.log.debug('[AFA] Nobody to notify. Time to destination ' + timeStr)



    def routeUpdate(self, dest, alertees, toStr = None):
        """This function is to be called by the TelegramChatManager and tells the main logic where the new route is going. It initiates or terminates the process. The desitination is None if the follow process is to be terminated, otherwise the desitnation coordinates. Alerts is a list of chatIDs which are to be alerted."""
        if dest == None:
            self.aprs.stop()
            self.following = False
            self.dest = None
            self.alertees = None
            self.alertState = [False, False, False, False, False, False]
            self.toStr = 'you'
            cf.log.info('[AFA] Quitting following process.')    
        else:
            self.dest = dest
            self.alertees = alertees
            self.following = True
            self.alertState = [False, False, False, False, False, False]
            if toStr == None or toStr == '':
                self.toStr = 'you'
            else:
                self.toStr = toStr
            self.aprs.start()
            cf.log.info('[AFA] New following process initiated.')


    



if __name__ == '__main__':
    afa = APRSFriendAlert(dummy=True)
    afa.main()
    afa.aprs.stop()
    cf.log.info('[AFA] System shutting down.')
    #tcm = TelegramChatManager(None, None)
    #distance = 2300
    #timeStr = APRSFriendAlert.getTimeStr(63)
    #tcm.sendMessage(cf.MASTER_CHATID, 'OOPS! It seems you\'re already at your destination! I won\'t do anything further.' )
