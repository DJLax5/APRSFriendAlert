import config as cf
from OpenRouteService import OpenRouteService
from APRS import APRS
from TelegramChatManager import TelegramChatManager
import logging
import os
import numpy as np


class APRSFriendAlert:
    """The main class for the whole application. It provides the requred logic."""


    class ErrorHandler(logging.Handler):
        """ An inner class which provides the error handler to also send messages to telegram."""
        def __init__(self, afa) -> None:
            super().__init__()
            self.afa = afa # store APRSFriendAlertObject

        def emit(self, record):
            """ The function which is called on each logging event, pushes the errors and worse to telegram"""
            if record.levelno == logging.CRITICAL or record.levelno == logging.ERROR:
                try:
                    self.afa.tcm.sendMessage(cf.MASTER_CHATID,'Oh no! There was an error! \n' + record.message)
                except: # this exception is not needed, the error is logged anyways
                    pass
    

    def __init__(self):
        """Constructor for the basic logic of this bot. This Object holds all subroutines/objects needed to work. """

        # Flags
        self.following = False
        self.dest = None
        self.alertees = None
        self.ALERT_TIMES = [-1, 60, 30, 15, 5, 2] # the intervals during which the alertees are alerted. -1 means the inital away time, regardless of how far that is
        self.alertState = [False, False, False, False, False, False]

        # Setup the API Bouncers 
        self.ors = OpenRouteService()
        self.aprs = APRS(self.newAPRSData)
        self.tcm = TelegramChatManager(self.routeUpdate(), self.ors.geocode)
        cf.log.addHandler(self.ErrorHandler(self)) # now add the telegram error handler
        
    def main(self):
        """This function starts the telegram conversation handler. This function will not return, as long as the bot is running."""
        self.tcm.execTCM()

    @staticmethod
    def getTimeStr(time):
        """Basic methon to convert minutes into a string in h and mins."""
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
        
        # now chech how long it takes from the current position to the destination
        response = self.ors.getRouteSummary(coords, self.dest) 
        if response != None:
            # extract the distance and time 
            distance = np.round(response[0])
            time = response[1]
            timeStr = APRSFriendAlert.getTimeStr(time)

            # now check weather we have to alert somebody
            if self.alertState[0] == False: # the initial alert. Notify master an the clients
                self.alertState[0] = True # set the flag for inital alert
                self.alertState[1:] = [round(time) <= alert_time for alert_time in self.ALERT_TIMES[1:]] # set all flags for longer times. This route will not need every alert

                if all(self.alertState): # we've arrived at the desitination already!?
                    self.tcm.sendMessage(cf.MASTER_CHATID, 'OOPS! It seems you\'re already at your destination! I won\'t do anything further.')
                    self.aprs.stop()
                    return
                # Ok now send the messages
                self.tcm.sendMessage(cf.MASTER_CHATID, 'EN-ROUTE!\n' + os.getenv('APRS_FOLLOW_CALL') + ' is now beeing followed. Your route is ' + distance + ' km long and will take ' + timeStr + '.\nYou can cancel this, by the \quit command.')
                for alertee in self.alertees:
                    self.tcm.sendMessage(alertee, 'Great!\n'+ os.getenv('APRS_FOLLOW_CALL') + 'is on its way to you!\n' + os.getenv('APRS_FOLLOW_CALL') + ' is currently ' + distance + ' km and ' + timeStr + 'away.'  )
                cf.log.debug('Follow Process is started, first packet arrived successfully!')

            else:
                # now get the next index of the time we have to wait for. 
                # if the self.alertState is [True, True, False, False, False] nextAlertIx will be 2
                nextAlertIx = np.where(self.alertState)[0][-1] + 1 

                # now check if the next time falls below the alert threshold
                if round(time) <= self.ALERT_TIMES(nextAlertIx):
                    message = ''
                    self.alertState[nextAlertIx] = True # set the flag
                    if self.ALERT_TIMES(nextAlertIx) == self.ALERT_TIMES[-1]: # are we there yet?
                        message = '\u00128680 ' + os.getenv('APRS_FOLLOW_CALL') + ' arrived! \u00128680'
                        self.tcm(cf.MASTER_CHATID, 'You\'ve arrived at your destination.')
                        self.aprs.stop()
                    else:
                        message = os.getenv('APRS_FOLLOW_CALL') + ' is currently ' + distance + ' km and ' + timeStr + 'away.'
                    
                    # message is built, send it 
                    for alertee in self.alertees:
                        self.tcm.sendMessage(alertee, message)



    def routeUpdate(self, dest, alertees):
        """This function is to be called by the TelegramChatManager and tells the main logic where the new route is going. It initiates or terminates the process. The desitination is None if the follow process is to be terminated, otherwise the desitnation coordinates. Alerts is a list of chatIDs which are to be alerted."""
        if dest == None:
            self.aprs.stop()
            self.following = False
            self.dest = None
            self.alertees = None
            self.alertState = [False, False, False, False, False, False]
            cf.log.info('[ADA] Quitting following process.')    
        else:
            self.dest = dest
            self.alerts = alertees
            self.following = True
            self.alertState = [False, False, False, False, False, False]
            try:
                self.aprs.start()
            except Exception as e:
                self.aprs.restart()

            cf.log.info('[AFA] New following process initiated.')


    



if __name__ == '__main__':
    cf.MASTER_CHATID = '402776996'
    afa = APRSFriendAlert()
    afa.main()
    cf.log.info('[AFA] System shutting down.')
