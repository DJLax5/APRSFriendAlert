import config as cf
import os
import threading
import time
import requests
import json
import numpy as np

class APRS():

    def __init__(self, newDataHandler):
        """ Constructor for the APRS API Object. It reads the key and Call from the .env file an tries to test the connection. """

        # As this is a child class, execute the parent constructor
        super().__init__()

        self.newDataHandler = newDataHandler
        self._stop_event = True
        self._running = False

        # Define the APRS URL
        self.APRS_ENDPOINT = "https://api.aprs.fi/api/get"

        # read the .env Data
        self.key = os.getenv('APRS_API_KEY')
        self.call = os.getenv('APRS_FOLLOW_CALL')
        

        self.coord = [0.0, 0.0]
        self.lastTimestamp = 0

        # check the correctness of the set data
        self.validated = False
        if self.key != None and self.key != '' and self.call != None and self.call != '':
            data = self.getPosition(tryAnyway=True) 
            if data != None:
                self.validated = True
                cf.log.info('[APRS] APRS Validated! Response: ' + str(data))
                self.coord = data[0]
                self.lastTimestamp = data[1]
            else:
                cf.log.critical('[APRS] Unable to validate APRS API!')

        else:
            cf.log.error('[APRS] APRS API Key/Call is not set, cannot use APRS!')

    def stop(self):
        """ Stops the thread. To peacfully exit the infiite loop"""
        self._stop_event = True

    def start(self):
        """Creates a new thread using the run function and starts it, if we cannot use the previous thread"""
        self._stop_event = False
        if self._running == False:
            threading.Thread(target=self.run).start()
        

    def run(self): 
        """ This is the entry point for the loop. It will start to query APRS.fi and get the position.  It implemenmts an exponential backoff algorithm, if aprs.fi is offline."""
        cf.log.debug('[APRS] New Thread entry')
        self._running = True
        failCount = 0
        self.lastTimestamp = int(time.time()) # the thread has started, waint for the next incoming packet to be seen as "new"
        while self._stop_event == False: # loop, unless stopped
            cf.log.debug('[APRS] Querring APRS API...')
            data = self.getPosition()
            if data != None:
                newTimestamp = data[1]
                newCoord = data[0]
                if newTimestamp > self.lastTimestamp:
                    self.coord = newCoord
                    self.lastTimestamp = newTimestamp
                    self.newDataHandler(newCoord) # Call the new Data Handler with the new coordinates
                failCount = 0
                time.sleep(90) # wait 90sec, aprs packets are not that frequent
            else: 
                failCount = failCount + 1
                if failCount == 7:
                    cf.log.critical('[APRS] Data fetching failed for 6 or more consecutive events!') # The last try was more than 1h ago, we're gonna shutoff
                    self.validated = False
                    self.stop()
                    return
                time.sleep(int(86+np.pow(4,failCount))) # implement the exponential backoff, The intervals are 90sec, 102sec, 150sec, etc.
        self._running = False
        cf.log.debug('[APRS] Thread exit')

    def getPosition(self, tryAnyway=False):
        """ This function calls the APRS API and querys the postion. It will return ([longitude, latitude], timestamp) or None, if the query fails."""
        if self.validated or tryAnyway:
            try:
                params = {
                        "name" : self.call,
                        "what" : "loc",
                        "apikey":self.key,
                        "format": "json"
                    }
                response = requests.get(self.APRS_ENDPOINT, params, timeout=(3,5))
                if response.status_code != 200: # check for the correct error code
                    cf.log.error('[APRS] APRS could not fetch date! Server status code: ' + str(response.status_code))
                    return None
                data = json.loads(response.text)
                if data['result'] != "ok":
                    cf.log.error('[APRS] APRS.fi did not respond with ""ok""! Response: ' + data)
                    return None
                lat = float(data['entries'][0]['lat']) # if the conversion does not fail, we can be confident, that the response was valid
                lng = float(data['entries'][0]['lng'])
                timestamp = int(data['entries'][0]['time']) 
                cf.log.debug('[APRS] Data received: '+ str(lng) + ' ' +str(lat) + ' Timestamp: ' + str(timestamp))
                return [lng, lat], timestamp
            except Exception as e:
                cf.log.error('[APRS] Fetching APRS Data failes. Reason: ' + str(e))
                return None
        else:
            cf.log.warn('[APRS] Tried getPosition, but APRS API is not validated!')
            return None
