from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from hotel import models as m


class ManualCashIncomeTests(TestCase):
    def setUp(self):
        m.HotelSettings.objects.create(pk=1)
        self.user = m.User.objects.create_user(
            username="cash-income@example.it",
            email="cash-income@example.it",
            password="Test-cash-income-password2026",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.income_reason = m.CashReason.objects.create(name="Versamento banca", direction="in")
        self.expense_reason = m.CashReason.objects.create(name="Forniture", direction="out")

    def post(self, path, payload, status=201):
        response = self.client.post(f"/api/v1/{path}", payload, format="json")
        self.assertEqual(response.status_code, status, response.data)
        return response

    def test_manual_cash_income_updates_expected_cash_and_audit_trail(self):
        shift = self.post("cash/shifts/", {"opening_cash": "100.00"}).data

        response = self.post(
            "cash/movements/income/",
            {
                "amount": "25.50",
                "method": "cash",
                "reason": self.income_reason.pk,
                "description": "Versamento contante in cassa",
            },
        )

        self.assertEqual(response.data["direction"], "in")
        self.assertEqual(Decimal(response.data["amount"]), Decimal("25.50"))
        self.assertEqual(response.data["reason"], "Versamento banca")
        self.assertEqual(response.data["shift"], shift["id"])
        self.assertEqual(response.data["payment"], None)
        movement = m.CashMovement.objects.get(pk=response.data["id"])
        self.assertEqual(movement.created_by, self.user)
        self.assertEqual(movement.shift_id, shift["id"])
        self.assertEqual(
            m.AuditEvent.objects.filter(
                actor=self.user,
                action="cash.income",
                object_type="CashMovement",
                object_id=movement.pk,
            ).count(),
            1,
        )

        current = self.client.get("/api/v1/cash/shifts/")
        self.assertEqual(current.status_code, 200, current.data)
        open_shift = next(item for item in current.data["results"] if item["id"] == shift["id"])
        self.assertEqual(Decimal(open_shift["expected_cash"]), Decimal("125.50"))

    def test_manual_income_requires_matching_active_reason_and_open_cash_shift(self):
        payload = {
            "amount": "10.00",
            "method": "cash",
            "reason": self.income_reason.pk,
            "description": "Fondo aggiuntivo",
        }
        response = self.post("cash/movements/income/", payload, status=400)
        self.assertIn("Aprire un turno", str(response.data))
        self.assertEqual(m.CashMovement.objects.count(), 0)

        self.post("cash/shifts/", {"opening_cash": "0.00"})
        invalid = self.post("cash/movements/income/", {**payload, "reason": self.expense_reason.pk}, status=400)
        self.assertIn("causale di entrata", str(invalid.data))
        self.assertEqual(m.CashMovement.objects.count(), 0)
