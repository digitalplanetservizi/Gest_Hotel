from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from zoneinfo import ZoneInfo

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError

from hotel import models as m
from hotel import services as d


@skipUnless(connection.vendor == "postgresql", "Concurrent writes require PostgreSQL")
class ConcurrentCommandTests(TransactionTestCase):
    def setUp(self):
        m.HotelSettings.objects.create(pk=1)
        self.user = m.User.objects.create_user(
            username="op@test.it", email="op@test.it", password="Testing-password-2026"
        )
        self.room = m.Room.objects.create(number="1", room_type="double", capacity=2)
        self.arrival = datetime(2026, 10, 20, 14, tzinfo=ZoneInfo("Europe/Rome"))

    def data(self):
        return {
            "room": m.Room.objects.get(pk=self.room.pk),
            "guest_name": "Concurrent",
            "guest_count": 1,
            "board": "RO",
            "arrival": self.arrival,
            "departure": self.arrival + timedelta(days=1),
            "nightly_rate": Decimal("100"),
        }

    def parallel(self, callback):
        barrier = Barrier(2)

        def worker(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                callback(index)
                return "success"
            except ValidationError:
                return "rejected"
            finally:
                # Thread-local persistent connections otherwise outlive workers
                # and prevent PostgreSQL from dropping the Django test DB.
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(worker, range(2)))

    def test_concurrent_booking_only_one_succeeds(self):
        def book(index):
            d.save_stay(self.data(), m.User.objects.get(pk=self.user.pk))

        self.assertCountEqual(self.parallel(book), ["success", "rejected"])
        self.assertEqual(m.Stay.objects.count(), 1)

    def test_concurrent_payments_cannot_double_spend_balance(self):
        stay = d.save_stay(self.data(), self.user)

        def pay(index):
            d.record_payment(
                {
                    "stay": m.Stay.objects.get(pk=stay.pk),
                    "amount": Decimal("100"),
                    "method": "card",
                    "scope": "all",
                },
                m.User.objects.get(pk=self.user.pk),
                f"parallel-{index}",
            )

        self.assertCountEqual(self.parallel(pay), ["success", "rejected"])
        self.assertEqual(m.Payment.objects.count(), 1)
        self.assertEqual(d.statement(stay.charges.all())["balance"], Decimal("0"))

    def test_concurrent_retry_produces_one_payment(self):
        stay = d.save_stay(self.data(), self.user)

        def pay(index):
            d.record_payment(
                {
                    "stay": m.Stay.objects.get(pk=stay.pk),
                    "amount": Decimal("50"),
                    "method": "card",
                    "scope": "all",
                },
                m.User.objects.get(pk=self.user.pk),
                "same-parallel-key",
            )

        self.assertEqual(self.parallel(pay), ["success", "success"])
        self.assertEqual(m.Payment.objects.count(), 1)
        self.assertEqual(m.CashMovement.objects.count(), 1)
