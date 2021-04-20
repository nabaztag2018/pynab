import sys, json
import datetime
import logging
from asgiref.sync import sync_to_async
from nabcommon.nabservice import NabInfoService
from nabcommon.nabservice import NabRecurrentService
from meteofrance.client import MeteoFranceClient
from meteofrance.client import  Place
from . import rfid_data
import requests
import random
from dateutil import tz


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
        "Eclaircies": ("sunny", SUNNY_INFO_ANIMATION),
        "Peu nuageux": ("sunny", SUNNY_INFO_ANIMATION),
        "Ensoleillé": ("sunny", SUNNY_INFO_ANIMATION),

        "Ciel voilé": ("cloudy", CLOUDY_INFO_ANIMATION),
        "Ciel voilé nuit": ("cloudy", CLOUDY_INFO_ANIMATION),
        "Très nuageux": ("cloudy", CLOUDY_INFO_ANIMATION),
        "Couvert": ("cloudy", CLOUDY_INFO_ANIMATION),

        "Rares averses": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),
        "Averses": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),
        "Pluies éparses": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),
        "Pluie": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),
        "Pluie modérée": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),
        "Pluie faible": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),
        "Pluie forte": (
            "rainy",
            RAINY_INFO_ANIMATION,
        ),
        "Risque de grêle": ("rainy", RAINY_INFO_ANIMATION),         
        "Risque de grèle": ("rainy", RAINY_INFO_ANIMATION),
        "Bruine / Pluie faible": ("rainy", RAINY_INFO_ANIMATION),
        "Bruine": ("rainy", RAINY_INFO_ANIMATION),
        "Pluies éparses / Rares averses": ("rainy", RAINY_INFO_ANIMATION),
        "Pluie / Averses": ("rainy", RAINY_INFO_ANIMATION),

        "Pluie et neige mêlées": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),
        "Neige / Averses de neige": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),
        "Neige": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),
        "Averses de neige": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),
        "Neige forte": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),
        "Quelques flocons": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),
        "Pluie et neige": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),
        "Pluie verglaçante": (
            "snowy",
            SNOWY_INFO_ANIMATION,
        ),
        "Brume ou bancs de brouillard": (
            "foggy",
            FOGGY_INFO_ANIMATION,
        ),
        "Brouillard": (
            "foggy",
            FOGGY_INFO_ANIMATION,
        ),
        "Brouillard givrant": (
            "foggy",
            FOGGY_INFO_ANIMATION,
        ),
        "Brume": (
            "foggy",
            FOGGY_INFO_ANIMATION,
        ),
        "Pluies orageuses": ("stormy", STORMY_INFO_ANIMATION),
        "Pluie orageuses": ("stormy", STORMY_INFO_ANIMATION),
        "Orages": ("stormy", STORMY_INFO_ANIMATION),
        "Averses orageuses": ("stormy", STORMY_INFO_ANIMATION),
        "Risque d'orages": ("stormy", STORMY_INFO_ANIMATION),
        
    }

    weather_bedtime_done=False
    weather_wakeup_done=False
    
    
    async def perform(self, expiration, args, config):
        
        weather_forecast="today"
        
        await NabInfoService.perform(self, expiration, args, config)
        
        location, unit, weather_animation_type, weather_frequency,next_performance_weather_vocal_date, next_performance_weather_vocal_flag  = config
        
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
        
        if next_performance_weather_vocal_flag == True and next_performance_weather_vocal_date < now:
            logging.debug(f"performing random weather forecast")
            
            if (now.hour > 18):
                weather_forecast="tomorrow"
            else:
                weather_forecast="today"    
            
            await self._do_perform_additional(config,weather_forecast)
            from . import models
            config_t = await models.Config.load_async()
            config_t.next_performance_weather_vocal_flag = False
            await config_t.save_async()
            
        if (weather_frequency == 3):
            import sys
            sys.path.append("..") # Adds higher directory to python modules path.
            from nabclockd import models

            config_clockd = await models.Config.load_async()

            bedtime = datetime.datetime(now.year, now.month, now.day, config_clockd.sleep_hour, config_clockd.sleep_min, tzinfo=tz.gettz(current_tz))
            wakeup = datetime.datetime(now.year, now.month, now.day, config_clockd.wakeup_hour, config_clockd.wakeup_min, tzinfo=tz.gettz(current_tz))

            just_before_bedtime = bedtime + datetime.timedelta(minutes=-5)
            just_after_wakeup = wakeup + datetime.timedelta(minutes=5)
            
            if now < just_after_wakeup and now > wakeup:
                weather_forecast = "today"
                if (self.weather_wakeup_done == False):
                    await self._do_perform_additional(config,weather_forecast)
                    self.weather_wakeup_done=True
                    from . import models
                    config_t = await models.Config.load_async()
                    config_t.next_performance_weather_vocal_flag = False
                    await config_t.save_async()
            else :
                self.weather_wakeup_done=False

            if now > just_before_bedtime and now < bedtime:
                weather_forecast = "tomorrow"
                if (self.weather_bedtime_done == False):
                    await self._do_perform_additional(config,weather_forecast)
                    self.weather_bedtime_done=True
                    from . import models
                    config_t = await models.Config.load_async()
                    config_t.next_performance_weather_vocal_flag = False
                    await config_t.save_async()
            else :
                self.weather_bedtime_done=False

            
        
    async def get_config(self):
        from . import models

        config = await models.Config.load_async()
        return (
            config.next_performance_date,
            config.next_performance_type,
            (config.location, config.unit, config.weather_animation_type, config.weather_frequency, config.next_performance_weather_vocal_date, config.next_performance_weather_vocal_flag),
        )

    async def update_next(self, next_date, next_args):
        from . import models
        config = await models.Config.load_async()
        config.next_performance_date = next_date
        config.next_performance_type = next_args
        
        current_tz = self.get_system_tz()
        now = datetime.datetime.now(tz=tz.gettz(current_tz))
                
        if config.next_performance_weather_vocal_flag == False:
            #every hour approx
            if (config.weather_frequency == 1):
                config.next_performance_weather_vocal_date = now + datetime.timedelta(minutes=random.randint(40,70))
                logging.debug(f"update_next / next_performance_weather_vocal={config.next_performance_weather_vocal_date}")
                config.next_performance_weather_vocal_flag = True

            elif (config.weather_frequency == 2):
                config.next_performance_weather_vocal_date = now + datetime.timedelta(minutes=random.randint(100,190))
                logging.debug(f"update_next / next_performance_weather_vocal={config.next_performance_weather_vocal_date}")
                config.next_performance_weather_vocal_flag = True

            elif (config.weather_frequency == 3):
                config.next_performance_weather_vocal_date = None
                config.next_performance_weather_vocal_flag = False
                
        await config.save_async()

    def get_system_tz(self):
        with open("/etc/timezone") as w:
            return w.read().strip()


    def next_info_update(self, config):
        if config is None:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        next_5mn = now + datetime.timedelta(seconds=300)
        return next_5mn

    async def fetch_info_data(self, config_t):
        from . import models

        location, unit, weather_animation_type, weather_frequency, next_performance_weather_vocal_date, next_performance_weather_vocal_flag = config_t
        
        if location is None:
            return None
                
        location_string_json = json.loads(location)
        logging.debug(location_string_json)
        
        place = Place(location_string_json)

        client = await sync_to_async(MeteoFranceClient)()
        my_place_weather_forecast = client.get_forecast_for_place(place)
        data = my_place_weather_forecast.daily_forecast
        logging.debug(data)

        # Rain info
        next_rain = False
        try:
            raininfo = client.get_rain(place.latitude, place.longitude)
            logging.debug(raininfo.forecast)
            for five_min_slots in raininfo.forecast:
                if (five_min_slots['rain'] != 1):
                    next_rain = True
                    break
        except requests.HTTPError as e:
            next_rain = False
            # todo : prevenir que les infos de rain ne sont pas dispo
    
        current_weather_class = self.normalize_weather_class(
            data[0]['weather12H']['desc']
        )
        today_forecast_weather_class = self.normalize_weather_class(
            data[0]['weather12H']['desc']
        )

        today_forecast_max_temp = int(data[0]['T']['max'])

        tomorrow_forecast_weather_class = self.normalize_weather_class(
            data[1]['weather12H']['desc']
        )
        tomorrow_forecast_max_temp = int(data[0]['T']['max'])
        
        
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
        logging.warning(weather_class)
        return None

    def get_animation(self, info_data):
        

        if (info_data is None):
            return
        
        logging.debug(f"get_animation :{info_data['weather_animation_type']}")
        # 
        if (info_data['weather_animation_type'] == 'weather_and_rain') or \
             (info_data['weather_animation_type'] == 'rain_only'):
             
            if info_data["next_rain"] is True:
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
    
        if (info_data['weather_animation_type'] == 'weather_and_rain') or \
            ((info_data['weather_animation_type'] == 'weather_only')):

            # si weather on supprime l'animation rain
            if (info_data['weather_animation_type'] == 'weather_only'):
                packet = (
                        '{"type":"info",'
                        '"info_id":"nabweatherd_rain"}\r\n'
                    )
                self.writer.write(packet.encode("utf8"))
        
            (weather_class, info_animation) = NabWeatherd.WEATHER_CLASSES[info_data["today_forecast_weather_class"]]
            return info_animation        
        else:
            logging.debug(f"get_animation : return none")  
            return None

    async def perform_additional(self, expiration, type, info_data, config_t):
        location, unit, weather_animation_type, weather_frequency, next_performance_weather_vocal_date, next_performance_weather_vocal_local = config_t
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

    async def _do_perform_additional(self, config, type):
        
        info_data = await self.fetch_info_data(config)

        now = datetime.datetime.now(datetime.timezone.utc)
        expiration = now + datetime.timedelta(minutes=1)
        
        await self.perform_additional(expiration, type, info_data, config)


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
