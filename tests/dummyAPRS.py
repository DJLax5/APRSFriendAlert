import config as cf
import os
import threading
import time
import requests
import json
import numpy as np

class dummyAPRS():

    def __init__(self, newDataHandler):
        """ Constructor for the DUMMY APRS Object. It reads the route.json which is a list of coordinates [[lng, lat],[lng, lat],[lng, lat],[lng, lat]] which are returned one by one """

        # As this is a child class, execute the parent constructor
        super().__init__()

        self.newDataHandler = newDataHandler
        self._stop_event = True
        self._running = False
        

        self.ix = 0
        try:    
            with open('tests/route.json') as f:
                self.coords = json.loads(f.read())
        except:
            cf.log.critical('[DUMMY APRS] Cannot load route.json')
            self.coords= [[0,0], [1,1] ]
                       
        cf.log.warn('[DUMMY APRS] The DUMMY APRS class is in use. No actual APRS Data is used!')

    def stop(self):
        """ Stops the thread. To peacfully exit the infiite loop"""
        self._stop_event = True

    def start(self):
        """Creates a new thread using the run function and starts it, if we cannot use the previous/still running thread"""
        self._stop_event = False
        if self._running == False:
            threading.Thread(target=self.run).start()
        

    def run(self): 
        """ This is the entry point for the loop. It will call the new data handler with the stored coordinates. """
        cf.log.debug('[DUMMY APRS] New Thread entry')
        self._running = True
        time.sleep(2)
        while self._stop_event == False: # loop, unless stopped
            cf.log.debug('[APRS] Querring APRS API...')
            data = self.getPosition()
            self.newDataHandler(data)
            time.sleep(15)
        self._running = False
        cf.log.debug('[DUMMY APRS] Thread exit')

    def getPosition(self, tryAnyway=False):
        """ This function returns the dummy data one by one"""
        cf.log.debug('[DUMMY APRS] Retruning next coords')
        self.ix += 1
        if self.ix >= len(self.coords):
            self.ix = 0
        return self.coords[self.ix]
