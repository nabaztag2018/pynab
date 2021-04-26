# -*- coding: utf-8 -*-
"""
aqicn
"""

import requests
import json
import logging

AQICN_URL = "http://api.waqi.info/feed/here/?token=4cf7f445134f3fb69a4c3f0e5001e507a6cc386f"

class aqicnError(Exception):
    """Raise when errors occur while fetching or parsing data"""


class aqicnClient:
    """Client to fetch and parse data from aqicn"""

    def __init__(self, indice, update=False):
        """Initialize the client object."""
        self._airquality = 0
        self._city = "-"
        self._indice = indice 
        if update == True:
            self.update()

    def update(self):
        """Fetch new data and format it"""
        self._fetch_airquality_data()

    def _fetch_airquality_data(self):

        try:
            result = requests.get(AQICN_URL, timeout=10)
            raw_data = result.text
            json_data = json.loads(raw_data)
            logging.debug(json_data)
            city = json_data["data"]["city"]["name"]
            indice_aqi = json_data["data"]["aqi"]
            if ("pm25" in json_data["data"]["iaqi"]) :
                indice_pm25 = json_data["data"]["iaqi"]["pm25"]["v"]
            else:
                logging.debug("no pm25 information available")
                indice_pm25 = indice_aqi
            logging.debug(
                "air quality from aqicn.org and for "
                + str(city)
                + " is "
                + str(indice_aqi)
                + " (AQI) and "
                + str(indice_pm25)
                + " (PM25) selected ->"
                + str(self._indice)
            )

            if self._indice == "aqi":
                indice_to_be_analyzed = indice_aqi
            elif self._indice == "pm25":
                indice_to_be_analyzed = indice_pm25
            else:
                indice_to_be_analyzed = indice_aqi

            try:
                if indice_to_be_analyzed > 100:
                    self._airquality = 0
                elif indice_to_be_analyzed > 50:
                    self._airquality = 1
                else:
                    self._airquality = 2
            except TypeError:
                """Invalid index: assume worst"""
                self._airquality = 0

            self._city = city

        except Exception as err:
            raise aqicnError(err)

    def get_data(self):
        return self._airquality

    def get_city(self):
        return self._city
