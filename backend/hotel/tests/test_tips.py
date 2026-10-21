from datetime import UTC, datetime
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from hotel import models as m


class TipsTests(TestCase):
    def setUp(self):
        m.HotelSettings.objects.create(pk=1)
        self.user = m.User.objects.create_user(
            username="tips@example.it",
            email="tips@example.it",
            password="Test-tips-password2026",
            role="admin",
            first_name="Anna",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        room = self.post("rooms/", {"number": "T1", "room_type": "double", "capacity": 2})
        self.stay = self.post(
            "stays/",
            {
                "room": room["id"],
                "guest_name": "Ospite mance",
                "guest_count": 1,
                "board": "RO",
                "arrival": "2026-10-20T14:00:00+02:00",
                "departure": "2026-10-22T10:00:00+02:00",
                "nightly_rate": "50.00",
            },
        )

    def post(self, path, payload, key=None):
        headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
        response = self.client.post(f"/api/v1/{path}", payload, format="json", **headers)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_tip_is_separate_from_guest_balance_and_revenue(self):
        payment = self.post(
            "payments/",
            {
                "stay": self.stay["id"],
                "amount": "100.00",
                "tip_amount": "12.50",
                "method": "card",
                "scope": "all",
            },
            key="tip-payment",
        )
        self.assertEqual(Decimal(payment["amount"]), Decimal("100.00"))
        self.assertEqual(Decimal(payment["tip_amount"]), Decimal("12.50"))
        movement = m.CashMovement.objects.get(payment_id=payment["id"])
        self.assertEqual(movement.amount, Decimal("112.50"))
        self.assertEqual(movement.tip_amount, Decimal("12.50"))

        occurred_at = datetime(2026, 10, 21, 10, 30, tzinfo=UTC)
        m.Payment.objects.filter(pk=payment["id"]).update(created_at=occurred_at)
        m.CashMovement.objects.filter(pk=movement.pk).update(created_at=occurred_at)

        stay = self.client.get(f"/api/v1/stays/{self.stay['id']}/")
        self.assertEqual(Decimal(stay.data["balance"]), Decimal("0.00"))
        report = self.client.get("/api/v1/reports/?start=2026-10-21&end=2026-10-22")
        self.assertEqual(report.status_code, 200, report.data)
        self.assertEqual(Decimal(report.data["income"]), Decimal("100.00"))

        tips = self.client.get("/api/v1/tips/?period=week&date=2026-10-21")
        self.assertEqual(tips.status_code, 200, tips.data)
        self.assertEqual(tips.data["start_date"], "2026-10-19")
        self.assertEqual(tips.data["end_date"], "2026-10-25")
        self.assertEqual(Decimal(tips.data["total"]), Decimal("12.50"))
        self.assertEqual(tips.data["count"], 1)
        self.assertEqual(tips.data["payments"][0]["id"], payment["id"])

    def test_tip_period_supports_month_and_year(self):
        payment = m.Payment.objects.create(
            stay_id=self.stay["id"],
            amount=Decimal("1.00"),
            tip_amount=Decimal("3.00"),
            method="card",
            created_by=self.user,
        )
        m.Payment.objects.filter(pk=payment.pk).update(created_at=datetime(2026, 10, 21, 10, tzinfo=UTC))
        month = self.client.get("/api/v1/tips/?period=month&date=2026-10-01")
        year = self.client.get("/api/v1/tips/?period=year&date=2026-01-01")
        self.assertEqual(Decimal(month.data["total"]), Decimal("3.00"))
        self.assertEqual(Decimal(year.data["total"]), Decimal("3.00"))

    def test_cash_tip_is_included_in_the_expected_drawer_total(self):
        shift = self.post("cash/shifts/", {"opening_cash": "20.00"})
        self.post(
            "payments/",
            {
                "stay": self.stay["id"],
                "amount": "100.00",
                "tip_amount": "8.00",
                "method": "cash",
                "scope": "all",
            },
            key="cash-tip-payment",
        )
        shifts = self.client.get("/api/v1/cash/shifts/")
        current = next(item for item in shifts.data["results"] if item["id"] == shift["id"])
        self.assertEqual(Decimal(current["expected_cash"]), Decimal("128.00"))

    def test_standalone_tip_has_its_own_payment_kind_and_does_not_allocate(self):
        payment = self.post(
            "payments/",
            {
                "stay": self.stay["id"],
                "kind": "tip",
                "amount": "0.00",
                "tip_amount": "6.50",
                "method": "card",
                "scope": "all",
            },
            key="standalone-tip",
        )
        self.assertEqual(payment["kind"], "tip")
        self.assertEqual(Decimal(payment["amount"]), Decimal("0.00"))
        self.assertEqual(Decimal(payment["tip_amount"]), Decimal("6.50"))
        self.assertFalse(m.Payment.objects.get(pk=payment["id"]).allocations.exists())
        self.assertEqual(Decimal(self.client.get(f"/api/v1/stays/{self.stay['id']}/").data["balance"]), Decimal("100.00"))

        invalid = self.client.post(
            "/api/v1/payments/",
            {
                "stay": self.stay["id"],
                "kind": "tip",
                "amount": "0.01",
                "tip_amount": "6.50",
                "method": "card",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="invalid-standalone-tip",
        )
        self.assertEqual(invalid.status_code, 400)
