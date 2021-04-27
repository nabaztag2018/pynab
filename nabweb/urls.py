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
from django.urls import path, include
from .views import NabWebView, NabWebServicesView, NabWebSytemInfoView
from .views import NabWebRfidView, NabWebRfidReadView, NabWebRfidWriteView
from .views import NabWebUpgradeView, NabWebUpgradeStatusView
from .views import NabWebUpgradeNowView, NabWebUpgradeCheckNowView
from .views import NabWebUpgradeRepositoryInfoView, NabWebHardwareTestView
from .views import NabWebShutdownView

urlpatterns = [
    path("", NabWebView.as_view()),
    path("services/", NabWebServicesView.as_view()),
    path("rfid/", NabWebRfidView.as_view()),
    path("rfid/read", NabWebRfidReadView.as_view(), name="rfid.read"),
    path("rfid/write", NabWebRfidWriteView.as_view(), name="rfid.write"),
    path(
        "system-info/test/<test>",
        NabWebHardwareTestView.as_view(),
        name="nabweb.test",
    ),
    path("system-info/", NabWebSytemInfoView.as_view()),
    path(
        "system-info/shutdown/<mode>",
        NabWebShutdownView.as_view(),
        name="nabweb.shutdown",
    ),
    path("upgrade/", NabWebUpgradeView.as_view()),
    path(
        "upgrade/info/<repository>",
        NabWebUpgradeRepositoryInfoView.as_view(),
        name="nabweb.upgrade.info",
    ),
    path(
        "upgrade/status",
        NabWebUpgradeStatusView.as_view(),
        name="nabweb.upgrade.status",
    ),
    path(
        "upgrade/now",
        NabWebUpgradeNowView.as_view(),
        name="nabweb.upgrade.now",
    ),
    path(
        "upgrade/checknow",
        NabWebUpgradeCheckNowView.as_view(),
        name="nabweb.upgrade.checknow",
    ),
]

# Service URLs added automatically
for config in apps.get_app_configs():
    if hasattr(config.module, "NABAZTAG_SERVICE_PRIORITY"):
        urlpatterns.append(
            path(config.name + "/", include(config.name + ".urls"))
        )
