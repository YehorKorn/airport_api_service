from django.urls import path, include
from rest_framework import routers

from airport.views import (
    AirplaneTypeViewSet,
    AirplaneViewSet,
    AirportViewSet,
    FlightViewSet,
    RouteViewSet,
    CrewViewSet,
    OrderViewSet,
)

router = routers.DefaultRouter()
router.register("flights", FlightViewSet)
router.register("crews", CrewViewSet)
router.register("airplanes", AirplaneViewSet)
router.register("airplane_types", AirplaneTypeViewSet)

urlpatterns = [path("", include(router.urls))]

app_name = "airport"
