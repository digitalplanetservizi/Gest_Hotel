import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from hotel import models as m
from hotel import selectors
from hotel import services as d
from hotel.pdf_reports import room_label


class ReportFlowTests(TestCase):
    def setUp(self):
        m.HotelSettings.objects.create(pk=1)
        self.user = m.User.objects.create_user(
            username="report@example.it",
            email="report@example.it",
            password="Test-report-password2026",
            first_name="Reception",
            role="admin",
            last_name="Uno",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.shift = self.post("cash/shifts/", {"opening_cash": "100.00"})
        room = self.post("rooms/", {"number": "A1", "room_type": "double", "capacity": 2})
        stay = self.post(
            "stays/",
            {
                "room": room["id"],
                "guest_name": "Ospite",
                "guest_count": 1,
                "board": "RO",
                "arrival": "2026-10-20T14:00:00+02:00",
                "departure": "2026-10-22T10:00:00+02:00",
                "nightly_rate": "50.00",
            },
        )
        self.post(
            f"stays/{stay['id']}/charges/",
            {
                "description": "Colazioni",
                "quantity": "2",
                "unit_price": "10.00",
                "price_item": None,
            },
        )
        self.payment = self.post(
            "payments/",
            {
                "stay": stay["id"],
                "amount": "120.00",
                "method": "cash",
                "scope": "all",
            },
            key="report-flow-payment",
        )
        self.refund = self.post(
            f"payments/{self.payment['id']}/refund/",
            {
                "amount": "20.00",
                "reason": "Rettifica",
                "note": "Rimborso extra",
            },
            key="report-flow-refund",
        )
        reason = self.post("cash/reasons/", {"name": "Forniture", "direction": "out"})
        self.expense = self.post(
            "cash/movements/",
            {
                "amount": "5.00",
                "method": "cash",
                "reason": reason["id"],
                "description": "=formula non eseguibile",
            },
        )
        # One shift crosses local midnight: allocations retain their immutable
        # charge kind while money movements are grouped by actual cash date.
        m.CashMovement.objects.filter(payment_id=self.payment["id"]).update(
            created_at=datetime(2026, 10, 20, 21, 30, tzinfo=UTC)
        )
        m.CashMovement.objects.filter(payment_id=self.refund["id"]).update(
            created_at=datetime(2026, 10, 20, 22, 30, tzinfo=UTC)
        )
        m.CashMovement.objects.filter(pk=self.expense["id"]).update(
            created_at=datetime(2026, 10, 21, 1, tzinfo=UTC)
        )

    def post(self, path, payload, key=None):
        headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
        response = self.client.post(f"/api/v1/{path}", payload, format="json", **headers)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_payment_refund_report_split_by_operator_shift_local_day(self):
        response = self.client.get("/api/v1/reports/?start=2026-10-20&end=2026-10-22")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data["income"]), Decimal("120.00"))
        self.assertEqual(Decimal(response.data["expenses"]), Decimal("25.00"))
        self.assertEqual(Decimal(response.data["balance"]), Decimal("95.00"))
        self.assertEqual(Decimal(response.data["outstanding"]), Decimal("20.00"))
        sections = {section["key"]: section for section in response.data["sections"]}
        self.assertEqual(Decimal(sections["rooms"]["total"]), Decimal("100.00"))
        self.assertEqual(Decimal(sections["extras"]["total"]), Decimal("20.00"))
        self.assertEqual(Decimal(sections["tips"]["total"]), Decimal("0.00"))
        self.assertEqual(Decimal(sections["expenses"]["total"]), Decimal("25.00"))
        self.assertEqual(sections["rooms"]["rows"][0]["account"], "Camera A1")
        rows = response.data["by_operator_shift"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0],
            {
                "operator_id": self.user.pk,
                "operator_name": "Reception Uno",
                "shift": self.shift["id"],
                "day": "2026-10-20",
                "movements_count": 1,
                "room_income": "100.00",
                "extra_income": "20.00",
                "income": "120.00",
                "expenses": "0.00",
                "balance": "120.00",
            },
        )
        self.assertEqual(rows[1]["day"], "2026-10-21")
        self.assertEqual(rows[1]["movements_count"], 2)
        self.assertEqual(rows[1]["income"], "0.00")
        self.assertEqual(rows[1]["expenses"], "25.00")
        self.assertEqual(rows[1]["room_income"], "0.00")
        self.assertEqual(rows[1]["extra_income"], "0.00")

    def test_shift_direction_filters_apply_to_json_and_csv(self):
        query = f"start=2026-10-20&end=2026-10-22&shift={self.shift['id']}&direction=out"
        response = self.client.get(f"/api/v1/reports/?{query}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data["income"]), Decimal("0.00"))
        self.assertEqual(Decimal(response.data["expenses"]), Decimal("25.00"))
        self.assertEqual(response.data["movements_count"], 2)
        self.assertEqual(len(response.data["by_operator_shift"]), 1)
        cash = self.client.get(f"/api/v1/cash/movements/?{query}")
        self.assertEqual(cash.status_code, 200)
        self.assertEqual(cash.data["count"], 2)
        export = self.client.get(f"/api/v1/reports/export/?{query}")
        self.assertEqual(export.status_code, 200)
        rows = list(csv.reader(io.StringIO(export.content.decode("utf-8-sig")), delimiter=";"))
        self.assertIn("SPESE E RIMBORSI", [row[0] for row in rows if row])
        expense_rows = [row for row in rows if len(row) == 9 and row[2] == "Uscita"]
        self.assertEqual(len(expense_rows), 2)
        self.assertIn("'=formula non eseguibile", [row[6] for row in expense_rows])
        empty = self.client.get("/api/v1/reports/?start=2026-10-20&end=2026-10-22&shift=999999")
        self.assertEqual(empty.data["by_operator_shift"], [])
        for invalid in ("direction=other", "shift=abc", "shift=-1"):
            self.assertEqual(self.client.get(f"/api/v1/reports/?{invalid}").status_code, 400)

    def test_pdf_report_uses_filters_and_includes_the_paid_room(self):
        movement = m.CashMovement.objects.select_related("payment__stay__room").get(payment_id=self.payment["id"])
        self.assertEqual(room_label(movement), "Camera A1")
        response = self.client.get("/api/v1/reports/pdf/?start=2026-10-20&end=2026-10-22")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("rapporto-cassa.pdf", response["Content-Disposition"])
        self.assertIn("inline", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 2_000)

    def test_grouping_query_count_is_constant_with_multiple_payment_allocations(self):
        qs = selectors.filtered_movements({"start": "2026-10-20", "end": "2026-10-22"})
        # Movement + payment/author, then all allocation rows + charge in one
        # query. More receipts/lines do not add per-row database round trips.
        with self.assertNumQueries(2):
            rows = selectors.operator_shift_totals(qs, ZoneInfo("Europe/Rome"))
        self.assertEqual(len(rows), 2)

    def test_grouping_uses_transaction_author_in_shared_shift(self):
        other = m.User.objects.create_user(
            username="second@example.it", email="second@example.it", password="Test-report-password2026"
        )
        m.CashMovement.objects.filter(pk=self.expense["id"]).update(created_by=other)
        response = self.client.get("/api/v1/reports/?start=2026-10-20&end=2026-10-22")
        other_rows = [row for row in response.data["by_operator_shift"] if row["operator_id"] == other.pk]
        self.assertEqual(len(other_rows), 1)
        self.assertEqual(other_rows[0]["shift"], self.shift["id"])
        self.assertEqual(other_rows[0]["expenses"], "5.00")
        self.assertEqual(other_rows[0]["operator_name"], other.email)


class EmailUniquenessTests(TestCase):
    def test_normalization_and_database_case_insensitive_constraint(self):
        user = m.User.objects.create_user(
            username="ONE@example.it", email="ONE@Example.IT", password="Testing-email2026"
        )
        self.assertEqual(user.email, "one@example.it")
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.User.objects.create_user(
                username="different", email="One@EXAMPLE.it", password="Testing-email2026"
            )

    def test_api_rejects_duplicate_case_insensitive_email(self):
        user = m.User.objects.create_user(
            username="one@example.it", email="one@example.it", password="Testing-email2026", role="admin"
        )
        client = APIClient()
        client.force_authenticate(user)
        response = client.post(
            "/api/v1/users/",
            {
                "email": "ONE@EXAMPLE.IT",
                "password": "Another-safe-password2026",
                "role": "operator",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)


class SelectorAggregateTests(TestCase):
    def setUp(self):
        m.HotelSettings.objects.create(pk=1)
        self.user = m.User.objects.create_user(
            username="aggregate@example.it", email="aggregate@example.it", password="Testing-aggregate2026"
        )
        self.room = m.Room.objects.create(number="1", room_type="double", capacity=2)

    def stay(self, room=None):
        return d.save_stay(
            {
                "room": room or self.room,
                "guest_name": "Ospite",
                "guest_count": 1,
                "board": "RO",
                "arrival": datetime(2026, 10, 24, 14, tzinfo=ZoneInfo("Europe/Rome")),
                "departure": datetime(2026, 10, 27, 10, tzinfo=ZoneInfo("Europe/Rome")),
                "nightly_rate": Decimal("50.00"),
            },
            self.user,
        )

    def test_full_occupancy_on_twenty_five_hour_dst_day_is_one_hundred_percent(self):
        self.stay()
        start, end = selectors.period({"start": "2026-10-25", "end": "2026-10-26"})
        self.assertEqual((end.astimezone(UTC) - start.astimezone(UTC)).total_seconds(), 25 * 3600)
        report = selectors.report({"start": "2026-10-25", "end": "2026-10-26"})
        self.assertEqual(report["occupancy"], "100.00")

    def test_outstanding_aggregate_matches_statements_after_refunds_and_voids_in_two_queries(self):
        first = self.stay()
        room2 = m.Room.objects.create(number="2", room_type="double", capacity=2)
        second = self.stay(room2)
        extra = d.add_charge(
            first,
            {
                "description": "Bar",
                "quantity": Decimal("1"),
                "unit_price": Decimal("20.00"),
            },
            self.user,
        )
        payment = d.record_payment(
            {
                "stay": first,
                "amount": Decimal("70.00"),
                "method": "card",
                "scope": "all",
            },
            self.user,
            "aggregate-receipt",
        )
        d.refund_payment(
            payment, {"amount": Decimal("20.00"), "reason": "Rettifica"}, self.user, "aggregate-refund"
        )
        d.void_charge(extra, "Extra annullato", self.user)
        d.void_charge(second.charges.first(), "Notte annullata", self.user)
        expected = sum(
            (d.statement(stay.charges.all())["balance"] for stay in (first, second)), Decimal("0.00")
        )
        with self.assertNumQueries(2):
            outstanding = selectors.outstanding_balance()
        self.assertEqual(outstanding, expected)
        self.assertEqual(outstanding, Decimal("200.00"))

    def test_dashboard_operational_lists_use_hotel_local_day_at_utc_midnight_boundary(self):
        zone = ZoneInfo("Europe/Rome")
        arrival = d.save_stay(
            {
                "room": self.room,
                "guest_name": "In arrivo",
                "guest_count": 1,
                "board": "RO",
                "arrival": datetime(2026, 11, 1, 0, 30, tzinfo=zone),
                "departure": datetime(2026, 11, 2, 10, tzinfo=zone),
                "nightly_rate": Decimal("50"),
            },
            self.user,
        )
        room2 = m.Room.objects.create(number="2", room_type="double", capacity=2)
        departure = d.save_stay(
            {
                "room": room2,
                "guest_name": "In partenza",
                "guest_count": 1,
                "board": "RO",
                "arrival": datetime(2026, 10, 30, 14, tzinfo=zone),
                "departure": datetime(2026, 11, 1, 0, 40, tzinfo=zone),
                "nightly_rate": Decimal("50"),
            },
            self.user,
        )
        d.stay_action(departure.pk, "check-in", {}, self.user)
        room3 = m.Room.objects.create(number="3", room_type="double", capacity=2)
        completed_departure = d.save_stay(
            {
                "room": room3,
                "guest_name": "Partenza conclusa",
                "guest_count": 1,
                "board": "RO",
                "arrival": datetime(2026, 10, 30, 14, tzinfo=zone),
                "departure": datetime(2026, 11, 1, 0, 40, tzinfo=zone),
                "nightly_rate": Decimal("50"),
            },
            self.user,
        )
        d.stay_action(completed_departure.pk, "check-in", {}, self.user)
        d.record_payment(
            {"stay": completed_departure, "amount": Decimal("100.00"), "method": "card", "scope": "all"},
            self.user,
            "completed-departure-payment",
        )
        d.stay_action(completed_departure.pk, "check-out", {}, self.user)
        room4 = m.Room.objects.create(number="4", room_type="double", capacity=2)
        reserved_departure = d.save_stay(
            {
                "room": room4,
                "guest_name": "Partenza prevista",
                "guest_count": 1,
                "board": "RO",
                "arrival": datetime(2026, 10, 30, 14, tzinfo=zone),
                "departure": datetime(2026, 11, 1, 0, 40, tzinfo=zone),
                "nightly_rate": Decimal("50"),
            },
            self.user,
        )
        client = APIClient()
        client.force_authenticate(self.user)
        with patch("hotel.selectors.timezone.now", return_value=datetime(2026, 10, 31, 23, 35, tzinfo=UTC)):
            response = client.get("/api/v1/dashboard/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row["id"] for row in response.data["arrivals"]], [arrival.pk])
        self.assertEqual(
            [row["id"] for row in response.data["departures"]],
            [departure.pk, completed_departure.pk, reserved_departure.pk],
        )
        self.assertEqual(response.data["departures_today"], 3)
