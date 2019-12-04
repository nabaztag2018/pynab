from django.urls import path
from .views import SettingsView

urlpatterns = [path("settings", SettingsView.as_view())]
