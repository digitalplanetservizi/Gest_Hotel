from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import IntegrityError, connection, transaction
from django.db.models import Sum
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from hotel import models as m
from hotel import services as d

ZONE = ZoneInfo("Europe/Rome")


class DomainTests(TestCase):
    def setUp(self):
        m.HotelSettings.objects.create(pk=1)
        self.user = m.User.objects.create_user(
            username="operator@example.com", email="operator@example.com", password="Safe-test-password-2026"
        )
        self.room = m.Room.objects.create(number="101", room_type="double", capacity=2)
        self.arrival = datetime(2026, 10, 20, 14, tzinfo=ZONE)
        self.departure = datetime(2026, 10, 22, 10, tzinfo=ZONE)

    def create_stay(self, **overrides):
        return d.save_stay(
            {
                "room": self.room,
                "guest_name": "Ospite",
                "guest_count": 2,
                "board": "BB",
                "arrival": self.arrival,
                "departure": self.departure,
                "nightly_rate": Decimal("50.00"),
                **overrides,
            },
            self.user,
        )

    def pay(self, stay, amount="30.00", **overrides):
        return d.record_payment(
            {"stay": stay, "amount": Decimal(amount), "method": "card", "scope": "all", **overrides},
            self.user,
            "payment-1",
        )

    def test_season_person_pricing_and_historical_prices(self):
        m.Rate.objects.create(
            name="A",
            room_type="double",
            board="BB",
            start_date=date(2026, 10, 20),
            end_date=date(2026, 10, 20),
            amount="20.00",
            basis="person",
        )
        rate = m.Rate.objects.create(
            name="B",
            room_type="double",
            board="BB",
            start_date=date(2026, 10, 21),
            end_date=date(2026, 10, 22),
            amount="30.00",
            basis="room",
        )
        stay = self.create_stay(nightly_rate=None)
        self.assertEqual(d.statement(stay.charges.all())["total"], Decimal("70.00"))
        rate.amount = 100
        rate.save()
        self.assertEqual(d.statement(stay.charges.all())["total"], Decimal("70.00"))

    def test_missing_rate_requires_explicit_override(self):
        with self.assertRaises(ValidationError):
            self.create_stay(nightly_rate=None)
        self.assertEqual(m.Stay.objects.count(), 0)

    def test_overlapping_booking_rejected_and_back_to_back_allowed(self):
        self.create_stay()
        with self.assertRaises(ValidationError):
            self.create_stay()
        other = self.create_stay(arrival=self.departure, departure=self.departure + timedelta(days=1))
        self.assertIsNotNone(other.pk)

    def test_day_use_and_capacity(self):
        with self.assertRaises(ValidationError):
            self.create_stay(guest_count=3)
        stay = self.create_stay(departure=self.arrival + timedelta(hours=4), is_day_use=True)
        self.assertEqual(d.statement(stay.charges.all())["total"], Decimal("50.00"))

    def test_default_group_and_explicit_individual_override(self):
        group = m.Group.objects.create(name="Gruppo", reference_name="Referente")
        self.room.default_group = group
        self.room.save()
        grouped = self.create_stay()
        self.assertEqual(grouped.group, group)
        other_room = m.Room.objects.create(number="102", room_type="double", capacity=2, default_group=group)
        individual = self.create_stay(room=other_room, group=None)
        self.assertIsNone(individual.group)

    def test_group_payment_allocates_to_multiple_rooms(self):
        group = m.Group.objects.create(name="Gruppo", reference_name="Referente")
        stay = self.create_stay(group=group)
        room2 = m.Room.objects.create(number="102", room_type="double", capacity=2)
        stay2 = self.create_stay(room=room2, group=group)
        with self.assertRaises(ValidationError):
            self.pay(stay)
        payment = d.record_payment(
            {"group": group, "amount": Decimal("150"), "method": "card", "scope": "all"},
            self.user,
            "group-pay",
        )
        self.assertEqual(
            payment.allocations.aggregate(n=Sum("amount"))["n"],
            Decimal("150"),
        )
        self.assertEqual(
            d.statement(stay.charges.all())["balance"] + d.statement(stay2.charges.all())["balance"],
            Decimal("50"),
        )

    def test_operator_must_collect_full_balance_before_checkout_but_admin_can_override(self):
        stay = self.create_stay()
        self.pay(stay)
        d.stay_action(stay.pk, "check-in", {}, self.user)
        with self.assertRaises(ValidationError):
            d.stay_action(stay.pk, "check-out", {}, self.user)
        stay.refresh_from_db()
        self.assertEqual(stay.status, "checked_in")
        admin = m.User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="Safe-admin-password-2026",
            role="admin",
        )
        d.stay_action(stay.pk, "check-out", {}, admin)
        self.assertEqual(d.statement(stay.charges.all())["balance"], Decimal("70.00"))
        self.assertEqual(m.CashMovement.objects.count(), 1)
        self.assertEqual(m.CashMovement.objects.get().amount, Decimal("30.00"))
        event = m.AuditEvent.objects.get(action="stay.check-out")
        self.assertEqual(event.actor, admin)
        self.assertEqual(event.data["outstanding_balance"], "70.00")
        self.assertTrue(event.data["debt_override"])

    def test_superadmin_can_checkout_with_outstanding_balance(self):
        stay = self.create_stay()
        d.stay_action(stay.pk, "check-in", {}, self.user)
        superadmin = m.User.objects.create_user(
            username="superadmin@example.com",
            email="superadmin@example.com",
            password="Safe-superadmin-password-2026",
            role="superadmin",
        )
        result = d.stay_action(stay.pk, "check-out", {}, superadmin)
        self.assertEqual(result.status, "checked_out")

    def test_idempotency_retries_and_conflicting_payload(self):
        stay = self.create_stay()
        payment = self.pay(stay)
        repeated = self.pay(stay)
        self.assertEqual(repeated.pk, payment.pk)
        self.assertEqual(m.CashMovement.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.pay(stay, "31.00")

    def test_payment_scope_and_overpayment(self):
        stay = self.create_stay()
        d.add_charge(
            stay, {"description": "Bar", "quantity": Decimal("2"), "unit_price": Decimal("5")}, self.user
        )
        with self.assertRaises(ValidationError):
            self.pay(stay, "11", scope="extra")
        self.pay(stay, "10", scope="extra")
        balances = d.statement(stay.charges.all())
        self.assertEqual(balances["room_balance"], Decimal("100"))
        self.assertEqual(balances["extras_balance"], Decimal("0"))

    def test_refunds_restore_balance_then_allow_reprice_and_cancellation(self):
        stay = self.create_stay()
        payment = self.pay(stay)
        d.refund_payment(payment, {"amount": Decimal("30"), "reason": "Errore"}, self.user, "refund-1")
        self.assertEqual(d.statement(stay.charges.all())["paid"], Decimal("0"))
        d.save_stay({"nightly_rate": Decimal("60")}, self.user, stay)
        self.assertEqual(d.statement(stay.charges.all())["total"], Decimal("120"))
        result = d.stay_action(stay.pk, "cancel", {}, self.user)
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(d.statement(result.charges.all())["balance"], Decimal("0"))

    def test_partial_refund_limits_and_idempotency(self):
        stay = self.create_stay()
        payment = self.pay(stay)
        data = {"amount": Decimal("10"), "reason": "Rettifica"}
        first = d.refund_payment(payment, data, self.user, "refund-1")
        self.assertEqual(first.pk, d.refund_payment(payment, data, self.user, "refund-1").pk)
        with self.assertRaises(ValidationError):
            d.refund_payment(payment, {"amount": Decimal("21"), "reason": "Errore"}, self.user, "refund-2")
        self.assertEqual(d.statement(stay.charges.all())["paid"], Decimal("20"))

    def test_note_change_after_deposit_preserves_charge_and_group_change_rejected(self):
        stay = self.create_stay()
        self.pay(stay)
        before = list(stay.charges.values_list("id", flat=True))
        updated = d.save_stay({"notes": "Nuova nota"}, self.user, stay)
        self.assertEqual(updated.notes, "Nuova nota")
        self.assertEqual(before, list(stay.charges.values_list("id", flat=True)))
        group = m.Group.objects.create(name="New", reference_name="Ref")
        with self.assertRaises(ValidationError):
            d.save_stay({"group": group}, self.user, stay)

    def test_move_on_departure_morning_and_extension(self):
        stay = self.create_stay()
        room2 = m.Room.objects.create(number="102", room_type="double", capacity=2)
        d.stay_action(
            stay.pk, "move", {"room": room2, "effective_at": self.departure - timedelta(hours=2)}, self.user
        )
        self.assertEqual(stay.segments.count(), 2)
        result = d.stay_action(
            stay.pk, "extend", {"departure": self.departure + timedelta(days=1)}, self.user
        )
        self.assertEqual(result.departure, self.departure + timedelta(days=1))
        self.assertEqual(d.statement(stay.charges.all())["total"], Decimal("150"))

    def test_stale_stay_cannot_add_charge_after_cancellation(self):
        stay = self.create_stay()
        d.stay_action(stay.pk, "cancel", {}, self.user)
        with self.assertRaises(ValidationError):
            d.add_charge(
                stay, {"description": "Bar", "quantity": Decimal("1"), "unit_price": Decimal("5")}, self.user
            )

    def test_shift_cash_count_refund_expenses_and_duplicate_close(self):
        stay = self.create_stay()
        with self.assertRaises(ValidationError):
            self.pay(stay, method="cash")
        shift = d.open_shift({"opening_cash": Decimal("100")}, self.user)
        with self.assertRaises(ValidationError):
            d.open_shift({"opening_cash": Decimal("100")}, self.user)
        payment = self.pay(stay, method="cash")
        d.refund_payment(payment, {"amount": Decimal("5"), "reason": "Rettifica"}, self.user, "refund")
        reason = m.CashReason.objects.create(name="Pulizie", direction="out")
        d.manual_expense({"amount": Decimal("10"), "method": "cash", "reason": reason}, self.user)
        closed = d.close_shift(shift, {"counted_cash": Decimal("114")}, self.user)
        self.assertEqual(closed.expected_at_close, Decimal("115"))
        self.assertEqual(d.close_shift(shift, {"counted_cash": Decimal("114")}, self.user).pk, closed.pk)
        with self.assertRaises(ValidationError):
            d.close_shift(shift, {"counted_cash": Decimal("110")}, self.user)

    def test_stock_no_negative_or_zero(self):
        item = m.StockItem.objects.create(code="A", name="Sapone")
        d.stock_movement(
            {"item": item, "direction": "in", "quantity": Decimal("2.5"), "reason": "Acquisto"}, self.user
        )
        with self.assertRaises(ValidationError):
            d.stock_movement(
                {"item": item, "direction": "out", "quantity": Decimal("3"), "reason": "Uso"}, self.user
            )
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal("2.5"))

    def test_inventory_api_returns_the_updated_stock_quantity(self):
        item = m.StockItem.objects.create(code="API-STOCK", name="Articolo API")
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            "/api/v1/inventory/movements/",
            {"item": item.pk, "direction": "in", "quantity": "3.250", "reason": "Carico test"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["quantity_after"], "3.250")
        listed = client.get("/api/v1/inventory/items/")
        self.assertEqual(listed.status_code, 200, listed.data)
        self.assertEqual(listed.data["results"][0]["quantity"], "3.250")

    def test_postgres_constraint_rejects_direct_overlap(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL exclusion constraint")
        stay = self.create_stay()
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.StaySegment.objects.create(
                stay=stay, room=self.room, arrival=self.arrival, departure=self.departure
            )

    def test_api_free_extra_accepts_explicit_null_catalogue(self):
        stay = self.create_stay()
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            f"/api/v1/stays/{stay.pk}/charges/",
            {"price_item": None, "description": "Parcheggio", "quantity": "2", "unit_price": "5.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], "10.00")

    def test_api_missing_stay_action_returns_not_found(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post("/api/v1/stays/99999/check-in/", {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_stale_stay_metadata_patch_preserves_moved_room(self):
        stay = self.create_stay()
        other_room = m.Room.objects.create(number="102", room_type="double", capacity=2)
        d.stay_action(stay.pk, "move", {"room": other_room, "effective_at": stay.arrival}, self.user)
        updated = d.save_stay({"notes": "Nota dopo trasferimento"}, self.user, stay)
        self.assertEqual(updated.room_id, other_room.pk)
        self.assertEqual(updated.segments.get().room_id, other_room.pk)


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = m.User.objects.create_user(
            username="op@test.it", email="op@test.it", password="Safe-test-password-2026", role="admin"
        )
        self.client = APIClient(enforce_csrf_checks=True)

    def test_login_requires_csrf_and_session_commands_remain_protected(self):
        self.assertEqual(self.client.get("/api/v1/rooms/").status_code, 401)
        payload = {"email": self.user.email, "password": "Safe-test-password-2026"}
        self.assertEqual(self.client.post("/api/v1/auth/login/", payload).status_code, 403)
        self.client.get("/api/v1/auth/csrf/")
        token = self.client.cookies["csrftoken"].value
        self.assertEqual(
            self.client.post("/api/v1/auth/login/", payload, HTTP_X_CSRFTOKEN=token).status_code, 200
        )
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/v1/rooms/", {"number": "1", "room_type": "double", "capacity": 2}
            ).status_code,
            403,
        )
        token = self.client.cookies["csrftoken"].value
        result = self.client.post(
            "/api/v1/rooms/", {"number": "1", "room_type": "double", "capacity": 2}, HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(result.status_code, 201, result.data)

    def test_operator_cannot_configure_property_or_manage_users(self):
        self.user.role = "operator"
        self.user.save()
        self.client.force_authenticate(self.user)
        response = self.client.patch("/api/v1/settings/", {"name": "Hotel Test"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/planning/?start=2026-10-20&end=2026-10-22").status_code, 200)
