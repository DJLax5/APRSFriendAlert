import config as cf
import os
import requests
import json
import numpy as np


class OpenRouteService:

    def __init__(self):
        """ Constructor for the OpenRouteServeice API. It reads the API Key from the .env file and tries to test the connection. """

        # Define the URL Endpoints we need 
        self.ROUTE_CAR_ENDPOINT = "https://api.openrouteservice.org/v2/directions/driving-car"
        self.GEOCODE_ENDPOINT = "https://api.openrouteservice.org/geocode/search"

        self.validated = False
        self.key = os.getenv('OPEN_ROUTE_SERVICE_KEY')
        if self.key != None and self.key != '': # demo bounce the API to check if it is working
            # Simply try to geocode "Berlin, Germany"
            coord = self.geocode("Berlin, Germany", tryAnyway = True)
            if coord != None:
                self.validated = True
                cf.log.info('[ORS] ORS validated.')
            else:
                cf.log.critical('[ORS] Unable to validate the API Key!')
        else:
            cf.log.critical('[ORS] ORS Key is not set, cannot use ORS.')

    
    def geocode(self, text, tryAnyway = False):
        """ Function to geocode a text to coordinates, returns a list of the coordinates [longitude, latitude], if valid, None otherwise. It will not run, if the startup validation failed. This can be overridden by setting tryAnyway = True. """
        if self.validated or tryAnyway: # check if the demo bounce was successfull
            params = {
                "api_key":self.key,
                "text": text,
                "size" : 1
            }
            try:
                response = requests.get(self.GEOCODE_ENDPOINT, params, timeout=(5,15))
                if response.status_code != 200:
                    cf.log.error('[ORS] Geocoding could failed! Server status code: ' + str(response.status_code))
                    return None
                data = json.loads(response.text)
                coord = data['features'][0]['geometry']['coordinates'] # extract the coordinates from the json response
                cf.log.debug("[ORS] Geocoding of " + text + " resulted in these coordinates: " + str(coord))
                return coord
            except Exception as e:
                cf.log.error('[ORS] Geocoding failed! Reason: ' + str(e))
                return None

        else:
            cf.log.warn('[ORS] Tried to geocode but ORS is not validated!')
            return None


    def getRouteSummary(self, start, dest, tryAnyway = False):
        """Function to get the travel time between the coordinates start, dest. Returns a list of two numbers. The first is the distance in km the second the travel time in minutes. It will not run, if the startup validation failed. This can be overridden by setting tryAnyway = True. """
        if self.validated or tryAnyway:
            try:
                params = {
                    "api_key":self.key,
                    "start": str(start[0]) + ',' + str(start[1]),
                    "end" : str(dest[0]) + ',' + str(dest[1])
                }
                response = requests.get(self.ROUTE_CAR_ENDPOINT, params, timeout=(5,15))
                if response.status_code != 200: # check server result
                    cf.log.error('[ORS] Route computation failed Server status code: ' + str(response.status_code))
                    return None
                data = json.loads(response.text)
                distance = float(data['features'][0]['properties']['summary']['distance'])/1000 # extract data, change the unit to km
                time = float(data['features'][0]['properties']['summary']['duration'])/60 # extract date, change the unit to min
                cf.log.debug('[ORS] Route computed, it takes ' + str(int(np.round(time))) + ' min to travel ' + str(np.round(distance,1)) + ' km.') 
                return [distance, time]
            except Exception as e:
                cf.log.error('[ORS] Route computation failed! Reason: ' + str(e))
                return None
        else:
            cf.log.warn('[ORS] Tried to getRouteSummary but ORS is not validated!')
            return None
