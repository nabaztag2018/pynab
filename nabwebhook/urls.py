from django.urls import path

from .views import RFIDDataView

urlpatterns = [
    path("rfid-data", RFIDDataView.as_view()),
]
