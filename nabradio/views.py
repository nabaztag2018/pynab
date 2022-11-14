from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from . import rfid_data


class RFIDDataView(TemplateView):
    template_name = "nabradio/rfid-data.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        uid = request.GET.get("uid", None)

        streaming_url = rfid_data.read_data_ui_for_views(uid)

        context["streaming_url"] = streaming_url
        context["radio_uid"] = uid

        return render(request, RFIDDataView.template_name, context=context)

    def post(self, request, *args, **kwargs):

        data = "DATA_IN_LOCAL_DB"
        uid = ""

        if "radio_uid" in request.POST:
            uid = request.POST["radio_uid"]
        if "streaming_url" in request.POST:
            streaming_url = request.POST["streaming_url"]
        else:
            streaming_url = uid

        rfid_data.write_data_ui_for_views(uid, streaming_url)

        return JsonResponse({"data": data})
