import re
from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.apps import apps
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from hotel import models as m
from hotel import services as domain
from hotel.extra_statements import group_extra_days, render_extra_statement

ROME = ZoneInfo("Europe/Rome")


class ExtraStatementTests(TestCase):
    def setUp(self):
        self.hotel = m.HotelSettings.objects.create(pk=1, name="Hotel Tempio", timezone="Europe/Rome")
        self.user = m.User.objects.create_user(
            username="extras@example.it", email="extras@example.it", password="Extras-test-password-2026"
        )
        self.room = m.Room.objects.create(number="203", room_type="double", capacity=2)
        self.stay = self.make_stay(self.room)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def make_stay(self, room, group=None):
        return domain.save_stay(
            {
                "room": room,
                "guest_name": "Ospite & Referente",
                "guest_count": 1,
                "board": "RO",
                "arrival": datetime(2026, 10, 20, 14, tzinfo=ROME),
                "departure": datetime(2026, 10, 28, 10, tzinfo=ROME),
                "nightly_rate": Decimal("100.00"),
                "group": group,
            },
            self.user,
        )

    def extra(self, when, amount="2.50", stay=None, description="Caffè"):
        return domain.add_charge(
            stay or self.stay,
            {
                "description": description,
                "quantity": Decimal("1"),
                "unit_price": Decimal(amount),
                "consumed_at": when,
            },
            self.user,
        )

    def test_consumption_time_can_differ_from_immutable_registration_time(self):
        when = "2026-10-21T00:15:00+02:00"
        response = self.client.post(
            f"/api/v1/stays/{self.stay.pk}/charges/",
            {"description": "Caffè", "quantity": "2", "unit_price": "2.00", "consumed_at": when},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        charge = m.Charge.objects.get(pk=response.data["id"])
        self.assertEqual(charge.consumed_at, datetime.fromisoformat(when))
        self.assertEqual(charge.amount, Decimal("4.00"))
        self.assertNotEqual(charge.consumed_at, charge.created_at)
        result = self.client.get(f"/api/v1/stays/{self.stay.pk}/charges/")
        extra = next(row for row in result.data["results"] if row["kind"] == "extra")
        self.assertEqual(datetime.fromisoformat(extra["consumed_at"]), charge.consumed_at)
        for value in ("not-a-timestamp", None):
            rejected = self.client.post(
                f"/api/v1/stays/{self.stay.pk}/charges/",
                {"description": "Errato", "unit_price": "1.00", "consumed_at": value},
                format="json",
            )
            self.assertEqual(rejected.status_code, 400)
        self.assertEqual(self.stay.charges.filter(kind="extra").count(), 1)

    def test_missing_consumption_time_defaults_to_server_now_without_affecting_room_charges(self):
        now = datetime(2026, 10, 21, 10, 15, tzinfo=UTC)
        with patch("hotel.services.timezone.now", return_value=now):
            response = self.client.post(
                f"/api/v1/stays/{self.stay.pk}/charges/",
                {"description": "Bar", "unit_price": "3.00"},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(datetime.fromisoformat(response.data["consumed_at"]), now)
        self.assertFalse(self.stay.charges.filter(kind="room", consumed_at__isnull=False).exists())

    def test_backfill_preserves_known_timestamp_and_audit_without_overwriting_manual_time(self):
        legacy = self.extra(datetime(2026, 10, 21, 9, tzinfo=UTC))
        custom = self.extra(datetime(2026, 10, 22, 8, tzinfo=UTC))
        original_created = legacy.created_at
        m.Charge.objects.filter(pk=legacy.pk).update(consumed_at=None)
        migration = import_module("hotel.migrations.0004_charge_consumed_at")
        migration.backfill_consumption_time(apps, SimpleNamespace(connection=connection))
        legacy.refresh_from_db()
        custom.refresh_from_db()
        self.assertEqual(legacy.consumed_at, original_created)
        self.assertEqual(legacy.created_at, original_created)
        self.assertEqual(custom.consumed_at, datetime(2026, 10, 22, 8, tzinfo=UTC))
        self.assertFalse(self.stay.charges.filter(kind="room", consumed_at__isnull=False).exists())

    def test_daily_groups_use_consumption_local_day_and_exclude_voids_from_totals(self):
        first = self.extra(datetime(2026, 10, 20, 21, 45, tzinfo=UTC), "2.50")  # 23:45 20/10
        second = self.extra(datetime(2026, 10, 20, 22, 15, tzinfo=UTC), "5.00")  # 00:15 21/10
        void = self.extra(datetime(2026, 10, 21, 12, tzinfo=UTC), "9.00")
        domain.void_charge(void, "Inserimento duplicato", self.user)
        groups = group_extra_days(self.stay.charges.all(), ROME)
        self.assertEqual([day.date.isoformat() for day in groups], ["2026-10-20", "2026-10-21"])
        self.assertEqual([day.total for day in groups], [Decimal("2.50"), Decimal("5.00")])
        self.assertEqual([row.pk for row in groups[0].charges], [first.pk])
        self.assertEqual([row.pk for row in groups[1].charges], [second.pk, void.pk])
        self.assertTrue(groups[1].charges[1].voided_at)

    def test_dst_repeated_hour_is_sorted_by_instant_and_remains_in_one_local_day(self):
        first = self.extra(datetime(2026, 10, 25, 2, 45, tzinfo=ROME, fold=0), "2.00")
        second = self.extra(datetime(2026, 10, 25, 2, 15, tzinfo=ROME, fold=1), "3.00")
        groups = group_extra_days([second, first], ROME)
        self.assertEqual(len(groups), 1)
        self.assertEqual([row.pk for row in groups[0].charges], [first.pk, second.pk])
        self.assertEqual(groups[0].total, Decimal("5.00"))

    def test_pdf_download_requires_authentication_and_checks_resource_existence(self):
        anon = APIClient()
        self.assertEqual(anon.get(f"/api/v1/stays/{self.stay.pk}/extras/pdf/").status_code, 401)
        self.assertEqual(anon.get("/api/v1/groups/1/extras/pdf/").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/stays/999999/extras/pdf/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/groups/999999/extras/pdf/").status_code, 404)
        self.extra(datetime(2026, 10, 21, 9, tzinfo=UTC), description="Caffè <b> & acqua")
        response = self.client.get(f"/api/v1/stays/{self.stay.pk}/extras/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertTrue(response.content.rstrip().endswith(b"%%EOF"))

    def test_empty_and_group_exports_use_the_same_read_only_renderer(self):
        response = self.client.get(f"/api/v1/stays/{self.stay.pk}/extras/pdf/")
        self.assertEqual(response.status_code, 200)
        group = m.Group.objects.create(name="Comune Pozzuoli", reference_name="Referente unico")
        room2 = m.Room.objects.create(number="204", room_type="double", capacity=2)
        grouped = self.make_stay(room2, group)
        self.extra(datetime(2026, 10, 21, 9, tzinfo=UTC), "6.00", grouped)
        self.extra(datetime(2026, 10, 21, 9, tzinfo=UTC), "8.00")  # Another account must not leak.
        response = self.client.get(f"/api/v1/groups/{group.pk}/extras/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"extra-gruppo-{group.pk}.pdf", response["Content-Disposition"])
        with patch("hotel.api.extra_views.render_extra_statement", return_value=b"%PDF-test") as render:
            self.client.get(f"/api/v1/groups/{group.pk}/extras/pdf/")
        rows = list(render.call_args.kwargs["charges"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].stay_id, grouped.pk)
        self.assertEqual(m.CashMovement.objects.count(), 0)

    def test_many_extras_produce_a_paginated_pdf_with_long_escaped_descriptions(self):
        timestamp = datetime(2026, 10, 21, 9, tzinfo=UTC)
        m.Charge.objects.bulk_create(
            [
                m.Charge(
                    stay=self.stay,
                    kind="extra",
                    description=f"Caffè & colazione <servizio> {i} " + "descrizione " * 8,
                    quantity=1,
                    unit_price="2.00",
                    amount="2.00",
                    consumed_at=timestamp,
                    created_by=self.user,
                )
                for i in range(80)
            ]
        )
        content = render_extra_statement(
            hotel=self.hotel,
            heading="Camera 203 - Ospite",
            subtitle="Prova paginazione",
            charges=self.stay.charges.filter(kind="extra")
            .select_related("stay__room")
            .prefetch_related("stay__segments__room"),
        )
        self.assertGreater(len(re.findall(rb"/Type\s*/Page\b", content)), 1)
        groups = group_extra_days(self.stay.charges.all(), ROME)
        self.assertEqual(groups[0].total, Decimal("160.00"))
