"""nabweb URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.apps import apps
from django.contrib import admin
from django.urls import path, include
from .views import NabWebView, NabWebServicesView, NabWebSytemInfoView
from .views import NabWebUpgradeView, NabWebUpgradeStatusView, NabWebUpgradeNowView
from .views import NabWebUpgradeNowView

urlpatterns = [
    path("", NabWebView.as_view()),
    path("services/", NabWebServicesView.as_view()),
    path("system-info/", NabWebSytemInfoView.as_view()),
    path("upgrade/", NabWebUpgradeView.as_view()),
    path("upgrade/status", NabWebUpgradeStatusView.as_view(), name="nabweb.upgrade.status"),
    path("upgrade/now", NabWebUpgradeNowView.as_view(), name="nabweb.upgrade.now"),
]

# Service URLs added automatically
for config in apps.get_app_configs():
    if hasattr(config.module, 'NABAZTAG_SERVICE_PRIORITY'):
        urlpatterns.append(path(config.name + "/", include(config.name + ".urls")))
