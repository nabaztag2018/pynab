import sys
import datetime
import logging
from asgiref.sync import sync_to_async
from nabcommon.nabservice import NabInfoService
from meteofrance.client import meteofranceClient
from . import rfid_data


class NabWeatherd(NabInfoService):
    UNIT_CELSIUS = 1
    UNIT_FARENHEIT = 2

    # [25 {3 3 3 3 3 3 3 3 3 3 3 3 3 3 3 0 0 0 0 0 0 0 0 0}] // soleil
    SUNNY_INFO_ANIMATION = (
        '{"tempo":25,"colors":['
        '{"left":"ffff00","center":"ffff00","right":"ffff00"},'
        '{"left":"ffff00","center":"ffff00","right":"ffff00"},'
        '{"left":"ffff00","center":"ffff00","right":"ffff00"},'
        '{"left":"ffff00","center":"ffff00","right":"ffff00"},'
        '{"left":"ffff00","center":"ffff00","right":"ffff00"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"}]}'
    )

    RAIN_ONE_HOUR = (
        '{"tempo":16,"colors":['
        '{"left":"00000","center":"003399","right":"000000"},'
        '{"left":"003399","center":"000000","right":"003399"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"003399","right":"000000"},'
        '{"left":"003399","center":"000000","right":"003399"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"003399","right":"000000"},'
        '{"left":"003399","center":"000000","right":"003399"},'
        '{"left":"00000","center":"00000","right":"000000"},'
        '{"left":"00000","center":"003399","right":"000000"},'
        '{"left":"003399","center":"000000","right":"003399"},'
        '{"left":"000000","center":"000000","right":"000000"}]}'
    )

    # [125 {0 3 0 4 0 4}] // nuages
    CLOUDY_INFO_ANIMATION = (
        '{"tempo":125,"colors":['
        '{"left":"000000","center":"ffff00","right":"000000"},'
        '{"left":"0000ff","center":"000000","right":"0000ff"}]}'
    )

    WHITE_INFO_ANIMATION = (
        '{"tempo":125,"colors":['
        '{"left":"ffffff","center":"ffffff","right":"ffffff"},'
        '{"left":"000000","center":"000000","right":"000000"}]}'
    )

    # [25 {4 4 4 4 4 4 4 4 4 4 4 4 4 4 4 0 0 0}] // brouillard
    FOGGY_INFO_ANIMATION = (
        '{"tempo":25,"colors":['
        '{"left":"0000ff","center":"0000ff","right":"0000ff"},'
        '{"left":"0000ff","center":"0000ff","right":"0000ff"},'
        '{"left":"0000ff","center":"0000ff","right":"0000ff"},'
        '{"left":"0000ff","center":"0000ff","right":"0000ff"},'
        '{"left":"0000ff","center":"0000ff","right":"0000ff"},'
        '{"left":"000000","center":"000000","right":"000000"}]}'
    )

    # [20 {0 0 0 0 4 0 4 0 4 0 0 0 0 0 4 4 0 0 0 0 0 0 4 0 0 0 4}] // pluie
    RAINY_INFO_ANIMATION = (
        '{"tempo":20,"colors":['
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"0000ff","right":"000000"},'
        '{"left":"0000ff","center":"000000","right":"0000ff"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"0000ff"},'
        '{"left":"0000ff","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"0000ff"},'
        '{"left":"000000","center":"0000ff","right":"000000"},'
        '{"left":"000000","center":"000000","right":"0000ff"}]}'
    )

    # [40 {4 0 0 0 0 0 0 0 4 0 0 0 0 4 0 0 0 0 0 0 4 0 0 0 0 4 0
    #      0 0 0 4 0 0 0 0 0}] // neige
    SNOWY_INFO_ANIMATION = (
        '{"tempo":40,"colors":['
        '{"left":"0000ff","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"0000ff"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"0000ff","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"0000ff"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"0000ff","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"0000ff","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"}]}'
    )

    # [25 {0 4 3 0 0 0 0 0 0 0 0 0 0 0 0 4 3 0 0 4 3 0 0 0 0 0 0
    #      0 3 4 3 4 0}] // orage
    STORMY_INFO_ANIMATION = (
        '{"tempo":25,"colors":['
        '{"left":"000000","center":"0000ff","right":"ffff00"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"0000ff","center":"ffff00","right":"000000"},'
        '{"left":"000000","center":"0000ff","right":"ffff00"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"000000","right":"000000"},'
        '{"left":"000000","center":"ffff00","right":"0000ff"},'
        '{"left":"ffff00","center":"0000ff","right":"000000"}]}'
    )

    # Météo France weather classes
    WEATHER_CLASSES = {
        "J_W1_0-N_0": ("sunny", SUNNY_INFO_ANIMATION),  # Ensoleillé
        "N_W1_0-N_0": ("sunny", SUNNY_INFO_ANIMATION),  # Nuit Claire
        "J_W1_0-N_5": ("cloudy", CLOUDY_INFO_ANIMATION),  # Ciel voilé
        "N_W1_0-N_5": ("cloudy", CLOUDY_INFO_ANIMATION),  # Ciel voilé nuit
        "J_W1_0-N_1": ("sunny", SUNNY_INFO_ANIMATION),  # Éclaircies
        "J_W1_0-N_2": ("sunny", SUNNY_INFO_ANIMATION),  # Éclaircies
        "N_W1_0-N_1": ("sunny", SUNNY_INFO_ANIMATION),  # Éclaircies (nuit)
        "J_W1_0-N_3": ("cloudy", CLOUDY_INFO_ANIMATION),  # Très nuageux
        "J_W1_1-N_0": (
            "foggy",
            FOGGY_INFO_ANIMATION,
        ),  # Brume ou bancs de brouillard (jour)
        "N_W1_1-N_0": (
            "foggy",
            FOGGY_INFO_ANIMATION,
        ),  # Brume ou bancs de brouillard (nuit)
        "J_W1_1-N_3": (
            "foggy",
            FOGGY_INFO_ANIMATION,
        ),  # Brume ou bancs de brouillard (non précisé)
        "J_W1_3-N_0": ("foggy", FOGGY_INFO_ANIMATION),  # Brouillard
        "J_W1_6-N_0": ("foggy", FOGGY_INFO_ANIMATION),  # Brouillard givrant
        "J_W1_7-N_0": ("rainy", RAINY_INFO_ANIMATION),  # Bruine
        "J_W1_8-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluie verglaçante (jour)
        "N_W1_8-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluie verglaçante (nuit)
        "J_W1_8-N_3": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluie verglaçante (non précisé)
        "J_W1_9-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluies éparses / Rares averses (jour)
        "N_W1_9-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluies éparses / Rares averses (nuit)
        "J_W1_9-N_3": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluies éparses / Rares averses (non précisé)
        "J_W2_14": ("rainy", RAINY_INFO_ANIMATION),  # Pluie / Averses (jour)
        "N_W2_14": ("rainy", RAINY_INFO_ANIMATION),  # Pluie / Averses (nuit)
        "J_W1_10-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluie / Averses (non précisé)
        "J_W1_11-N_0": ("rainy", RAINY_INFO_ANIMATION),  # Pluie forte
        "J_W1_12-N_0": ("rainy", RAINY_INFO_ANIMATION),  # Pluies orageuses
        "J_W1_32-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluies orageuses (jour)
        "N_W1_32-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Pluies orageuses (nuit)
        "J_W1_13-N_0": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),  # Quelques flocons (jour)
        "N_W1_13-N_0": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),  # Quelques flocons (nuit)
        "J_W1_13-N_3": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),  # Quelques flocons (non précisé)
        "J_W1_14-N_0": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),  # Pluie et neige (jour)
        "N_W1_14-N_0": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),  # Pluie et neige (nuit)
        "J_W1_14-N_3": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),  # Pluie et neige (non précisé)
        "J_W1_15-N_0": ("snowy", SNOWY_INFO_ANIMATION),  # Neige (jour)
        "N_W1_15-N_0": ("snowy", SNOWY_INFO_ANIMATION),  # Neige (nuit)
        "J_W1_22-N_3": ("snowy", SNOWY_INFO_ANIMATION),  # Neige (non précisé)
        "J_W1_17-N_0": ("snowy", SNOWY_INFO_ANIMATION),  # Neige forte
        "J_W1_23-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Risque de grêle (jour)
        "N_W1_23-N_0": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Risque de grêle (nuit)
        "J_W1_23-N_3": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),  # Risque de grêle (non précisé)
        "J_W1_24-N_0": (
            "stormy",
            STORMY_INFO_ANIMATION,
        ),  # Risque d’orages (jour)
        "N_W1_24-N_0": (
            "stormy",
            STORMY_INFO_ANIMATION,
        ),  # Risque d’orages (nuit)
        "J_W1_24-N_3": (
            "stormy",
            STORMY_INFO_ANIMATION,
        ),  # Risque d’orages (non précisé)
        "J_W1_27-N_0": ("stormy", STORMY_INFO_ANIMATION),  # Orages (jour)
        "N_W1_27-N_0": ("stormy", STORMY_INFO_ANIMATION),  # Orages (nuit)
        "J_W1_27-N_3": (
            "stormy",
            STORMY_INFO_ANIMATION,
        ),  # Orages (non précisé)
    }

    # Dictionary built from css rules
    WEATHER_CLASSES_ALIASES = {
        "J_W1_0-N_4": "J_W1_0-N_1",
        "J_W1_0-N_6": "J_W1_0-N_1",
        "J_W1_1-N": "J_W1_1-N_0",
        "J_W1_2-N_3": "J_W1_1-N_3",
        "J_W1_2-N": "J_W1_1-N_0",
        "J_W1_3-N": "J_W1_3-N_0",
        "J_W1_4-N": "J_W1_6-N_0",
        "J_W1_5-N": "J_W1_6-N_0",
        "J_W1_6-N": "J_W1_6-N_0",
        "J_W1_7-N": "J_W1_7-N_0",
        "J_W1_8-N": "J_W1_8-N_0",
        "J_W1_9-N": "J_W1_9-N_0",
        "J_W1_10-N": "J_W1_10-N_0",
        "J_W1_11-N": "J_W1_11-N_0",
        "J_W1_12": "J_W1_12-N_0",
        "J_W1_13": "J_W1_13-N_0",
        "J_W1_14": "J_W1_14-N_0",
        "J_W1_15-N_3": "J_W1_22-N_3",
        "J_W1_15": "J_W1_15-N_0",
        "J_W1_17-N": "J_W1_17-N_0",
        "J_W1_18-N_3": "J_W1_9-N_3",
        "J_W1_18-N": "J_W1_9-N_0",
        "J_W1_19-N": "J_W1_10-N_0",
        #       "J_W1_19-N": "J_W2_14",
        "J_W1_20-N_3": "J_W1_14-N_3",
        "J_W1_20": "J_W1_14-N_0",
        "J_W1_21-N_3": "J_W1_13-N_3",
        "J_W1_21": "J_W1_13-N_0",
        "J_W1_22": "J_W1_15-N_0",
        "J_W1_23-N": "J_W1_23-N_0",
        "J_W1_24-N": "J_W1_24-N_0",
        "J_W1_25-N_3": "J_W1_27-N_3",
        "J_W1_25-N": "J_W1_27-N_0",
        "J_W1_26-N_3": "J_W1_24-N_3",
        "J_W1_26-N": "J_W1_24-N_0",
        "J_W1_27-N": "J_W1_27-N_0",
        "J_W1_28-N_3": "J_W1_23-N_3",
        "J_W1_28-N": "J_W1_23-N_0",
        "J_W1_29-N_3": "J_W1_23-N_3",
        "J_W1_29-N": "J_W1_23-N_0",
        "J_W1_30-N_3": "J_W1_9-N_3",
        "J_W1_30-N": "J_W1_9-N_0",
        "J_W1_31-N_3": "J_W1_24-N_3",
        "J_W1_31-N": "J_W1_24-N_0",
        "J_W1_32-N_3": "J_W1_12-N_0",
        "J_W1_32": "J_W1_32-N_0",
        "J_W1_33-N_3": "J_W1_1-N_3",
        "J_W1_33-N": "J_W1_1-N_0",
        "J_W2_2": "J_W1_0-N_1",
        "J_W2_3": "J_W1_0-N_3",
        "J_W2_4": "J_W1_3-N_0",
        "J_W2_5": "J_W1_6-N_0",
        "J_W2_6": "J_W1_9-N_0",
        "J_W2_7": "J_W1_13-N_0",
        "J_W2_8": "J_W2_14",
        "J_W2_9": "J_W1_11-N_0",
        "J_W2_10": "J_W1_15-N_0",
        "J_W2_11": "J_W1_17-N_0",
        "J_W2_12": "J_W1_9-N_0",
        "J_W2_13": "J_W1_13-N_0",
        "J_W2_15": "J_W1_15-N_0",
        "J_W2_16": "J_W1_32-N_0",
        "J_W2_17": "J_W1_12-N_0",
        "J_W2_18": "J_W1_24-N_0",
        "J_W2_19": "J_W1_15-N_0",
        "N_W1_0-N_2": "N_W1_0-N_1",
        "N_W1_0-N_3": "J_W1_0-N_3",
        "N_W1_0-N_4": "N_W1_0-N_1",
        "N_W1_0-N_6": "N_W1_0-N_1",
        "N_W1_0-N_7": "N_W1_0-N_0",
        "N_W1_1-N_3": "J_W1_1-N_3",
        "N_W1_1-N": "N_W1_1-N_0",
        "N_W1_2-N_3": "J_W1_1-N_3",
        "N_W1_2-N": "N_W1_1-N_0",
        "N_W1_4-N": "J_W1_6-N_0",
        "N_W1_5-N": "J_W1_6-N_0",
        "N_W1_6-N": "J_W1_6-N_0",
        "N_W1_7-N": "J_W1_7-N_0",
        "N_W1_8-N_3": "J_W1_8-N_3",
        "N_W1_8-N": "N_W1_8-N_0",
        "N_W1_9-N_3": "J_W1_9-N_3",
        "N_W1_9-N": "N_W1_9-N_0",
        "N_W1_10-N": "J_W1_10-N_0",
        "N_W1_11-N": "J_W1_11-N_0",
        "N_W1_12": "J_W1_12-N_0",
        "N_W1_13-N_3": "J_W1_13-N_3",
        "N_W1_13": "N_W1_13-N_0",
        "N_W1_14-N_3": "J_W1_14-N_3",
        "N_W1_14": "N_W1_14-N_0",
        "N_W1_15-N_3": "J_W1_22-N_3",
        "N_W1_15": "N_W1_15-N_0",
        "N_W1_17-N": "J_W1_17-N_0",
        "N_W1_18-N_3": "J_W1_9-N_3",
        "N_W1_18-N": "N_W1_9-N_0",
        "N_W1_19-N": "J_W1_10-N_0",
        #       "N_W1_19-N": "N_W2_14",
        "N_W1_20-N_3": "J_W1_14-N_3",
        "N_W1_20": "N_W1_14-N_0",
        "N_W1_21-N_3": "J_W1_13-N_3",
        "N_W1_21": "N_W1_13-N_0",
        "N_W1_22-N_3": "J_W1_22-N_3",
        "N_W1_22": "N_W1_15-N_0",
        "N_W1_23-N_3": "J_W1_23-N_3",
        "N_W1_23-N": "N_W1_23-N_0",
        "N_W1_24-N_3": "J_W1_24-N_3",
        "N_W1_24-N": "N_W1_24-N_0",
        "N_W1_25-N_3": "J_W1_27-N_3",
        "N_W1_25-N": "N_W1_27-N_0",
        "N_W1_26-N_3": "J_W1_24-N_3",
        "N_W1_26-N": "N_W1_24-N_0",
        "N_W1_27-N_3": "J_W1_27-N_3",
        "N_W1_27-N": "N_W1_27-N_0",
        "N_W1_28-N_3": "J_W1_23-N_3",
        "N_W1_28-N": "N_W1_23-N_0",
        "N_W1_29-N_3": "J_W1_23-N_3",
        "N_W1_29-N": "N_W1_23-N_0",
        "N_W1_30-N_3": "J_W1_9-N_3",
        "N_W1_30-N": "N_W1_9-N_0",
        "N_W1_31-N_3": "J_W1_24-N_3",
        "N_W1_31-N": "N_W1_24-N_0",
        "N_W1_32-N_3": "J_W1_12-N_0",
        "N_W1_32": "N_W1_32-N_0",
        "N_W1_33-N_3": "J_W1_1-N_3",
        "N_W1_33-N": "N_W1_1-N_0",
        "N_W2_1": "N_W1_0-N_0",
        "N_W2_2": "N_W1_0-N_1",
        "N_W2_3": "J_W1_0-N_3",
        "N_W2_4": "J_W1_3-N_0",
        "N_W2_5": "J_W1_6-N_0",
        "N_W2_6": "N_W1_9-N_0",
        "N_W2_7": "N_W1_13-N_0",
        "N_W2_8": "N_W2_14",
        "N_W2_9": "J_W1_11-N_0",
        "N_W2_10": "N_W1_15-N_0",
        "N_W2_11": "J_W1_17-N_0",
        "N_W2_12": "N_W1_9-N_0",
        "N_W2_13": "N_W1_13-N_0",
        "N_W2_15": "N_W1_15-N_0",
        "N_W2_16": "N_W1_32-N_0",
        "N_W2_17": "J_W1_12-N_0",
        "N_W2_18": "N_W1_24-N_0",
        "N_W2_19": "N_W1_15-N_0",
        "W1_3-N": "J_W1_3-N_0",
        "W1_7-N": "J_W1_7-N_0",
        "W1_10-N": "J_W1_10-N_0",
        "W1_12": "J_W1_12-N_0",
        "W1_16": "J_W1_22-N_3",
    }

    async def get_config(self):
        from . import models

        config = await models.Config.load_async()
        return (
            config.next_performance_date,
            config.next_performance_type,
            (config.location, config.unit, config.weather_animation_type),
        )

    async def update_next(self, next_date, next_args):
        from . import models

        config = await models.Config.load_async()
        config.next_performance_date = next_date
        config.next_performance_type = next_args
        await config.save_async()

    def next_info_update(self, config):
        if config is None:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        next_5mn = now + datetime.timedelta(seconds=300)
        return next_5mn

    async def fetch_info_data(self, config_t):
        from . import models

        location, unit, weather_animation_type = config_t
        if location is None:
            return None
        client = await sync_to_async(meteofranceClient)(location, True)
        data = client.get_data()
        logging.debug(data)

        # saving real city in the location
        config = await models.Config.load_async()
        config.location = data["printName"]
        await config.save_async()

        if ("next_rain") in data:
            if data["next_rain"] == "No rain":
                next_rain = None
            else:
                next_rain = self.RAINY_INFO_ANIMATION
        else:
            next_rain = None

        current_weather_class = self.normalize_weather_class(
            data["weather_class"]
        )
        today_forecast_weather_class = self.normalize_weather_class(
            data["forecast"][0]["weather_class"]
        )

        today_forecast_max_temp = data["forecast"][0]["max_temp"]
        tomorrow_forecast_weather_class = self.normalize_weather_class(
            data["forecast"][1]["weather_class"]
        )
        tomorrow_forecast_max_temp = data["forecast"][1]["max_temp"]
        return {
            "weather_animation_type": weather_animation_type,
            "current_weather_class": current_weather_class,
            "next_rain": next_rain,
            "today_forecast_weather_class": today_forecast_weather_class,
            "today_forecast_max_temp": today_forecast_max_temp,
            "tomorrow_forecast_weather_class": tomorrow_forecast_weather_class,
            "tomorrow_forecast_max_temp": tomorrow_forecast_max_temp,
        }

    def normalize_weather_class(self, weather_class):
        if weather_class in NabWeatherd.WEATHER_CLASSES:
            return weather_class
        if weather_class in NabWeatherd.WEATHER_CLASSES_ALIASES:
            return NabWeatherd.WEATHER_CLASSES_ALIASES[weather_class]
        return self.normalize_weather_class(weather_class[:-1])

    def get_animation(self, info_data):

        if (info_data is None):
            return
        
        logging.debug(f"get_animation :{info_data['weather_animation_type']}")

        if (info_data['weather_animation_type'] == 'both') or \
             (info_data['weather_animation_type'] == 'rain'):
            if info_data["next_rain"] is not None:
                packet = (
                    '{"type":"info",'
                    '"info_id":"nabweatherd_rain",'
                    '"animation":' + self.RAIN_ONE_HOUR+ '}\r\n'
                )
            else:
                packet = (
                    '{"type":"info",'
                    '"info_id":"nabweatherd_rain"}\r\n'
                )
            self.writer.write(packet.encode("utf8"))
    
        if (info_data['weather_animation_type'] == 'both') or \
            ((info_data['weather_animation_type'] == 'weather')):
            
            # si weather on supprime l'animation rain
            if (info_data['weather_animation_type'] == 'weather'):
                packet = (
                        '{"type":"info",'
                        '"info_id":"nabweatherd_rain"}\r\n'
                    )
                self.writer.write(packet.encode("utf8"))
        
            (weather_class, info_animation) = NabWeatherd.WEATHER_CLASSES[info_data["today_forecast_weather_class"]]
            logging.debug(f"get_animation : return classic rain")     

            return info_animation        
        
        else:
            logging.debug(f"get_animation : return none")          
            return None

    async def perform_additional(self, expiration, type, info_data, config_t):
        location, unit, weather_animation_type = config_t
        if location is None:
            logging.debug(f"location is None (service is unconfigured)")
            packet = (
                '{"type":"message",'
                '"signature":{"audio":['
                '"nabweatherd/signature.mp3"]},'
                '"body":[{"audio":["nabweatherd/no-location-error.mp3"]}],'
                '"expiration":"' + expiration.isoformat() + '"}\r\n'
            )
            self.writer.write(packet.encode("utf8"))
        else:
            if type == "today":
                (weather_class, info_animation) = NabWeatherd.WEATHER_CLASSES[
                    info_data["today_forecast_weather_class"]
                ]
                max_temp = info_data["today_forecast_max_temp"]
            if type == "tomorrow":
                (weather_class, info_animation) = NabWeatherd.WEATHER_CLASSES[
                    info_data["tomorrow_forecast_weather_class"]
                ]
                max_temp = info_data["tomorrow_forecast_max_temp"]
            if type == "today" or type == "tomorrow":
                unit_sound_file = "degree.mp3"
                if unit == NabWeatherd.UNIT_FARENHEIT:
                    max_temp = round(max_temp * 1.8 + 32.0)
                    unit_sound_file = "degree_f.mp3"

                packet = (
                    '{"type":"message",'
                    '"signature":{"audio":["nabweatherd/signature.mp3"]},'
                    '"body":[{"audio":["nabweatherd/' + type + '.mp3",'
                    '"nabweatherd/sky/' + weather_class + '.mp3",'
                    '"nabweatherd/temp/' + str(max_temp) + '.mp3",'
                    '"nabweatherd/' + unit_sound_file + '"]}],'
                    '"expiration":"' + expiration.isoformat() + '"}\r\n'
                )
                self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

            
    async def _do_perform(self, type):
        next_date, next_args, config_t = await self.get_config()
        now = datetime.datetime.now(datetime.timezone.utc)
        expiration = now + datetime.timedelta(minutes=1)
        await self.perform(expiration, type, config_t)

    async def process_nabd_packet(self, packet):
        if (
            packet["type"] == "asr_event"
            and packet["nlu"]["intent"] == "nabweatherd/forecast"
        ):
            # todo : detect today/tomorrow
            await self._do_perform("today")
        elif (
            packet["type"] == "rfid_event"
            and packet["app"] == "nabweatherd"
            and packet["event"] == "detected"
        ):
            if "data" in packet:
                type = rfid_data.unserialize(packet["data"].encode("utf8"))
            else:
                type = "today"
            await self._do_perform(type)


if __name__ == "__main__":
    NabWeatherd.main(sys.argv[1:])
