import datetime
import tempfile
import os

from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from airport.models import (
    AirplaneType,
    Airplane,
    Flight,
    Airport,
    Route,
    Crew,
)
from airport.serializers import (
    AirplaneListSerializer,
    FlightListSerializer,
    FlightDetailSerializer,
)

AIRPLANE_URL = reverse("airport:airplane-list")
FLIGHT_URL = reverse("airport:flight-list")


def sample_airplane(**params):
    airplane_type = AirplaneType.objects.create(name="Boeing 747")

    defaults = {
        "name": "Sample airplane",
        "rows": 10,
        "seats_in_row": 6,
        "airplane_type": airplane_type,
    }
    defaults.update(params)

    return Airplane.objects.create(**defaults)


def sample_route(**params):
    source = Airport.objects.create(name="Airport 1", closest_big_city="City 1")
    destination = Airport.objects.create(name="Airport 1", closest_big_city="City 1")

    defaults = {
        "source": source,
        "destination": destination,
    }
    defaults.update(params)

    return Route.objects.create(**defaults)


def sample_flight(**params):
    airplane = sample_airplane()
    route = sample_route()

    defaults = {
        "route": route,
        "airplane": airplane,
        "departure_time": datetime.datetime.now(),
        "arrival_time": None,
    }
    defaults.update(params)
    defaults.update(
        {"arrival_time": defaults.get("departure_time") + datetime.timedelta(hours=6)}
    )

    return Flight.objects.create(**defaults)


def image_upload_url(airplane_id):
    """Return URL for recipe image upload"""
    return reverse("airport:airplane-upload-image", args=[airplane_id])


def flight_detail_url(flight_id):
    return reverse("airport:flight-detail", args=[flight_id])


class UnauthenticatedAirplaneApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(AIRPLANE_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedAirplaneApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "test@test.com",
            "testpass",
        )
        self.client.force_authenticate(self.user)

    def test_list_airplanes(self):
        sample_airplane()
        sample_airplane()

        res = self.client.get(AIRPLANE_URL)

        airplanes = Airplane.objects.order_by("id")
        serializer = AirplaneListSerializer(airplanes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_airplane_forbidden(self):
        airplane_type = AirplaneType.objects.create(name="Boeing 747")

        payload = {
            "name": "Sample airplane",
            "rows": 10,
            "seats_in_row": 6,
            "airplane_type": airplane_type,
        }
        res = self.client.post(AIRPLANE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_flights_by_date(self):
        flight1 = sample_flight(
            departure_time=datetime.datetime.strptime(
                "2023-10-21 18:00", "%Y-%m-%d %H:%M"
            )
        )
        flight2 = sample_flight(
            departure_time=datetime.datetime.strptime(
                "2023-10-21 22:00", "%Y-%m-%d %H:%M"
            )
        )
        flight3 = sample_flight(
            departure_time=datetime.datetime.strptime("2023-10-23", "%Y-%m-%d")
        )

        res = self.client.get(FLIGHT_URL, {"date": "2023-10-21"})

        serializer1 = FlightListSerializer(flight1)
        serializer2 = FlightListSerializer(flight2)
        serializer3 = FlightListSerializer(flight3)

        for data in res.data:
            data.pop("tickets_available", None)
        for serializer in [serializer1, serializer2]:
            print(res.data)
            print(serializer1.data)
            self.assertIn(serializer.data, res.data)
        self.assertNotIn(serializer3.data, res.data)

    def test_filter_flights_by_source(self):
        route2 = sample_route(
            source=Airport.objects.create(name="Airport 2", closest_big_city="City 2")
        )
        route3 = sample_route(
            source=Airport.objects.create(name="Airport 3", closest_big_city="City 3")
        )

        flight1 = sample_flight()
        flight2 = sample_flight(route=route2)
        flight3 = sample_flight(route=route3)

        res1 = self.client.get(FLIGHT_URL, {"source": flight1.route.source.name})
        res2 = self.client.get(FLIGHT_URL, {"source": "Airport 2"})

        serializer1 = FlightListSerializer(flight1)
        serializer2 = FlightListSerializer(flight2)
        serializer3 = FlightListSerializer(flight3)

        res1.data[0].pop("tickets_available", None)
        res2.data[0].pop("tickets_available", None)

        self.assertIn(serializer1.data, res1.data)
        self.assertIn(serializer2.data, res2.data)
        self.assertNotIn(serializer3.data, res1.data)
        self.assertNotIn(serializer3.data, res2.data)

    def test_filter_flights_by_destination(self):
        route2 = sample_route(
            destination=Airport.objects.create(
                name="Airport 2", closest_big_city="City 2"
            )
        )
        route3 = sample_route(
            destination=Airport.objects.create(
                name="Airport 3", closest_big_city="City 3"
            )
        )

        flight1 = sample_flight()
        flight2 = sample_flight(route=route2)
        flight3 = sample_flight(route=route3)

        res1 = self.client.get(
            FLIGHT_URL, {"destination": flight1.route.destination.name}
        )
        res2 = self.client.get(
            FLIGHT_URL, {"destination": flight2.route.destination.name}
        )

        serializer1 = FlightListSerializer(flight1)
        serializer2 = FlightListSerializer(flight2)
        serializer3 = FlightListSerializer(flight3)

        res1.data[0].pop("tickets_available", None)
        res2.data[0].pop("tickets_available", None)

        self.assertIn(serializer1.data, res1.data)
        self.assertIn(serializer2.data, res2.data)
        self.assertNotIn(serializer3.data, res1.data)
        self.assertNotIn(serializer3.data, res2.data)

    def test_retrieve_flight_detail(self):
        flight = sample_flight()
        flight.crews.add(Crew.objects.create(first_name="Jane", last_name="Smith"))

        url = flight_detail_url(flight.id)
        res = self.client.get(url)

        serializer = FlightDetailSerializer(flight)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)


class AdminMovieApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "admin@admin.com", "password", is_staff=True
        )
        self.client.force_authenticate(self.user)

    def test_create_airplane(self):
        airplane_type = AirplaneType.objects.create(name="Boeing 747")

        payload = {
            "name": "Sample airplane",
            "rows": 10,
            "seats_in_row": 6,
            "airplane_type": airplane_type.id,
        }
        res = self.client.post(AIRPLANE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        airplane = Airplane.objects.get(id=res.data["id"])
        payload.update({"airplane_type": airplane_type})
        for key in payload.keys():
            self.assertEqual(payload[key], getattr(airplane, key))


class AirplaneImageUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser(
            "admin@myproject.com", "password"
        )
        self.client.force_authenticate(self.user)
        self.airplane = sample_airplane()

    def tearDown(self):
        self.airplane.image.delete()

    def test_upload_image_to_airplane(self):
        """Test uploading an image to airplane"""
        url = image_upload_url(self.airplane.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            res = self.client.post(url, {"image": ntf}, format="multipart")
        self.airplane.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertTrue(os.path.exists(self.airplane.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading an invalid image"""
        url = image_upload_url(self.airplane.id)
        res = self.client.post(url, {"image": "not image"}, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_image_url_is_shown_on_airplane_list(self):
        url = image_upload_url(self.airplane.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            self.client.post(url, {"image": ntf}, format="multipart")
        res = self.client.get(AIRPLANE_URL)

        self.assertIn("image", res.data[0].keys())

    def test_post_image_to_airplane_list_should_not_work(self):
        url = AIRPLANE_URL
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)

            airplane_type = AirplaneType.objects.create(name="Boeing 747")

            res = self.client.post(
                url,
                {
                    "name": "Sample airplane243",
                    "rows": 10,
                    "seats_in_row": 6,
                    "airplane_type": airplane_type.id,
                    "image": ntf,
                },
                format="multipart",
            )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        airplane = Airplane.objects.get(name="Sample airplane243")
        self.assertFalse(airplane.image)
