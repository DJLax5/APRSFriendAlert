import config as cf
import os
import threading
import time
import requests
import json
import numpy as np

class APRS(threading.Thread):

    def __init__(self):
        # As this is a child class, execute the parent constructor
        super().__init__()
        self._stop_event = threading.Event()

        # Define the APRS URL
        self.APRS_ENDPOINT = "https://api.aprs.fi/api/get"

        # read the .env Data
        self.key = os.getenv('APRS_API_KEY')
        self.call = os.getenv('APRS_FOLLOW_CALL')
        

        self.coord = [0.0, 0.0]
        self.lastTimestamp = 0
        self.newData = False

        # check the correctness of the set data
        self.validated = False
        if self.key != None and self.key != '':
            data = self.getPosition(tryAnyway=True) 
            if data != None:
                self.validated = True
                cf.log.info('[APRS] APRS Validated! Response: ' + str(data))
                self.coord = data[0]
                self.lastTimestamp = data[1]
            else:
                cf.log.critical('[APRS] Unable to validate APRS API!')

        else:
            cf.log.error('[APRS] APRS API Key is not set, cannot use APRS!')

    def stop(self): # to peacfully exit the infiite loop
        self._stop_event.set()

    def run(self): # entry point for the new thread
        failCount = 0
        while not self._stop_event.is_set(): # loop, unless stopped
            data = self.getPosition()
            if data != None:
                newTimestamp = data[1]
                newCoord = data[0]
                if newTimestamp > self.lastTimestamp:
                    self.coord = newCoord
                    self.lastTimestamp = newTimestamp
                    self.newData = True
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

    def getPosition(self, tryAnyway=False):
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
