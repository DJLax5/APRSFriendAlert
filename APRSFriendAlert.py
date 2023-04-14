import config as cf
from OpenRouteService import OpenRouteService
from APRS import APRS
from TelegramChatManager import TelegramChatManager
import logging


class APRSFriendAlert:
    """The main class for the whole application. It provides the requred logic."""


    class ErrorHandler(logging.Handler):
        """ An inner class which provides the error handler to also send messages to telegram."""
        def __init__(self, afa) -> None:
            super().__init__()
            self.afa = afa # store APRSFriendAlertObecjt

        def emit(self, record):
            """ The function which is called on each logging event."""
            if record.levelno == logging.CRITICAL or record.levelno == logging.ERROR:
                try:
                    self.afa.tcm.sendMessage(cf.MASTER_CHATID,'Oh no! There was an error! \n' + record.message)
                except: # this exception is not needed, the error is logged anyways
                    pass
    

    def __init__(self):
        self.aprs.stop()
        self.following = False
        self.dest = None
        self.alertees = None
        self.ALERT_TIMES = [-1, 60, 30, 15, 5, 2] # the intervals during which the alertees are alerted. -1 means the inital away time, regardless of how far that is
        self.alertState = [False, False, False, False, False, False]

        self.ors = OpenRouteService()
        self.aprs = APRS(self.newAPRSData)
        self.tcm = TelegramChatManager(self.routeUpdate(), self.ors.geocode)
        cf.log.addHandler(self.ErrorHandler(self)) # now add the telegram error handler
        
    def main(self):
        self.tcm.execTCM()

    def newAPRSData(self, coords):
        #TODO: Do Something!
        cf.log.error('[AFA] This method is not implemented yet!')

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
            self.aprs.start()
            cf.log.info('[AFA] New following process initiated.')


    



if __name__ == '__main__':
    cf.MASTER_CHATID = '402776996'
    afa = APRSFriendAlert()
    afa.main()
    cf.log.info('[AFA] System shutting down.')
