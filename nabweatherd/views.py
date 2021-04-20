from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse, QueryDict
from django.utils.translation import ugettext as _
from .models import Config, ScheduledMessage
from .nabweatherd import NabWeatherd
from . import rfid_data
from meteofrance.client import MeteoFranceClient
from meteofrance.client import Place
import datetime
import logging, json


class SettingsView(TemplateView):
    template_name = "nabweatherd/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["config"] = Config.load()
        context["scheduled_messages"] = ScheduledMessage.objects.all()
        celsius_available = True
        farenheit_available = True
        user_language = self.request.LANGUAGE_CODE
        if user_language == "fr-fr":
            # Sounds not available for temperatures higher than 50
            farenheit_available = False
        context["celsius_available"] = celsius_available
        context["farenheit_available"] = farenheit_available
        return context

    def get(self, request, *args, **kwargs):
        json_item = {}
        json_places = []
        context = self.get_context_data(**kwargs)
        if "q" in request.GET:
            search_location = request.GET["q"]
            client = MeteoFranceClient()
            list_places = client.search_places(search_location)
            for one_place in list_places:
                # correct bad json returned my MeteoFrance + admin is not always there
                if ('name' in one_place.raw_data):
                    one_place.raw_data['name'] = one_place.raw_data['name'].replace("'", " ")
                if ('admin' in one_place.raw_data):
                    one_place.raw_data['admin'] = one_place.raw_data['admin'].replace("'", " ")    
                json_item['value'] = str(one_place.raw_data)
                json_item['text'] = one_place.__str__()
                json_places.append(json_item)
                json_item = {}
            return JsonResponse(json_places,status=200,safe=False)
        return render(request, SettingsView.template_name, context=context)
    
    def post(self, request, *args, **kwargs):
        config = Config.load()
        if "location" in request.POST:
            location = request.POST["location"]
            logging.info(location)
            if (location != ""):
                location = location.replace("None", "''")
                location = location.replace("\'", "\"")
                
                
                location_json = json.loads(location)
                location_place = Place(location_json)
                config.location = location
                config.location_user_friendly = location_place.__str__()

        if "unit" in request.POST:
            unit = request.POST["unit"]
            config.unit = int(unit)

        if "weather_animation_type" in request.POST:
            weather_animation_type = request.POST["weather_animation_type"]
            config.weather_animation_type = weather_animation_type

        if "weather_frequency" in request.POST:
            weather_frequency = request.POST["weather_frequency"]
            config.weather_frequency = weather_frequency

        config.save()
        NabWeatherd.signal_daemon()
        context = self.get_context_data(**kwargs)
        return render(request, SettingsView.template_name, context=context)

    def put(self, request, *args, **kwargs):
        put_dict = QueryDict(request.body, encoding=request._encoding)
        config = Config.load()
        config.next_performance_date = datetime.datetime.now(
            datetime.timezone.utc
        )
        config.next_performance_type = put_dict["type"]
        config.save()
        NabWeatherd.signal_daemon()
        return JsonResponse({"status": "ok"})


class RFIDDataView(TemplateView):
    template_name = "nabweatherd/rfid-data.html"

    def get(self, request, *args, **kwargs):
        """
        Unserialize RFID application data
        """
        type = "today"
        data = request.GET.get("data", None)
        if data:
            type = rfid_data.unserialize(data.encode("utf8"))
        context = self.get_context_data(**kwargs)
        context["type"] = type
        return render(request, RFIDDataView.template_name, context=context)

    def post(self, request, *args, **kwargs):
        """
        Serialize RFID application data
        """
        type = "today"
        if "type" in request.POST:
            type = request.POST["type"]
        data = rfid_data.serialize(type)
        data = data.decode("utf8")
        return JsonResponse({"data": data})
