from django.urls import path

from .views import RFIDDataView, SettingsView

urlpatterns = [
    path("settings", SettingsView.as_view()),
    path("rfid-data", RFIDDataView.as_view()),
]
