from django.urls import path

from .views import CatzOverviewView, NotifyOverviewView

urlpatterns = [
    path("catz/", CatzOverviewView.as_view(), name="catz"),
    path("notify/", NotifyOverviewView.as_view(), name="notify"),
]
